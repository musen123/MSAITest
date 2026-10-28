<template>
  <div class="celery-monitor-page">
    <AppPageHeader
      title="Worker 节点监控"
      description="实时查看 Agent Worker 节点 运行状态，保障任务处理的稳定与高效性"
      :breadcrumbs="['任务监控中心', 'Worker 监控']"
      icon="i-solar-checklist-bold-duotone"
    >
      <template #actions>
        <div class="mon-toolbar">
          <span class="health" :class="health.tone"><span class="health-dot" />{{ health.text }}</span>
          <div class="tb-refresh">
            <span class="tb-label">自动刷新</span>
            <el-select v-model="intervalMs" size="small" style="width: 92px">
              <el-option label="关闭" :value="0" />
              <el-option label="5 秒" :value="5000" />
              <el-option label="10 秒" :value="10000" />
              <el-option label="30 秒" :value="30000" />
            </el-select>
          </div>
          <span class="upd">更新时间：{{ updatedAt }}</span>
          <el-button size="small" :loading="loading" @click="refresh(true)">
            <i class="i-solar-refresh-linear btn-icon-sm" />刷新
          </el-button>
        </div>
      </template>
    </AppPageHeader>

    <!-- 告警条 -->
    <div v-if="bannerText" class="banner">
      <i class="i-solar-danger-triangle-bold b-icon" /><span v-html="bannerText" />
    </div>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div v-for="k in kpis" :key="k.label" class="kpi-card" :class="k.tone">
        <div class="kpi-icon"><i :class="k.icon" /></div>
        <div class="kpi-body">
          <div class="kpi-num">{{ k.value }}</div>
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-sub">{{ k.sub }}</div>
        </div>
      </div>
    </div>

    <!-- 主体：左（队列 + 实时指标 + Beat）｜ 右（Worker 独占全高） -->
    <div class="main-grid">
      <div class="main-left">
        <div class="left-top">
          <!-- 消息队列 -->
          <div class="panel">
            <div class="panel-head"><span class="panel-title">消息队列 <span class="muted">({{ queues.length }})</span></span></div>
            <el-table :data="queues" size="small" class="flat-table">
              <el-table-column label="队列名称" min-width="150">
                <template #default="{ row }">
                  <div class="qt-name"><span class="qt-dot" :class="`d-${row.level}`" /><code>{{ row.name }}</code></div>
                  <div class="qt-desc">{{ queueDesc(row.name) }}</div>
                </template>
              </el-table-column>
              <el-table-column label="积压" width="64" align="center">
                <template #default="{ row }"><span :class="{ bad: row.backlog > 0 && !row.has_worker }">{{ row.backlog }}</span></template>
              </el-table-column>
              <el-table-column label="消费" width="64" align="center" prop="worker_count" />
              <el-table-column label="状态" width="88" align="center">
                <template #default="{ row }">
                  <el-tag size="small" :type="queueTagType(row.level)" class="status-tag">{{ queueLabel(row) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 实时指标 + 最近告警 -->
          <div class="panel">
            <div class="panel-head"><span class="panel-title">实时指标</span></div>
            <div ref="chartRef" class="chart-box" />
            <div class="alerts">
              <div class="alerts-head">最近告警</div>
              <div v-if="alertQueues.length" class="alerts-list">
                <div v-for="q in alertQueues" :key="q.name" class="alert-item">
                  <i class="i-solar-danger-triangle-bold ai-ico" />
                  <div><div class="ai-t">队列 {{ q.name }} 无人消费</div><div class="ai-d">{{ q.backlog }} 条任务积压，请启动对应 worker</div></div>
                </div>
              </div>
              <div v-else class="alerts-empty">
                <i class="i-solar-bell-off-linear ae-ico" />
                <div><div class="ae-t">暂无告警</div><div class="ae-d">一切正常，继续保持 👍</div></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 定时计划（Beat） -->
        <div class="panel">
          <div class="panel-head"><span class="panel-title">定时计划（Beat）<span class="muted">({{ beat.length }})</span></span></div>
          <el-table :data="beat" size="small" class="flat-table">
            <el-table-column label="任务名称" min-width="190">
              <template #default="{ row }">
                <div class="bt-name">{{ beatMeta(row.name).title }}</div>
                <div class="bt-desc">{{ beatMeta(row.name).desc }}</div>
              </template>
            </el-table-column>
            <el-table-column label="任务路径" min-width="200"><template #default="{ row }"><code class="mono">{{ row.task }}</code></template></el-table-column>
            <el-table-column label="执行周期" width="140"><template #default="{ row }"><span class="mono">{{ formatSchedule(row.schedule) }}</span></template></el-table-column>
            <el-table-column label="状态" width="80" align="center"><template #default><el-tag size="small" type="success" class="status-tag">已启用</el-tag></template></el-table-column>
          </el-table>
        </div>
      </div>

      <!-- Worker 节点（独占右侧，全高） -->
      <div class="main-right">
        <div class="panel worker-panel">
          <div class="panel-head"><span class="panel-title">Worker 节点 <span class="muted">({{ workers.length }})</span></span></div>
          <div v-if="workers.length" class="panel-scroll">
            <div v-for="w in workers" :key="w.name" class="worker-card">
              <div class="wc-head">
                <span class="wc-dot-wrap" :class="{ online: w.alive }"><span class="wc-dot" /></span>
                <div class="wc-id"><code class="wc-name">{{ w.name }}</code><div class="wc-role">{{ workerRole(w) }}</div></div>
                <span class="wc-badge" :class="w.alive ? 'ok' : 'off'">{{ w.alive ? '在线' : '离线' }}</span>
              </div>
              <div class="wc-stats">
                <div class="wc-stat"><div class="wc-sn">{{ w.concurrency }}</div><div class="wc-sl">并发</div></div>
                <div class="wc-stat"><div class="wc-sn">{{ w.processed }}</div><div class="wc-sl">已处理</div></div>
                <div class="wc-stat"><div class="wc-sn">{{ w.active }}</div><div class="wc-sl">正在跑</div></div>
                <div class="wc-stat"><div class="wc-sn">{{ formatMem(w.mem_rss_kb) }}</div><div class="wc-sl">内存</div></div>
              </div>
              <div class="wc-util">
                <div class="wc-util-head"><span>负载 {{ w.active }} / {{ w.concurrency }}</span><span :class="`u-${utilTone(w)}`">{{ utilPct(w) }}%</span></div>
                <div class="wc-bar"><div class="wc-fill" :class="utilTone(w)" :style="{ width: utilPct(w) + '%' }" /></div>
              </div>
              <div class="wc-queues">
                <el-tag v-for="q in w.queues" :key="q" size="small" effect="plain" class="wc-qtag">{{ q }}</el-tag>
              </div>
            </div>
          </div>
          <div v-else class="mini-empty"><i class="i-solar-server-square-linear" /><span>无 worker 在线</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">/**
 * Celery Worker 监控仪表盘（系统级权限 system:monitor）。
 * 布局：KPI 卡 + 左（队列表 / 实时折线+告警 / Beat 表）+ 右（Worker 节点独占全高）。
 * 原生 inspect + broker LLEN 快照，自动刷新可调；实时折线由前端累积历史快照绘制。
 */
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { AppPageHeader } from '@/components/common';
import { useThemeStore } from '@/stores/theme';
import { systemApi, type CeleryMonitor, type CeleryQueue, type CeleryWorker, } from '@/api/system';
const themeStore = useThemeStore();
const QUEUE_META: Record<string, string> = {
    ai_tasks: 'AI 用例生成、文档解析和知识库任务',
    app_tasks: 'App 自动化执行独立队列',
    app_tasks: '真机 App 用例执行，长时持有设备的 RPC'
};
const QUEUE_ROLE: Record<string, string> = {
    ai_tasks: 'AI 生成 / 执行',
    app_tasks: 'App 自动化',
    app_tasks: 'App 自动化'
};
const BEAT_META: Record<string, {
    title: string;
    desc: string;
}> = {
    'reap-zombie-ai-tasks': { title: '僵尸任务回收', desc: '回收 worker 崩溃遗留的 running / 投递丢失的 pending' },
    'archive-ai-task-events': { title: '事件流归档', desc: '导出超保留期任务的事件流并清理数据库' },
    'dispatch-scheduled-jobs': { title: '定时计划派发', desc: '扫描到期的定时计划并投递执行' },
};
const data = ref<CeleryMonitor | null>(null);
const loading = ref(false);
const intervalMs = ref(5000);
let timer: ReturnType<typeof setInterval> | null = null;
const summary = computed(() => data.value?.summary || { workers_online: 0, total_concurrency: 0, total_backlog: 0, active_tasks: 0, alerts: 0 });
const queues = computed(() => data.value?.queues || []);
const workers = computed(() => data.value?.workers || []);
const beat = computed(() => data.value?.beat_jobs || []);
const alertQueues = computed(() => queues.value.filter((q) => q.level === 'danger'));
const kpis = computed(() => {
    const s = summary.value;
    return [
        { label: '在线 Worker', value: s.workers_online, sub: `共 ${workers.value.length} 个节点`, icon: 'i-solar-server-2-bold-duotone', tone: s.workers_online > 0 ? 'ok' : 'danger' },
        { label: '总并发', value: s.total_concurrency, sub: '并行执行槽', icon: 'i-solar-cpu-bolt-bold-duotone', tone: 'accent' },
        { label: '队列积压', value: s.total_backlog, sub: '待处理任务', icon: 'i-solar-layers-minimalistic-bold-duotone', tone: s.total_backlog > 0 ? 'warn' : 'neutral' },
        { label: '正在执行', value: s.active_tasks, sub: '活跃任务', icon: 'i-solar-play-circle-bold-duotone', tone: 'neutral' },
        { label: '告警', value: s.alerts, sub: '当前快照', icon: 'i-solar-danger-triangle-bold-duotone', tone: s.alerts > 0 ? 'danger' : 'neutral' },
    ];
});
const health = computed(() => {
    if (data.value?.degraded)
        return { tone: 'danger', text: '无 Worker 在线' };
    if (summary.value.alerts > 0)
        return { tone: 'danger', text: `${summary.value.alerts} 个队列告警` };
    return { tone: 'ok', text: '运行正常' };
});
const bannerText = computed(() => {
    if (data.value?.degraded)
        return '当前<strong>无 worker 在线</strong>：AI 生成 / 执行 / 压测 / App 任务都会堆积不跑，请启动对应队列的 Celery worker。';
    if (alertQueues.value.length)
        return `<strong>${alertQueues.value.length}</strong> 个队列有积压却无人消费：<strong>${alertQueues.value.map((q) => q.name).join('、')}</strong> —— 任务会永远 pending。`;
    return '';
});
const updatedAt = computed(() => {
    if (!data.value?.inspected_at)
        return '-';
    const d = new Date(data.value.inspected_at);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
});
// ==================== 实时折线（前端累积快照）====================
const chartRef = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;
const buffer = ref<{
    t: string;
    c: number;
    a: number;
}[]>([]);
const axisColor = () => (themeStore.isDark ? '#9CA3AF' : '#6B7280');
const splitColor = () => (themeStore.isDark ? '#2b2b2f' : '#eef0f2');
const renderChart = () => {
    if (!chart)
        return;
    const b = buffer.value;
    chart.setOption({
        grid: { left: 6, right: 10, top: 28, bottom: 4, containLabel: true },
        legend: { data: ['并发数', '正在执行'], right: 0, top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, itemGap: 12, textStyle: { color: axisColor(), fontSize: 11 } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', boundaryGap: false, data: b.map((x) => x.t), axisLabel: { color: axisColor(), fontSize: 10 }, axisLine: { lineStyle: { color: splitColor() } }, axisTick: { show: false } },
        yAxis: { type: 'value', minInterval: 1, axisLabel: { color: axisColor(), fontSize: 10 }, splitLine: { lineStyle: { color: splitColor(), type: 'dashed' } } },
        series: [
            { name: '并发数', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, data: b.map((x) => x.c), itemStyle: { color: '#22c55e' }, lineStyle: { color: '#22c55e', width: 2 }, areaStyle: { color: 'rgba(34,197,94,0.08)' } },
            { name: '正在执行', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, data: b.map((x) => x.a), itemStyle: { color: '#3b82f6' }, lineStyle: { color: '#3b82f6', width: 2 } },
        ],
    });
};
const refresh = async (force = false) => {
    loading.value = true;
    try {
        const res = await systemApi.getCeleryMonitor(force);
        data.value = res.data as CeleryMonitor;
        const d = new Date();
        const pad = (n: number) => String(n).padStart(2, '0');
        buffer.value.push({ t: `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`, c: summary.value.total_concurrency, a: summary.value.active_tasks });
        if (buffer.value.length > 20)
            buffer.value.shift();
        renderChart();
    }
    catch (error) {
        console.error('获取 worker 监控失败:', error);
    }
    finally {
        loading.value = false;
    }
};
const stopTimer = () => { if (timer) {
    clearInterval(timer);
    timer = null;
} };
const resetTimer = () => { stopTimer(); if (intervalMs.value > 0)
    timer = setInterval(() => refresh(), intervalMs.value); };
watch(intervalMs, resetTimer);
// ==================== 展示辅助 ====================
const queueLabel = (q: CeleryQueue) => (q.level === 'danger' ? '无人消费' : q.level === 'warn' ? '无 worker' : '正常');
const queueTagType = (level: string) => (({ ok: 'success', warn: 'warning', danger: 'danger' } as Record<string, string>)[level] || 'info') as 'success' | 'warning' | 'danger' | 'info';
const queueDesc = (name: string) => QUEUE_META[name] || '自定义任务队列';
const workerRole = (w: CeleryWorker) => {
    const roles = [...new Set(w.queues.map((q) => QUEUE_ROLE[q]).filter(Boolean))];
    return roles.length ? `处理：${roles.join(' · ')}` : '通用任务处理';
};
const beatMeta = (name: string) => BEAT_META[name] || { title: name, desc: '周期任务' };
const utilPct = (w: CeleryWorker) => (w.concurrency > 0 ? Math.min(100, Math.round((w.active / w.concurrency) * 100)) : 0);
const utilTone = (w: CeleryWorker) => { const p = utilPct(w); return p >= 90 ? 'hot' : p >= 60 ? 'busy' : 'idle'; };
const formatMem = (v: number) => { if (!v)
    return '-'; const mb = v > 10000000 ? v / 1048576 : v / 1024; return `${mb.toFixed(0)}MB`; };
const formatSchedule = (s: string) => {
    const n = Number(s);
    if (!isNaN(n))
        return `每 ${Math.round(n)} 秒`;
    const m = /<crontab:\s*([^\s]+\s+[^\s]+\s+[^\s]+\s+[^\s]+\s+[^\s]+)/.exec(s);
    return m ? `cron ${m[1]}` : s;
};
const onResize = () => chart?.resize();
onMounted(async () => {
    await nextTick();
    if (chartRef.value)
        chart = echarts.init(chartRef.value);
    window.addEventListener('resize', onResize);
    await refresh(true);
    resetTimer();
});
onBeforeUnmount(() => {
    stopTimer();
    window.removeEventListener('resize', onResize);
    chart?.dispose();
    chart = null;
});
</script>

<style scoped lang="scss">
.celery-monitor-page {
  min-height: calc(100vh - 100px);
  padding-bottom: 24px;
}

// ==================== 头部工具条 ====================
.mon-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;

  .health {
    display: inline-flex; align-items: center; gap: 7px;
    font-size: 13px; font-weight: 500; padding: 5px 13px; border-radius: 20px;
    .health-dot { width: 7px; height: 7px; border-radius: 50%; }
    &.ok { color: var(--el-color-success); background: var(--theme-color-f0f9eb); .health-dot { background: var(--el-color-success); } }
    &.danger { color: var(--el-color-danger); background: var(--theme-danger-bg); .health-dot { background: var(--el-color-danger); } }
  }
  .tb-refresh { display: inline-flex; align-items: center; gap: 8px; }
  .tb-label { font-size: 13px; color: var(--el-text-color-secondary); }
  .upd { font-size: 12.5px; color: var(--el-text-color-placeholder); }
  .btn-icon-sm { margin-right: 4px; }
}

// ==================== 告警条 ====================
.banner {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; border-radius: 12px; margin-bottom: 18px; font-size: 13.5px;
  background: var(--theme-danger-bg); border: 1px solid var(--el-color-danger-light-7); color: var(--el-color-danger);
  .b-icon { font-size: 18px; flex-shrink: 0; }
  :deep(strong) { font-weight: 600; }
}

// ==================== KPI ====================
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 18px; }
.kpi-card {
  display: flex; align-items: center; gap: 14px; padding: 18px 20px;
  background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 12px;
  transition: box-shadow 0.2s, transform 0.2s;
  &:hover { box-shadow: 0 4px 16px rgba(var(--theme-rgb-black), 0.06); transform: translateY(-1px); }
  .kpi-icon { width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; flex-shrink: 0; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); }
  .kpi-num { font-size: 26px; font-weight: 700; line-height: 1.1; color: var(--el-text-color-primary); }
  .kpi-label { font-size: 12.5px; color: var(--el-text-color-secondary); margin-top: 2px; }
  .kpi-sub { font-size: 11.5px; color: var(--el-text-color-placeholder); margin-top: 1px; }
  &.ok .kpi-icon { color: var(--el-color-success); background: var(--theme-color-f0f9eb); }
  &.accent .kpi-icon { color: var(--el-color-primary); background: var(--theme-color-ecf5ff); }
  &.warn .kpi-icon { color: var(--el-color-warning); background: var(--theme-warning-bg); } &.warn .kpi-num { color: var(--el-color-warning); }
  &.danger .kpi-icon { color: var(--el-color-danger); background: var(--theme-danger-bg); } &.danger .kpi-num { color: var(--el-color-danger); }
}

