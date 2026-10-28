<template>
  <div class="ai-task-detail" :data-status="status">
    <!-- ============ 顶部 ============ -->
    <div class="detail-header">
      <div class="header-main">
        <div class="bread">
          <span>AI 中心</span>
          <i class="i-solar-alt-arrow-right-linear sep" />
          <span>任务详情</span>
        </div>
        <h1 class="title">{{ task?.title || 'AI 任务详情' }}</h1>
        <div class="meta-row">
          <span class="type-chip" :class="`tc-${tMeta.color}`">
            <i :class="tMeta.icon" />
            {{ tMeta.label }}
          </span>
          <span class="meta-sep">·</span>
          <span class="meta-text">#{{ taskId }}</span>
          <span v-if="task?.celery_task_id" class="meta-sep">·</span>
          <span v-if="task?.celery_task_id" class="meta-text mono" :title="task.celery_task_id">
            <i class="i-solar-server-square-linear" />
            {{ shortId(task.celery_task_id) }}
          </span>
          <span v-if="task?.biz_ref_id" class="meta-sep">·</span>
          <span v-if="task?.biz_ref_id" class="meta-text">
            <i class="i-solar-link-round-bold" />
            业务引用 #{{ task.biz_ref_id }}
          </span>
        </div>
      </div>
      <div class="header-actions">
        <el-button @click="goBack">
          <i class="i-solar-alt-arrow-left-linear btn-icon" />返回
        </el-button>
        <el-popconfirm
          v-if="isActive"
          v-permission="'ai_task:manage'"
          title="确定取消此任务？取消后无法恢复。"
          confirm-button-text="确认取消"
          cancel-button-text="再想想"
          @confirm="handleCancel"
        >
          <template #reference>
            <el-button type="warning" plain :loading="canceling">
              <i class="i-solar-close-circle-bold btn-icon" />取消任务
            </el-button>
          </template>
        </el-popconfirm>
        <el-button
          v-if="isFailed || isCanceled"
          v-permission="'ai_task:manage'"
          type="primary"
          @click="handleRetry"
        >
          <i class="i-solar-refresh-bold btn-icon" />重试
        </el-button>
        <el-popconfirm
          v-if="!isActive"
          v-permission="'ai_task:manage'"
          title="删除任务及其全部事件记录？删除后不可恢复。"
          confirm-button-text="删除"
          cancel-button-text="取消"
          @confirm="handleDelete"
        >
          <template #reference>
            <el-button type="danger" plain>
              <i class="i-solar-trash-bin-trash-linear btn-icon" />删除
            </el-button>
          </template>
        </el-popconfirm>
      </div>
    </div>

    <!-- 4px 状态色条 -->
    <div class="status-bar" :class="`bar-${status}`" />

    <!-- 整体接管渲染器（逃生舱）：状态色条以下整块由类型自渲染，仅共享头部/操作/生命周期 -->
    <div v-if="bodyRendererComp" class="body-takeover">
      <component
        :is="bodyRendererComp"
        :key="taskId"
        :task="task"
        :events="rawEvents"
        :active="isActive"
        :summary="resultSummary"
        :result-ref="resultRef"
        :project-id="projectId"
      />
    </div>

    <template v-else>
    <div class="detail-body" :class="{ 'has-device': devicePanelComp }">
    <div class="db-main">
    <!-- ============ 统计卡（2×2）+ 执行阶段（同一行） ============ -->
    <div v-if="showTopRow" class="top-row" :class="{ solo: !showStats || !showStages }">
      <div v-if="showStats" class="mini-grid">
        <div class="mini-card">
          <div class="mc-icon" :class="`mi-${statColor}`">
            <i class="i-solar-chart-square-bold" />
          </div>
          <div class="mc-body">
            <span class="mc-label">进度</span>
            <span class="mc-value">{{ progress }}%</span>
            <span class="mc-extra">{{ statusText }}</span>
          </div>
        </div>
        <div class="mini-card">
          <div class="mc-icon mi-info">
            <i class="i-solar-clock-circle-bold" />
          </div>
          <div class="mc-body">
            <span class="mc-label">耗时</span>
            <span class="mc-value">{{ durationText }}</span>
            <span class="mc-extra">自任务开始</span>
          </div>
        </div>
        <div class="mini-card">
          <div class="mc-icon mi-purple">
            <i class="i-solar-list-check-bold" />
          </div>
          <div class="mc-body">
            <span class="mc-label">阶段</span>
            <span class="mc-value">{{ stageCounter }} / {{ totalStages }}</span>
            <span class="mc-extra" :title="task?.current_stage || ''">{{ task?.current_stage || '—' }}</span>
          </div>
        </div>
        <div class="mini-card">
          <div class="mc-icon mi-warning">
            <i class="i-solar-cpu-bolt-bold" />
          </div>
          <div class="mc-body">
            <span class="mc-label">模型</span>
            <span class="mc-value mc-sm" :title="task?.ai_model || ''">{{ task?.ai_model || '—' }}</span>
            <span class="mc-extra">AI 引擎</span>
          </div>
        </div>
      </div>

      <!-- 执行阶段（横向时间轴） -->
      <div v-if="showStages" class="panel stages-panel">
        <div class="panel-head">
          <h3 class="panel-title">执行阶段</h3>
          <span v-if="isActive" class="live-tag">
            <span class="live-dot small" />进行中
          </span>
          <span v-else-if="isFailed && stageList.length" class="head-pill hp-danger">
            <i class="i-solar-danger-triangle-bold" />第 {{ currentStageIdx + 1 }} 阶段失败
          </span>
          <span v-else-if="isCanceled && stageList.length" class="head-pill hp-warning">
            <i class="i-solar-close-circle-linear" />已取消
          </span>
          <span class="stage-progress">{{ stageCounter }} / {{ totalStages }}</span>
        </div>
        <div class="panel-body stages-body">
          <div v-if="stageList.length" class="h-timeline">
            <div
              v-for="(s, i) in stageList"
              :key="`${s.name}-${i}`"
              class="ht-step"
              :class="stageState(i)"
            >
              <span v-if="i > 0" class="ht-line l" :class="{ ok: lineDone(i - 1) }" />
              <span v-if="i < stageList.length - 1" class="ht-line r" :class="{ ok: lineDone(i) }" />
              <span v-if="i < stageList.length - 1 && segDurText(i)" class="ht-durwrap">
                <span class="ht-dur">{{ segDurText(i) }}</span>
              </span>
              <span class="ht-dot">
                <i v-if="stageState(i) === 'done'" class="i-tabler-check" />
                <i v-else-if="stageState(i) === 'active'" class="i-svg-spinners-90-ring-with-bg" />
                <i v-else-if="stageState(i) === 'fail'" class="i-tabler-x" />
                <i v-else-if="stageState(i) === 'cancel'" class="i-tabler-x" />
                <span v-else class="ht-num">{{ i + 1 }}</span>
              </span>
              <div class="ht-name">{{ s.name }}</div>
              <div class="ht-time">{{ stageTimeText(i) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无阶段信息" :image-size="60" />
        </div>
      </div>
    </div>

    <!-- ============ 运行日志 + AI 实时输出 ============ -->
    <div v-if="showTwoRow" class="row two" :class="{ solo: !showLogs || !showConsole }">
      <div v-if="showLogs" class="col logs-col">
        <div class="panel">
          <div class="panel-head">
            <h3 class="panel-title">运行日志</h3>
            <span class="logs-count">{{ filteredLogs.length }} 条</span>
            <el-radio-group v-model="logFilter" size="small" class="logs-filter">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="error">错误</el-radio-button>
              <el-radio-button value="warning">警告</el-radio-button>
              <el-radio-button value="info">信息</el-radio-button>
            </el-radio-group>
          </div>
          <div class="logs">
            <div v-for="(l, i) in filteredLogs" :key="i" class="log-line" :class="`lv-${l.level}`">
              <span class="log-time">{{ l.timeText }}</span>
              <span class="log-dot" />
              <span class="log-msg">{{ l.message }}</span>
            </div>
            <div v-if="!filteredLogs.length" class="log-empty">
              {{ logFilter === 'all' ? '暂无日志' : `暂无 ${logFilterLabel} 日志` }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="showConsole" class="col console-col">
        <div class="panel">
          <div class="panel-head">
            <h3 class="panel-title">
              <span v-if="isActive" class="live-tag">
                <span class="live-dot small" />
              </span>
              AI 实时输出
            </h3>
            <div class="panel-tools">
              <template v-if="!streamRendererComp">
                <el-switch
                  v-model="autoScroll"
                  inline-prompt
                  active-text="自动滚动"
                  inactive-text="手动"
                  size="small"
                />
                <button class="icon-btn-sm" title="复制内容" :disabled="!consoleText" @click="copyConsole">
                  <i class="i-solar-copy-linear" />
                  <span>复制</span>
                </button>
              </template>
              <button class="icon-btn-sm" :title="fullscreen ? '退出全屏' : '全屏'" @click="toggleFullscreen">
                <i :class="fullscreen ? 'i-solar-minimize-linear' : 'i-solar-maximize-linear'" />
                <span>{{ fullscreen ? '退出' : '全屏' }}</span>
              </button>
            </div>
          </div>
          <!-- 定制渲染器（web_agent 步骤流等），未注册回退 Markdown 控制台 -->
          <div v-if="streamRendererComp" class="console-host" :class="{ 'is-fs': fullscreen }">
            <component
              :is="streamRendererComp"
              :key="taskId"
              :events="rawEvents"
              :active="isActive"
              :task="task"
            />
          </div>
          <div v-else ref="consoleEl" class="console" :class="{ 'is-fs': fullscreen }">
            <div v-if="consoleText" class="console-md markdown-body" v-html="renderMarkdown(consoleText)"></div>
            <span v-if="isActive && consoleText" class="cursor">▋</span>
            <div v-if="!consoleText" class="console-empty">
              {{ isActive ? '等待 AI 输出...' : '本次任务无流式输出' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ 产出结果（全宽） ============ -->
    <div v-if="showResult" class="panel">
      <div class="panel-head">
        <h3 class="panel-title">产出结果</h3>
        <span v-if="resultRefLabel" class="kind-chip" :class="`kc-${resultRefColor}`">
          {{ resultRefLabel }}
        </span>
      </div>
      <div class="result-body">
        <div v-if="errorMsg" class="result-error">
          <i class="i-solar-danger-triangle-bold err-ico" />
          <div class="err-main">
            <div class="err-title">任务失败</div>
            <div class="err-msg">{{ errorMsg }}</div>
          </div>
          <button class="err-copy" title="复制错误" @click="copyText(errorMsg)">
            <i class="i-solar-copy-linear" />
          </button>
        </div>

        <!-- 定制结果渲染器（接口结构预览等），未注册回退 metrics 卡片 -->
        <template v-else-if="resultRendererComp && resultSummary">
          <component :is="resultRendererComp" :summary="resultSummary" :result-ref="resultRef" />
          <el-button
            v-if="resultJumpable"
            type="success"
            class="result-jump"
            @click="jumpToResult"
          >
            <i class="i-solar-list-heart-bold btn-icon" />
            {{ resultJumpText }}
            <i class="i-solar-arrow-right-linear" />
          </el-button>
        </template>

        <template v-else-if="resultMetrics.length">
          <div class="metric-grid">
            <div
              v-for="(m, i) in resultMetrics"
              :key="i"
              class="metric-item"
              :class="[`mc-${m.color || 'default'}`, { hot: m.highlight }]"
            >
              <span class="metric-val">
                {{ m.value }}<small v-if="m.unit">{{ m.unit }}</small>
              </span>
              <span class="metric-label">{{ m.label }}</span>
            </div>
          </div>
          <el-button
            v-if="resultJumpable"
            type="success"
            class="result-jump"
            @click="jumpToResult"
          >
            <i class="i-solar-list-heart-bold btn-icon" />
            {{ resultJumpText }}
            <i class="i-solar-arrow-right-linear" />
          </el-button>
        </template>

        <template v-else-if="rawKv.length">
          <div class="result-kv">
            <div v-for="(v, k) in rawKv" :key="k" class="kv">
              <span class="kv-k">{{ v.k }}</span>
              <span class="kv-v">{{ v.v }}</span>
            </div>
          </div>
          <el-button
            v-if="resultJumpable"
            type="primary"
            class="result-jump"
            @click="jumpToResult"
          >
            {{ resultJumpText }}
            <i class="i-solar-arrow-right-linear" />
          </el-button>
        </template>

        <div v-else class="result-empty">
          <i class="i-solar-box-minimalistic-linear" />
          <span>暂无产出</span>
        </div>

        <!-- 元素自愈传播（POM 闭环）：自愈结果含可传播候选时展示，人工确认后一键传播 -->
        
      </div>
    </div>

    <!-- ============ 输入参数（折叠） ============ -->
    <div v-if="inputParamsText" class="panel">
      <div class="panel-head params-head" @click="showParams = !showParams">
        <h3 class="panel-title">输入参数</h3>
        <span class="params-hint">提交任务时的参数快照（重试复用）</span>
        <i
          class="params-arrow i-solar-alt-arrow-down-linear"
          :class="{ open: showParams }"
        />
      </div>
      <div v-show="showParams" class="params-body">
        <pre class="params-pre">{{ inputParamsText }}</pre>
      </div>
    </div>
    </div>

    <!-- 右侧常驻手机设备面板（App 自动化：观战投屏） -->
    <aside v-if="devicePanelComp" class="db-device">
      <component :is="devicePanelComp" :key="taskId" :task="task" :active="isActive" />
    </aside>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { aiTaskApi, streamAiTask } from '@/api/aiTask';
import type { AiTaskDetail, AiTaskStatus, AiTaskStreamEvent } from '@/types/ai-task';
import { useMarkdown } from '@/composables/useMarkdown';
import { typeMeta, refKindMeta, statusColor, statusLabel, layoutProfile, durationText as fmtDuration, formatDurationMs, formatTime, } from './task-meta';
import { STREAM_RENDERERS, RESULT_RENDERERS, BODY_RENDERERS, DEVICE_PANEL_RENDERERS, } from './detail-renderers';
const route = useRoute();
const router = useRouter();
const { render: renderMarkdown } = useMarkdown();
const projectId = computed(() => Number(route.params.id));
const taskId = computed(() => Number(route.params.taskId));
// ============ 状态 ============
const task = ref<AiTaskDetail | null>(null);
const status = ref<AiTaskStatus>('pending');
const progress = ref(0);
const stageList = ref<{
    name: string;
    at?: string | null;
}[]>([]);
const currentStageIdx = ref(0);
const consoleText = ref('');
const logLines = ref<{
    level: string;
    message: string;
    timeText: string;
}[]>([]);
const resultSummary = ref<Record<string, unknown> | null>(null);
const resultRef = ref<Record<string, unknown> | null>(null);
const errorMsg = ref('');
const canceling = ref(false);
const autoScroll = ref(true);
const fullscreen = ref(false);
const logFilter = ref<'all' | 'error' | 'warning' | 'info'>('all');
let stopStream: (() => void) | null = null;
let maxSeq = 0;
const consoleEl = ref<HTMLElement | null>(null);
// 运行中耗时每秒跳动
const nowTick = ref(Date.now());
let tickTimer: ReturnType<typeof setInterval> | null = null;
// ============ 计算 ============
const isActive = computed(() => status.value === 'pending' || status.value === 'running');
const isSucceeded = computed(() => status.value === 'succeeded');
const isFailed = computed(() => status.value === 'failed');
const isCanceled = computed(() => status.value === 'canceled');
const statColor = computed(() => statusColor(status.value));
const statusText = computed(() => statusLabel(status.value));
const tMeta = computed(() => typeMeta(task.value?.task_type));
// 按任务类型注册的定制渲染器（未注册回退通用渲染）
const streamRendererComp = computed(() => task.value ? STREAM_RENDERERS[task.value.task_type] || null : null);
const resultRendererComp = computed(() => task.value ? RESULT_RENDERERS[task.value.task_type] || null : null);
// 整体接管渲染器（逃生舱）：存在时独占状态色条以下整块，忽略布局档案与 STREAM/RESULT
const bodyRendererComp = computed(() => task.value ? BODY_RENDERERS[task.value.task_type] || null : null);
// 右侧常驻设备面板（App 自动化）：存在时正文变「左主区 + 右手机框」两栏
const devicePanelComp = computed(() => task.value ? DEVICE_PANEL_RENDERERS[task.value.task_type] || null : null);
// 布局档案：按类型声明壳内各区块显隐（未声明全展示）。有整体接管时不参与。
const layout = computed(() => layoutProfile(task.value?.task_type));
const showStats = computed(() => !layout.value.hideStats);
const showStages = computed(() => !layout.value.hideStages);
const showTopRow = computed(() => showStats.value || showStages.value);
const showLogs = computed(() => !layout.value.hideLogs);
const showConsole = computed(() => !layout.value.hideConsole);
const showTwoRow = computed(() => showLogs.value || showConsole.value);
const showResult = computed(() => !layout.value.hideResult);
// 定制实时输出渲染器消费的原始事件流
const rawEvents = ref<AiTaskStreamEvent[]>([]);
const totalStages = computed(() => {
    const t = task.value;
    if (t?.total_stages && t.total_stages > 0)
        return t.total_stages;
    return Math.max(stageList.value.length, 1);
});
const durationText = computed(() => {
    void nowTick.value; // 运行中每秒重算
    return task.value ? fmtDuration(task.value) : '—';
});
interface Metric {
    label: string;
    value: unknown;
    unit?: string;
    color?: string | null;
    highlight?: boolean;
}
const resultMetrics = computed<Metric[]>(() => {
    const m = (resultSummary.value as Record<string, unknown> | null)?.metrics;
    return Array.isArray(m) ? (m as Metric[]) : [];
});
// 元素自愈传播候选（仅 Web 自愈结果含 propagation 且有候选时非空）
const resultPropagation = computed(() => {
    const p = (resultSummary.value as Record<string, unknown> | null)?.propagation as {
        element_id: number;
        new_locator: Record<string, unknown>;
        candidates: unknown[];
    } | undefined | null;
    return p && Array.isArray(p.candidates) && p.candidates.length ? p : null;
});
const rawKv = computed(() => {
    const s = resultSummary.value;
    if (!s)
        return [] as {
            k: string;
            v: unknown;
        }[];
    return Object.entries(s)
        .filter(([k]) => k !== 'metrics' && k !== 'propagation')
        .map(([k, v]) => ({ k, v }));
});
const refMeta = computed(() => refKindMeta(resultRef.value));
const resultJumpable = computed(() => !!refMeta.value?.jump);
const resultRefLabel = computed(() => refMeta.value?.label || '');
const resultRefColor = computed(() => refMeta.value?.color || 'brand');
const resultJumpText = computed(() => refMeta.value?.jumpText || '查看产出详情');
const showParams = ref(false);
const inputParamsText = computed(() => {
    const p = task.value?.input_params;
    if (!p || !Object.keys(p).length)
        return '';
    try {
        return JSON.stringify(p, null, 2);
    }
    catch {
        return '';
    }
});
const filteredLogs = computed(() => {
    if (logFilter.value === 'all')
        return logLines.value;
    return logLines.value.filter((l) => l.level === logFilter.value);
});
const logFilterLabel = computed(() => ({ error: '错误', warning: '警告', info: '信息' } as Record<string, string>)[logFilter.value] || '');
function shortId(id: string) {
    if (!id)
        return '—';
    if (id.length <= 12)
        return id;
    return id.slice(0, 8) + '…' + id.slice(-4);
}
// ============ 阶段时间线 ============
type StageState = 'done' | 'active' | 'fail' | 'cancel' | '';
function stageState(i: number): StageState {
    if (isSucceeded.value || i < currentStageIdx.value)
        return 'done';
    if (i === currentStageIdx.value) {
        if (isActive.value)
            return 'active';
        if (isFailed.value)
            return 'fail';
        if (isCanceled.value)
            return 'cancel';
        return 'done';
    }
    return '';
}
/** 第 i 段连接线（节点 i → i+1）是否已走完：下一阶段已开始即视为完成 */
function lineDone(segIdx: number): boolean {
    return isSucceeded.value || segIdx + 1 <= currentStageIdx.value;
}
/** 第 i 段耗时（节点 i 开始 → 节点 i+1 开始），挂在连接线上 */
function segDurText(i: number): string {
    const a = stageList.value[i]?.at;
    const b = stageList.value[i + 1]?.at;
    if (!a || !b)
        return '';
    return formatDurationMs(new Date(b).getTime() - new Date(a).getTime());
}
function stageTimeText(i: number): string {
    const s = stageList.value[i];
    if (!s?.at)
        return '—';
    const base = formatTime(s.at);
    if (i !== currentStageIdx.value)
        return base;
    const state = stageState(i);
    if (state === 'active') {
        void nowTick.value; // 每秒重渲染
        return `${base} · 已进行 ${formatDurationMs(Date.now() - new Date(s.at).getTime())}`;
    }
    const endAt = task.value?.completed_at;
    if (state === 'fail')
        return endAt ? `${base} · 失败于 ${formatTime(endAt)}` : base;
    if (state === 'cancel')
        return endAt ? `${base} · 取消于 ${formatTime(endAt)}` : base;
    return base;
}
const stageCounter = computed(() => {
    if (!stageList.value.length)
        return 0;
    if (isSucceeded.value)
        return totalStages.value;
    return Math.min(currentStageIdx.value + 1, totalStages.value);
});
// ============ 工具 ============
async function copyText(t: string) {
    if (!t)
        return;
    try {
        await navigator.clipboard.writeText(t);
        ElMessage.success('已复制');
    }
    catch {
        ElMessage.error('复制失败');
    }
}
function copyConsole() { copyText(consoleText.value); }
function toggleFullscreen() { fullscreen.value = !fullscreen.value; }
// ============ 事件处理 ============
function applyEvent(ev: AiTaskStreamEvent) {
    if (ev.seq)
        maxSeq = Math.max(maxSeq, ev.seq);
    // 有定制实时输出渲染器或整体接管渲染器时，原始事件透传给渲染器（message_delta/biz 由其消费）
    const hasStreamRenderer = !!streamRendererComp.value || !!bodyRendererComp.value;
    if (hasStreamRenderer)
        rawEvents.value.push(ev);
    const p = ev.payload || {};
    const evTime = (ev as unknown as {
        created_at?: string | null;
    }).created_at;
    switch (ev.type) {
        case 'task_start': {
            const stages = p.stages as string[] | undefined;
            if (Array.isArray(stages)) {
                stageList.value = stages.map((n) => ({ name: n }));
            }
            break;
        }
        case 'stage': {
            const name = (p.name as string) || '';
            if (!name)
                break;
            const exist = stageList.value.findIndex((s) => s.name === name);
            if (exist < 0) {
                stageList.value.push({ name, at: evTime ?? null });
                currentStageIdx.value = stageList.value.length - 1;
            }
            else {
                const item = stageList.value[exist];
                if (item) {
                    currentStageIdx.value = exist;
                    if (evTime)
                        item.at = evTime;
                }
            }
            break;
        }
        case 'progress':
            if (typeof p.percent === 'number')
                progress.value = p.percent;
            break;
        case 'log': {
            if (p.message) {
                logLines.value.push({
                    level: (p.level as string) || 'info',
                    message: p.message as string,
                    timeText: evTime ? formatTime(evTime) : '',
                });
            }
            break;
        }
        case 'biz': {
            // 无定制渲染器时兜底：翻译成可读日志行（有渲染器时由其展示步骤/截图）
            if (hasStreamRenderer)
                break;
            const line = bizToLog(p);
            if (line) {
                logLines.value.push({ ...line, timeText: evTime ? formatTime(evTime) : '' });
            }
            break;
        }
        case 'message_delta':
            if (hasStreamRenderer)
                break;
            if (p.text) {
                consoleText.value += p.text as string;
                if (autoScroll.value)
                    scrollConsole();
            }
            break;
        case 'result':
            resultSummary.value = (p.summary as Record<string, unknown>) || null;
            resultRef.value = (p.ref as Record<string, unknown>) || null;
            break;
        case 'error':
            errorMsg.value = (p.message as string) || '未知错误';
            break;
        case 'task_end': {
            const ns = (p.status as AiTaskStatus) || status.value;
            status.value = ns;
            if (status.value === 'succeeded')
                progress.value = 100;
            stopSse();
            refreshDetailMeta();
            break;
        }
    }
}
/** biz 事件（payload.kind 区分业务类型）→ 日志行兜底展示 */
function bizToLog(p: Record<string, unknown>): {
    level: string;
    message: string;
} | null {
    const kind = String(p.kind || '');
    const msg = String(p.message || '');
    switch (kind) {
        case 'command': {
            const stepNo = p.step_no ? `第 ${p.step_no} 步 ` : '';
            const desc = [p.action, p.target, p.value].filter(Boolean).join(' ');
            return { level: 'info', message: `▶ ${stepNo}${desc || String(p.command || '')}` };
        }
        case 'result':
            return msg ? { level: 'success', message: `✓ ${msg}` } : null;
        case 'screenshot':
            return { level: 'stream', message: `📸 已截图${p.path ? `：${p.path}` : ''}` };
        case 'element':
            return msg ? { level: 'stream', message: msg } : null;
        case 'step':
        case 'report':
            return msg ? { level: 'info', message: msg } : null;
        case 'assertion':
            return {
                level: p.passed === false ? 'error' : 'success',
                message: msg || `断言${p.passed === false ? '失败' : '通过'}`,
            };
        default:
            return msg ? { level: 'info', message: `[${kind}] ${msg}` } : null;
    }
}
function scrollConsole() {
    nextTick(() => {
        if (consoleEl.value)
            consoleEl.value.scrollTop = consoleEl.value.scrollHeight;
    });
}
async function refreshDetailMeta() {
    try {
        const { data } = await aiTaskApi.detail(projectId.value, taskId.value);
        task.value = data;
        status.value = data.status;
    }
    catch { /* ignore */ }
}
function resetState() {
    stopSse();
    maxSeq = 0;
    task.value = null;
    status.value = 'pending';
    progress.value = 0;
    stageList.value = [];
    currentStageIdx.value = 0;
    consoleText.value = '';
    logLines.value = [];
    rawEvents.value = [];
    resultSummary.value = null;
    resultRef.value = null;
    errorMsg.value = '';
}
async function load() {
    const { data } = await aiTaskApi.detail(projectId.value, taskId.value);
    task.value = data;
    status.value = data.status;
    progress.value = data.progress;
    for (const e of data.events || []) {
        applyEvent({
            seq: e.seq,
            type: e.event_type,
            payload: e.payload || {},
            created_at: e.created_at,
        } as AiTaskStreamEvent);
    }
    if (status.value === 'pending' || status.value === 'running')
        startSse();
}
function startSse() {
    stopSse();
    stopStream = streamAiTask(projectId.value, taskId.value, {
        onEvent: applyEvent,
        onClose: () => { if (isActive.value)
            refreshDetailMeta(); },
        onError: () => { },
    }, maxSeq);
}
function stopSse() {
    if (stopStream) {
        stopStream();
        stopStream = null;
    }
}
// ============ 操作 ============
async function handleCancel() {
    canceling.value = true;
    try {
        await aiTaskApi.cancel(projectId.value, taskId.value);
        ElMessage.success('取消请求已发送');
    }
    catch (e) {
        console.error('取消任务失败', e);
    }
    finally {
        canceling.value = false;
    }
}
async function handleRetry() {
    try {
        const { data } = await aiTaskApi.retry(projectId.value, taskId.value);
        ElMessage.success('已重新提交');
        // taskId 变化由 watch 触发就地重载，无需刷新页面
        router.push({ name: 'AiTaskDetail', params: { id: projectId.value, taskId: data.id } });
    }
    catch (e) {
        console.error('重试任务失败', e);
    }
}
async function handleDelete() {
    try {
        await aiTaskApi.remove(projectId.value, taskId.value);
        ElMessage.success('已删除');
        router.push({ name: 'AiTaskCenter', params: { id: projectId.value } });
    }
    catch (e) {
        console.error('删除任务失败', e);
    }
}
function jumpToResult() {
    refMeta.value?.jump?.(router, projectId.value, (resultRef.value || {}) as Record<string, unknown>);
}
function goBack() { router.back(); }
// 同页路由切换（重试跳新任务）就地重载
watch(taskId, (n, o) => {
    if (n && n !== o && route.name === 'AiTaskDetail') {
        resetState();
        load();
    }
});
onMounted(() => {
    load();
    tickTimer = setInterval(() => {
        if (isActive.value)
            nowTick.value = Date.now();
    }, 1000);
});
onBeforeUnmount(() => {
    stopSse();
    if (tickTimer)
        clearInterval(tickTimer);
});
</script>

<style scoped lang="scss">
.ai-task-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 正文容器：默认单栏（主区各区块纵向堆叠）；App 类型开右侧手机面板时变两栏 */
.detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.db-main {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}
.detail-body.has-device {
  flex-direction: row;
  align-items: flex-start;
}
.detail-body.has-device .db-main {
  flex: 1;
  min-width: 0;
}
.db-device {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: var(--space-4);
}
/* 窄屏：手机面板落到主区下方，恢复单栏 */
@media (max-width: 1100px) {
  .detail-body.has-device {
    flex-direction: column;
  }
  .db-device {
    width: 100%;
    max-width: 340px;
    align-self: center;
    position: static;
  }
}

/* ============ 顶部 ============ */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-4);
}
.header-main { flex: 1; min-width: 0; }
.bread {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.bread .sep { font-size: 12px; opacity: 0.5; }
.title {
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 8px;
  line-height: 1.3;
}
.meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
.meta-sep { opacity: 0.4; }
.meta-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  > i { font-size: 13px; }
  &.mono { font-family: var(--font-mono); }
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  > i { font-size: 12px; }
  &.tc-brand   { background: var(--brand-50);          color: var(--brand-600); }
  &.tc-info    { background: var(--color-info-50);     color: var(--color-info-600); }
  &.tc-purple  { background: var(--color-purple-50);   color: var(--color-purple-600); }
  &.tc-warning { background: var(--color-warning-50);  color: var(--color-warning-600); }
  &.tc-success { background: var(--color-success-50);  color: var(--color-success-600); }
  &.tc-danger  { background: var(--color-danger-50);   color: var(--color-danger-600); }
}

.header-actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn-icon { margin-right: 4px; font-size: 14px; vertical-align: -2px; }

/* ============ 状态色条 ============ */
.status-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--gray-200);
  &.bar-running   { background: var(--brand-500); }
  &.bar-succeeded { background: var(--color-success-500); }
  &.bar-failed    { background: var(--color-danger-500); }
  &.bar-canceled  { background: var(--color-warning-500); }
  &.bar-pending   { background: var(--gray-300); }
}

/* ============ 顶部行：统计卡 2×2 + 执行阶段 ============ */
.top-row {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: var(--space-4);
  align-items: stretch;
}
/* 布局档案隐藏统计卡或阶段轴后，剩下的单块占满整行 */
.top-row.solo { grid-template-columns: 1fr; }
/* 只剩统计卡（阶段轴被隐藏）时，2×2 铺满一整行会显空——宽屏改单行四列 */
@media (min-width: 1080px) {
  .top-row.solo .mini-grid { grid-template-columns: repeat(4, 1fr); grid-template-rows: 1fr; }
}
@media (max-width: 1000px) { .top-row { grid-template-columns: 1fr; } }

.mini-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: var(--space-3);
}
.mini-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  min-width: 0;
}
.mc-icon {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;

  &.mi-brand   { background: var(--brand-50);          color: var(--brand-600); }
  &.mi-info    { background: var(--color-info-50);     color: var(--color-info-600); }
  &.mi-success { background: var(--color-success-50);  color: var(--color-success-600); }
  &.mi-warning { background: var(--color-warning-50);  color: var(--color-warning-600); }
  &.mi-danger  { background: var(--color-danger-50);   color: var(--color-danger-600); }
  &.mi-purple  { background: var(--color-purple-50);   color: var(--color-purple-600); }
}
.mc-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.mc-label {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.3;
}
.mc-value {
  font-size: 18px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  &.mc-sm {
    font-size: 13px;
    font-family: var(--font-mono);
  }
}
.mc-extra {
  font-size: 11px;
  color: var(--text-placeholder);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stages-panel { min-width: 0; }
.stages-body {
  display: flex;
  align-items: center;

  .h-timeline { flex: 1; min-width: 0; }
  :deep(.el-empty) { flex: 1; padding: var(--space-2) 0; }
}

/* ============ 双列行 ============ */
.row.two {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: 3fr 7fr;
}
/* 布局档案隐藏日志列或实时输出列后，剩下的单列占满整行 */
.row.two.solo { grid-template-columns: 1fr; }
/* 关键：grid 子项默认 min-width:auto，右侧宽内容会把左列挤扁 */
.row.two > .col {
  min-width: 0;
}
@media (max-width: 900px) {
  .row.two { grid-template-columns: 1fr; }
}

/* 整体接管渲染器容器（逃生舱）：类型自渲染，不加约束，仅撑满宽度 */
.body-takeover { min-width: 0; }

/* ============ Panel 通用 ============ */
.panel {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  min-height: 100%;
  height: 100%;
}
.panel-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.panel-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.panel-body { padding: var(--space-4) var(--space-5); flex: 1; }

/* ============ 横向时间轴 ============ */
.stage-progress {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-weight: var(--font-weight-medium);
}
/* 节点/名称/时间同轴居中；连接线固定在圆心高度，贯通相邻节点 */
.h-timeline {
  display: flex;
  padding: var(--space-4) var(--space-2) var(--space-2);
}
.ht-step {
  flex: 1;
  min-width: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.ht-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-100);
  color: var(--text-placeholder);
  flex-shrink: 0;
  z-index: 1;
  transition: var(--transition-fast);
  > i { font-size: 16px; }
}
.ht-num {
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  font-family: var(--font-mono);
}
.ht-line {
  position: absolute;
  top: 15px;
  height: 2px;
  background: var(--gray-200);
  transition: var(--transition-fast);

  &.l { left: 0; right: calc(50% + 24px); }
  &.r { left: calc(50% + 24px); right: 0; }
  /* 注意：tokens 的 success 只有 50/500/600 档，不存在 300（透明线踩坑） */
  &.ok { background: var(--color-success-500); }
}
/* 段耗时药丸：悬在本节点与下一节点之间的连接线上 */
.ht-durwrap {
  position: absolute;
  top: 0;
  height: 32px;
  left: calc(50% + 24px);
  right: calc(-50% + 24px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  pointer-events: none;
}
.ht-dur {
  font-size: 11px;
  font-family: var(--font-mono);
  line-height: 16px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  padding: 0 7px;
  white-space: nowrap;
}
.ht-name {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-regular);
  line-height: 1.4;
  text-align: center;
  padding: 0 4px;
  transition: var(--transition-fast);
}
.ht-time {
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-placeholder);
  font-family: var(--font-mono);
  text-align: center;
}

