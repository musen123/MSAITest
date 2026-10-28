<template>
  <div class="app-stat-card" :class="{ 'is-clickable': clickable }">
    <!-- 右下角图表形态背景插画（低透明度，随色板着色；chart='none' 关闭） -->
    <svg
      v-if="resolvedChart === 'bars'"
      class="stat-chart"
      :style="chartStyle"
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
      v-else-if="resolvedChart === 'area'"
      class="stat-chart"
      :style="chartStyle"
      viewBox="0 0 64 40"
      preserveAspectRatio="xMaxYMax meet"
    >
      <path d="M0 34 L12 27 L24 30 L36 16 L48 21 L64 4 L64 40 L0 40 Z" />
      <circle cx="36" cy="16" r="2.5" />
      <circle cx="64" cy="4" r="2.5" />
    </svg>
    <svg
      v-else-if="resolvedChart === 'gauge'"
      class="stat-chart is-stroke"
      :style="chartStyle"
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
      v-else-if="resolvedChart === 'pulse'"
      class="stat-chart"
      :style="chartStyle"
      viewBox="0 0 64 40"
      preserveAspectRatio="xMaxYMax meet"
    >
      <path
        d="M0 24 L14 24 L20 10 L28 34 L36 18 L42 24 L64 24"
        fill="none" stroke="currentColor" stroke-width="3"
        stroke-linecap="round" stroke-linejoin="round"
      />
    </svg>

    <!-- 左侧软色图标 -->
    <div class="stat-icon" :style="iconStyle">
      <slot name="icon">
        <i v-if="iconName" :class="iconName" class="icon-svg" />
        <component v-else-if="icon" :is="icon" class="icon-svg" />
      </slot>
    </div>

    <!-- 右侧数据 -->
    <div class="stat-body">
      <div class="stat-label">{{ label }}</div>
      <div class="stat-value">
        <AppCountUp
          :end="numericValue"
          :decimals="decimals"
          :suffix="valueSuffix"
        />
        <!-- 趋势/备注都行内跟随数值，不再独占一行撑高卡片（对齐迷你卡观感） -->
        <span v-if="trend !== undefined" class="stat-delta" :class="trendClass">
          {{ trendLabel }} {{ trend > 0 ? '↑' : trend < 0 ? '↓' : '' }}{{ Math.abs(trend) }}%
        </span>
        <span v-else-if="extra" class="stat-extra">{{ extra }}</span>
      </div>
    </div>

    <!-- 装饰背景（可选） -->
    <div v-if="decoration" class="stat-decoration" />
  </div>
</template>

<script setup lang="ts">
/**
 * AppStatCard - 软质彩色统计卡（参考原型图工作台）
 *
 * 用法：
 *   <AppStatCard
 *     label="用例总数"
 *     :value="2560"
 *     :trend="12.5"
 *     color="brand"
 *     icon-name="i-solar-document-text-bold"
 *   />
 */
import { computed } from 'vue'
import AppCountUp from './AppCountUp.vue'

type StatColor =
  | 'brand'    // 绿
  | 'info'     // 蓝
  | 'success'  // 翠
  | 'warning'  // 橙
  | 'danger'   // 红
  | 'purple'   // 紫
  | 'cyan'     // 青
  | 'pink'     // 粉

/** 右下角背景插画形态；'auto' 按色板自动分配，'none' 关闭 */
type StatChart = 'bars' | 'area' | 'gauge' | 'pulse' | 'none' | 'auto'

const props = withDefaults(
  defineProps<{
    label: string
    value: number | string
    decimals?: number
    valueSuffix?: string
    trend?: number
    /** 趋势对比文案，默认「较上周」；窗口可变时传「较上期」等 */
    trendLabel?: string
    extra?: string
    color?: StatColor
    /** Iconify 图标名（如 'i-solar-document-text-bold'）会作为 class */
    iconName?: string
    /** 直接传入 icon 组件（如 unplugin-icons 引入） */
    icon?: any
    /** 右下角背景插画形态（默认 auto：按色板自动分配；none 关闭） */
    chart?: StatChart
    clickable?: boolean
    decoration?: boolean
  }>(),
  {
    decimals: 0,
    color: 'brand',
    valueSuffix: '',
    trendLabel: '较上周',
    chart: 'auto',
    clickable: false,
    decoration: false,
  },
)

