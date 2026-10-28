<template>
  <div class="report-page">
    <AppPageHeader
      title="AI 提效"
      description="任务量 · 生成质量 · 节省工时"
      icon="i-app-ai-agent"
      :illustration="illustAi"
    >
      <template #actions>
        <el-radio-group v-model="days" size="small">
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
      </template>
    </AppPageHeader>

    <!-- 左 6 迷你卡 + 右紫色英雄卡(节省工时) -->
    <div class="ai-stat-zone" v-loading="loading">
      <div class="ai-side-grid">
        <AppStatCardMini
          label="AI 任务总数" chart="bars" :value="c.total.value" icon="i-solar-cpu-bolt-bold"
          color="purple" :note="trendNote(c.total.trend)" :note-type="trendType(c.total.trend)" />
        <AppStatCardMini
          label="任务成功率" chart="gauge" :value="c.success_rate ?? 0" suffix="%"
          icon="i-solar-check-circle-bold" color="success"
          :note="c.success_rate == null ? '暂无完成任务' : ''" />
        <AppStatCardMini
          label="AI 生成用例" chart="bars" :value="c.ai_cases.value" icon="i-solar-cpu-bolt-bold"
          color="purple" :note="c.ai_cases.pct != null ? `占功能用例 ${c.ai_cases.pct}%` : ''" />
        <AppStatCardMini
          label="AI 用例评审通过率" chart="gauge" :value="c.ai_review_pass ?? 0" suffix="%"
          icon="i-solar-shield-check-bold" color="success"
          :note="c.ai_review_pass == null ? '暂无数据' : ''" />
        
        
      </div>
      <div class="ai-hero">
        <div class="hero-glow" />
        <div class="hero-label">
          <i class="i-solar-hourglass-bold" />
          估算节省工时
        </div>
        <div class="hero-num">
          {{ c.saved_hours }}<small>小时</small>
        </div>
        <div class="hero-rows">
          <div v-for="s in heroSaved" :key="s.label" class="hero-row">
            <span class="hr-label">{{ s.label }}</span>
            <span class="hr-val">{{ s.hours }}h</span>
          </div>
        </div>
        <div class="hero-foot">
          平均每任务 {{ c.avg_duration_min ?? '-' }} 分钟 · 估算口径见下方
        </div>
      </div>
    </div>

    <div class="grid-2">
      <AppSectionCard title="AI 任务量趋势" class="panel">
        <v-chart :option="trendOption" class="chart-md" autoresize />
      </AppSectionCard>
      <AppSectionCard title="任务类型分布" class="panel">
        <div class="pie-row">
          <v-chart :option="typePieOption" class="chart-pie" autoresize />
          <ul class="pie-legend">
            <li v-for="(t, i) in topTypes" :key="t.type">
              <span class="dot" :style="{ background: TYPE_COLORS[i % TYPE_COLORS.length] }" />
              <span class="lg-label">{{ aiTaskTypeLabel(t.type) }}</span>
              <span class="lg-num">{{ t.count }}</span>
            </li>
          </ul>
        </div>
      </AppSectionCard>
    </div>

    <div class="grid-3">
      <AppSectionCard title="AI vs 手工创建用例" class="panel">
        <v-chart :option="vsOption" class="chart-sm" autoresize />
        <div class="panel-note">{{ vsNote }}</div>
      </AppSectionCard>
      <AppSectionCard title="各类型成功率" class="panel">
        <div class="bar-list">
          <div v-for="t in topTypes" :key="t.type" class="bar-row">
            <span class="bar-label">{{ aiTaskTypeLabel(t.type) }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{
                  width: (t.success_rate ?? 0) + '%',
                  background: (t.success_rate ?? 0) >= 90 ? 'var(--color-success-500)' : 'var(--color-warning-500)',
                }"
              />
            </div>
            <span class="bar-num">{{ t.success_rate ?? '-' }}%</span>
          </div>
        </div>
      </AppSectionCard>
      <AppSectionCard title="节省工时构成" class="panel">
        <template #extra><span class="muted-tag">估算</span></template>
        <div v-if="savedRows.length" class="saved-list">
          <div v-for="s in savedRows" :key="s.key" class="saved-row">
            <span class="saved-label">{{ s.label }}</span>
            <span class="saved-rate">×{{ s.count }} · {{ s.rate }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: s.pct + '%', background: 'var(--color-purple-500)' }" />
            </div>
            <span class="bar-num">{{ s.hours }}h</span>
          </div>
        </div>
        <div v-else class="panel-empty">暂无 AI 产出</div>
        <div class="panel-note">{{ data?.saved_rule || '' }}</div>
      </AppSectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">import { computed, onMounted, ref, watch } from 'vue';
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace';
import { AppPageHeader, AppSectionCard, AppStatCardMini } from '@/components/common';
import { reportCenterApi, aiTaskTypeLabel } from '@/api/report-center';
import type { AiReportData } from '@/api/report-center';
import illustAi from '@/assets/illustrations/ai-agent.svg';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent]);
const workspaceStore = useProjectWorkspaceStore();
const projectId = computed(() => workspaceStore.currentProject?.id || 0);
const loading = ref(false);
const days = ref(30);
const data = ref<AiReportData | null>(null);
const fetch = async () => {
    if (!projectId.value)
        return;
    loading.value = true;
    try {
        const res = await reportCenterApi.aiEfficiency(projectId.value, days.value);
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
    total: { value: 0, trend: null },
    success_rate: null,
    ai_cases: { value: 0, pct: null },
    ai_review_pass: null,
    avg_duration_min: null,
    saved_hours: 0
});
function trendNote(t: number | null | undefined): string {
    if (t == null)
        return '';
    return `较上期 ${t > 0 ? '↑' : t < 0 ? '↓' : ''}${Math.abs(t)}%`;
}
function trendType(t: number | null | undefined): 'success' | 'danger' | 'muted' {
    if (t == null || t === 0)
        return 'muted';
    return t > 0 ? 'success' : 'danger';
}
const TYPE_COLORS = ['#8B5CF6', '#00B96B', '#3B82F6', '#06B6D4', '#F59E0B', '#EC4899', '#9CA3AF'];
const topTypes = computed(() => (data.value?.type_dist || []).slice(0, 6));
const trendOption = computed(() => {
    const daily = data.value?.trend || [];
    const dates = daily.map((d) => d.date.slice(5));
    return {
        tooltip: { trigger: 'axis' },
        legend: { data: ['任务数', '成功数'], top: 0, right: 0, icon: 'circle', textStyle: { fontSize: 11, color: '#6B7280' } },
        grid: { left: 0, right: 8, top: 28, bottom: 0, containLabel: true },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#9CA3AF', fontSize: 10 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#EEF1F4' } } },
        yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } }, axisLabel: { color: '#9CA3AF', fontSize: 10 } },
        series: [
            { name: '任务数', type: 'bar', data: daily.map((d) => d.count), itemStyle: { color: '#8B5CF6', borderRadius: [2, 2, 0, 0] }, barMaxWidth: 14 },
            { name: '成功数', type: 'line', smooth: true, symbol: 'none', data: daily.map((d) => d.succeeded), lineStyle: { color: '#00B96B', width: 2 } },
        ],
    };
});
const typePieOption = computed(() => {
    const items = topTypes.value
        .filter((t) => t.count > 0)
        .map((t, i) => ({
        name: aiTaskTypeLabel(t.type),
        value: t.count,
        itemStyle: { color: TYPE_COLORS[i % TYPE_COLORS.length] },
    }));
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
const vsOption = computed(() => {
    const weeks = data.value?.ai_vs_manual || [];
    return {
        tooltip: { trigger: 'axis' },
        legend: { data: ['AI 生成', '手工'], top: 0, right: 0, icon: 'circle', textStyle: { fontSize: 11, color: '#6B7280' } },
        grid: { left: 0, right: 8, top: 28, bottom: 0, containLabel: true },
        xAxis: { type: 'category', data: weeks.map((w) => w.week), axisLabel: { color: '#9CA3AF', fontSize: 10 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#EEF1F4' } } },
        yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } }, axisLabel: { color: '#9CA3AF', fontSize: 10 } },
        series: [
            { name: 'AI 生成', type: 'bar', data: weeks.map((w) => w.ai), itemStyle: { color: '#8B5CF6', borderRadius: [2, 2, 0, 0] }, barMaxWidth: 16 },
            { name: '手工', type: 'bar', data: weeks.map((w) => w.manual), itemStyle: { color: '#D1D5DB', borderRadius: [2, 2, 0, 0] }, barMaxWidth: 16 },
        ],
    };
});
const vsNote = computed(() => {
    const weeks = data.value?.ai_vs_manual || [];
    const last = weeks[weeks.length - 1];
    if (!last || last.ai + last.manual === 0)
        return '本周暂无新增用例';
    const pct = Math.round((last.ai / (last.ai + last.manual)) * 100);
    return `本周 AI 生成占比 ${pct}%`;
});
/** 构成明细:只展示有贡献的项,按节省量降序 */
const savedRows = computed(() => {
    const bd = data.value?.saved_breakdown || [];
    const items = bd
        .filter((v) => v.count > 0)
        .map((v) => ({
        key: v.key,
        label: v.label,
        rate: `${v.unit_minutes}分/${v.unit}`,
        count: v.count,
        hours: Math.round((v.minutes / 60) * 10) / 10,
        minutes: v.minutes,
    }))
        .sort((a, b) => b.minutes - a.minutes);
    const max = Math.max(...items.map((i) => i.minutes), 1);
    return items.map((i) => ({ ...i, pct: Math.round((i.minutes / max) * 100) }));
});
/** 英雄卡里的构成简列 */
const heroSaved = computed(() => savedRows.value.slice(0, 4));
</script>

<style scoped lang="scss">
@use './report-shared';

/* 节省工时构成(带费率列) */
.saved-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.saved-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
}
.saved-label {
  width: 84px;
  flex-shrink: 0;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.saved-rate {
  width: 82px;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text-placeholder);
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 本页特色:左 6 迷你卡 + 右紫色英雄卡 */
.ai-stat-zone {
  display: grid;
  grid-template-columns: 2.2fr 1fr;
  gap: var(--space-3);
}
@media (max-width: 1100px) {
  .ai-stat-zone {
    grid-template-columns: 1fr;
  }
}

.ai-side-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}
@media (max-width: 900px) {
  .ai-side-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.ai-hero {
  position: relative;
  overflow: hidden;
  background: var(--color-purple-50);
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
}
.hero-glow {
  position: absolute;
  right: -30px;
  bottom: -30px;
  width: 130px;
  height: 130px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.18), transparent 70%);
  pointer-events: none;
}
.hero-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-purple-600);

  i { font-size: 16px; }
}
.hero-num {
  margin-top: var(--space-2);
  font-size: 38px;
  line-height: 1.1;
  font-weight: var(--font-weight-bold);
  color: var(--color-purple-600);
  font-variant-numeric: tabular-nums;

  small {
    font-size: var(--font-size-sm);
    font-weight: 400;
    margin-left: 4px;
  }
}
.hero-rows {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hero-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
  color: var(--color-purple-600);
}
.hr-val {
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
}
.hero-foot {
  margin-top: auto;
  padding-top: var(--space-3);
  font-size: 10px;
  color: var(--color-purple-500);
  opacity: 0.85;
}
</style>
