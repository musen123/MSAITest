<template>
  <div class="dash-page">
    <!-- ============ 紧凑欢迎区 ============ -->
    <header class="dash-hello">
      <div class="hello-left">
        <h1 class="hello-title">
          {{ greeting }}，{{ userName }}
          <span class="hello-wave">👋</span>
        </h1>
        <p class="hello-sub">「{{ projectName }}」工作台 · 数据截至 {{ refreshedAt }}</p>
      </div>
      <div class="hello-right">
        <el-button size="small" @click="fetchDashboard">
          <i class="i-solar-refresh-bold ds-btn-icon" />
          刷新
        </el-button>
        <el-button size="small" type="primary" @click="goNewCase">
          <i class="i-solar-add-circle-bold ds-btn-icon" />
          新建用例
        </el-button>
      </div>
    </header>

    <!-- ============ 统计卡 ×7 一排 ============ -->
    <div class="dash-mini-grid" v-loading="loading">
      <AppStatCardMini
        label="用例总数" chart="bars" :value="cards.caseTotal"
        icon="i-app-test-case" color="brand" :note="cards.caseNote" />
      <AppStatCardMini
        :label="`近 ${trendDays} 天执行`" chart="area" :value="cards.executions"
        icon="i-app-test-run" color="info" :note="cards.execTrend"
        :note-type="cards.execTrendType" />
      <AppStatCardMini
        label="执行通过率" chart="gauge" :value="cards.passRate" suffix="%"
        icon="i-solar-check-circle-bold" color="success" :note="cards.rateTrend"
        :note-type="cards.rateTrendType" />
      <AppStatCardMini
        label="未关闭缺陷" chart="bars" :value="cards.openBugs"
        icon="i-app-bug" color="warning" :note="cards.bugNote"
        :note-type="cards.bugNote ? 'danger' : 'muted'" />
      <AppStatCardMini
        :label="`近 ${trendDays} 天 AI 任务`" chart="pulse" :value="cards.aiTasks"
        icon="i-app-ai-agent" color="purple" :note="cards.aiNote" />
      <AppStatCardMini
        label="新增用例" chart="area" :value="cards.newCases"
        icon="i-solar-stars-bold" color="cyan" :note="cards.newTrend"
        :note-type="cards.newTrendType" />
      <AppStatCardMini
        label="今日执行" chart="pulse" :value="today.executions"
        icon="i-solar-calendar-bold" color="brand" :note="todayNote" />
    </div>

    <!-- ============ 趋势 + 最近执行 ============ -->
    <div class="dash-row dash-row-2">
      <AppSectionCard title="测试执行趋势" class="dash-trend">
        <template #extra>
          <el-radio-group v-model="trendDays" size="small">
            <el-radio-button :value="7">近 7 天</el-radio-button>
            <el-radio-button :value="30">近 30 天</el-radio-button>
          </el-radio-group>
        </template>
        <v-chart :option="trendOption" class="trend-chart" autoresize />
      </AppSectionCard>

      <AppSectionCard title="最近执行" class="dash-tasks">
        <div v-if="recentExecutions.length" class="task-list">
          <div
            v-for="t in recentExecutions"
            :key="`${t.module}-${t.kind}-${t.execution_id}`"
            class="task-item is-link"
            @click="goExecution(t)"
          >
            <span class="task-module" :class="`is-${t.module}`">
              {{ moduleLabel(t) }}
            </span>
            <span class="task-name">{{ t.name }}</span>
            <span class="task-cases" :class="t.failed > 0 ? 'is-bad' : 'is-good'">
              {{ t.passed }}/{{ t.total }}
            </span>
            <span class="task-time">{{ formatTime(t.started_at) }}</span>
          </div>
        </div>
        <div v-else class="panel-empty">暂无执行记录</div>
      </AppSectionCard>
    </div>

    <!-- ============ 三列分布 ============ -->
    <div class="dash-row dash-row-3">
      <AppSectionCard title="缺陷状态" class="dash-bugs">
        <div v-if="bugTotal > 0" class="bugs-row">
          <v-chart :option="bugPieOption" class="bug-chart" autoresize />
          <ul class="bugs-legend">
            <li v-for="b in bugLegend" :key="b.label">
              <span class="dot" :style="{ background: b.color }" />
              <span class="lg-label">{{ b.label }}</span>
              <span class="lg-num">{{ b.value }}</span>
            </li>
          </ul>
        </div>
        <div v-else class="panel-empty">暂无缺陷数据</div>
      </AppSectionCard>

      <AppSectionCard title="测试资产构成" class="dash-modules">
        <ul class="mod-list">
          <li v-for="m in caseAssets" :key="m.name" class="mod-item">
            <div class="mod-row1">
              <span class="mod-name">{{ m.name }}</span>
              <span class="mod-num">{{ m.value }}</span>
            </div>
            <div class="mod-bar">
              <div class="mod-bar-fill" :style="{ width: m.pct + '%', background: m.color }" />
            </div>
          </li>
        </ul>
        <div class="asset-total">
          合计 <b>{{ data?.stat_cards.case_total.value ?? 0 }}</b> 条
          <span v-if="aiPct !== null" class="asset-ai">· AI 生成占 {{ aiPct }}%</span>
        </div>
      </AppSectionCard>

      <AppSectionCard title="知识库" class="dash-kb">
        <template #extra>
          <span class="kb-status-pill" :class="`is-${kbStatusType}`">{{ kbStatusLabel }}</span>
        </template>
        <div class="kb-grid">
          <div class="kb-cell">
            <div class="kb-num">{{ kb.documents }}</div>
            <div class="kb-label">文档</div>
          </div>
          <div class="kb-cell">
            <div class="kb-num">{{ kb.chunks }}</div>
            <div class="kb-label">分块</div>
          </div>
          <div class="kb-cell">
            <div class="kb-num">{{ kb.nodes }}</div>
            <div class="kb-label">实体</div>
          </div>
          <div class="kb-cell">
            <div class="kb-num">{{ kb.edges }}</div>
            <div class="kb-label">关系</div>
          </div>
        </div>
      </AppSectionCard>
    </div>

    <!-- ============ 维度报表入口 ============ -->
    <div class="dash-entries">
      <div class="entry-card is-brand" @click="goReport('ReportAssets')">
        <div class="entry-body">
          <div class="entry-title">测试资产</div>
          <div class="entry-sub">{{ cards.caseTotal }} 条用例 · AI 生成 {{ data?.stat_cards.case_total.ai_generated ?? 0 }}</div>
        </div>
        <i class="i-solar-alt-arrow-right-linear entry-arrow" />
      </div>
      <div class="entry-card is-info" @click="goReport('ProjectReports')">
        <div class="entry-body">
          <div class="entry-title">执行汇总</div>
          <div class="entry-sub">本期 {{ cards.executions }} 次 · 通过率 {{ cards.passRate }}%</div>
        </div>
        <i class="i-solar-alt-arrow-right-linear entry-arrow" />
      </div>
      <div class="entry-card is-danger" @click="goReport('ReportQuality')">
        <div class="entry-body">
          <div class="entry-title">缺陷质量</div>
          <div class="entry-sub">未关闭 {{ cards.openBugs }}{{ cards.bugNote ? ` · ${cards.bugNote}` : '' }}</div>
        </div>
        <i class="i-solar-alt-arrow-right-linear entry-arrow" />
      </div>
      <div class="entry-card is-purple" @click="goReport('ReportAi')">
        <div class="entry-body">
          <div class="entry-title">AI 提效</div>
          <div class="entry-sub">任务 {{ cards.aiTasks }} 个{{ cards.aiNote ? ` · ${cards.aiNote}` : '' }}</div>
        </div>
        <i class="i-solar-alt-arrow-right-linear entry-arrow" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace';
