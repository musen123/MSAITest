<template>
  <div class="project-overview">
    <!-- ① 项目头部 -->
    <el-card class="header-card" shadow="never" v-loading="loadingDetail">
      <div v-if="project" class="project-header">
        <div class="project-avatar">
          <img v-if="project.avatar" :src="project.avatar" class="avatar-img" alt="项目图标" />
          <div v-else class="avatar-placeholder">{{ project.name.charAt(0).toUpperCase() }}</div>
        </div>
        <div class="project-info">
          <div class="project-title-row">
            <span class="project-name">{{ project.name }}</span>
            <el-tag :type="statusTagType(project.status)" size="small" class="status-tag">
              {{ statusLabel(project.status) }}
            </el-tag>
            <span class="project-code"># {{ project.code }}</span>
            <el-tag v-if="project.is_public" type="info" size="small">公开</el-tag>
          </div>
          <p class="project-desc">{{ project.description || '暂无描述' }}</p>
          <div class="project-meta">
            <span class="meta-item">
              <el-icon><Calendar /></el-icon>
              {{ project.start_date || '—' }} → {{ project.end_date || '—' }}
            </span>
            <span class="meta-item">
              <el-icon><User /></el-icon>
              负责人：{{ project.owner?.real_name || project.owner?.username || '—' }}
            </span>
            <span class="meta-item">
              <el-icon><Clock /></el-icon>
              创建于 {{ formatDate(project.created_at) }}
            </span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- ② 用例统计 -->
    <el-card class="section-card" shadow="never" v-loading="loadingStats">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon case-icon"><Document /></el-icon>
          <span>测试用例统计</span>
        </div>
      </template>
      <div class="case-stats">
        <!-- 4 个数字格 -->
        <div class="case-counts">
          <div class="case-count-item total">
            <el-icon class="item-icon"><Files /></el-icon>
            <div class="item-body">
              <span class="item-num">{{ stats.case_statistics.total }}</span>
              <span class="item-label">用例总数</span>
            </div>
          </div>
          <div class="case-count-item functional">
            <el-icon class="item-icon"><Setting /></el-icon>
            <div class="item-body">
              <span class="item-num">{{ stats.case_statistics.by_type?.functional ?? 0 }}</span>
              <span class="item-label">功能用例</span>
              <span class="item-pct">{{ caseTypePct('functional') }}%</span>
            </div>
          </div>
          <div class="case-count-item api">
            <el-icon class="item-icon"><Connection /></el-icon>
            <div class="item-body">
              <span class="item-num">{{ stats.case_statistics.by_type?.api ?? 0 }}</span>
              <span class="item-label">接口用例</span>
              <span class="item-pct">{{ caseTypePct('api') }}%</span>
            </div>
          </div>
          <div class="case-count-item web">
            <el-icon class="item-icon"><Monitor /></el-icon>
            <div class="item-body">
              <span class="item-num">{{ stats.case_statistics.by_type?.web_automation ?? 0 }}</span>
              <span class="item-label">Web用例</span>
              <span class="item-pct">{{ caseTypePct('web_automation') }}%</span>
            </div>
          </div>
          <div class="case-count-item app">
            <el-icon class="item-icon"><Iphone /></el-icon>
            <div class="item-body">
              <span class="item-num">{{ stats.case_statistics.by_type?.app ?? 0 }}</span>
              <span class="item-label">App用例</span>
              <span class="item-pct">{{ caseTypePct('app') }}%</span>
            </div>
          </div>
          <div class="case-count-item perf">
            <el-icon class="item-icon"><Odometer /></el-icon>
            <div class="item-body">
              <span class="item-num">{{ stats.case_statistics.by_type?.perf ?? 0 }}</span>
              <span class="item-label">压测场景</span>
              <span class="item-pct">{{ caseTypePct('perf') }}%</span>
            </div>
          </div>
        </div>

        <!-- 3 条进度率 -->
        <el-divider />
        <div class="case-rates">
          <div class="rate-item">
            <span class="rate-label">
              <el-icon><TrendCharts /></el-icon> 执行率
            </span>
            <el-progress
              :percentage="stats.case_statistics.execution_rate"
              :stroke-width="10"
              color="#409EFF"
              :format="(p: number) => p.toFixed(1) + '%'"
            />
          </div>
          <div class="rate-item">
            <span class="rate-label">
              <el-icon><CircleCheck /></el-icon> 通过率
            </span>
            <el-progress
              :percentage="stats.case_statistics.pass_rate"
              :stroke-width="10"
              :color="passRateColor(stats.case_statistics.pass_rate)"
              :format="(p: number) => p.toFixed(1) + '%'"
            />
          </div>
          <div class="rate-item">
            <span class="rate-label">
              <el-icon><Cpu /></el-icon> 自动化率
            </span>
            <el-progress
              :percentage="stats.case_statistics.automation_rate"
              :stroke-width="10"
              color="#9B59B6"
              :format="(p: number) => p.toFixed(1) + '%'"
            />
          </div>
        </div>
      </div>
    </el-card>

    <!-- ③ Bug 概览 + 项目基础数据 -->
    <div class="two-col">
      <!-- Bug 概览 -->
      <el-card class="section-card" shadow="never" v-loading="loadingStats">
        <template #header>
          <div class="card-header">
            <el-icon class="header-icon bug-icon"><Warning /></el-icon>
            <span>Bug 概览</span>
            <span class="header-sub">
              共 {{ stats.bug_statistics.total }} 个 · 修复率 {{ stats.bug_statistics.resolution_rate.toFixed(1) }}%
            </span>
          </div>
        </template>
        <div class="bug-stats">
          <div
            v-for="s in bugStatusList"
            :key="s.key"
            class="bug-status-row"
            v-show="stats.bug_statistics.total > 0 || true"
          >
            <span class="status-dot" :style="{ background: s.color }"></span>
            <span class="status-name">{{ s.label }}</span>
            <el-progress
              class="status-bar"
              :percentage="bugStatusPct(s.key)"
              :stroke-width="8"
              :color="s.color"
              :show-text="false"
            />
            <span class="status-count">{{ stats.bug_statistics.by_status?.[s.key] ?? 0 }}</span>
            <span class="status-pct">{{ bugStatusPct(s.key) }}%</span>
          </div>
        </div>
      </el-card>

      <!-- 项目基础数据 -->
      <el-card class="section-card" shadow="never" v-loading="loadingDetail">
        <template #header>
          <div class="card-header">
            <el-icon class="header-icon info-icon"><InfoFilled /></el-icon>
            <span>项目基础数据</span>
          </div>
        </template>
        <div class="basic-stats" v-if="project">
          <div class="basic-item">
            <el-icon class="basic-icon members"><Avatar /></el-icon>
            <div class="basic-body">
              <span class="basic-num">{{ project.member_count }}</span>
              <span class="basic-label">项目成员</span>
            </div>
          </div>
          <div class="basic-item">
            <el-icon class="basic-icon modules"><FolderOpened /></el-icon>
            <div class="basic-body">
              <span class="basic-num">{{ project.module_count }}</span>
              <span class="basic-label">功能模块</span>
            </div>
          </div>
          <div class="basic-item">
            <el-icon class="basic-icon bugs"><BrushFilled /></el-icon>
            <div class="basic-body">
              <span class="basic-num">{{ project.bug_count }}</span>
              <span class="basic-label">Bug 总数</span>
            </div>
          </div>
          <div class="basic-item">
            <el-icon class="basic-icon cases"><DocumentChecked /></el-icon>
            <div class="basic-body">
              <span class="basic-num">{{ project.case_count }}</span>
              <span class="basic-label">用例关联</span>
            </div>
          </div>
          <el-divider />
          <div class="time-info">
            <div class="time-row">
              <el-icon><Calendar /></el-icon>
              <span>创建时间：{{ formatDate(project.created_at) }}</span>
            </div>
            <div class="time-row">
              <el-icon><Refresh /></el-icon>
              <span>最近更新：{{ formatRelative(project.updated_at) }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- ④ 测试基础设施 -->
    <el-card class="section-card" shadow="never" v-loading="loadingInfra">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon infra-icon"><Tools /></el-icon>
          <span>测试基础设施</span>
        </div>
      </template>
      <div class="infra-grid">
        <div class="infra-item" @click="navigateTo('environments')">
          <div class="infra-icon-wrap env">
            <el-icon><ChromeFilled /></el-icon>
          </div>
          <div class="infra-body">
            <span class="infra-num">{{ infraCounts.environments }}</span>
            <span class="infra-label">测试环境</span>
          </div>
          <el-button link type="primary" class="infra-link">前往管理 →</el-button>
        </div>
        <div class="infra-item" @click="navigateTo('databases')">
          <div class="infra-icon-wrap db">
            <el-icon><Coin /></el-icon>
          </div>
          <div class="infra-body">
            <span class="infra-num">{{ infraCounts.databases }}</span>
            <span class="infra-label">数据库配置</span>
          </div>
          <el-button link type="primary" class="infra-link">前往管理 →</el-button>
        </div>
        <div class="infra-item" @click="navigateTo('functions')">
          <div class="infra-icon-wrap fn">
            <el-icon><MagicStick /></el-icon>
          </div>
          <div class="infra-body">
            <span class="infra-num">{{ infraCounts.functions }}</span>
            <span class="infra-label">全局函数</span>
          </div>
          <el-button link type="primary" class="infra-link">前往管理 →</el-button>
        </div>
      </div>
    </el-card>

    <!-- ⑤ 图表 -->
    <div class="two-col">
      <!-- 执行趋势折线图 -->
      <el-card class="section-card" shadow="never" v-loading="loadingStats">
        <template #header>
          <div class="card-header">
            <el-icon class="header-icon trend-icon"><TrendCharts /></el-icon>
            <span>用例执行趋势</span>
            <el-radio-group v-model="trendDays" size="small" class="trend-toggle" @change="onTrendDaysChange">
              <el-radio-button :value="7">近7天</el-radio-button>
              <el-radio-button :value="30">近30天</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <div ref="trendChartRef" class="chart-container"></div>
      </el-card>

      <!-- Bug 严重程度饼图 -->
      <el-card class="section-card" shadow="never" v-loading="loadingStats">
        <template #header>
          <div class="card-header">
            <el-icon class="header-icon bug-icon"><PieChart /></el-icon>
            <span>Bug 严重程度分布</span>
          </div>
        </template>
        <div ref="severityChartRef" class="chart-container"></div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as echarts from 'echarts';
import { Avatar, BrushFilled, Calendar, ChromeFilled, CircleCheck, Clock, Coin, Connection, Cpu, Document, DocumentChecked, Files, FolderOpened, InfoFilled, Iphone, MagicStick, Monitor, Odometer, PieChart as PieChartIcon, Refresh, Setting, Tools, TrendCharts, User, Warning, } from '@element-plus/icons-vue';
import { projectApi } from '@/api/projects';
import { environmentApi } from '@/api/environments';
const route = useRoute();
const router = useRouter();
const projectId = computed(() => Number(route.params.id));
// ── 状态 ────────────────────────────────────────────────────
const loadingDetail = ref(false);
const loadingStats = ref(false);
const loadingInfra = ref(false);
const project = ref<any>(null);
const stats = ref({
    case_statistics: {
        total: 0,
        executed: 0,
        passed: 0,
        failed: 0,
        blocked: 0,
        pass_rate: 0,
        execution_rate: 0,
        automation_rate: 0,
        by_type: { functional: 0, app: 0 } as Record<string, number>,
    },
    bug_statistics: {
        total: 0,
        new: 0,
        resolved: 0,
        closed: 0,
        resolution_rate: 0,
        by_severity: {} as Record<string, number>,
        by_status: {} as Record<string, number>,
    },
    execution_trend: [] as Array<{
        date: string;
        count: number;
        passed: number;
        failed: number;
    }>,
    member_statistics: [] as any[],
});
const infraCounts = ref({ environments: 0, databases: 0, functions: 0 });
const trendDays = ref<7 | 30>(7);
// ── 图表 ref ────────────────────────────────────────────────
const trendChartRef = ref<HTMLDivElement>();
const severityChartRef = ref<HTMLDivElement>();
let trendChart: echarts.ECharts | null = null;
let severityChart: echarts.ECharts | null = null;
// ── 辅助常量 ────────────────────────────────────────────────
const bugStatusList = [
    { key: 'new', label: '新建', color: '#409EFF' },
    { key: 'assigned', label: '已指派', color: '#E6A23C' },
    { key: 'in_progress', label: '处理中', color: '#9B59B6' },
    { key: 'resolved', label: '已解决', color: '#67C23A' },
    { key: 'verified', label: '已验证', color: '#00BCD4' },
    { key: 'reopened', label: '重新打开', color: '#F56C6C' },
    { key: 'closed', label: '已关闭', color: '#909399' },
    { key: 'postponed', label: '延期', color: '#FF9800' },
    { key: 'wontfix', label: '不修复', color: '#795548' },
];
const severityColors: Record<string, string> = {
    critical: '#F56C6C',
    major: '#E6A23C',
    moderate: '#F0C040',
    minor: '#409EFF',
    trivial: '#909399',
};
const severityLabels: Record<string, string> = {
    critical: '严重',
    major: '重要',
    moderate: '中等',
    minor: '轻微',
    trivial: '无关紧要',
};
// ── 计算属性 ────────────────────────────────────────────────
function caseTypePct(type: string): string {
    const total = stats.value.case_statistics.total;
    const val = stats.value.case_statistics.by_type?.[type] ?? 0;
    return total ? ((val / total) * 100).toFixed(1) : '0.0';
}
function bugStatusPct(key: string): number {
    const total = stats.value.bug_statistics.total;
    const val = stats.value.bug_statistics.by_status?.[key] ?? 0;
    return total ? Math.round((val / total) * 100) : 0;
}
function passRateColor(rate: number): string {
    if (rate >= 90)
        return '#67C23A';
    if (rate >= 70)
        return '#E6A23C';
    return '#F56C6C';
}
function statusLabel(s: string): string {
    return s === 'active' ? '活跃' : s === 'archived' ? '已归档' : s;
}
function statusTagType(s: string): '' | 'success' | 'info' | 'warning' | 'danger' {
    return s === 'active' ? 'success' : s === 'archived' ? 'info' : 'warning';
}
function formatDate(dt?: string): string {
    if (!dt)
        return '—';
    return dt.substring(0, 10);
}
function formatRelative(dt?: string): string {
    if (!dt)
        return '—';
    const diff = Date.now() - new Date(dt).getTime();
    const h = Math.floor(diff / 3600000);
    if (h < 1)
        return '刚刚';
    if (h < 24)
        return `${h}小时前`;
    const d = Math.floor(h / 24);
    if (d < 30)
        return `${d}天前`;
    return formatDate(dt);
}
// ── 导航 ────────────────────────────────────────────────────
function navigateTo(section: 'environments' | 'databases' | 'functions') {
    const pathMap = {
        environments: `/projects/${projectId.value}/environments`,
        databases: `/projects/${projectId.value}/environments/databases`,
        functions: `/projects/${projectId.value}/environments/functions`,
    };
    router.push(pathMap[section]);
}
// ── 数据加载 ────────────────────────────────────────────────
async function loadProjectDetail() {
    loadingDetail.value = true;
    try {
        const res = await projectApi.getProjectDetail(projectId.value);
        project.value = res.data;
    }
    finally {
        loadingDetail.value = false;
    }
}
async function loadStatistics(days?: number) {
    loadingStats.value = true;
    try {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - ((days ?? trendDays.value) - 1));
        const params = {
            start_date: startDate.toISOString().substring(0, 10),
            end_date: endDate.toISOString().substring(0, 10),
        };
        const res = await projectApi.getProjectStatistics(projectId.value, params);
        if (res.data) {
            stats.value = res.data;
            await nextTick();
            renderTrendChart();
            renderSeverityChart();
        }
    }
    finally {
        loadingStats.value = false;
    }
}
async function loadInfra() {
    loadingInfra.value = true;
    try {
        const [envRes, dbRes, fnRes] = await Promise.all([
            environmentApi.getEnvironmentList(projectId.value),
            environmentApi.getDatabaseList(projectId.value),
            environmentApi.getFunctionList(projectId.value),
        ]);
        infraCounts.value = {
            environments: envRes.data?.length ?? 0,
            databases: dbRes.data?.length ?? 0,
            functions: (fnRes.data?.custom?.length ?? 0) + (fnRes.data?.built_in?.length ?? 0),
        };
    }
    finally {
        loadingInfra.value = false;
    }
}
function onTrendDaysChange(val: 7 | 30) {
    loadStatistics(val);
}
// ── 图表渲染 ────────────────────────────────────────────────
function renderTrendChart() {
    if (!trendChartRef.value)
        return;
    if (!trendChart)
        trendChart = echarts.init(trendChartRef.value);
    const trend = stats.value.execution_trend;
    const dates = trend.map((t) => t.date.substring(5));
    const passed = trend.map((t) => t.passed);
    const failed = trend.map((t) => t.failed);
    trendChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['通过', '失败'], bottom: 0 },
        grid: { left: 40, right: 20, top: 20, bottom: 36 },
        xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', minInterval: 1 },
        series: [
            { name: '通过', type: 'line', data: passed, smooth: true, itemStyle: { color: '#67C23A' }, areaStyle: { opacity: 0.1 } },
            { name: '失败', type: 'line', data: failed, smooth: true, itemStyle: { color: '#F56C6C' }, areaStyle: { opacity: 0.1 } },
        ],
    });
}
function renderSeverityChart() {
    if (!severityChartRef.value)
        return;
    if (!severityChart)
        severityChart = echarts.init(severityChartRef.value);
    const bySev = stats.value.bug_statistics.by_severity;
    const pieData = Object.entries(bySev)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({
        name: severityLabels[k] ?? k,
        value: v,
        itemStyle: { color: severityColors[k] ?? '#ccc' },
    }));
    severityChart.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', right: 10, top: 'center' },
        series: [
            {
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['40%', '50%'],
                data: pieData.length ? pieData : [{ name: '暂无数据', value: 1, itemStyle: { color: '#EBEEF5' } }],
                label: { show: false },
                emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' } },
            },
        ],
    });
}
// ── 生命周期 ────────────────────────────────────────────────
onMounted(async () => {
    await Promise.all([loadProjectDetail(), loadStatistics(), loadInfra()]);
});
watch(projectId, async () => {
    await Promise.all([loadProjectDetail(), loadStatistics(), loadInfra()]);
});
onUnmounted(() => {
    trendChart?.dispose();
    severityChart?.dispose();
});
// 窗口 resize 时重绘
function handleResize() {
    trendChart?.resize();
    severityChart?.resize();
}
window.addEventListener('resize', handleResize);
onUnmounted(() => window.removeEventListener('resize', handleResize));
</script>