.ht-step.done {
  .ht-dot { background: var(--color-success-500); color: #fff; }
  .ht-name { color: var(--text-secondary); }
}
.ht-step.active {
  .ht-dot {
    background: var(--bg-card);
    color: var(--brand-600);
    border: 2px solid var(--brand-500);
    box-shadow: 0 0 0 4px var(--brand-100);
  }
  .ht-name { color: var(--brand-700); font-weight: var(--font-weight-semibold); }
}
.ht-step.fail {
  .ht-dot { background: var(--color-danger-500); color: #fff; }
  .ht-name { color: var(--color-danger-600); font-weight: var(--font-weight-semibold); }
}
.ht-step.cancel {
  .ht-dot { background: var(--color-warning-500); color: #fff; }
  .ht-name { color: var(--color-warning-600); font-weight: var(--font-weight-semibold); }
}

/* 面板头部状态药丸（失败/取消） */
.head-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 9px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  > i { font-size: 12px; }

  &.hp-danger  { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.hp-warning { background: var(--color-warning-50); color: var(--color-warning-600); }
}

/* ============ 实时输出 ============ */
.live-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-success-600);
  font-weight: var(--font-weight-medium);
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success-500);
  box-shadow: 0 0 0 0 var(--color-success-500);
  animation: live-pulse 1.4s ease-out infinite;
  &.small { width: 6px; height: 6px; }
}
@keyframes live-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
  70%  { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.panel-tools {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.icon-btn-sm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border-light);
  background: var(--bg-card);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  transition: var(--transition-fast);
  > i { font-size: 13px; }
  &:hover:not(:disabled) {
    border-color: var(--brand-300);
    color: var(--brand-600);
    background: var(--brand-50);
  }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
}

