<script setup lang="ts">
/**
 * App 自动化任务实时输出渲染器（run_app_script / run_app_suite / explore_app_script）
 *
 * 「AI 实时输出」区替换为设备观战直播：mode=observe 只读投屏，不占设备锁，
 * 与正在驱动设备的 exec 会话零冲突（P4 观战通道，安卓/鸿蒙/iOS 平台透明）。
 * 模型逐轮日志由详情页左侧「运行日志」面板承担，此处不重复。
 *
 * 平台解码器三级解析：input_params.platform（提交时落）→ 设备列表按 udid 反查
 * （老任务/定时套件缺省场景）→ android 兜底。解析完成后才开流，避免 M-JPEG
 * 设备被按 H264 解码黑屏。任务进入终态即断流上遮罩，不再占用隧道。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { appDeviceApi } from '@/api/appDevice'
import { useDeviceScreencast, type DeviceCastPlatform } from '@/composables/useDeviceScreencast'
import type { AiTaskDetail, AiTaskStreamEvent } from '@/types/ai-task'

const props = defineProps<{
  events: AiTaskStreamEvent[]
  active: boolean
  task?: AiTaskDetail | null
}>()

const params = computed(() => (props.task?.input_params || {}) as Record<string, unknown>)
const udid = computed(() => String(params.value.device_udid || ''))

const platform = ref<DeviceCastPlatform>('android')
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)
const sc = useDeviceScreencast({
  udid: () => udid.value,
  canvasRef,
  stageRef,
  platform: () => platform.value,
})

/** 结束态：不再开流；运行中断流后也置位（遮罩文案区分） */
const ended = ref(false)
const started = ref(false)

const PLATFORM_LABEL: Record<DeviceCastPlatform, string> = {
  android: 'Android',
  harmony: '鸿蒙',
  ios: 'iOS',
}

/** 最新阶段名 / 进度（从事件流提取，直播头部展示） */
const stageText = computed(() => {
  for (let i = props.events.length - 1; i >= 0; i--) {
    const ev = props.events[i]
    if (ev?.type === 'stage') return String(ev.payload?.name || '')
  }
  return ''
})
const percent = computed(() => {
  for (let i = props.events.length - 1; i >= 0; i--) {
    const ev = props.events[i]
    if (ev?.type === 'progress' && typeof ev.payload?.percent === 'number') return ev.payload.percent
  }
  return 0
})

async function resolvePlatformAndStart() {
  if (!udid.value || started.value) return
  const fromParams = params.value.platform
  if (fromParams === 'android' || fromParams === 'harmony' || fromParams === 'ios') {
    platform.value = fromParams
  } else {
    // 老任务 / 定时套件缺省：设备列表反查（失败按 android 兜底）
    try {
      const devices = await appDeviceApi.listDevices()
      const hit = devices.find((d) => d.udid === udid.value)
      if (hit?.platform) platform.value = hit.platform
    } catch {
      /* 兜底 android */
    }
  }
  if (!props.active) return // 解析期间任务已结束
  started.value = true
  void sc.startObserve()
}

onMounted(() => {
  if (props.active) void resolvePlatformAndStart()
  else ended.value = true
})

watch(
  () => props.active,
  (act) => {
    if (!act) {
      ended.value = true
      sc.cleanup()
    }
  },
)
// 详情页任务数据晚于渲染器挂载到位时补启（task 异步加载）
watch(udid, () => {
  if (props.active) void resolvePlatformAndStart()
})

onBeforeUnmount(() => sc.cleanup())
</script>

<template>
  <div class="app-exec-live">
    <div class="ael-head">
      <template v-if="!ended">
        <span class="ael-live"><span class="ael-dot" />观战直播 · 只读</span>
        <span v-if="stageText" class="ael-stage" :title="stageText">{{ stageText }}</span>
        <span v-if="percent" class="ael-pct">{{ percent }}%</span>
      </template>
      <template v-else>
        <span class="ael-ended-tag"><i class="i-solar-flag-bold" />任务已结束</span>
      </template>
      <span class="ael-meta">
        <template v-if="udid">
          {{ PLATFORM_LABEL[platform] }}
          <template v-if="sc.meta.width"> · {{ sc.meta.width }}×{{ sc.meta.height }}</template>
        </template>
      </span>
    </div>

    <div ref="stageRef" class="ael-stage-box">
      <div
        class="ael-screen"
        :style="sc.meta.width ? { aspectRatio: sc.screenAspect.value } : undefined"
      >
        <canvas
          ref="canvasRef"
          class="ael-canvas"
          :class="{ 'is-live': sc.viewState.value === 'streaming' && !ended }"
        />
        <div v-if="ended || sc.viewState.value !== 'streaming'" class="ael-overlay">
          <template v-if="ended">
            <i class="i-solar-monitor-smartphone-bold ael-icon" />
            <span>任务已结束，直播仅任务运行期间提供</span>
            <span class="ael-hint">执行录像与截图请查看下方产出的执行报告</span>
          </template>
          <template v-else-if="!udid">
            <i class="i-solar-smartphone-2-bold ael-icon" />
            <span>任务未绑定具体设备（套件默认设备）</span>
            <span class="ael-hint">执行开始后可到 App 执行记录页实时查看</span>
          </template>
          <template v-else>
            <i class="i-solar-eye-bold ael-icon" />
            <span>{{ sc.stateLabel.value }}</span>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-exec-live {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ael-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 24px;
}
.ael-live {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--success-600);
  background: var(--success-50);
  border: 1px solid var(--success-200);
  border-radius: var(--radius-full);
  padding: 2px 10px;
  white-space: nowrap;
}
.ael-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success-500);
  animation: ael-pulse 1.2s ease-in-out infinite;
}
@keyframes ael-pulse {
  50% { opacity: 0.35; }
}
.ael-ended-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--gray-100);
  border-radius: var(--radius-full);
  padding: 2px 10px;
}
.ael-stage {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.ael-pct {
  font-size: var(--font-size-xs);
  color: var(--brand-600);
  font-weight: var(--font-weight-semibold);
  font-family: var(--font-mono);
}
.ael-meta {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  white-space: nowrap;
}
.ael-stage-box {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0b0f14;
  border-radius: 14px;
  overflow: hidden;
  height: clamp(380px, 48vh, 560px);
}
.ael-screen {
  position: relative;
  height: 100%;
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ael-canvas {
  max-width: 100%;
  max-height: 100%;
  height: 100%;
  width: auto;
  object-fit: contain;
  display: block;
  &:not(.is-live) { opacity: 0; }
}
.ael-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
  font-size: var(--font-size-sm);
  text-align: center;
  padding: 0 24px;
}
.ael-icon {
  font-size: 40px;
  color: var(--brand-400, #4ade80);
}
.ael-hint {
  font-size: var(--font-size-xs);
  color: #6b7280;
}
</style>
