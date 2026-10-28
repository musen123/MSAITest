<template>
  <div class="ai-task-center">
    <AppPageHeader
      :icon="pageMeta.icon"
      :illustration="illustAiAgent"
      :title="pageMeta.title"
      :description="pageMeta.description"
      :breadcrumbs="['任务监控中心', pageMeta.crumb]"
    >
      <template #actions>
        <el-button @click="refreshAll">
          <i class="i-solar-refresh-linear btn-icon" />刷新
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 统计卡（全项目维度） -->
    <div class="stat-grid">
      <AppStatCard label="任务总数" :value="stats.total" color="brand" :clickable="true" @click="filterByStatus('')">
        <template #icon><i class="i-app-ai-spark dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard
        label="进行中"
        :value="stats.running + stats.pending"
        color="brand"
        :extra="stats.pending ? `含排队 ${stats.pending}` : ''"
        :clickable="true"
        @click="filterByStatus('running')"
      >
        <template #icon><i class="i-svg-spinners-90-ring-with-bg dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="已成功" :value="stats.succeeded" color="success" :clickable="true" @click="filterByStatus('succeeded')">
        <template #icon><i class="i-solar-check-circle-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="失败" :value="stats.failed" color="danger" :clickable="true" @click="filterByStatus('failed')">
        <template #icon><i class="i-solar-close-circle-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <div class="filter-fields">
        <div class="filter-field">
          <label>任务类型</label>
          <el-select v-model="query.task_type" placeholder="全部类型" clearable @change="handleSearch">
            <el-option v-for="o in typeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </div>
        <div class="filter-field">
          <label>状态</label>
          <el-select v-model="query.status" placeholder="全部状态" clearable @change="handleSearch">
            <el-option v-for="o in STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </div>
      </div>
    </div>

    <!-- 列表 -->
    <AppSectionCard padless class="table-card">
      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="items"
          :empty-text="loading ? '加载中...' : ''"
          style="width: 100%"
          row-class-name="task-row"
          @row-click="openDetail"
        >
          <el-table-column label="任务" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="task-cell">
                <span class="task-type-icon" :class="`tt-${typeMeta(row.task_type).color}`">
                  <i :class="typeMeta(row.task_type).icon" />
                </span>
                <div class="task-text">
                  <span class="task-title">{{ row.title }}</span>
                  <span class="task-sub">#{{ row.id }} · {{ typeMeta(row.task_type).label }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="进度" min-width="170">
            <template #default="{ row }">
              <div class="progress-cell">
                <div class="progress-bar" :class="`pg-${row.status}`">
                  <div class="progress-fill" :style="{ width: row.progress + '%' }" />
                </div>
                <div class="progress-meta">
                  <span class="progress-pct" :class="`txt-${statusColor(row.status)}`">
                    {{ row.progress }}%
                  </span>
                  <span v-if="row.current_stage" class="stage-hint" :title="row.current_stage">
                    {{ row.current_stage }}
                  </span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="AI模型" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="model-text">{{ row.ai_model || '—' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="状态" min-width="100">
            <template #default="{ row }">
              <span class="status-pill" :class="`st-${row.status}`">
                <span class="status-dot" />{{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="耗时" min-width="80">
            <template #default="{ row }">
              <span class="output-meta">
                <i class="i-solar-clock-circle-linear" />
                {{ durationText(row) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="提交时间" width="150">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDateTime(row.created_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="产出" min-width="120">
            <template #default="{ row }">
              <!-- 成功：显示主指标 -->
              <span v-if="row.status === 'succeeded' && primaryMetric(row)" class="output-pill">
                <i class="i-solar-check-circle-bold" />
                <strong>{{ primaryMetric(row)!.value }}</strong>
                <span>{{ primaryMetric(row)!.unit || primaryMetric(row)!.label }}</span>
              </span>
              <span v-else-if="row.status === 'succeeded'" class="output-empty">—</span>
              <!-- 失败：错误 -->
              <el-tooltip
                v-else-if="row.status === 'failed'"
                :content="row.error_message || '任务失败'"
                placement="top"
              >
                <span class="output-err">
                  <i class="i-solar-danger-triangle-bold" />
                  失败
                </span>
              </el-tooltip>
              <!-- 取消 -->
              <span v-else-if="row.status === 'canceled'" class="output-canceled">已取消</span>
              <!-- 运行中 / 排队 -->
              <span v-else class="output-running">—</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="250" fixed="right" align="center">
            <template #default="{ row }">
              <div class="row-actions" @click.stop>
                <el-button size="small" title="查看详情" @click="openDetail(row)">
                  <i class="i-solar-eye-linear btn-icon-sm" />
                  详情
                </el-button>
                <el-popconfirm
                  v-if="isActive(row)"
                  v-permission="'ai_task:manage'"
                  title="确定取消此任务？"
                  confirm-button-text="确认"
                  cancel-button-text="再想想"
                  @confirm="handleCancel(row)"
                >
                  <template #reference>
                    <el-button size="small" title="取消任务">
                      <i class="i-solar-close-circle-linear btn-icon-sm" />
                      取消
                    </el-button>
                  </template>
                </el-popconfirm>
                <el-popconfirm
                  v-if="isTerminal(row)"
                  v-permission="'ai_task:manage'"
                  title="删除任务及其全部事件记录？"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  @confirm="handleDelete(row)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain title="删除任务">
                      <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <AppEmpty v-if="!loading" scene="data" description="还没有任何 AI 任务" />
          </template>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="query.page"
            v-model:page-size="query.page_size"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            background
            @size-change="loadData"
            @current-change="loadData"
          />
        </div>
      </div>
    </AppSectionCard>
  </div>
</template>

<script setup lang="ts">
import illustAiAgent from '@/assets/illustrations/ai-agent.svg'
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { aiTaskApi } from '@/api/aiTask'
import type { AiTask, AiTaskStats } from '@/types/ai-task'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import {
  STATUS_OPTIONS,
  taskTypeOptions,
  typeMeta,
  statusLabel,
  statusColor,
  primaryMetric,
  durationText,
  formatDateTime,
} from './task-meta'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

const loading = ref(false)
const items = ref<AiTask[]>([])
const total = ref(0)
const stats = ref<AiTaskStats>({ total: 0, pending: 0, running: 0, succeeded: 0, failed: 0, canceled: 0 })
// 本组件被「AI任务中心(kind=ai)」与「执行监控中心(kind=exec)」两条路由复用，
// kind 由 route.meta.taskKind 锁定（默认 ai），页面标题/文案随之切换。
const routeKind = () => (route.meta.taskKind as 'ai' | 'exec') || 'ai'

const query = reactive({
  kind: routeKind() as 'ai' | 'exec',
  task_type: '',
  status: '',
  page: 1,
  page_size: 20,
})

const pageMeta = computed(() =>
  query.kind === 'exec'
    ? {
        icon: 'i-solar-play-circle-bold',
        title: '执行监控中心',
        description: '统一盯所有用例 / 套件 / 任务执行的实时进度与结果（Web / 接口 / App / 压测）',
        crumb: '执行监控',
      }
    : {
        icon: 'i-app-ai-agent',
        title: 'AI 任务中心',
        description: '统一查看 AI 生成 / 分析任务的执行进度、实时输出与产出结果',
        crumb: 'AI 任务',
      },
)

const typeOptions = computed(() => taskTypeOptions(query.kind))

let pollTimer: ReturnType<typeof setInterval> | null = null

const hasActive = computed(() =>
  stats.value.running + stats.value.pending > 0 ||
  items.value.some((t) => t.status === 'running' || t.status === 'pending'),
)

function isActive(row: AiTask) {
  return row.status === 'running' || row.status === 'pending'
}
function isTerminal(row: AiTask) {
  return row.status === 'succeeded' || row.status === 'failed' || row.status === 'canceled'
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: query.page, page_size: query.page_size }
    if (query.kind) params.kind = query.kind
    if (query.task_type) params.task_type = query.task_type
    if (query.status) params.status = query.status
    const { data } = await aiTaskApi.list(projectId.value, params)
    items.value = data.items
    total.value = data.total
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const params: Record<string, unknown> = {}
    if (query.kind) params.kind = query.kind
    if (query.task_type) params.task_type = query.task_type
    const { data } = await aiTaskApi.stats(projectId.value, params)
    stats.value = data
  } catch {
    /* ignore */
  }
}

function refreshAll() {
  loadData()
  loadStats()
}

function handleSearch() {
  query.page = 1
  refreshAll()
}

function filterByStatus(status: string) {
  query.status = status
  handleSearch()
}

function openDetail(row: AiTask) {
  router.push({ name: 'AiTaskDetail', params: { id: projectId.value, taskId: row.id } })
}

async function handleCancel(row: AiTask) {
  try {
    await aiTaskApi.cancel(projectId.value, row.id)
    ElMessage.success('取消请求已发送')
    refreshAll()
  } catch (e) {
    console.error('取消任务失败', e)
  }
}

async function handleDelete(row: AiTask) {
  try {
    await aiTaskApi.remove(projectId.value, row.id)
    ElMessage.success('已删除')
    refreshAll()
  } catch (e) {
    console.error('删除任务失败', e)
  }
}

// 两条路由复用同一组件实例：切页时 route.meta.taskKind 变化，重置筛选并重载
watch(
  () => route.meta.taskKind,
  () => {
    query.kind = routeKind()
    query.task_type = ''
    query.status = ''
    query.page = 1
    refreshAll()
  },
)

onMounted(() => {
  refreshAll()
  // 有进行中任务时轮询刷新
  pollTimer = setInterval(() => {
    if (hasActive.value) refreshAll()
  }, 4000)
})
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped lang="scss">
.ai-task-center {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}

/* ============ 统计卡 ============ */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.dash-card-icon {
  font-size: 26px;
}
@media (max-width: 1100px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px)  { .stat-grid { grid-template-columns: 1fr; } }

/* ============ 筛选区 ============ */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-6);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.kind-tabs {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
  padding-right: var(--space-4);
  border-right: 1px solid var(--border-light);
}
.kind-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;

  i { font-size: 15px; }

  &:hover {
    color: var(--text-primary);
    background: var(--gray-100);
  }
  &.active {
    color: var(--brand-600);
    background: var(--brand-50);
    font-weight: var(--font-weight-semibold);
  }
}
.filter-fields {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  flex: 1;
}
@media (max-width: 900px) {
  .filter-bar { flex-direction: column; align-items: stretch; }
  .kind-tabs { border-right: none; padding-right: 0; }
}
.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 180px;
  flex: 1;
  max-width: 320px;

  label {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
  }
}

/* ============ 表格 ============ */
.table-card { overflow: hidden; }
.table-wrap { padding: var(--space-3) var(--space-2) var(--space-2); }

.task-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.task-type-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;

  &.tt-brand   { background: var(--brand-50);          color: var(--brand-600); }
  &.tt-purple  { background: var(--color-purple-50);   color: var(--color-purple-600); }
  &.tt-warning { background: var(--color-warning-50);  color: var(--color-warning-600); }
  &.tt-info    { background: var(--color-info-50);     color: var(--color-info-600); }
  &.tt-success { background: var(--color-success-50);  color: var(--color-success-600); }
  &.tt-danger  { background: var(--color-danger-50);   color: var(--color-danger-600); }
}
.task-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.task-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-sub {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

/* 状态药丸 */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  &.st-pending  { background: var(--gray-100);          color: var(--gray-600); }
  &.st-running  { background: var(--brand-50);          color: var(--brand-600); }
  &.st-succeeded{ background: var(--color-success-50);  color: var(--color-success-600); }
  &.st-failed   { background: var(--color-danger-50);   color: var(--color-danger-600); }
  &.st-canceled { background: var(--color-warning-50);  color: var(--color-warning-600); }
}

/* ============ 进度条（自绘） ============ */
.progress-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}
.progress-bar {
  position: relative;
  width: 100%;
  height: 6px;
  background: var(--gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.6s var(--ease-out);
  background: var(--brand-500);
}
.progress-bar.pg-running .progress-fill {
  background: linear-gradient(
    90deg,
    var(--brand-400) 0%,
    var(--brand-500) 50%,
    var(--brand-400) 100%
  );
  background-size: 200% 100%;
  animation: progress-shimmer 1.6s linear infinite;
}
.progress-bar.pg-succeeded .progress-fill { background: var(--color-success-500); }
.progress-bar.pg-failed .progress-fill    { background: var(--color-danger-500); }
.progress-bar.pg-canceled .progress-fill  { background: var(--color-warning-500); }
.progress-bar.pg-pending .progress-fill   { background: var(--gray-300); }

@keyframes progress-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.progress-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}
.progress-pct {
  font-weight: var(--font-weight-semibold);
  font-family: var(--font-mono);
  flex-shrink: 0;
}
.stage-hint {
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 状态色文字（用于百分比） */
.txt-brand   { color: var(--brand-600); }
.txt-info    { color: var(--color-info-600); }
.txt-success { color: var(--color-success-600); }
.txt-danger  { color: var(--color-danger-600); }
.txt-warning { color: var(--color-warning-600); }

.muted-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

/* ============ 产出/耗时列 ============ */
.output-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  background: var(--color-success-50);
  color: var(--color-success-600);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  max-width: 100%;

  > i { font-size: 12px; flex-shrink: 0; }
  strong {
    font-size: 13px;
    font-weight: var(--font-weight-bold);
    margin: 0 1px;
    flex-shrink: 0;
  }
  span {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
.output-empty {
  font-size: 11px;
  color: var(--text-placeholder);
}
.output-canceled {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  background: var(--color-warning-50);
  color: var(--color-warning-600);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
}
.output-running {
  font-size: 11px;
  color: var(--text-placeholder);
}
.output-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);

  > i { font-size: 12px; }
}
.output-err {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-danger-600);
  font-weight: var(--font-weight-medium);

  > i { font-size: 12px; }
}
.model-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--gray-50);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-light);
}

/* ============ 操作列 ============ */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 13px;
  vertical-align: -2px;
}

/* ============ 分页 ============ */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) var(--space-2);
  border-top: 1px solid var(--border-light);
}

/* ============ 表格行交互 + 头部 ============ */
:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  tr.task-row {
    cursor: pointer;
    transition: background-color 0.15s ease;

    &:hover > td {
      background-color: var(--brand-50) !important;
    }
  }

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
    letter-spacing: 0.3px;
  }
  td.el-table__cell {
    padding: 12px 0;
  }
}
</style>