import { AppStatCardMini, AppSectionCard } from '@/components/common';
import { projectApi } from '@/api/projects';
import type { ProjectDashboardData, DashboardRecentExecution } from '@/api/projects';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent]);
const router = useRouter();
const userStore = useUserStore();
const workspaceStore = useProjectWorkspaceStore();
const projectId = computed(() => workspaceStore.currentProject?.id || 0);
// ============ 欢迎语 ============
const userName = computed(() => userStore.realName || userStore.username || 'Admin');
const projectName = computed(() => workspaceStore.currentProject?.name || '当前项目');
const greeting = computed(() => {
    const h = new Date().getHours();
    if (h < 6)
        return '凌晨好';
    if (h < 12)
        return '早上好';
    if (h < 14)
        return '中午好';
    if (h < 18)
        return '下午好';
    if (h < 22)
        return '晚上好';
    return '夜深了';
});
// ============ 数据加载 ============
const loading = ref(false);
const data = ref<ProjectDashboardData | null>(null);
const trendDays = ref(7);
const refreshedAt = ref('--:--');
const fetchDashboard = async () => {
    if (!projectId.value)
        return;
    loading.value = true;
    try {
        const res = await projectApi.getProjectDashboard(projectId.value, trendDays.value);
        data.value = res.data;
        const now = new Date();
        refreshedAt.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    }
    catch (err) {
        console.error(err);
    }
    finally {
        loading.value = false;
    }
};
onMounted(fetchDashboard);
watch(trendDays, fetchDashboard);
watch(projectId, (v) => v && fetchDashboard());
// ============ 迷你卡数据 ============
function trendNote(t: number | null | undefined): string {
    if (t == null)
        return '';
    return `${t > 0 ? '↑' : t < 0 ? '↓' : ''}${Math.abs(t)}%`;
}
function trendType(t: number | null | undefined): 'success' | 'danger' | 'muted' {
    if (t == null || t === 0)
        return 'muted';
    return t > 0 ? 'success' : 'danger';
}
const cards = computed(() => {
    const s = data.value?.stat_cards;
    const byType = s?.case_total.by_type;
    const sev = s?.open_bugs.by_severity || {};
    const urgent = (sev.critical || 0) + (sev.major || 0);
    return {
        caseTotal: s?.case_total.value ?? 0,
        caseNote: byType
            ? `功能 ${byType.functional} · App ${byType.app ?? 0}`
            : '',
        executions: s?.executions.value ?? 0,
        execTrend: trendNote(s?.executions.trend),
        execTrendType: trendType(s?.executions.trend),
        passRate: s?.pass_rate.value ?? 0,
        rateTrend: s?.pass_rate.value == null ? '暂无记录' : trendNote(s?.pass_rate.trend),
        rateTrendType: trendType(s?.pass_rate.trend),
        openBugs: s?.open_bugs.value ?? 0,
        bugNote: urgent > 0 ? `严重/主要 ${urgent}` : '',
        aiTasks: s?.ai_tasks.value ?? 0,
        aiNote: s?.ai_tasks.success_rate != null ? `成功率 ${s.ai_tasks.success_rate}%` : '',
        newCases: s?.new_cases.value ?? 0,
        newTrend: trendNote(s?.new_cases.trend),
        newTrendType: trendType(s?.new_cases.trend),
    };
});
const today = computed(() => data.value?.today ?? { executions: 0, passed: 0, pass_rate: null });
const todayNote = computed(() => today.value.pass_rate != null ? `通过率 ${today.value.pass_rate}%` : '尚无执行');
// ============ 趋势图 ============
const trendOption = computed(() => {
    const daily = data.value?.execution_trend || [];
    const dates = daily.map((d) => {
        const [, m, dd] = d.date.split('-');
        return `${m}-${dd}`;
    });
    const passed = daily.map((d) => d.passed);
    const failed = daily.map((d) => d.failed);
    const total = daily.map((d) => d.passed + d.failed);
    return {
        tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#EEF1F4', textStyle: { color: '#1F2937' } },
        legend: { data: ['已完成执行', '通过数', '失败数'], top: 0, right: 0, icon: 'circle', textStyle: { color: '#6B7280', fontSize: 11 } },
        grid: { left: 0, right: 8, top: 28, bottom: 0, containLabel: true },
        xAxis: {
            type: 'category', data: dates, boundaryGap: false,
            axisLine: { lineStyle: { color: '#EEF1F4' } },
            axisLabel: { color: '#9CA3AF', fontSize: 10 }, axisTick: { show: false },
        },
        yAxis: {
            type: 'value', minInterval: 1,
            splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } },
            axisLabel: { color: '#9CA3AF', fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false },
        },
        series: [
            {
                name: '已完成执行', type: 'line', smooth: true, data: total,
                symbol: 'circle', symbolSize: 5,
                lineStyle: { color: '#3B82F6', width: 2 },
                itemStyle: { color: '#3B82F6' },
                areaStyle: { color: 'rgba(59, 130, 246, 0.08)' },
            },
            {
                name: '通过数', type: 'line', smooth: true, data: passed,
                symbol: 'circle', symbolSize: 5,
                lineStyle: { color: '#00B96B', width: 2 },
                itemStyle: { color: '#00B96B' },
                areaStyle: { color: 'rgba(0, 185, 107, 0.10)' },
            },
            {
                name: '失败数', type: 'line', smooth: true, data: failed,
                symbol: 'circle', symbolSize: 5,
                lineStyle: { color: '#EF4444', width: 2 },
                itemStyle: { color: '#EF4444' },
            },
        ],
    };
});
// ============ 最近执行 ============
const recentExecutions = computed(() => data.value?.recent_executions || []);
function formatTime(iso: string | null): string {
    if (!iso)
        return '-';
    const d = new Date(iso);
    const now = new Date();
    const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    const sameDay = (a: Date, b: Date) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    if (sameDay(d, now))
        return `今天 ${hm}`;
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (sameDay(d, yesterday))
        return `昨天 ${hm}`;
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
// 最近执行条目的模块+粒度标签（压测为单次运行，无套件/任务之分）
function moduleLabel(_t: DashboardRecentExecution): string { return "App 套件" }
function goExecution(t: DashboardRecentExecution) { router.push({ name: "AppSuiteDetail", params: { id: projectId.value, suiteId: t.ref_id } }) }
function goNewCase() {
    router.push({ name: 'FuncTestCases', params: { id: projectId.value } });
}
function goReport(name: string) {
    router.push({ name, params: { id: projectId.value } });
}
// ============ 缺陷状态饼图 ============
const BUG_BUCKET_META = [
    { key: 'pending', label: '待处理', color: '#EF4444' },
    { key: 'processing', label: '处理中', color: '#3B82F6' },
    { key: 'resolved', label: '已解决', color: '#F59E0B' },
    { key: 'closed', label: '已关闭', color: '#10B981' },
    { key: 'suspended', label: '已搁置', color: '#9CA3AF' },
] as const;
const bugTotal = computed(() => {
    const dist = data.value?.bug_status_dist || {};
    return Object.values(dist).reduce((a, b) => a + b, 0);
});
const bugLegend = computed(() => {
    const dist = data.value?.bug_status_dist || {};
    return BUG_BUCKET_META.filter((m) => (dist[m.key] || 0) > 0).map((m) => ({
        label: m.label,
        value: dist[m.key] || 0,
        color: m.color,
    }));
});
const bugPieOption = computed(() => {
    const multi = bugLegend.value.length > 1;
    return {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [
            {
                type: 'pie',
                radius: ['55%', '78%'],
                center: ['50%', '50%'],
                avoidLabelOverlap: false,
                itemStyle: {
                    borderRadius: multi ? 4 : 0,
                    borderColor: '#fff',
                    borderWidth: multi ? 2 : 0,
                },
                label: {
                    show: true,
                    position: 'center',
                    formatter: `{a|总计}\n{b|${bugTotal.value}}`,
                    rich: {
                        a: { fontSize: 10, color: '#9CA3AF', padding: [0, 0, 2, 0] },
                        b: { fontSize: 18, fontWeight: 700, color: '#1F2937' },
                    },
                },
                labelLine: { show: false },
                data: bugLegend.value.map((b) => ({
                    value: b.value,
                    name: b.label,
                    itemStyle: { color: b.color },
                })),
            },
        ],
    };
});
// ============ 测试资产构成 ============
const caseAssets = computed(() => {
    const byType = data.value?.stat_cards.case_total.by_type;
    if (!byType)
        return [];
    const total = byType.functional +
        
        
        (byType.app ?? 0)  || 1;
    const items = [
        { name: '功能用例', value: byType.functional, color: 'var(--brand-500)' },
        { name: 'App 自动化', value: byType.app ?? 0, color: '#00B96B' }
    ];
    return items.map((m) => ({
        ...m,
        pct: Math.round((m.value / total) * 1000) / 10,
    }));
});
const aiPct = computed(() => {
    const s = data.value?.stat_cards.case_total;
    if (!s || !s.value)
        return null;
    return Math.round((s.ai_generated / s.value) * 1000) / 10;
});
// ============ 知识库状态 ============
const kb = computed(() => data.value?.kb ?? {
    status: 'inactive',
    documents: 0,
    chunks: 0,
    nodes: 0,
    edges: 0,
    last_built_at: null,
});
const kbStatusLabel = computed(() => ({ ready: '就绪', building: '构建中', error: '异常', inactive: '未启用' })[kb.value.status] || kb.value.status);
const kbStatusType = computed(() => ({ ready: 'success', building: 'info', error: 'danger', inactive: 'muted' })[kb.value.status] || 'muted');
</script>

<style scoped lang="scss">
.dash-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0 auto;
}

