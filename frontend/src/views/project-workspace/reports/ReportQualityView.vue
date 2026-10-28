<template>
  <div class="report-page">
    <AppPageHeader
      title="缺陷质量"
      description="收敛趋势 · 解决时长 · 负载与积压"
      icon="i-app-bug"
      :illustration="illustBug"
    >
      <template #actions>
        <el-radio-group v-model="days" size="small">
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
      </template>
    </AppPageHeader>

    <!-- 通栏健康横幅 + 警示卡排 -->
    <div class="quality-banner" v-loading="loading">
      <div class="banner-main">
        <div class="banner-label">未关闭缺陷</div>
        <div class="banner-num" :class="c.open.value > 0 ? 'is-warn' : 'is-ok'">
          {{ c.open.value }}
        </div>
        <div class="banner-badges">
          <span v-if="c.open.urgent > 0" class="badge is-danger">严重/主要 {{ c.open.urgent }}</span>
          <span class="badge" :class="c.closed.converging ? 'is-success' : 'is-danger'">
            <i :class="c.closed.converging ? 'i-solar-arrow-down-bold' : 'i-solar-arrow-up-bold'" />
            {{ c.closed.converging ? '收敛中' : '发散中' }}
          </span>
        </div>
      </div>
      <div class="banner-divider" />
      <div class="banner-metrics">
        <div class="bm-item">
          <div class="bm-label">本期新增</div>
          <div class="bm-num">{{ c.created.value }}</div>
          <div class="bm-note" :class="`is-${invTrendType(c.created.trend)}`">{{ trendNote(c.created.trend) || '—' }}</div>
        </div>
        <div class="bm-item">
          <div class="bm-label">本期关闭</div>
          <div class="bm-num">{{ c.closed.value }}</div>
          <div class="bm-note is-muted">{{ c.closed.converging ? '关闭 ≥ 新增' : '新增 > 关闭' }}</div>
        </div>
        <div class="bm-item">
          <div class="bm-label">平均解决时长</div>
          <div class="bm-num">{{ c.avg_resolve_days ?? '-' }}<small>天</small></div>
          <div class="bm-note is-muted">resolved 口径</div>
        </div>
        <div class="bm-item">
          <div class="bm-label">解决率</div>
          <div class="bm-num">{{ c.resolve_rate ?? 0 }}<small>%</small></div>
          <div class="bm-note is-muted">已解决+已关闭</div>
        </div>
      </div>
    </div>

    <div class="quality-alerts">
      <div class="alert-card" :class="c.reopened > 0 ? 'is-active' : ''">
        <i class="i-solar-restart-bold alert-icon is-orange" />
        <div class="alert-body">
          <div class="alert-num">{{ c.reopened }}</div>
          <div class="alert-label">重新打开{{ c.reopened > 0 ? ' · 质量回潮' : '' }}</div>
        </div>
      </div>
      <div class="alert-card">
        <i class="i-app-ai-agent alert-icon is-purple" />
        <div class="alert-body">
          <div class="alert-num">{{ c.ai_coverage ?? 0 }}<small>%</small></div>
          <div class="alert-label">AI 分析覆盖</div>
        </div>
      </div>
      <div class="alert-card" :class="c.stale > 0 ? 'is-active' : ''">
        <i class="i-solar-hourglass-bold alert-icon is-danger" />
        <div class="alert-body">
          <div class="alert-num">{{ c.stale }}</div>
          <div class="alert-label">超 7 天未处理{{ c.stale > 0 ? ' · 需关注' : '' }}</div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <AppSectionCard title="新增 vs 关闭趋势" class="panel">
        <v-chart :option="trendOption" class="chart-md" autoresize />
      </AppSectionCard>
      <AppSectionCard title="严重程度分布" class="panel">
        <template #extra><span class="muted-tag">未关闭</span></template>
        <div v-if="sevTotal > 0" class="pie-row">
          <v-chart :option="sevOption" class="chart-pie" autoresize />
          <ul class="pie-legend">
            <li v-for="s in sevRows" :key="s.key">
              <span class="dot" :style="{ background: s.color }" />
              <span class="lg-label">{{ s.label }}</span>
              <span class="lg-num">{{ s.value }}</span>
            </li>
          </ul>
        </div>
        <div v-else class="panel-empty">暂无未关闭缺陷</div>
      </AppSectionCard>
    </div>

    <div class="grid-3">
      <AppSectionCard title="处理人负载" class="panel">
        <template #extra><span class="muted-tag">未关闭</span></template>
        <div v-if="assignees.length" class="bar-list">
          <div v-for="a in assignees" :key="a.name" class="bar-row">
            <span class="bar-label">{{ a.name }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: a.pct + '%', background: 'var(--color-orange-500)' }" />
            </div>
            <span class="bar-num">{{ a.count }}</span>
          </div>
        </div>
        <div v-else class="panel-empty">暂无数据</div>
      </AppSectionCard>
      <AppSectionCard title="缺陷来源" class="panel">
        <div v-if="srcTotal > 0" class="pie-row">
          <v-chart :option="sourceOption" class="chart-pie" autoresize />
          <ul class="pie-legend">
            <li v-for="s in srcRows" :key="s.key">
              <span class="dot" :style="{ background: s.color }" />
              <span class="lg-label">{{ s.label }}</span>
              <span class="lg-num">{{ s.value }}</span>
            </li>
          </ul>
        </div>
        <div v-else class="panel-empty">暂无数据</div>
      </AppSectionCard>
      <AppSectionCard title="积压预警" class="panel">
        <template #extra><span class="muted-tag">超 7 天未动</span></template>
        <div v-if="staleList.length" class="stale-list">
          <div
            v-for="s in staleList" :key="s.id" class="stale-item"
            @click="goBug(s.id)"
          >
            <span class="stale-title">{{ s.title }}</span>
            <span class="stale-days" :class="s.days >= 10 ? 'is-bad' : 'is-warn'">{{ s.days }}天</span>
          </div>
        </div>
        <div v-else class="panel-empty">无积压缺陷</div>
      </AppSectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace';