<style scoped lang="scss">
.project-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  background: var(--el-fill-color-light);
  min-height: 100%;
}

// ── 通用 card ───────────────────────────────────────────────

.section-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);

  .header-icon {
    font-size: 18px;
  }
  .case-icon { color: var(--el-color-info); }
  .bug-icon  { color: var(--el-color-danger); }
  .info-icon { color: var(--el-color-success); }
  .infra-icon{ color: var(--theme-color-9b59b6); }
  .trend-icon{ color: var(--el-color-info); }

  .header-sub {
    margin-left: auto;
    font-size: 13px;
    font-weight: 400;
    color: var(--el-text-color-secondary);
  }

  .trend-toggle {
    margin-left: auto;
  }
}

// ── ① 项目头部 ──────────────────────────────────────────────

.header-card {
  border-radius: 8px;
}

.project-header {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.project-avatar {
  flex-shrink: 0;

  .avatar-img {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    object-fit: cover;
  }

  .avatar-placeholder {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    background: var(--theme-transparent);
    border: 2px solid var(--el-color-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    font-weight: 700;
    color: var(--el-color-primary);
  }
}

.project-info {
  flex: 1;

  .project-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 8px;

    .project-name {
      font-size: 20px;
      font-weight: 700;
      color: var(--el-text-color-primary);
    }

    .project-code {
      font-size: 13px;
      color: var(--el-text-color-secondary);
      font-family: monospace;
    }

    .status-tag {
      font-size: 12px;
    }
  }

  .project-desc {
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin: 0 0 12px;
    line-height: 1.6;
  }

  .project-meta {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: var(--el-text-color-regular);

      .el-icon {
        color: var(--el-text-color-secondary);
      }
    }
  }
}