const numericValue = computed(() => {
  if (typeof props.value === 'number') return props.value
  const n = parseFloat(props.value)
  return isNaN(n) ? 0 : n
})

// 颜色 → CSS 变量
const colorMap: Record<StatColor, { bg: string; fg: string }> = {
  brand:   { bg: 'var(--brand-glow-soft)',         fg: 'var(--brand-500)' },
  info:    { bg: 'rgba(59, 130, 246, 0.10)',       fg: 'var(--color-info-500)' },
  success: { bg: 'rgba(16, 185, 129, 0.10)',       fg: 'var(--color-success-500)' },
  warning: { bg: 'rgba(245, 158, 11, 0.10)',       fg: 'var(--color-warning-500)' },
  danger:  { bg: 'rgba(239, 68, 68, 0.10)',        fg: 'var(--color-danger-500)' },
  purple:  { bg: 'rgba(139, 92, 246, 0.10)',       fg: 'var(--color-purple-500)' },
  cyan:    { bg: 'rgba(6, 182, 212, 0.10)',        fg: 'var(--color-cyan-500)' },
  pink:    { bg: 'rgba(236, 72, 153, 0.10)',       fg: 'var(--color-pink-500)' },
}

const iconStyle = computed(() => {
  // 未知 color 值兜底到 brand，避免整页渲染崩溃
  const palette = colorMap[props.color] ?? colorMap.brand
  return {
    background: palette.bg,
    color: palette.fg,
  }
})

// 'auto' 时按色板分配插画形态，让相邻不同色的卡片天然错开图形
const chartByColor: Record<StatColor, Exclude<StatChart, 'none' | 'auto'>> = {
  brand: 'bars',
  info: 'area',
  success: 'gauge',
  warning: 'pulse',
  danger: 'pulse',
  purple: 'area',
  cyan: 'area',
  pink: 'bars',
}

const resolvedChart = computed(() => {
  if (props.chart && props.chart !== 'auto') return props.chart // 含 'none'
  return chartByColor[props.color] ?? 'bars'
})

const chartStyle = computed(() => {
  const palette = colorMap[props.color] ?? colorMap.brand
  return { color: palette.fg }
})

const trendClass = computed(() => {
  if (props.trend === undefined) return ''
  if (props.trend > 0) return 'is-up'
  if (props.trend < 0) return 'is-down'
  return ''
})
</script>

<style scoped lang="scss">
.app-stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-5);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: var(--transition-base);
  overflow: hidden;
  min-height: 56px;

  &.is-clickable {
    cursor: pointer;
    &:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-hover);
    }
  }
}

/* 右下角图表插画：低透明度、随色板着色，衬在内容之下 */
.stat-chart {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 62px;
  height: 38px;
  fill: currentColor;
  opacity: 0.12;
  pointer-events: none;

  &.is-stroke {
    fill: none;
  }
}

.stat-icon {
  position: relative;
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;

  :deep(.icon-svg),
  :deep(svg) {
    width: 18px;
    height: 18px;
  }
}

.stat-body {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

.stat-value {
  display: flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: var(--line-height-tight);
  letter-spacing: -0.5px;
  white-space: nowrap;
}

/* extra 行内小字：跟随数值、不加粗、可省略号截断 */
.stat-extra {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-regular);
  letter-spacing: 0;
  color: var(--text-secondary);
}

/* 趋势 delta：行内跟随数值、带涨跌色、可省略号截断 */
.stat-delta {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0;
  color: var(--text-secondary);

  &.is-up   { color: var(--color-success-600); }
  &.is-down { color: var(--color-danger-600);  }
}

.stat-decoration {
  position: absolute;
  right: -20px;
  bottom: -20px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--brand-glow-soft), transparent 60%);
  pointer-events: none;
}
</style>