import { AppPageHeader, AppSectionCard } from '@/components/common';
import { reportCenterApi } from '@/api/report-center';
import type { QualityReportData } from '@/api/report-center';
import illustBug from '@/assets/illustrations/bug-fix.svg';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent]);
const router = useRouter();
const workspaceStore = useProjectWorkspaceStore();
const projectId = computed(() => workspaceStore.currentProject?.id || 0);
const loading = ref(false);
const days = ref(30);
const data = ref<QualityReportData | null>(null);
const fetch = async () => {
    if (!projectId.value)
        return;
    loading.value = true;
    try {
        const res = await reportCenterApi.quality(projectId.value, days.value);
        data.value = res.data;
    }
    catch (err) {
        console.error(err);
    }
    finally {
        loading.value = false;
    }
};
onMounted(fetch);
watch([days, projectId], fetch);
const c = computed(() => data.value?.cards ?? {
    open: { value: 0, urgent: 0 },
    created: { value: 0, trend: null },
    closed: { value: 0, converging: true },
    avg_resolve_days: null,
    resolve_rate: null,
    reopened: 0,
    ai_coverage: null,
    stale: 0,
});
function trendNote(t: number | null): string {
    if (t == null)
        return '';
    const arrow = t > 0 ? '↑' : t < 0 ? '↓' : '';
    return `较上期 ${arrow}${Math.abs(t)}%`;
}
/** 缺陷新增是「越少越好」,趋势语义反转 */
function invTrendType(t: number | null): 'success' | 'danger' | 'muted' {
    if (t == null || t === 0)
        return 'muted';
    return t < 0 ? 'success' : 'danger';
}
const trendOption = computed(() => {
    const daily = data.value?.trend || [];
    const dates = daily.map((d) => d.date.slice(5));
    return {
        tooltip: { trigger: 'axis' },
        legend: { data: ['新增', '关闭', '存量未关闭'], top: 0, right: 0, icon: 'circle', textStyle: { fontSize: 11, color: '#6B7280' } },
        grid: { left: 0, right: 8, top: 28, bottom: 0, containLabel: true },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#9CA3AF', fontSize: 10 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#EEF1F4' } } },
        yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } }, axisLabel: { color: '#9CA3AF', fontSize: 10 } },
        series: [
            { name: '新增', type: 'bar', data: daily.map((d) => d.created), itemStyle: { color: '#EF4444', borderRadius: [2, 2, 0, 0] }, barMaxWidth: 10 },
            { name: '关闭', type: 'bar', data: daily.map((d) => d.closed), itemStyle: { color: '#00B96B', borderRadius: [2, 2, 0, 0] }, barMaxWidth: 10 },
            { name: '存量未关闭', type: 'line', smooth: true, symbol: 'none', data: daily.map((d) => d.open), lineStyle: { color: '#F59E0B', width: 2, type: 'dashed' } },
        ],
    };
});
const SEV_META = [
    { key: 'critical', label: '严重', color: '#EF4444' },
    { key: 'major', label: '主要', color: '#F97316' },
    { key: 'moderate', label: '一般', color: '#F59E0B' },
    { key: 'minor', label: '轻微', color: '#D1D5DB' },
    { key: 'trivial', label: '微小', color: '#E5E7EB' },
];
const sevRows = computed(() => {
    const dist = data.value?.severity_dist || {};
    return SEV_META.filter((m) => (dist[m.key] || 0) > 0).map((m) => ({
        ...m,
        value: dist[m.key] || 0,
    }));
});
const sevTotal = computed(() => sevRows.value.reduce((a, b) => a + b.value, 0));
const sevOption = computed(() => {
    const multi = sevRows.value.length > 1;
    return {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [
            {
                type: 'pie', radius: ['52%', '74%'],
                label: {
                    show: true, position: 'center',
                    formatter: `{v|${sevTotal.value}}`,
                    rich: { v: { fontSize: 18, fontWeight: 700, color: '#1F2937' } },
                },
                itemStyle: {
                    borderRadius: multi ? 4 : 0,
                    borderColor: '#fff',
                    borderWidth: multi ? 2 : 0,
                },
                data: sevRows.value.map((s) => ({ name: s.label, value: s.value, itemStyle: { color: s.color } })),
            },
        ],
    };
});
const assignees = computed(() => {
    const list = data.value?.assignee_load || [];
    const max = Math.max(...list.map((a) => a.count), 1);
    return list.map((a) => ({ ...a, pct: Math.round((a.count / max) * 100) }));
});
const SRC_META = [
    { key: 'functional', label: '功能测试', color: '#00B96B' },
    { key: 'app', label: 'App 测试', color: '#14B8A6' }
];
const srcRows = computed(() => {
    const dist = data.value?.source_dist || {};
    return SRC_META.filter((m) => (dist[m.key] || 0) > 0).map((m) => ({
        ...m,
        value: dist[m.key] || 0,
    }));
});
const srcTotal = computed(() => srcRows.value.reduce((a, b) => a + b.value, 0));
const sourceOption = computed(() => {
    const multi = srcRows.value.length > 1;
    return {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [
            {
                type: 'pie', radius: ['52%', '74%'], label: { show: false },
                itemStyle: {
                    borderRadius: multi ? 4 : 0,
                    borderColor: '#fff',
                    borderWidth: multi ? 2 : 0,
                },
                data: srcRows.value.map((s) => ({ name: s.label, value: s.value, itemStyle: { color: s.color } })),
            },
        ],
    };
});
const staleList = computed(() => data.value?.stale_list || []);
function goBug(bugId: number) {
    router.push({
        name: 'ProjectBugs',
        params: { id: projectId.value },
        query: { bug_id: bugId },
    });
}
</script>

