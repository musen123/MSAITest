<template>
  <div class="exec-report">
    <div class="report-head">
      <div class="head-left">
        <i class="i-solar-chart-square-bold head-icon" />
        <span class="head-title">执行概览</span>
        <span class="head-sub">近 {{ days }} 天 · {{ dimLabel }}维度</span>
      </div>
      <div class="head-right">
        <el-radio-group v-model="days" size="small">
          <el-radio-button :value="7">7 天</el-radio-button>
          <el-radio-button :value="14">14 天</el-radio-button>
          <el-radio-button :value="30">30 天</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <div v-loading="loading" class="report-body">
      <!-- 统计卡 -->
      <div class="stat-grid">
        <AppStatCard
          label="执行总数"
          :value="summary.total"
          color="brand"
          :icon="iSolarPlayCircleBold"
          :extra="`近 ${days} 天`"
        />
        <AppStatCard
          label="通过率"
          :value="summary.pass_rate ?? 0"
          :decimals="1"
          value-suffix="%"
          color="success"
          :icon="iSolarCheckCircleBold"
          :trend="rateTrend"
          :extra="summary.pass_rate === null ? '暂无已完成记录' : undefined"
        />
        <AppStatCard
          label="失败/取消"
          :value="summary.failed"
          color="danger"
          :icon="iSolarCloseCircleBold"
          :clickable="summary.failed > 0"
          :extra="summary.failed > 0 ? '点击筛选失败记录' : undefined"
          @click="onFailedClick"
        />
        <AppStatCard
          label="平均耗时"
          :value="avgSeconds"
          :decimals="1"
          value-suffix="s"
          color="cyan"
          :icon="iSolarClockCircleBold"
        />
        <AppStatCard
          label="执行中"
          :value="summary.running"
          color="warning"
          :icon="iSolarRefreshCircleBold"
          extra="实时"
        />
      </div>

      <!-- 趋势图 -->
      <div class="panel trend-panel">
        <div class="panel-title">每日执行趋势</div>
        <VChart class="trend-chart" :option="trendOption" autoresize />
      </div>

      <!-- 失败排行 + 分布 -->
      <div class="bottom-grid" :class="{ single: !showDistChart }">
        <div class="panel">
          <div class="panel-title">
            不稳定{{ dimLabel }} Top 5
            <span class="panel-sub">按失败次数 · 近 {{ days }} 天</span>
          </div>
          <div v-if="topFailures.length" class="flaky-list">
            <div
              v-for="item in topFailures"
              :key="item.id"
              class="flaky-row"
              @click="emit('drill', item)"
            >
              <span class="flaky-name" :title="item.name">{{ item.name }}</span>
              <span class="flaky-bar">
                <span class="flaky-bar-inner" :style="{ width: barWidth(item.failures) }" />
              </span>
              <span class="flaky-count">{{ item.failures }}/{{ item.runs }} 次</span>
            </div>
          </div>
          <div v-else class="panel-empty">
            <i class="i-solar-check-circle-bold empty-icon" />
            近 {{ days }} 天没有失败记录
          </div>
        </div>

        <div v-if="showDistChart" class="panel">
          <div class="panel-title">{{ distTitle }}</div>
          <VChart class="dist-chart" :option="distOption" autoresize />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * App 执行记录报表（执行概览）——与 Web/接口自动化报表组件同构。
 *
 * 维度跟随执行记录页 tab（case/suite），时间窗 7/14/30 天可切。
 * 点失败卡/排行行向父组件发联动筛选（drill/filter-failed）。
 * 分布环按维度换语义：case=单跑/套件来源，suite=手动/定时触发。
 */
import { ref, computed, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { AppStatCard } from '@/components/common'
import iSolarPlayCircleBold from '~icons/solar/play-circle-bold'
import iSolarCheckCircleBold from '~icons/solar/check-circle-bold'
import iSolarCloseCircleBold from '~icons/solar/close-circle-bold'
import iSolarClockCircleBold from '~icons/solar/clock-circle-bold'
import iSolarRefreshCircleBold from '~icons/solar/refresh-circle-bold'
import { appTestApi, type AppExecStats } from '@/api/appTest'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  projectId: number
  dimension: 'case' | 'suite'
}>()

const emit = defineEmits<{
  (e: 'drill', item: { id: number; name: string }): void
  (e: 'filter-failed'): void
}>()

// 语义色（与 design-system 一致；ECharts canvas 无法读 CSS 变量）
const C_SUCCESS = '#10B981'
const C_DANGER = '#EF4444'
const C_PURPLE = '#8B5CF6'
const C_CYAN = '#06B6D4'

const days = ref<7 | 14 | 30>(7)
const loading = ref(false)
const stats = ref<AppExecStats | null>(null)

const dimLabel = computed(() => ({ case: '用例', suite: '套件' })[props.dimension])

const summary = computed(
  () =>
    stats.value?.summary || {
      total: 0,
      passed: 0,
      failed: 0,
      running: 0,
      pass_rate: null,
      prev_pass_rate: null,
      avg_duration_ms: null,
    },
)

const rateTrend = computed(() => {
  const cur = summary.value.pass_rate
  const prev = summary.value.prev_pass_rate
  if (cur === null || prev === null) return undefined
  return Math.round((cur - prev) * 10) / 10
})

const avgSeconds = computed(() => {
  const ms = summary.value.avg_duration_ms
  return ms === null ? 0 : Math.round(ms / 100) / 10
})