/* ============ 紧凑欢迎区 ============ */
.dash-hello {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.hello-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.3px;
}
.hello-wave {
  display: inline-block;
  animation: wave 1.6s ease-in-out infinite;
  transform-origin: 70% 70%;
  font-size: var(--font-size-lg);
}
@keyframes wave {
  0%, 100% { transform: rotate(0); }
  20%, 60% { transform: rotate(-14deg); }
  40%, 80% { transform: rotate(10deg); }
}
.hello-sub {
  margin: 2px 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.hello-right {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
.ds-btn-icon {
  margin-right: 4px;
  vertical-align: -2px;
}

/* ============ 统计卡 ×7 一排 ============ */
.dash-mini-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: var(--space-2);
}
@media (max-width: 1500px) {
  .dash-mini-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
@media (max-width: 900px) {
  .dash-mini-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* ============ 行布局 ============ */
.dash-row {
  display: grid;
  gap: var(--space-3);
}
.dash-row-2 {
  grid-template-columns: 1.5fr 1fr;
}
.dash-row-3 {
  grid-template-columns: 1fr 1fr 1fr;
}
@media (max-width: 1100px) {
  .dash-row-2,
  .dash-row-3 {
    grid-template-columns: 1fr;
  }
}

.trend-chart {
  width: 100%;
  height: 220px;
}

.panel-empty {
  padding: var(--space-6) 0;
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--text-placeholder);
}

/* ============ 最近执行(紧凑行) ============ */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.task-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  transition: var(--transition-fast);

  &.is-link { cursor: pointer; }
  &:hover { background: var(--bg-hover); }
}
.task-module {
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: var(--font-weight-medium);
  flex-shrink: 0;

  &.is-api { background: var(--color-info-50); color: var(--color-info-600); }
  &.is-web { background: var(--color-purple-50); color: var(--color-purple-600); }
  &.is-app { background: var(--color-success-50); color: var(--color-success-600); }
  &.is-perf { background: var(--color-warning-50); color: var(--color-warning-600); }
}
.task-name {
  flex: 1;
  min-width: 0;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-cases {
  flex-shrink: 0;
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;

  &.is-good { color: var(--color-success-600); }
  &.is-bad  { color: var(--color-danger-600); }
}
.task-time {
  flex-shrink: 0;
  color: var(--text-placeholder);
  font-size: 10px;
}

/* ============ 缺陷分布 ============ */
.bugs-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-5);
}
.bug-chart {
  width: 120px;
  height: 120px;
  flex-shrink: 0;
}
.bugs-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;

  li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-xs);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lg-label {
    color: var(--text-regular);
    white-space: nowrap;
  }
  .lg-num {
    margin-left: var(--space-2);
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold);
    font-variant-numeric: tabular-nums;
  }
}