<style scoped lang="scss">
@use './report-shared';

/* 本页特色:通栏健康横幅 */
.quality-banner {
  display: flex;
  align-items: stretch;
  gap: var(--space-5);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-4) var(--space-5);
}
.banner-main {
  flex-shrink: 0;
  min-width: 150px;
}
.banner-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.banner-num {
  margin-top: 2px;
  font-size: 42px;
  line-height: 1.1;
  font-weight: var(--font-weight-bold);
  font-variant-numeric: tabular-nums;

  &.is-warn { color: var(--color-danger-600); }
  &.is-ok   { color: var(--color-success-600); }
}
.banner-badges {
  margin-top: var(--space-2);
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 20px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-weight-medium);
  background: var(--gray-100);
  color: var(--text-secondary);

  i { font-size: 10px; }

  &.is-danger  { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.is-success { background: var(--color-success-50); color: var(--color-success-600); }
}
.banner-divider {
  width: 1px;
  background: var(--border-light);
  flex-shrink: 0;
}
.banner-metrics {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  align-items: center;
}
.bm-item {
  min-width: 0;
}
.bm-label {
  font-size: 11px;
  color: var(--text-secondary);
}
.bm-num {
  margin-top: 2px;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;

  small {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-secondary);
    margin-left: 1px;
  }
}
.bm-note {
  margin-top: 1px;
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  &.is-success { color: var(--color-success-600); }
  &.is-danger  { color: var(--color-danger-600); }
  &.is-muted   { color: var(--text-placeholder); }
}
@media (max-width: 900px) {
  .quality-banner { flex-direction: column; }
  .banner-divider { display: none; }
  .banner-metrics { grid-template-columns: repeat(2, 1fr); }
}

/* 警示卡排 */
.quality-alerts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}
@media (max-width: 900px) {
  .quality-alerts { grid-template-columns: 1fr; }
}
.alert-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);

  &.is-active {
    border-color: var(--color-danger-200, var(--color-danger-50));
    background: var(--color-danger-50);
  }
}
.alert-icon {
  font-size: 22px;
  flex-shrink: 0;

  &.is-orange { color: var(--color-orange-500); }
  &.is-purple { color: var(--color-purple-500); }
  &.is-danger { color: var(--color-danger-500); }
}
.alert-body { min-width: 0; }
.alert-num {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;

  small {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-secondary);
  }
}
.alert-label {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stale-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.stale-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: var(--transition-fast);

  &:hover { background: var(--bg-hover); }
}
.stale-title {
  flex: 1;
  min-width: 0;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stale-days {
  flex-shrink: 0;
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;

  &.is-bad  { color: var(--color-danger-600); }
  &.is-warn { color: var(--color-orange-500); }
}
</style>
