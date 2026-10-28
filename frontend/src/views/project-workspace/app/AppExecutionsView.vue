<template>
  <div class="app-report-page">
    <!-- 页头 -->
    <AppPageHeader
      title="App 测试报表"
      description="单用例 / 套件双视角的执行数据、趋势分析与执行记录"
      :breadcrumbs="['App 自动化', '执行记录']"
      icon="i-solar-chart-square-bold"
      :illustration="illustTestApp"
      class="report-header"
    />

    <!-- 维度切换 + 内容 tabs -->
    <el-card class="search-card" shadow="never">
      <div class="dim-bar">
        <el-radio-group v-model="viewTab" size="default">
          <el-radio-button value="case">单用例视角</el-radio-button>
          <el-radio-button value="suite">套件视角</el-radio-button>
        </el-radio-group>

        <el-tag v-if="viewTab === 'case' && caseFilter" closable type="warning" @close="clearCaseFilter">
          用例：{{ caseFilterName || `#${caseFilter}` }}
        </el-tag>
        <el-tag v-if="viewTab === 'suite' && suiteFilter" closable type="warning" @close="clearSuiteFilter">
          套件：{{ suiteFilterName || `#${suiteFilter}` }}
        </el-tag>

        <el-form v-if="contentTab === 'records'" :inline="true" class="search-form">
          <el-form-item label="状态">
            <el-select
              v-model="statusFilter"
              placeholder="全部"
              clearable
              style="width: 120px"
              @change="reloadCurrent"
            >
              <el-option label="排队中" value="pending" />
              <el-option label="执行中" value="running" />
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <el-tabs v-model="contentTab" class="content-tabs">
        <el-tab-pane name="report">
          <template #label>
            <span class="tab-label"><i class="i-solar-chart-square-bold tab-icon" />图表数据</span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="records">
          <template #label>
            <span class="tab-label"><i class="i-solar-list-bold tab-icon" />执行记录</span>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 图表数据 tab -->
    <AppExecutionsReport
      v-show="contentTab === 'report'"
      :project-id="projectId"
      :dimension="viewTab"
      @drill="onReportDrill"
      @filter-failed="onReportFilterFailed"
    />

    <!-- 执行记录 tab -->
    <template v-if="contentTab === 'records'">
      <!-- 套件执行记录 -->
      <el-card v-if="viewTab === 'suite'" class="table-card" shadow="never">
        <el-table v-loading="suiteLoading" :data="suiteExecutions" stripe style="width: 100%">
          <el-table-column label="套件名称" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <el-text type="primary" class="name-link" @click="goSuiteDetail(row)">
                {{ row.suite_name || `套件 #${row.suite_id}` }}
              </el-text>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="通过/总数" width="100" align="center">
            <template #default="{ row }">{{ row.passed_count }}/{{ row.total_cases }}</template>
          </el-table-column>
          <el-table-column label="失败" width="80" align="center">
            <template #default="{ row }">
              <span :style="row.failed_count > 0 ? 'color: var(--el-color-danger)' : ''">
                {{ row.failed_count }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="设备" min-width="150">
            <template #default="{ row }">
              <el-tooltip :content="row.device_udid" placement="top">
                <span :class="row.device_name ? '' : 'mono-text'">
                  {{ row.device_name || row.device_udid }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="系统" width="80" align="center">
            <template #default="{ row }">
              <span v-if="row.device_platform" class="platform-chip" :class="`is-${row.device_platform}`">
                {{ PLATFORM_LABEL[row.device_platform] || row.device_platform }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="触发" width="70" align="center">
            <template #default="{ row }">
              {{ row.trigger_type === 'scheduled' ? '定时' : '手动' }}
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="90" align="center">
            <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="170" fixed="right" align="center">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button v-if="isActiveRow(row)" size="small" type="success" plain @click="openLive(row, `套件实时查看 · ${row.suite_name || '#' + row.suite_id}`)">
                  <i class="i-solar-eye-bold btn-icon-sm" />实时
                </el-button>
                <el-button size="small" @click="openSuiteDetail(row)">
                  <i class="i-solar-list-check-bold btn-icon-sm" />明细
                </el-button>
              </div>
            </template>
          </el-table-column>
          <template #empty>
            <AppEmpty v-if="!suiteLoading" scene="data" description="还没有套件执行记录。去「测试套件」编排并执行。" />
          </template>
        </el-table>
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="suitePagination.page"
            v-model:page-size="suitePagination.pageSize"
            :total="suitePagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            background
            @size-change="loadSuiteExecutions"
            @current-change="loadSuiteExecutions"
          />
        </div>
      </el-card>

      <!-- 单用例执行记录 -->
      <el-card v-else class="table-card" shadow="never">
        <el-table v-loading="caseLoading" :data="caseExecutions" stripe style="width: 100%">
          <el-table-column label="#" width="70">
            <template #default="{ row }">
              <span class="mono-text">#{{ row.id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="用例" min-width="130">
            <template #default="{ row }">
              <span>{{ row.script_name || `用例 #${row.script_id}` }}</span>
              <el-tag v-if="row.suite_execution_id" size="small" type="warning" effect="plain" class="src-tag">
                套件
              </el-tag>
              <el-tag v-else size="small" type="info" effect="plain" class="src-tag">单跑</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="设备" min-width="150">
            <template #default="{ row }">
              <el-tooltip :content="row.device_udid" placement="top">
                <span :class="row.device_name ? '' : 'mono-text'">
                  {{ row.device_name || row.device_udid }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="系统" width="80" align="center">
            <template #default="{ row }">
              <span
                v-if="row.device_platform || row.script_platform"
                class="platform-chip"
                :class="`is-${row.device_platform || row.script_platform}`"
              >
                {{ PLATFORM_LABEL[row.device_platform || row.script_platform] || row.device_platform || row.script_platform }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="90" align="center">
            <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="170" fixed="right" align="center">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button v-if="isActiveRow(row)" size="small" type="success" plain @click="openLive(row, `回放实时查看 · ${row.script_name || '用例 #' + row.script_id}`)">
                  <i class="i-solar-eye-bold btn-icon-sm" />实时
                </el-button>
                <el-button size="small" :disabled="isActiveRow(row)" @click="openReport(row)">
                  <i class="i-solar-document-text-bold btn-icon-sm" />报告
                </el-button>
              </div>
            </template>
          </el-table-column>
          <template #empty>
            <AppEmpty v-if="!caseLoading" scene="data" description="还没有执行记录。去「测试用例」选一条回放。" />
          </template>
        </el-table>
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="casePagination.page"
            v-model:page-size="casePagination.pageSize"
            :total="casePagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="loadCaseExecutions"
            @current-change="loadCaseExecutions"
          />
        </div>
      </el-card>
    </template>

    <!-- 套件执行明细（下钻用例级） -->
    <el-drawer
      v-model="detailDrawer"
      :title="`套件执行 #${suiteDetail?.id ?? ''} · ${suiteDetail?.suite_name ?? ''}`"
      size="680px"
    >
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="suiteDetail">
          <div class="detail-summary">
            <el-tag :type="tagType(suiteDetail.status)" effect="light">
              {{ statusLabel(suiteDetail.status) }}
            </el-tag>
            <span class="ds-item">通过 <b class="pass">{{ suiteDetail.passed_count }}</b></span>
            <span class="ds-item">失败 <b class="fail">{{ suiteDetail.failed_count }}</b></span>
            <span class="ds-item">跳过 <b>{{ suiteDetail.skipped_count }}</b></span>
            <span class="ds-item">共 {{ suiteDetail.total_cases }} 条</span>
            <span class="ds-item muted-text">{{ fmtDuration(suiteDetail.duration_ms) }}</span>
          </div>
          <div v-if="suiteDetail.error" class="detail-error">{{ suiteDetail.error }}</div>

          <el-table :data="suiteDetail.cases" size="small" stripe class="detail-table">
            <el-table-column label="顺序" width="60" align="center">
              <template #default="{ $index }">
                <span class="mono-text">{{ $index + 1 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="用例" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.script_name || `用例 #${row.script_id}` }}</template>
            </el-table-column>
            <el-table-column label="状态" width="96" align="center">
              <template #default="{ row }">
                <el-tag :type="tagType(row.status)" size="small" effect="light">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="86" align="center">
              <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" text :disabled="!row.report_path" @click="openReport(row)">
                  报告
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>

    <!-- 实时查看（观战直播 + SSE 日志） -->
    <el-drawer
      v-model="liveDrawer"
      :title="liveTarget?.title || '执行实时查看'"
      size="860px"
      destroy-on-close
    >
      <ExecutionLiveView
        v-if="liveTarget"
        :project-id="projectId"
        :udid="liveTarget.udid"
        :task-id="liveTarget.taskId"
        @finished="onLiveFinished"
      />
    </el-drawer>

    <!-- 报告（独立源签名 URL，跨源 iframe） -->
    <el-dialog v-model="reportDialog" title="执行报告" width="90%" top="4vh" class="report-dialog" @closed="closeReport">
      <div v-loading="reportLoading" class="report-body">
        <div v-if="reportError" class="report-error">{{ reportError }}</div>
        <template v-else-if="reportUrl">
          <div class="report-note">
            <i class="i-solar-shield-check-bold" />
            <span>报告在独立源中渲染（与平台会话隔离），也可
              <a :href="reportUrl" target="_blank" rel="noopener noreferrer">新窗口打开</a>。
            </span>
          </div>
          <iframe
            :src="reportUrl"
            class="report-frame"
            sandbox="allow-scripts allow-same-origin"
            referrerpolicy="no-referrer"
          />
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * App 测试报表页 —— 与接口自动化 ApiReportView 同构。
 *
 * 双视角（单用例/套件）×（图表数据 / 执行记录）tabs；图表 tab 复用
 * AppExecutionsReport（趋势/通过率/失败排行/分布），排行点击下钻联动
 * 记录筛选。App 特有能力全保留：运行中记录的实时查看抽屉（观战直播 +
 * SSE 日志，提交跳转 live=1 自动打开）、独立源报告弹窗、套件明细下钻。
 */
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import {
  appTestApi,
  PLATFORM_LABEL,
  type AppExecution,
  type AppSuiteExecution,
  type AppSuiteExecutionDetail,
} from '@/api/appTest'
import { AppPageHeader, AppEmpty } from '@/components/common'
import ExecutionLiveView from '@/components/app-test/ExecutionLiveView.vue'
import AppExecutionsReport from './components/AppExecutionsReport.vue'
import illustTestApp from '@/assets/illustrations/test-app.svg'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ==================== 维度与内容 tab ====================
type ViewTab = 'case' | 'suite'
const viewTab = ref<ViewTab>(route.query.view === 'suite' ? 'suite' : 'case')
// 提交跳转（live/明细）直接落记录 tab，平时默认图表
const contentTab = ref<'report' | 'records'>(
  route.query.live === '1' || route.query.suite_execution_id ? 'records' : 'report',
)

// ==================== 筛选 ====================
const statusFilter = ref('')
const caseFilter = ref<number | null>(null)
const caseFilterName = ref('')
const suiteFilter = ref<number | null>(null)
const suiteFilterName = ref('')

const clearCaseFilter = () => {
  caseFilter.value = null
  caseFilterName.value = ''
  reloadCurrent()
}
const clearSuiteFilter = () => {
  suiteFilter.value = null
  suiteFilterName.value = ''
  reloadCurrent()
}

// ==================== 状态映射/工具 ====================
const STATUS_META: Record<string, { label: string; type: string }> = {
  pending: { label: '排队中', type: 'info' },
  running: { label: '执行中', type: 'warning' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}
const statusLabel = (s: string) => STATUS_META[s]?.label || s
const tagType = (s: string) =>
  (STATUS_META[s]?.type || 'info') as 'success' | 'warning' | 'danger' | 'info'

function isActiveRow(row: { status: string }): boolean {
  return row.status === 'pending' || row.status === 'running'
}

const formatDateTime = (v?: string | null) => {
  if (!v) return '-'
  const d = new Date(v)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const fmtDuration = (ms?: number | null) => {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  return `${m}m${((ms % 60000) / 1000).toFixed(0)}s`
}

// ==================== 单用例执行记录 ====================
const caseLoading = ref(false)
const caseExecutions = ref<AppExecution[]>([])
const casePagination = reactive({ page: 1, pageSize: 20, total: 0 })

const loadCaseExecutions = async (showLoading = true) => {
  if (showLoading) caseLoading.value = true
  try {
    const res = await appTestApi.listExecutions(projectId.value, {
      script_id: caseFilter.value || undefined,
      status: statusFilter.value || undefined,
      page: casePagination.page,
      page_size: casePagination.pageSize,
    })
    caseExecutions.value = res.items
    casePagination.total = res.total
  } catch {
    /* 拦截器已提示 */
  } finally {
    if (showLoading) caseLoading.value = false
  }
}

// ==================== 套件执行记录 ====================
const suiteLoading = ref(false)
const suiteExecutions = ref<AppSuiteExecution[]>([])
const suitePagination = reactive({ page: 1, pageSize: 20, total: 0 })

const loadSuiteExecutions = async (showLoading = true) => {
  if (showLoading) suiteLoading.value = true
  try {
    const res = await appTestApi.listSuiteExecutions(projectId.value, {
      suite_id: suiteFilter.value || undefined,
      status: statusFilter.value || undefined,
      page: suitePagination.page,
      page_size: suitePagination.pageSize,
    })
    suiteExecutions.value = res.items
    suitePagination.total = res.total
  } catch {
    /* 拦截器已提示 */
  } finally {
    if (showLoading) suiteLoading.value = false
  }
}

const reloadCurrent = () => {
  casePagination.page = 1
  suitePagination.page = 1
  if (viewTab.value === 'case') void loadCaseExecutions()
  else void loadSuiteExecutions()
}

watch(viewTab, () => {
  statusFilter.value = ''
  reloadCurrent()
})

// ==================== 报表联动 ====================
const onReportFilterFailed = () => {
  statusFilter.value = 'failed'
  contentTab.value = 'records'
  reloadCurrent()
}

const onReportDrill = (item: { id: number; name: string }) => {
  if (viewTab.value === 'case') {
    caseFilter.value = item.id
    caseFilterName.value = item.name
  } else {
    suiteFilter.value = item.id
    suiteFilterName.value = item.name
  }
  contentTab.value = 'records'
  reloadCurrent()
}

// ==================== 轮询（任一视角有在跑记录时 10s 刷） ====================
let timer: ReturnType<typeof setInterval> | null = null
const hasActive = computed(() => {
  const list = viewTab.value === 'case' ? caseExecutions.value : suiteExecutions.value
  return list.some((e) => e.status === 'pending' || e.status === 'running')
})
watch(hasActive, (active) => {
  if (active && !timer) {
    timer = setInterval(() => {
      if (viewTab.value === 'case') void loadCaseExecutions(false)
      else {
        void loadSuiteExecutions(false)
        if (suiteDetail.value) void refreshSuiteDetail(suiteDetail.value.id)
      }
    }, 10_000)
  } else if (!active && timer) {
    clearInterval(timer)
    timer = null
  }
})

// ==================== 套件执行明细 ====================
const detailDrawer = ref(false)
const suiteDetail = ref<AppSuiteExecutionDetail | null>(null)
const detailLoading = ref(false)

async function refreshSuiteDetail(executionId: number) {
  try {
    suiteDetail.value = await appTestApi.getSuiteExecution(projectId.value, executionId)
  } catch {
    /* 拦截器已提示 */
  }
}

async function openSuiteDetail(e: { id: number }) {
  detailDrawer.value = true
  detailLoading.value = true
  suiteDetail.value = null
  await refreshSuiteDetail(e.id)
  detailLoading.value = false
}

function goSuiteDetail(row: AppSuiteExecution) {
  router.push({ name: 'AppSuiteDetail', params: { id: projectId.value, suiteId: row.suite_id } })
}

// ==================== 实时查看 ====================
const liveDrawer = ref(false)
const liveTarget = ref<{ udid: string; taskId: number; title: string } | null>(null)

function openLive(row: { ai_task_id?: string | null; device_udid: string }, title: string) {
  const taskId = Number(row.ai_task_id)
  if (!taskId) return
  liveTarget.value = { udid: row.device_udid, taskId, title }
  liveDrawer.value = true
}

function onLiveFinished() {
  if (viewTab.value === 'case') void loadCaseExecutions(false)
  else {
    void loadSuiteExecutions(false)
    if (suiteDetail.value) void refreshSuiteDetail(suiteDetail.value.id)
  }
}

// ==================== 报告查看（独立源签名 URL） ====================
const reportDialog = ref(false)
const reportUrl = ref<string | null>(null)
const reportLoading = ref(false)
const reportError = ref('')

async function openReport(e: { id: number; report_path?: string | null }) {
  reportDialog.value = true
  reportError.value = ''
  reportUrl.value = null
  if (!e.report_path) {
    reportError.value = '该执行暂无报告（可能失败于连接阶段或报告未生成）'
    return
  }
  reportLoading.value = true
  try {
    const url = await appTestApi.getReportUrl(projectId.value, e.id)
    if (url) reportUrl.value = url
    else reportError.value = '报告加载失败（签名 URL 获取失败）'
  } finally {
    reportLoading.value = false
  }
}

function closeReport() {
  reportDialog.value = false
  reportUrl.value = null
}

// ==================== 初始化（含提交跳转 query） ====================
if (route.query.live === '1' && route.query.task_id && route.query.udid) {
  liveTarget.value = {
    udid: String(route.query.udid),
    taskId: Number(route.query.task_id),
    title: String(route.query.title || '执行实时查看'),
  }
  liveDrawer.value = true
} else if (viewTab.value === 'suite' && route.query.suite_execution_id) {
  const sid = Number(route.query.suite_execution_id)
  if (sid) void openSuiteDetail({ id: sid })
}

reloadCurrent()

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.report-header {
  margin-bottom: 16px;
}

.app-report-page {
  min-height: calc(100vh - 60px);
  padding: 20px;

  .search-card,
  .table-card {
    margin-bottom: 20px;

    :deep(.el-card__body) {
      padding: 20px;
    }
  }

  .name-link {
    cursor: pointer;
    font-weight: 500;
    &:hover { text-decoration: underline; }
  }

  .row-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
    :deep(.el-button) { margin: 0; }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
  }
}

.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

.dim-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;

  .search-form {
    margin-bottom: 0;
    :deep(.el-form-item) { margin-bottom: 0; }
  }
}

.content-tabs {
  margin-top: 12px;
  :deep(.el-tabs__header) { margin-bottom: 0; }

  .tab-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    .tab-icon { font-size: 16px; }
  }
}

.mono-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.muted-text { color: var(--text-placeholder); }
.src-tag { margin-left: 6px; }

/* 系统芯片（与用例页 platform-chip 同款） */
.platform-chip {
  display: inline-block;
  padding: 0 6px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  line-height: 18px;
  &.is-android { background: var(--brand-50); color: var(--brand-600); }
  &.is-harmony { background: var(--color-info-50); color: var(--color-info-600); }
  &.is-ios { background: var(--gray-100); color: var(--gray-700); }
}

/* 套件明细抽屉 */
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}
.detail-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;

  .ds-item {
    font-size: var(--font-size-sm);
    color: var(--text-regular);
    b { font-weight: var(--font-weight-semibold); }
    b.pass { color: var(--color-success-600); }
    b.fail { color: var(--color-danger-600); }
  }
}
.detail-error {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-danger-50);
  color: var(--color-danger-600);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}

/* 报告弹窗 */
.report-body {
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.report-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  i { color: var(--brand-500); }
  a { color: var(--brand-600); }
}
.report-frame {
  width: 100%;
  height: 78vh;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fff;
}
.report-error {
  margin: auto;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
</style>