/* 定制渲染器宿主：与默认 console 同尺寸约束，全屏态透传 */
.console-host {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;

  &.is-fs :deep(.wa-stream) {
    max-height: none;
    height: calc(100vh - 240px);
  }

  &.is-fs :deep(.app-exec-live) {
    height: calc(100vh - 240px);
  }
}

.console {
  flex: 1;
  max-height: 540px;
  overflow-y: auto;
  background: var(--gray-50);
  padding: var(--space-4) var(--space-5);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  border-radius: 0 0 var(--radius-md) var(--radius-md);

  &.is-fs {
    max-height: none;
    height: calc(100vh - 240px);
  }
}
.console-md {
  word-break: break-word;
  :deep(h1), :deep(h2), :deep(h3) {
    font-family: var(--font-sans);
    margin-top: 16px; margin-bottom: 8px;
    font-weight: 600;
  }
  :deep(h1) { font-size: 18px; }
  :deep(h2) { font-size: 16px; }
  :deep(h3) { font-size: 15px; }
  :deep(p) { margin: 6px 0; }
  :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 20px; }
  :deep(li) { margin: 2px 0; }
  :deep(code) {
    background: var(--gray-100);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
    color: var(--brand-600);
    word-break: break-all; /* 长 id/URL 行内码可换行，不撑宽容器 */
  }
  :deep(pre) {
    background: var(--bg-card);
    padding: 12px;
    border-radius: 6px;
    border: 1px solid var(--border-light);
    overflow-x: auto;
    margin: 8px 0;
    code { background: none; padding: 0; color: var(--text-primary); }
  }
  :deep(table) { border-collapse: collapse; margin: 8px 0; width: 100%; }
  :deep(th), :deep(td) { border: 1px solid var(--border-light); padding: 6px 10px; font-size: 12px; }
  :deep(th) { background: var(--gray-50); font-weight: 600; }
  :deep(blockquote) {
    border-left: 3px solid var(--brand-300);
    margin: 8px 0; padding: 4px 12px;
    color: var(--text-secondary);
    background: var(--brand-50);
  }
  :deep(strong) { color: var(--text-primary); }
  :deep(a) { color: var(--brand-600); text-decoration: underline; }
}
.cursor { color: var(--brand-500); animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
.console-empty {
  color: var(--text-placeholder);
  font-size: 13px;
  text-align: center;
  padding: var(--space-4);
}

/* ============ 日志 ============ */
.logs-filter { margin-left: auto; flex-shrink: 0; }
.logs {
  /* 与右侧 AI 输出等高：填满面板剩余空间，上限对齐 console 的 540px */
  flex: 1;
  min-height: 180px;
  max-height: 540px;
  overflow-y: auto;
  padding: var(--space-3) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.logs-count {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: var(--font-weight-regular);
  flex-shrink: 0;
}
.log-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12.5px;
  color: var(--text-regular);
  line-height: 1.6;
  padding: 2px 0;
}
.log-time {
  color: var(--text-placeholder);
  font-family: var(--font-mono);
  font-size: 11px;
  flex-shrink: 0;
  min-width: 56px; /* 时间列对齐 */
  margin-top: 2px;
}
.log-dot {
  width: 8px; height: 8px; border-radius: 50%;
  margin-top: 6px; flex-shrink: 0;
  background: var(--color-info-500);
}
.log-msg { flex: 1; word-break: break-word; }
.log-line.lv-error .log-dot   { background: var(--color-danger-500); }
.log-line.lv-error            { color: var(--color-danger-600); }
.log-line.lv-warning .log-dot { background: var(--color-warning-500); }
.log-line.lv-warning          { color: var(--color-warning-600); }
.log-line.lv-success .log-dot { background: var(--color-success-500); }
.log-line.lv-success          { color: var(--color-success-600); }
.log-line.lv-stream .log-dot  { background: var(--gray-300); }
.log-line.lv-stream           { color: var(--text-secondary); }
.log-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  padding: var(--space-6);
}