// ── ② 用例统计 ──────────────────────────────────────────────

.case-stats {
  .case-counts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
  }

  .case-count-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    border-radius: 8px;
    border: 1px solid var(--el-border-color-lighter);
    transition: box-shadow 0.2s;

    &:hover {
      box-shadow: 0 2px 12px rgba(var(--theme-rgb-black), 0.08);
    }

    &.total    { background: linear-gradient(135deg, var(--theme-color-e8f4ff), var(--theme-info-bg)); }
    &.functional { background: linear-gradient(135deg, var(--theme-color-f0fff4), var(--theme-color-e8fdf0)); }
    &.api      { background: linear-gradient(135deg, var(--theme-color-fff8e6), var(--theme-color-fff3d6)); }
    &.web      { background: linear-gradient(135deg, var(--theme-color-f5f0ff), var(--theme-color-ede8ff)); }
    &.app      { background: linear-gradient(135deg, var(--theme-color-e8f4ff), var(--theme-info-bg)); }
    &.perf     { background: linear-gradient(135deg, var(--theme-color-fff8e6), var(--theme-color-fff3d6)); }

    .item-icon {
      font-size: 32px;
      flex-shrink: 0;
    }

    .total .item-icon    { color: var(--el-color-info); }
    .functional .item-icon { color: var(--el-color-success); }
    .api .item-icon      { color: var(--el-color-warning); }
    .web .item-icon      { color: var(--theme-color-9b59b6); }
    .app .item-icon      { color: var(--el-color-primary); }
    .perf .item-icon     { color: var(--el-color-danger); }

    .item-body {
      display: flex;
      flex-direction: column;

      .item-num {
        font-size: 28px;
        font-weight: 700;
        color: var(--el-text-color-primary);
        line-height: 1;
      }

      .item-label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-top: 4px;
      }

      .item-pct {
        font-size: 12px;
        color: var(--el-text-color-regular);
        margin-top: 2px;
      }
    }
  }

  // 修正图标颜色归属（需在父级）
  .total .item-icon    { color: var(--el-color-info); }
  .functional .item-icon { color: var(--el-color-success); }
  .api .item-icon      { color: var(--el-color-warning); }
  .web .item-icon      { color: var(--theme-color-9b59b6); }
  .app .item-icon      { color: var(--el-color-primary); }
  .perf .item-icon     { color: var(--el-color-danger); }

  .case-rates {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;

    .rate-item {
      .rate-label {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: var(--el-text-color-regular);
        margin-bottom: 8px;
      }
    }
  }
}