/* ============ 测试资产构成 ============ */
.mod-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.mod-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mod-row1 {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
}
.mod-name { color: var(--text-regular); }
.mod-num {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
}
.mod-bar {
  height: 7px;
  background: var(--gray-100);
  border-radius: 4px;
  overflow: hidden;
}
.mod-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 1s var(--ease-out);
}
.asset-total {
  margin-top: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--border-light);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);

  b {
    color: var(--text-primary);
    margin: 0 2px;
  }
}
.asset-ai {
  color: var(--color-purple-600);
}

/* ============ 知识库 ============ */
.kb-status-pill {
  height: 20px;
  line-height: 20px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-weight-medium);

  &.is-success { background: var(--color-success-50); color: var(--color-success-600); }
  &.is-info    { background: var(--color-info-50);    color: var(--color-info-600); }
  &.is-danger  { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.is-muted   { background: var(--gray-100);         color: var(--text-secondary); }
}
.kb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
.kb-cell {
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50);
  border-radius: var(--radius-sm);
  text-align: center;
}
.kb-num {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-family: var(--font-mono);
}
.kb-label {
  margin-top: 1px;
  font-size: 10px;
  color: var(--text-secondary);
}

/* ============ 维度报表入口 ============ */
.dash-entries {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
}
@media (max-width: 1100px) {
  .dash-entries {
    grid-template-columns: repeat(2, 1fr);
  }
}
.entry-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-left-width: 3px;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: var(--transition-fast);

  &:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-hover);

    .entry-arrow { transform: translateX(2px); }
  }

  &.is-brand  { border-left-color: var(--brand-500); }
  &.is-info   { border-left-color: var(--color-info-500); }
  &.is-danger { border-left-color: var(--color-danger-500); }
  &.is-purple { border-left-color: var(--color-purple-500); }
}
.entry-body {
  flex: 1;
  min-width: 0;
}
.entry-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.entry-sub {
  margin-top: 1px;
  font-size: 10px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.entry-arrow {
  flex-shrink: 0;
  font-size: 14px;
  color: var(--text-placeholder);
  transition: var(--transition-fast);
}
</style>
