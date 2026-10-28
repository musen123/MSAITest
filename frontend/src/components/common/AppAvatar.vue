<template>
  <div
    class="app-avatar"
    :style="{ width: sizePx, height: sizePx, fontSize: fontPx }"
  >
    <img v-if="src" :src="src" :alt="name" />
    <img v-else-if="autoUrl" :src="autoUrl" :alt="name" />
    <div v-else class="avatar-fallback" :style="fallbackStyle">
      {{ initials }}
    </div>
    <div v-if="dot" class="avatar-dot" :class="`is-${dotColor}`" />
  </div>
</template>

<script setup lang="ts">
/**
 * AppAvatar - 头像组件
 *
 * 支持：
 *   1. 上传头像 src
 *   2. DiceBear 自动生成（基于 name 哈希，视觉风格一致）
 *   3. 文字 fallback（中文首字 / 英文首字母）
 *
 * 用法：
 *   <AppAvatar name="张三" :size="32" />
 *   <AppAvatar src="..." name="Admin" :dot="true" dot-color="success" />
 *   <AppAvatar name="Tester" :size="40" auto-style="notionists" />
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    src?: string
    size?: number
    /** 是否使用 DiceBear 自动生成 */
    autoGen?: boolean
    autoStyle?: 'notionists' | 'lorelei' | 'avataaars' | 'bottts' | 'pixel-art' | 'micah'
    dot?: boolean
    dotColor?: 'success' | 'warning' | 'danger' | 'info'
  }>(),
  {
    size: 32,
    autoGen: false,
    autoStyle: 'notionists',
    dotColor: 'success',
  },
)

const sizePx = computed(() => `${props.size}px`)
const fontPx = computed(() => `${Math.round(props.size * 0.42)}px`)

const initials = computed(() => {
  const n = (props.name || '').trim()
  if (!n) return '?'
  // 中文取首字
  if (/[一-龥]/.test(n)) return n.slice(0, 1)
  // 英文取首字母（最多2）
  const words = n.split(/\s+/)
  return words
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('')
})

// 字符串简单哈希 → 颜色
const palette = [
  { bg: 'var(--brand-100)',          fg: 'var(--brand-700)' },
  { bg: 'var(--color-info-50)',      fg: 'var(--color-info-600)' },
  { bg: 'var(--color-purple-50)',    fg: 'var(--color-purple-600)' },
  { bg: 'var(--color-warning-50)',   fg: 'var(--color-warning-600)' },
  { bg: 'var(--color-pink-50)',      fg: 'var(--color-pink-600)' },
  { bg: 'var(--color-cyan-50)',      fg: 'var(--color-cyan-600)' },
]

function hashStr(s: string | null | undefined): number {
  if (!s) return 0
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h)
}

const fallbackStyle = computed(() => {
  const c = palette[hashStr(props.name) % palette.length] ?? palette[0]
  return { background: c.bg, color: c.fg }
})

const autoUrl = computed(() => {
  if (!props.autoGen) return ''
  const seed = encodeURIComponent(props.name)
  return `https://api.dicebear.com/7.x/${props.autoStyle}/svg?seed=${seed}`
})
</script>

<style scoped lang="scss">
.app-avatar {
  position: relative;
  border-radius: 50%;
  overflow: visible;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 50%;
    display: block;
  }
}

.avatar-fallback {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-semibold);
  user-select: none;
}

.avatar-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 25%;
  height: 25%;
  border-radius: 50%;
  border: 2px solid var(--bg-card);
  min-width: 8px;
  min-height: 8px;

  &.is-success { background: var(--color-success-500); }
  &.is-warning { background: var(--color-warning-500); }
  &.is-danger  { background: var(--color-danger-500); }
  &.is-info    { background: var(--color-info-500); }
}
</style>
