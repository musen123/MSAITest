<template>
  <div class="report-page">
    <AppPageHeader
      title="执行汇总"
      description="执行量 · 通过率 · 模块对比 · 失败聚焦"
      icon="i-app-test-report"
      :illustration="illustReport"
    >
      <template #actions>
        <el-radio-group v-model="days" size="small">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
      </template>
    </AppPageHeader>

    <!-- 顶部 5 迷你卡 -->
    <div class="exec-mini-row" v-loading="loading">
      <AppStatCardMini
        :label="`近 ${days} 天执行`" chart="bars" :value="c.executions.value"
        icon="i-solar-play-circle-bold" color="brand"
        :note="trendNote(c.executions.trend)" :note-type="trendType(c.executions.trend)" />
      <AppStatCardMini
        label="综合通过率" chart="gauge" :value="c.pass_rate.value ?? 0" suffix="%"
        icon="i-solar-check-circle-bold" color="success"
        :note="c.pass_rate.value == null ? '暂无完成执行' : rateTrendNote(c.pass_rate.trend)"
        :note-type="trendType(c.pass_rate.trend)" />
      <AppStatCardMini
        label="失败/错误" chart="pulse" :value="c.failed.value"
        icon="i-solar-danger-circle-bold" color="danger"
        :note="trendNote(c.failed.trend)" :note-type="invTrendType(c.failed.trend)" />
      <AppStatCardMini
        label="参与执行用例" chart="area" :value="c.executed_cases.value"
        icon="i-app-test-case" color="info"
        :note="c.executed_cases.coverage != null
          ? `占用例资产 ${c.executed_cases.coverage}%`
          : '暂无用例资产'" />
      <AppStatCardMini
        label="今日执行" chart="bars" :value="c.today.value"
        icon="i-solar-sun-bold" color="warning"
        :note="c.today.pass_rate != null ? `今日通过率 ${c.today.pass_rate}%` : ''" />
    </div>

    <!-- 三模块对比横幅（本页特色区） -->
    <div class="module-strip" v-loading="loading">
      <div
        v-for="m in moduleCards"
        :key="m.key"
        class="module-card"
        :class="`is-${m.key}`"
      >
        <div class="mc-head">
          <span class="mc-name">
            <i :class="m.icon" />
            {{ m.label }}
          </span>
          <span v-if="m.exec_trend != null" class="mc-trend" :class="trendType(m.exec_trend)">
            {{ m.exec_trend > 0 ? '↑' : m.exec_trend < 0 ? '↓' : '' }}{{ Math.abs(m.exec_trend) }}%
          </span>
        </div>
        <div class="mc-num">
          {{ m.executions }}<small>次执行</small>
        </div>
        <div class="mc-bar">
          <div
            v-if="m.passed + m.failed > 0"
            class="mc-seg is-pass"
            :style="{ width: segWidth(m.passed, m) }"
          />
          <div
            v-if="m.failed > 0"
            class="mc-seg is-fail"
            :style="{ width: segWidth(m.failed, m) }"
          />
        </div>
        <div class="mc-meta">
          <span>
            通过率
            <b :class="rateClass(m.pass_rate)">{{ m.pass_rate != null ? `${m.pass_rate}%` : '—' }}</b>
          </span>
          <span>{{ m.cases }} 个用例</span>
          <span>{{ m.avg_duration_s != null ? `均耗 ${formatSeconds(m.avg_duration_s)}` : '均耗 —' }}</span>
        </div>
      </div>
    </div>

    <!-- 趋势 + 结果分布 -->
    <div class="grid-2">
      <AppSectionCard title="每日执行趋势" subtitle="三模块堆叠 · 折线为当日通过率">
        <VChart class="chart-lg" :option="trendOption" autoresize />
      </AppSectionCard>
      <AppSectionCard title="执行结果分布" :subtitle="`近 ${days} 天全部执行记录`">
        <div class="pie-row">
          <VChart class="chart-pie" :option="resultPieOption" autoresize />
          <ul class="pie-legend">
            <li v-for="r in resultLegend" :key="r.label">
              <span class="dot" :style="{ background: r.color }" />
              <span class="lg-label">{{ r.label }}</span>
              <span class="lg-num">{{ r.value }}</span>
            </li>
          </ul>
        </div>
        <div class="panel-note">
          通过率分母 = 通过 + 失败；跳过/中止与运行中不计入。
        </div>
      </AppSectionCard>
    </div>

    <!-- 执行人排行 + 失败重灾用例 -->
    <div class="grid-2 even">
      <AppSectionCard title="执行人排行" :subtitle="`近 ${days} 天执行次数 Top`">
        <div v-if="executorRank.length" class="bar-list">
          <div v-for="u in executorRank" :key="u.user_id" class="bar-row">
            <span class="bar-label" :title="u.name">{{ u.name }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: barWidth(u.count, maxExecutorCount), background: 'var(--brand-400)' }"
              />
            </div>
            <span class="bar-num">{{ u.count }}</span>
            <span class="bar-rate" :class="rateClass(u.pass_rate)">
              {{ u.pass_rate != null ? `${u.pass_rate}%` : '—' }}
            </span>
          </div>
        </div>
        <div v-else class="panel-empty">窗口内暂无执行记录</div>
        <div class="panel-note">右侧为该执行人的通过率。</div>
      </AppSectionCard>

      <AppSectionCard title="失败重灾用例" subtitle="失败次数最多的用例，优先排查">
        <div v-if="topFailures.length" class="fail-list">
          <div v-for="f in topFailures" :key="`${f.module}-${f.case_id}`" class="fail-row">
            <span class="type-pill" :class="`type-${f.module}`">{{ moduleLabel(f.module) }}</span>
            <span class="fail-name" :title="f.name">{{ f.name }}</span>
            <span class="fail-count">败 {{ f.fail_count }}/{{ f.exec_count }} 次</span>
            <span class="fail-rate">{{ f.fail_rate != null ? `${f.fail_rate}%` : '—' }}</span>
          </div>
        </div>
        <div v-else class="panel-empty">窗口内没有失败的执行，保持住</div>
        <div class="panel-note">失败率 = 该用例窗口内失败次数 / 执行次数。</div>
      </AppSectionCard>
    </div>

    <!-- 核心业务流用例：全量回归健康度 -->
    

    <!-- 执行记录明细 -->
    <AppSectionCard padless>
      <div class="view-bar">
        <span class="section-title">
          <i class="i-solar-list-bold" />
          执行记录明细
        </span>
        <div class="view-right">
          <el-select
            v-model="execType"
            placeholder="全部类型"
            clearable
            size="small"
            style="width: 130px"
            @change="onTypeChange"
          >
            <el-option label="功能测试" value="functional" />
            
            
            <el-option label="App 自动化" value="app" />
            
          </el-select>
          <span class="result-hint">共 {{ pagination.total }} 条</span>
        </div>
      </div>

      <el-table v-loading="loadingList" :data="executions" style="width: 100%">
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <span class="type-pill" :class="`type-${row.exec_type}`">
              {{ moduleLabel(row.exec_type) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="执行名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="exec-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <span class="status-pill" :class="`status-${row.status}`">
              {{ statusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="用例" width="70" align="center">
          <template #default="{ row }">{{ row.total }}</template>
        </el-table-column>
        <el-table-column label="通过/失败" width="100" align="center">
          <template #default="{ row }">
            <span class="pass-num">{{ row.passed }}</span>
            <span class="sep">/</span>
            <span class="fail-num">{{ row.failed }}</span>
          </template>
        </el-table-column>
        <el-table-column label="通过率" width="140">
          <template #default="{ row }">
            <div class="rate-cell">
              <el-progress
                :percentage="row.pass_rate"
                :stroke-width="6"
                :color="passColor(row.pass_rate)"
                :show-text="false"
              />
              <span class="rate-text" :style="{ color: passColor(row.pass_rate) }">
                {{ row.pass_rate.toFixed(1) }}%
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90" align="center">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDuration(row.duration_ms) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="执行人" width="100" align="center">
          <template #default="{ row }">
            <span class="muted-text">{{ row.executor_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="执行时间" width="155" align="center">
          <template #default="{ row }">
            <span class="muted-text">{{ formatTime(row.executed_at) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <AppEmpty v-if="!loadingList" scene="data" description="暂无执行记录" />
        </template>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadExecutions"
          @current-change="loadExecutions"
        />
      </div>
    </AppSectionCard>
  </div>
</template>

<script setup lang="ts">import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace';
import { AppPageHeader, AppSectionCard, AppStatCardMini, AppEmpty, } from '@/components/common';
import { reportCenterApi } from '@/api/report-center';
import type { ExecutionReportData } from '@/api/report-center';
import { reportApi } from '@/api/reports';
import type { ExecType, ReportExecutionItem } from '@/types/reports';
import illustReport from '@/assets/illustrations/report.svg';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent]);
const workspaceStore = useProjectWorkspaceStore();
const projectId = computed(() => workspaceStore.currentProject?.id || 0);
const router = useRouter();
// ── 核心业务流用例维度 ──


const loading = ref(false);
const days = ref(30);
const data = ref<ExecutionReportData | null>(null);
const fetch = async () => {
    if (!projectId.value)
        return;
    loading.value = true;
    try {
        const res = await reportCenterApi.execution(projectId.value, days.value);
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
    executions: { value: 0, trend: null },
    pass_rate: { value: null, trend: null },
    failed: { value: 0, trend: null },
    executed_cases: { value: 0, total_cases: 0, coverage: null },
    today: { value: 0, pass_rate: null },
});
// ── 工具 ──
function trendNote(t: number | null | undefined): string {
    if (t == null)
        return '';
    return `较上期 ${t > 0 ? '↑' : t < 0 ? '↓' : ''}${Math.abs(t)}%`;
}
function rateTrendNote(t: number | null | undefined): string {
    if (t == null)
        return '';
    return `较上期 ${t > 0 ? '↑' : t < 0 ? '↓' : ''}${Math.abs(t)} 个点`;
}
function trendType(t: number | null | undefined): 'success' | 'danger' | 'muted' {
    if (t == null || t === 0)
        return 'muted';
    return t > 0 ? 'success' : 'danger';
}
/** 失败数语义反转：增长是坏事 */
function invTrendType(t: number | null | undefined): 'success' | 'danger' | 'muted' {
    if (t == null || t === 0)
        return 'muted';
    return t > 0 ? 'danger' : 'success';
}
function rateClass(rate: number | null): string {
    if (rate == null)
        return 'is-muted';
    if (rate >= 90)
        return 'is-good';
    if (rate >= 70)
        return 'is-warn';
    return 'is-bad';
}
function moduleLabel(k: string): string {
    return ({
        functional: '功能',
        app: 'App'
    } as Record<string, string>)[k] || k;
}
function formatSeconds(s: number): string {
    if (s < 60)
        return `${s}s`;
    const total = Math.round(s);
    return `${Math.floor(total / 60)}m${total % 60}s`;
}
function passColor(rate: number): string {
    if (rate >= 90)
        return '#67C23A';
    if (rate >= 70)
        return '#E6A23C';
    return '#F56C6C';
}
function formatDuration(ms: number): string {
    if (!ms)
        return '—';
    if (ms < 1000)
        return `${ms}ms`;
    if (ms < 60000)
        return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}
function formatTime(dt: string): string {
    if (!dt)
        return '—';
    return dt.replace('T', ' ').substring(0, 19);
}
function statusLabel(s: string) {
    const m: Record<string, string> = {
        passed: '通过', failed: '失败', blocked: '阻塞', skipped: '跳过',
        completed: '完成', running: '运行中', cancelled: '已取消', stopped: '已停止',
        error: '错误',
    };
    return m[s] ?? s;
}
function barWidth(n: number, max: number): string {
    if (!max)
        return '0%';
    return `${Math.max(4, Math.round((n / max) * 100))}%`;
}
// ── 模块对比 ──
const MODULE_META: Record<string, {
    label: string;
    icon: string;
}> = {
    functional: { label: '功能测试', icon: 'i-solar-document-text-bold' },
    app: { label: 'App 自动化', icon: 'i-app-mobile' }
};
const moduleCards = computed(() => (data.value?.modules || []).map((m) => ({
    ...m,
    ...MODULE_META[m.key],
})));
function segWidth(n: number, m: {
    executions: number;
}): string {
    if (!m.executions)
        return '0%';
    return `${Math.round((n / m.executions) * 100)}%`;
}
// ── 趋势主图 ──
const trendOption = computed(() => {
    const daily = data.value?.trend || [];
    const dates = daily.map((d) => d.date.slice(5));
    return {
        tooltip: { trigger: 'axis' },
        legend: {
            data: ['功能', '接口', 'Web', 'App', '压测', '通过率'],
            top: 0, right: 0, icon: 'circle',
            textStyle: { fontSize: 11, color: '#6B7280' },
        },
        grid: { left: 0, right: 36, top: 28, bottom: 0, containLabel: true },
        xAxis: {
            type: 'category', data: dates,
            axisLabel: { color: '#9CA3AF', fontSize: 10 },
            axisTick: { show: false },
            axisLine: { lineStyle: { color: '#EEF1F4' } },
        },
        yAxis: [
            {
                type: 'value', minInterval: 1,
                splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } },
                axisLabel: { color: '#9CA3AF', fontSize: 10 },
            },
            {
                type: 'value', min: 0, max: 100,
                splitLine: { show: false },
                axisLabel: { color: '#9CA3AF', fontSize: 10, formatter: '{value}%' },
            },
        ],
        series: [
            { name: '功能', type: 'bar', stack: 'exec', data: daily.map((d) => d.functional), itemStyle: { color: '#00B96B' }, barMaxWidth: 14 },
            { name: 'App', type: 'bar', stack: 'exec', data: daily.map((d) => d.app), itemStyle: { color: '#14B8A6' }, barMaxWidth: 14 },
            {
                name: '通过率', type: 'line', yAxisIndex: 1, smooth: true,
                symbol: 'circle', symbolSize: 4, connectNulls: true,
                data: daily.map((d) => d.pass_rate),
                lineStyle: { color: '#F59E0B', width: 2 },
                itemStyle: { color: '#F59E0B' },
            }
        ],
    };
});
// ── 结果分布 ──
const RESULT_META: {
    key: keyof ExecutionReportData['result_dist'];
    label: string;
    color: string;
}[] = [
    { key: 'passed', label: '通过', color: '#00B96B' },
    { key: 'failed', label: '失败/错误', color: '#F56C6C' },
    { key: 'skipped', label: '跳过/中止', color: '#9CA3AF' },
    { key: 'running', label: '运行中', color: '#F59E0B' },
];
const resultLegend = computed(() => {
    const dist = data.value?.result_dist;
    return RESULT_META.map((m) => ({ ...m, value: dist?.[m.key] ?? 0 }));
});
const resultPieOption = computed(() => {
    const items = resultLegend.value
        .filter((r) => r.value > 0)
        .map((r) => ({ name: r.label, value: r.value, itemStyle: { color: r.color } }));
    return {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [
            {
                type: 'pie',
                radius: ['52%', '74%'],
                label: { show: false },
                itemStyle: {
                    borderRadius: items.length > 1 ? 4 : 0,
                    borderColor: '#fff',
                    borderWidth: items.length > 1 ? 2 : 0,
                },
                data: items,
            },
        ],
    };
});
// ── 排行 ──
const executorRank = computed(() => data.value?.executor_rank || []);
const maxExecutorCount = computed(() => Math.max(0, ...executorRank.value.map((u) => u.count)));
const topFailures = computed(() => (data.value?.top_failures || []).slice(0, 6));
// ── 执行记录明细（沿用 /reports/executions） ──
const loadingList = ref(false);
const execType = ref<ExecType | ''>('');
const executions = ref<ReportExecutionItem[]>([]);
const pagination = ref({ page: 1, pageSize: 20, total: 0 });
async function loadExecutions() {
    if (!projectId.value)
        return;
    loadingList.value = true;
    try {
        // 与顶部 days 选择器同窗口，保证明细与卡片口径一致
        const startDate = new Date(Date.now() - (days.value - 1) * 86400000)
            .toISOString()
            .slice(0, 10);
        const res = await reportApi.getExecutions(projectId.value, {
            exec_type: execType.value || undefined,
            start_date: startDate,
            page: pagination.value.page,
            page_size: pagination.value.pageSize,
        });
        if (res.data) {
            executions.value = res.data.items;
            pagination.value.total = res.data.total;
        }
    }
    catch (err) {
        console.error(err);
    }
    finally {
        loadingList.value = false;
    }
}
function onTypeChange() {
    pagination.value.page = 1;
    loadExecutions();
}
onMounted(loadExecutions);
watch([days, projectId], () => {
    pagination.value.page = 1;
    loadExecutions();
});
</script>

<style scoped lang="scss">
@use './report-shared';

/* 顶部迷你卡一排 5 个 */
.exec-mini-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--space-3);
}
@media (max-width: 1300px) {
  .exec-mini-row { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 800px) {
  .exec-mini-row { grid-template-columns: 1fr; }
}

/* 三模块对比横幅 */
.module-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-3);
}
@media (max-width: 1000px) {
  .module-strip { grid-template-columns: repeat(2, 1fr); }
}
.module-card {
  position: relative;
  padding: var(--space-4) var(--space-5);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
  }
  &.is-functional::before { background: #00b96b; }
  &.is-api::before { background: #3b82f6; }
  &.is-web::before { background: #8b5cf6; }
  &.is-app::before { background: #14b8a6; }
  &.is-perf::before { background: #ec4899; }
}
.mc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mc-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);

  i { font-size: 16px; }
}
.is-functional .mc-name i { color: #00b96b; }
.is-api .mc-name i { color: #3b82f6; }
.is-web .mc-name i { color: #8b5cf6; }

.mc-trend {
  font-size: 11px;
  font-weight: var(--font-weight-semibold);

  &.success { color: var(--color-success-500); }
  &.danger { color: var(--color-danger-500); }
  &.muted { color: var(--text-placeholder); }
}
.mc-num {
  margin-top: var(--space-2);
  font-size: 30px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;

  small {
    margin-left: 4px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-regular);
    color: var(--text-secondary);
  }
}
.mc-bar {
  display: flex;
  height: 8px;
  margin-top: var(--space-3);
  border-radius: 4px;
  overflow: hidden;
  background: var(--gray-100);
}
.mc-seg {
  height: 100%;

  &.is-pass { background: var(--color-success-400, #34d399); }
  &.is-fail { background: var(--color-danger-400, #f87171); }
}
.mc-meta {
  display: flex;
  gap: var(--space-4);
  margin-top: var(--space-2);
  font-size: 11px;
  color: var(--text-secondary);

  b {
    font-weight: var(--font-weight-semibold);

    &.is-good { color: var(--color-success-500); }
    &.is-warn { color: var(--color-warning-500); }
    &.is-bad { color: var(--color-danger-500); }
    &.is-muted { color: var(--text-placeholder); }
  }
}

/* 大图 */
.chart-lg {
  width: 100%;
  height: 260px;
}

/* 排行两列等宽 */
.grid-2.even {
  grid-template-columns: 1fr 1fr;
}
@media (max-width: 1100px) {
  .grid-2.even { grid-template-columns: 1fr; }
}

.bar-rate {
  width: 44px;
  flex-shrink: 0;
  text-align: right;
  font-size: 11px;
  font-weight: var(--font-weight-semibold);

  &.is-good { color: var(--color-success-500); }
  &.is-warn { color: var(--color-warning-500); }
  &.is-bad { color: var(--color-danger-500); }
  &.is-muted { color: var(--text-placeholder); }
}

/* 失败重灾列表 */
.fail-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.fail-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
}
.fail-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-regular);
}
.fail-count {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.fail-rate {
  width: 48px;
  flex-shrink: 0;
  text-align: right;
  font-weight: var(--font-weight-semibold);
  color: var(--color-danger-500);
  font-variant-numeric: tabular-nums;
}

/* 明细表 */
.view-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);

  i { color: var(--brand-500); }
}
.view-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.result-hint {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.exec-name {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}
.type-pill {
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  flex-shrink: 0;

  &.type-functional { background: var(--color-success-50); color: var(--color-success-600); }
  &.type-api { background: var(--color-info-50); color: var(--color-info-600); }
  &.type-web { background: var(--color-purple-50); color: var(--color-purple-600); }
  &.type-app { background: var(--color-cyan-50, var(--color-success-50)); color: var(--color-cyan-600, var(--color-success-600)); }
  &.type-perf { background: var(--color-pink-50, var(--color-warning-50)); color: var(--color-pink-600, var(--color-warning-600)); }
}
.status-pill {
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  &.status-passed,
  &.status-completed { background: var(--color-success-50); color: var(--color-success-600); }
  &.status-failed,
  &.status-error { background: var(--color-danger-50); color: var(--color-danger-600); }
  &.status-running { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.status-blocked,
  &.status-skipped,
  &.status-cancelled,
  &.status-stopped { background: var(--gray-100); color: var(--gray-600); }
}

/* 核心业务流用例 */
.cf-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.cf-stats {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--el-text-color-regular);

  .cf-stat b { font-size: 15px; margin: 0 2px; }
  .cf-stat.ok b { color: var(--el-color-success); }
  .cf-stat.bad b { color: var(--el-color-danger); }
  .cf-stat.muted b { color: var(--el-text-color-secondary); }
  .is-good { color: var(--color-success-600); }
  .is-warn { color: var(--color-warning-600); }
  .is-bad { color: var(--color-danger-600); }
  .is-muted { color: var(--el-text-color-secondary); }
}
.cf-link {
  color: var(--el-color-primary);
  cursor: pointer;
  &:hover { text-decoration: underline; }
}
.pass-num { color: var(--color-success-500); font-weight: var(--font-weight-semibold); }
.sep { margin: 0 4px; color: var(--text-placeholder); }
.fail-num { color: var(--color-danger-500); font-weight: var(--font-weight-semibold); }
.rate-cell {
  display: flex;
  align-items: center;
  gap: 8px;

  .el-progress { flex: 1; }
  .rate-text {
    font-size: 11px;
    font-weight: var(--font-weight-medium);
    min-width: 42px;
    text-align: right;
  }
}
.muted-text { color: var(--text-secondary); }

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) var(--space-2);
  border-top: 1px solid var(--border-light);
}

:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
  }
  td.el-table__cell {
    padding: 12px 0;
    font-size: var(--font-size-sm);
  }
}
</style>