// ── ③ 两列布局 ──────────────────────────────────────────────

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

// Bug 状态行
.bug-stats {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bug-status-row {
  display: flex;
  align-items: center;
  gap: 8px;

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-name {
    width: 68px;
    font-size: 13px;
    color: var(--el-text-color-regular);
    flex-shrink: 0;
  }

  .status-bar {
    flex: 1;
  }

  .status-count {
    width: 28px;
    text-align: right;
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .status-pct {
    width: 40px;
    text-align: right;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

// 基础数据
.basic-stats {
  .basic-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 0;
    border-bottom: 1px solid var(--theme-color-f2f6fc);

    &:last-of-type {
      border-bottom: none;
    }

    .basic-icon {
      font-size: 24px;
      width: 40px;
      height: 40px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;

      &.members  { color: var(--el-color-info); background: var(--theme-color-e8f4ff); }
      &.modules  { color: var(--el-color-warning); background: var(--theme-color-fff8e6); }
      &.bugs     { color: var(--el-color-danger); background: var(--theme-danger-bg); }
      &.cases    { color: var(--el-color-success); background: var(--theme-color-f0fff4); }
    }

    .basic-body {
      display: flex;
      flex-direction: column;

      .basic-num   { font-size: 22px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1; }
      .basic-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 3px; }
    }
  }

  .time-info {
    padding-top: 4px;

    .time-row {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--el-text-color-regular);
      padding: 4px 0;

      .el-icon { color: var(--el-text-color-disabled); }
    }
  }
}

// ── ④ 测试基础设施 ──────────────────────────────────────────

.infra-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.infra-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;

  &:hover {
    border-color: var(--el-color-info);
    box-shadow: 0 2px 12px rgba(var(--theme-rgb-64-158-255), 0.15);
  }

  .infra-icon-wrap {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    margin-bottom: 12px;

    &.env { background: var(--theme-color-e8f4ff); color: var(--el-color-info); }
    &.db  { background: var(--theme-color-fff8e6); color: var(--el-color-warning); }
    &.fn  { background: var(--theme-color-f5f0ff); color: var(--theme-color-9b59b6); }
  }

  .infra-body {
    display: flex;
    flex-direction: column;
    margin-bottom: 12px;

    .infra-num   { font-size: 32px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1; }
    .infra-label { font-size: 13px; color: var(--el-text-color-secondary); margin-top: 4px; }
  }

  .infra-link {
    font-size: 12px;
  }
}

// ── ⑤ 图表 ─────────────────────────────────────────────────

.chart-container {
  height: 240px;
  width: 100%;
}

// ── 响应式 ──────────────────────────────────────────────────

@media (max-width: 1024px) {
  .case-counts {
    grid-template-columns: repeat(2, 1fr) !important;
  }

  .two-col {
    grid-template-columns: 1fr !important;
  }

  .infra-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }

  .case-rates {
    grid-template-columns: 1fr !important;
  }
}
</style>
