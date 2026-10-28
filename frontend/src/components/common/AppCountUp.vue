<template>
  <span ref="elRef" class="app-countup">{{ formattedInitial }}</span>
</template>

<script setup lang="ts">
/**
 * AppCountUp - 数字滚动入场动画
 *
 * 用法：
 *   <AppCountUp :end="2560" />
 *   <AppCountUp :end="98.32" :decimals="2" suffix="%" />
 *   <AppCountUp :end="12500" prefix="¥" :separator="','" />
 */
import { CountUp, type CountUpOptions } from 'countup.js'
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    end: number
    start?: number
    duration?: number
    decimals?: number
    separator?: string
    prefix?: string
    suffix?: string
    /** 是否在视口内才开始播放（IntersectionObserver） */
    lazy?: boolean
  }>(),
  {
    start: 0,
    duration: 2,
    decimals: 0,
    separator: ',',
    prefix: '',
    suffix: '',
    lazy: true,
  },
)

const elRef = ref<HTMLElement | null>(null)
let instance: CountUp | null = null
let observer: IntersectionObserver | null = null

/** 静态格式化（与 countup 默认口径一致：千分位分组 + 定点小数 + 前后缀）。
 *  用作动画不可用时的兜底渲染，保证卡片永不停在初始值。 */
function formatValue(val: number): string {
  const safe = Number.isFinite(val) ? val : props.start
  const [intPart, decPart] = safe.toFixed(props.decimals).split('.')
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, props.separator)
  return props.prefix + (decPart ? `${grouped}.${decPart}` : grouped) + props.suffix
}

const formattedInitial = formatValue(props.start)

function buildOptions(): CountUpOptions {
  return {
    startVal: props.start,
    duration: props.duration,
    decimalPlaces: props.decimals,
    separator: props.separator,
    prefix: props.prefix,
    suffix: props.suffix,
    useEasing: true,
  }
}

function play() {
  if (!elRef.value || instance) return
  instance = new CountUp(elRef.value, props.end, buildOptions())
  if (instance.error) {
    // countup 拒收该值（NaN/非法）——退化为静态渲染，避免显示 0 或乱码
    instance = null
    elRef.value.textContent = formatValue(props.end)
    return
  }
  instance.start()
}

onMounted(() => {
  if (!props.lazy) {
    play()
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          play()
          observer?.disconnect()
          observer = null
        }
      })
    },
    { threshold: 0.2 },
  )
  if (elRef.value) observer.observe(elRef.value)
})

watch(
  () => props.end,
  (newVal) => {
    if (instance) {
      instance.update(newVal)
    } else if (elRef.value) {
      // 尚未进入视口 / 观察器未触发时数据先到——直接静态写入正确值兜底。
      // 待观察器触发 play() 时，CountUp 构造会重置回 startVal 再滚动，动画照常。
      elRef.value.textContent = formatValue(newVal)
    }
  },
)

onUnmounted(() => {
  observer?.disconnect()
  observer = null
  instance = null
})
</script>

<style scoped>
.app-countup {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
}
</style>