// ==================== 主体两栏：左内容 / 右 Worker 独占全高 ====================
.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}
@media (max-width: 1180px) { .main-grid { grid-template-columns: 1fr; } }
.main-left { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.left-top { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
.main-right { display: flex; min-width: 0; }
.worker-panel { flex: 1; }

// ==================== 面板通用 ====================
.panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
}
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.panel-title { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); .muted { color: var(--el-text-color-placeholder); font-weight: 400; font-size: 13px; } }
.panel-scroll { flex: 1; overflow-y: auto; }
.mono { font-family: 'SFMono-Regular', Consolas, Menlo, monospace; font-size: 12px; color: var(--el-text-color-regular); }

:deep(.flat-table) {
  --el-table-border-color: var(--el-border-color-lighter);
  th.el-table__cell { background: transparent; font-weight: 500; color: var(--el-text-color-secondary); }
  .el-table__cell { padding: 8px 0; }
}
.qt-name { display: flex; align-items: center; gap: 6px; }
.qt-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; &.d-ok { background: var(--el-color-success); } &.d-warn { background: var(--el-color-warning); } &.d-danger { background: var(--el-color-danger); } }
.qt-name code { font-family: 'SFMono-Regular', Consolas, Menlo, monospace; font-size: 12.5px; font-weight: 600; color: var(--el-text-color-primary); }
.qt-desc { font-size: 11.5px; color: var(--el-text-color-secondary); margin-top: 2px; line-height: 1.4; }
.bad { color: var(--el-color-danger); font-weight: 700; }
.bt-name { font-size: 13px; font-weight: 500; color: var(--el-text-color-primary); }
.bt-desc { font-size: 11.5px; color: var(--el-text-color-secondary); margin-top: 2px; }