const topFailures = computed(() => stats.value?.top_failures || [])
const maxFailures = computed(() => Math.max(1, ...topFailures.value.map((i) => i.failures)))
const barWidth = (n: number) => `${Math.round((n / maxFailures.value) * 100)}%`

const DIST_LABELS: Record<string, string> = {
  standalone: '单跑',
  suite: '套件批量',
  manual: '手动触发',
  scheduled: '定时触发',
}
const distTitle = computed(() =>
  props.dimension === 'case' ? '执行来源分布' : '触发方式分布',
)
const showDistChart = computed(() => {
  const d = stats.value?.dist || {}
  return Object.values(d).some((v) => v > 0)
})

// ==================== 图表 option ====================
const trendOption = computed(() => {
  const daily = stats.value?.daily || []
  const dates = daily.map((d) => {
    const [, m, dd] = d.date.split('-')
    return `${Number(m)}/${Number(dd)}`
  })
  const rates = daily.map((d) => {
    const done = d.passed + d.failed
    return done === 0 ? null : Math.round((d.passed / done) * 1000) / 10
  })
  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: unknown) => (v === null ? '-' : String(v)),
    },
    legend: {
      data: ['通过', '失败/取消', '通过率'],
      top: 0,
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { fontSize: 12 },
    },
    grid: { left: 8, right: 8, top: 32, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisTick: { show: false },
      axisLabel: { fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { opacity: 0.4 } },
        axisLabel: { fontSize: 11 },
      },
      {
        type: 'value',
        min: 0,
        max: 100,
        splitLine: { show: false },
        axisLabel: { fontSize: 11, formatter: '{value}%' },
      },
    ],
    series: [
      {
        name: '通过',
        type: 'bar',
        stack: 'total',
        data: daily.map((d) => d.passed),
        itemStyle: { color: C_SUCCESS, borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 22,
      },
      {
        name: '失败/取消',
        type: 'bar',
        stack: 'total',
        data: daily.map((d) => d.failed),
        itemStyle: { color: C_DANGER, borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 22,
      },
      {
        name: '通过率',
        type: 'line',
        yAxisIndex: 1,
        data: rates,
        connectNulls: true,
        smooth: true,
        symbolSize: 5,
        lineStyle: { color: C_PURPLE, width: 2, type: 'dashed' },
        itemStyle: { color: C_PURPLE },
      },
    ],
  }
})

const distOption = computed(() => {
  const dist = stats.value?.dist || {}
  const data = Object.entries(dist)
    .map(([k, v]) => ({ name: DIST_LABELS[k] || k, value: v }))
    .filter((d) => d.value > 0)
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 12 } },
    color: [C_CYAN, C_PURPLE],
    series: [
      {
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data,
      },
    ],
  }
})

// ==================== 数据加载 ====================
const fetchStats = async () => {
  loading.value = true
  try {
    stats.value = await appTestApi.getReportStats(props.projectId, {
      dimension: props.dimension,
      days: days.value,
    })
  } finally {
    loading.value = false
  }
}

const onFailedClick = () => {
  if (summary.value.failed > 0) emit('filter-failed')
}

watch([() => props.dimension, days], fetchStats)
onMounted(fetchStats)

defineExpose({ refresh: fetchStats })
</script>

<style scoped lang="scss">
.exec-report {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  margin-bottom: 20px;
}

.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);

  .head-left {
    display: flex;
    align-items: center;
    gap: var(--space-2);

    .head-icon {
      font-size: 18px;
      color: var(--brand-500);
    }
    .head-title {
      font-size: var(--font-size-base, 14px);
      font-weight: var(--font-weight-semibold, 600);
      color: var(--text-primary);
    }
    .head-sub {
      font-size: 12px;
      color: var(--text-placeholder);
    }
  }
}

.report-body {
  padding: 0 var(--space-4) var(--space-4);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.panel {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);

  .panel-title {
    font-size: 13px;
    font-weight: var(--font-weight-semibold, 600);
    color: var(--text-primary);
    margin-bottom: var(--space-2);

    .panel-sub {
      font-weight: 400;
      font-size: 11px;
      color: var(--text-placeholder);
      margin-left: 6px;
    }
  }
}

.trend-panel {
  margin-bottom: var(--space-3);

  .trend-chart {
    height: 240px;
    width: 100%;
  }
}

.bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-3);

  &.single {
    grid-template-columns: 1fr;
  }

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.dist-chart {
  height: 180px;
  width: 100%;
}

.flaky-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.flaky-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: var(--brand-50);
  }

  .flaky-name {
    flex: 1;
    min-width: 0;
    font-size: 12.5px;
    color: var(--text-regular);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .flaky-bar {
    width: 96px;
    height: 6px;
    background: var(--gray-100);
    border-radius: 3px;
    overflow: hidden;
    flex-shrink: 0;

    .flaky-bar-inner {
      display: block;
      height: 100%;
      background: var(--color-danger-500, #ef4444);
      border-radius: 3px;
    }
  }

  .flaky-count {
    width: 72px;
    text-align: right;
    font-size: 12px;
    color: var(--color-danger-600, #dc2626);
    flex-shrink: 0;
  }
}

.panel-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: var(--space-6) 0;
  font-size: 12.5px;
  color: var(--text-placeholder);

  .empty-icon {
    font-size: 16px;
    color: var(--color-success-500, #10b981);
  }
}
</style>