/* ============ 产出结果 ============ */
.kind-chip {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  &.kc-brand   { background: var(--brand-50);         color: var(--brand-600); }
  &.kc-info    { background: var(--color-info-50);    color: var(--color-info-600); }
  &.kc-purple  { background: var(--color-purple-50);  color: var(--color-purple-600); }
  &.kc-warning { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.kc-success { background: var(--color-success-50); color: var(--color-success-600); }
  &.kc-danger  { background: var(--color-danger-50);  color: var(--color-danger-600); }
}
.result-body { padding: var(--space-5); }
.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-4);
  color: var(--text-placeholder);
  font-size: var(--font-size-sm);
  > i { font-size: 32px; opacity: 0.5; }
}
.result-error {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-danger-50);
  /* 语义色 token 只有 50/500/600 档，浅色边框用 color-mix 从 500 调透明度 */
  border: 1px solid color-mix(in srgb, var(--color-danger-500) 30%, transparent);
  border-radius: var(--radius-md);
}
.err-ico { font-size: 24px; color: var(--color-danger-500); flex-shrink: 0; }
.err-main { flex: 1; min-width: 0; }
.err-title { font-weight: var(--font-weight-semibold); color: var(--color-danger-600); margin-bottom: 4px; }
.err-msg { font-size: var(--font-size-sm); color: var(--text-regular); word-break: break-word; line-height: 1.6; }
.err-copy {
  width: 28px; height: 28px;
  border: 1px solid color-mix(in srgb, var(--color-danger-500) 40%, transparent);
  background: var(--bg-card);
  color: var(--color-danger-600);
  border-radius: var(--radius-sm);
  cursor: pointer; font-size: 14px; flex-shrink: 0;
  transition: var(--transition-fast);
  &:hover { background: color-mix(in srgb, var(--color-danger-500) 15%, transparent); }
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-3) var(--space-4);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  transition: var(--transition-fast);
  &:hover { box-shadow: var(--shadow-sm); }
  &.hot { background: var(--brand-50); border-color: var(--brand-100); }
}
.metric-val {
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1.1;
  font-family: var(--font-mono);
  small { font-size: 12px; font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-left: 2px; }
}
.metric-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
.metric-item.hot .metric-val { color: var(--brand-700); }
.mc-success .metric-val { color: var(--color-success-600); }
.mc-warning .metric-val { color: var(--color-warning-600); }
.mc-danger  .metric-val { color: var(--color-danger-600); }

.result-kv {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}
.kv {
  display: flex; justify-content: space-between;
  font-size: var(--font-size-sm);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
  &:last-child { border-bottom: none; }
}
.kv-k { color: var(--text-secondary); }
.kv-v { color: var(--text-primary); font-weight: var(--font-weight-medium); font-family: var(--font-mono); font-size: var(--font-size-xs); }

.result-jump { width: 100%; margin-top: var(--space-2); }

/* ============ 输入参数 ============ */
.params-head {
  cursor: pointer;
  user-select: none;
  &:hover .panel-title { color: var(--brand-600); }
}
.params-hint {
  font-size: 11px;
  color: var(--text-placeholder);
}
.params-arrow {
  margin-left: auto;
  font-size: 16px;
  color: var(--text-secondary);
  transition: transform 0.2s ease;
  &.open { transform: rotate(180deg); }
}
.params-body {
  padding: var(--space-3) var(--space-5) var(--space-4);
}
.params-pre {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-regular);
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

</style>