// ==================== Worker 卡 ====================
.worker-card { padding: 12px 14px; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; margin-bottom: 10px; &:last-child { margin-bottom: 0; }
  .wc-head { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 10px; }
  .wc-dot-wrap { position: relative; width: 8px; height: 8px; flex-shrink: 0; margin-top: 4px;
    .wc-dot { position: absolute; inset: 0; border-radius: 50%; background: var(--el-text-color-placeholder); }
    &.online .wc-dot { background: var(--el-color-success); }
    &.online::after { content: ''; position: absolute; inset: 0; border-radius: 50%; background: var(--el-color-success); animation: ping 1.8s cubic-bezier(0, 0, 0.2, 1) infinite; }
  }
  .wc-id { flex: 1; min-width: 0; }
  .wc-name { display: block; font-family: 'SFMono-Regular', Consolas, Menlo, monospace; font-size: 12.5px; font-weight: 600; color: var(--el-text-color-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .wc-role { margin-top: 2px; font-size: 11.5px; color: var(--el-text-color-secondary); }
  .wc-badge { font-size: 11px; padding: 1px 8px; border-radius: 20px; flex-shrink: 0; &.ok { color: var(--el-color-success); background: var(--theme-color-f0f9eb); } &.off { color: var(--el-text-color-secondary); background: var(--el-fill-color-light); } }
  .wc-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px 0; border-top: 1px solid var(--el-border-color-lighter); border-bottom: 1px solid var(--el-border-color-lighter);
    .wc-stat { text-align: center; } .wc-sn { font-size: 16px; font-weight: 700; color: var(--el-text-color-primary); } .wc-sl { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 1px; }
  }
  .wc-util { margin-top: 10px;
    .wc-util-head { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--el-text-color-secondary); margin-bottom: 5px; .u-idle { color: var(--el-color-success); } .u-busy { color: var(--el-color-warning); } .u-hot { color: var(--el-color-danger); } }
    .wc-bar { height: 5px; border-radius: 6px; background: var(--el-fill-color-light); overflow: hidden; } .wc-fill { height: 100%; border-radius: 6px; transition: width 0.4s; &.idle { background: var(--el-color-success); } &.busy { background: var(--el-color-warning); } &.hot { background: var(--el-color-danger); } }
  }
  .wc-queues { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 5px; }
  :deep(.wc-qtag) { font-family: 'SFMono-Regular', Consolas, Menlo, monospace; }
}
@keyframes ping { 0% { transform: scale(1); opacity: 0.5; } 100% { transform: scale(2.8); opacity: 0; } }
.mini-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 30px 10px; color: var(--el-text-color-placeholder); i { font-size: 30px; margin-bottom: 6px; } }

// ==================== 图表 + 告警 ====================
.chart-box { width: 100%; height: 176px; }
.alerts { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); }
.alerts-head { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); margin-bottom: 10px; }
.alert-item { display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px; border-radius: 8px; background: var(--theme-danger-bg); margin-bottom: 8px;
  .ai-ico { color: var(--el-color-danger); font-size: 16px; margin-top: 1px; } .ai-t { font-size: 12.5px; font-weight: 500; color: var(--el-color-danger); } .ai-d { font-size: 11.5px; color: var(--el-color-danger); margin-top: 1px; }
}
.alerts-empty { display: flex; align-items: center; gap: 10px; padding: 14px; border-radius: 8px; background: var(--el-fill-color-light);
  .ae-ico { font-size: 22px; color: var(--el-color-success); } .ae-t { font-size: 12.5px; font-weight: 500; color: var(--el-text-color-primary); } .ae-d { font-size: 11.5px; color: var(--el-text-color-secondary); margin-top: 1px; }
}
</style>
