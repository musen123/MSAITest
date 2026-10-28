<template>
  <div class="app-stat-mini" :class="{ 'is-clickable': clickable }">
    <!-- 图表形态背景插图 -->
    <svg
      v-if="chart === 'bars'"
      class="mini-bg"
      :style="bgStyle"
      viewBox="0 0 64 40"
      preserveAspectRatio="xMaxYMax meet"
    >
      <rect x="2" y="26" width="8" height="14" rx="2" />
      <rect x="14" y="18" width="8" height="22" rx="2" />
      <rect x="26" y="24" width="8" height="16" rx="2" />
      <rect x="38" y="10" width="8" height="30" rx="2" />
      <rect x="50" y="2" width="8" height="38" rx="2" />
    </svg>
    <svg
      v-else-if="chart === 'area'"
      class="mini-bg"
      :style="bgStyle"
      viewBox="0 0 64 40"
      preserveAspectRatio="xMaxYMax meet"
    >
      <path d="M0 34 L12 27 L24 30 L36 16 L48 21 L64 4 L64 40 L0 40 Z" />
      <circle cx="36" cy="16" r="2.5" />
      <circle cx="64" cy="4" r="2.5" />
    </svg>
    <svg
      v-else-if="chart === 'gauge'"
      class="mini-bg is-stroke"
      :style="bgStyle"
      viewBox="0 0 64 40"
      preserveAspectRatio="xMaxYMax meet"
    >
      <path
        d="M12 36 A 21 21 0 1 1 54 36" fill="none" stroke="currentColor"
        stroke-width="7" stroke-linecap="round" opacity="0.35"
      />
      <path
        d="M12 36 A 21 21 0 1 1 54 36" fill="none" stroke="currentColor"
        stroke-width="7" stroke-linecap="round" stroke-dasharray="46 80"
      />
      <circle cx="45" cy="18" r="3" fill="currentColor" />
    </svg>
    <svg
      v-else-if="chart === 'pulse'"
      class="mini-bg"
      :style="bgStyle"
      viewBox="0 0 64 40"
      preserveAspectRatio="xMaxYMax meet"
    >
      <path
        d="M0 24 L14 24 L20 10 L28 34 L36 18 L42 24 L64 24"
        fill="none" stroke="currentColor" stroke-width="3"
        stroke-linecap="round" stroke-linejoin="round"
      />
    </svg>

    <div class="mini-icon" :style="iconStyle">
      <i :class="icon" />
    </div>
    <div class="mini-body">
      <div class="mini-label">{{ label }}</div>
      <div class="mini-value">
        <span class="mini-num">{{ value }}</span>
        <span v-if="suffix" class="mini-suffix">{{ suffix }}</span>
        <span v-if="note" class="mini-note" :class="`is-${noteType}`">{{ note }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AppStatCardMini - 迷你统计卡(高密度报表用)
 *
 * 紧凑形态:左侧软底图标块 + label/value 一行装下;
 * note 是数值后的行内小字(趋势/备注),noteType 控制颜色语义;
 * chart 在卡片右下渲染低透明度的图表形态背景插图。
 *
 * 用法:
 *   <AppStatCardMini label="用例总数" :value="180" icon="i-solar-document-text-bold"
 *     color="brand" chart="bars" note="↑15.6%" note-type="success" />
 */
import { computed } from 'vue'

export type MiniStatColor =
  | 'brand' | 'info' | 'success' | 'warning'
  | 'danger' | 'purple' | 'cyan' | 'pink' | 'orange'

export type MiniChartType = 'bars' | 'area' | 'gauge' | 'pulse' | 'none'

const props = withDefaults(
  defineProps<{
    label: string
    value: number | string
    suffix?: string
    /** 数值后的行内小字(趋势/备注) */
    note?: string
    noteType?: 'success' | 'danger' | 'warning' | 'muted'
    color?: MiniStatColor
    /** UnoCSS 图标 class */
    icon: string
    /** 背景图表插图形态 */
    chart?: MiniChartType
    clickable?: boolean
  }>(),
  {
    color: 'brand',
    noteType: 'muted',
    chart: 'bars',
    clickable: false,
  },
)

const colorMap: Record<MiniStatColor, { bg: string; fg: string }> = {
  brand:   { bg: 'var(--brand-glow-soft)',       fg: 'var(--brand-500)' },
  info:    { bg: 'rgba(59, 130, 246, 0.10)',     fg: 'var(--color-info-500)' },
  success: { bg: 'rgba(16, 185, 129, 0.10)',     fg: 'var(--color-success-500)' },
  warning: { bg: 'rgba(245, 158, 11, 0.10)',     fg: 'var(--color-warning-500)' },
  danger:  { bg: 'rgba(239, 68, 68, 0.10)',      fg: 'var(--color-danger-500)' },
  purple:  { bg: 'rgba(139, 92, 246, 0.10)',     fg: 'var(--color-purple-500)' },
  cyan:    { bg: 'rgba(6, 182, 212, 0.10)',      fg: 'var(--color-cyan-500)' },
  pink:    { bg: 'rgba(236, 72, 153, 0.10)',     fg: 'var(--color-pink-500)' },
  orange:  { bg: 'rgba(249, 115, 22, 0.10)',     fg: 'var(--color-orange-500)' },
}

const iconStyle = computed(() => {
  const c = colorMap[props.color] ?? colorMap.brand
  return { background: c.bg, color: c.fg }
})

const bgStyle = computed(() => {
  const c = colorMap[props.color] ?? colorMap.brand
  return { color: c.fg }
})
</script>

<style scoped lang="scss">
.app-stat-mini {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  min-height: 60px;
  min-width: 0;
  transition: var(--transition-fast);

  &.is-clickable {
    cursor: pointer;

    &:hover {
      transform: translateY(-1px);
      box-shadow: var(--shadow-hover);
    }
  }
}

.mini-bg {
  position: absolute;
  right: -4px;
  bottom: -3px;
  width: 64px;
  height: 40px;
  fill: currentColor;
  opacity: 0.12;
  pointer-events: none;

  &.is-stroke {
    fill: none;
  }
}

.mini-icon {
  position: relative;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  i {
    font-size: 16px;
  }
}

.mini-body {
  position: relative;
  min-width: 0;
  flex: 1;
}

.mini-label {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
}

.mini-num {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.mini-suffix {
  font-size: 11px;
  color: var(--text-secondary);
}

.mini-note {
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;

  &.is-success { color: var(--color-success-600); }
  &.is-danger  { color: var(--color-danger-600); }
  &.is-warning { color: var(--color-warning-600); }
  &.is-muted   { color: var(--text-placeholder); }
}
</style>
