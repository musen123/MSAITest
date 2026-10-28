<template>
  <div class="operation-logs-view">
    <!-- 页头 -->
    <div class="page-header">
      <div class="page-title">
        <div class="title-row">
          <i class="i-solar-notebook-bookmark-bold title-icon" />
          <h2>操作日志</h2>
        </div>
        <p class="page-description">记录系统中的用户操作行为，便于审计与安全追溯</p>
      </div>
      <div class="page-actions">
        <el-button @click="handleRefresh">
          <i class="i-solar-refresh-bold" />
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡（真实数据） -->
    <div v-loading="todayStatsLoading" class="stat-row">
      <AppStatCard
        label="今日操作"
        :value="todayStats.total"
        :trend="todayStatsTrend.total"
        icon-name="i-solar-notebook-bold"
        color="success"
      />
      <AppStatCard
        label="今日用户数"
        :value="todayStats.users"
        :trend="todayStatsTrend.users"
        icon-name="i-solar-user-speak-bold"
        color="info"
      />
      <AppStatCard
        label="今日操作类型"
        :value="todayStats.actions"
        :trend="todayStatsTrend.actions"
        icon-name="i-solar-cursor-bold"
        color="purple"
      />
      <AppStatCard
        label="异常操作"
        :value="todayStats.abnormal"
        :trend="todayStatsTrend.abnormal"
        icon-name="i-solar-shield-warning-bold"
        color="warning"
      />
    </div>

    <!-- 筛选 + 表格 -->
    <AppSectionCard>
      <template #header>
        <span class="section-title">日志列表</span>
      </template>

      <!-- 筛选条件 -->
      <div class="filter-bar">
        <el-form :inline="true" :model="filterForm" class="filter-form">
          <el-form-item label="操作模块">
            <el-input
              v-model="filterForm.module"
              placeholder="请输入操作模块"
              clearable
              class="filter-input"
            />
          </el-form-item>
          <el-form-item label="操作类型">
            <el-select
              v-model="filterForm.action"
              placeholder="请选择操作类型"
              clearable
              filterable
              class="filter-select"
            >
              <el-option
                v-for="item in actionOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              class="filter-daterange"
              @change="handleDateRangeChange"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">
              <i class="i-solar-magnifer-bold" />
              查询
            </el-button>
            <el-button @click="resetFilter">
              <i class="i-solar-restart-bold" />
              重置
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 日志列表 -->
      <el-table
        v-loading="loading"
        :data="logsData"
        class="log-table"
        empty-text="暂无日志"
      >
        <el-table-column prop="id" label="ID" width="80" />

        <el-table-column label="操作人" min-width="160">
          <template #default="{ row }">
            <div class="user-cell">
              <AppAvatar :name="row.username || '未知'" :size="32" />
              <span class="user-name">{{ row.username || '-' }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作模块" min-width="120">
          <template #default="{ row }">
            <span
              class="module-tag"
              :style="{
                background: moduleStyle(row.module).bg,
                color: moduleStyle(row.module).fg,
              }"
            >
              {{ row.module }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作类型" width="100">
          <template #default="{ row }">
            <span class="status-pill" :class="actionPillClass(row.action)">
              {{ getActionLabel(row.action) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="操作描述" min-width="240">
          <template #default="{ row }">
            <span class="desc-text">{{ row.description || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="请求方法" width="90" align="center">
          <template #default="{ row }">
            <span
              v-if="row.request_method"
              class="method-tag"
              :class="`method-${(row.request_method || '').toLowerCase()}`"
            >
              {{ row.request_method }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="状态码" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.response_status != null" class="status-pill" :class="statusPillClass(row.response_status)">
              {{ row.response_status }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="耗时(ms)" width="100" align="right">
          <template #default="{ row }">
            <span class="duration-cell">
              {{ row.execution_time ?? '-' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="IP地址" width="140">
          <template #default="{ row }">
            <span class="ip-text">{{ row.ip_address || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click="handleViewDetail(row)">
                <i class="i-solar-eye-linear" />
                详情
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          background
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </AppSectionCard>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      title="操作日志详情"
      width="700px"
      :destroy-on-close="true"
      class="log-detail-dialog"
    >
      <div v-loading="detailLoading" class="detail-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="日志ID">{{ detailData.id }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ detailData.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作模块">{{ detailData.module }}</el-descriptions-item>
          <el-descriptions-item label="操作类型">
            <span class="status-pill" :class="actionPillClass(detailData.action || '')">
              {{ getActionLabel(detailData.action || '') }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="请求方法">
            <span
              v-if="detailData.request_method"
              class="method-tag"
              :class="`method-${(detailData.request_method || '').toLowerCase()}`"
            >
              {{ detailData.request_method }}
            </span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="响应状态码">
            <span
              v-if="detailData.response_status"
              class="status-pill"
              :class="statusPillClass(detailData.response_status)"
            >
              {{ detailData.response_status }}
            </span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="执行耗时">
            {{ detailData.execution_time != null ? `${detailData.execution_time} ms` : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ detailData.ip_address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作描述" :span="2">{{ detailData.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="请求URL" :span="2">{{ detailData.request_url || '-' }}</el-descriptions-item>
          <el-descriptions-item label="User-Agent" :span="2">{{ detailData.user_agent || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作时间" :span="2">{{ formatTime(detailData.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 请求参数 -->
        <div v-if="detailData.request_params" class="request-params-section">
          <h4 class="section-title">请求参数</h4>
          <div class="params-content">
            <pre>{{ formatParams(detailData.request_params) }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getOperationLogs, getOperationLogOptions, getOperationLogDetail, getOperationLogStats } from '@/api/logs'
import { AppStatCard, AppSectionCard, AppAvatar } from '@/components/common'

interface LogItem {
  id: number
  username: string | null
  module: string
  action: string
  description: string | null
  request_method: string | null
  request_url: string | null
  request_params: string | null
  response_status: number | null
  ip_address: string | null
  user_agent: string | null
  execution_time: number | null
  created_at: string | null
}

const filterForm = ref({
  module: '',
  action: '',
  start_time: undefined as number | undefined,
  end_time: undefined as number | undefined,
})

const actionOptions = ref<{ label: string; value: string }[]>([])
const dateRange = ref<[string, string] | null>(null)
const loading = ref(false)
const logsData = ref<LogItem[]>([])
const pagination = ref({ current: 1, pageSize: 10 })
const total = ref(0)

// 详情抽屉
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<Partial<LogItem>>({})

const getActionLabel = (action: string) => {
  // 与后端 OperationLog.Action 枚举 + 中间件 _ACTION_VALUES 对齐
  // 后端实际写入：query / create / update / delete / login / logout / export / import
  const map: Record<string, string> = {
    query:   '查询',
    create:  '创建',
    update:  '更新',
    delete:  '删除',
    login:   '登录',
    logout:  '登出',
    export:  '导出',
    import:  '导入',
    authorize: '授权',
  }
  return map[action] || action
}

/** 操作类型 → status-pill class（遵循设计系统状态徽章规范） */
const actionPillClass = (action: string): string => {
  const map: Record<string, string> = {
    query:   'is-running',
    create:  'is-passed',
    update:  'is-pending',
    delete:  'is-failed',
    login:   'is-passed',
    logout:  'is-blocked',
    export:  'is-running',
    import:  'is-running',
    authorize: 'is-passed',
  }
  return map[action] || 'is-blocked'
}

/** HTTP 状态码 → status-pill class */
const statusPillClass = (status: number): string => {
  if (status >= 200 && status < 300) return 'is-passed'
  if (status >= 300 && status < 400) return 'is-running'
  if (status >= 400 && status < 500) return 'is-pending'
  return 'is-failed'
}

/** 模块 → 配色（背景色 + 前景色），循环使用设计系统色板 */
const moduleStyleMap: Record<string, { bg: string; fg: string }> = {
  '用户管理':  { bg: 'var(--color-info-50, #eff6ff)',     fg: 'var(--color-info-600, #2563eb)' },
  '项目管理':  { bg: 'var(--color-purple-50, #faf5ff)',   fg: 'var(--color-purple-600, #9333ea)' },
  '角色管理':  { bg: 'var(--color-info-50, #eff6ff)',     fg: 'var(--color-info-600, #2563eb)' },
  '权限管理':  { bg: 'var(--color-warning-50, #fffbeb)',  fg: 'var(--color-warning-600, #d97706)' },
  '测试管理':  { bg: 'var(--color-success-50, #f0fdf4)',  fg: 'var(--color-success-600, #16a34a)' },
  '测试报告':  { bg: 'rgba(6, 182, 212, 0.10)',           fg: 'var(--color-cyan-500)' },
  '登录系统':  { bg: 'var(--color-success-50, #f0fdf4)',  fg: 'var(--color-success-600, #16a34a)' },
  '系统设置':  { bg: 'var(--color-warning-50, #fffbeb)',  fg: 'var(--color-warning-600, #d97706)' },
}

const moduleStyle = (moduleName: string): { bg: string; fg: string } =>
  moduleStyleMap[moduleName] || {
    bg: 'var(--gray-100, #f3f4f6)',
    fg: 'var(--gray-600, #4b5563)',
  }

/** 今日统计（真实数据，调用后端聚合接口） */
interface TodayStatsState {
  total: number
  users: number
  actions: number
  abnormal: number
}

const todayStats = ref<TodayStatsState>({
  total: 0,
  users: 0,
  actions: 0,
  abnormal: 0,
})
const todayStatsTrend = ref<{ total?: number; users?: number; actions?: number; abnormal?: number }>({})
const todayStatsLoading = ref(false)

/** 计算环比百分比（(cur - prev) / prev * 100），prev 为 0 时返回 undefined */
const calcTrendPct = (cur: number, prev: number | undefined): number | undefined => {
  if (prev === undefined || prev === null || prev === 0) return undefined
  return Number((((cur - prev) / prev) * 100).toFixed(1))
}

/** 拉取今日操作日志聚合统计 */
const fetchTodayStats = async () => {
  todayStatsLoading.value = true
  try {
    const now = new Date()
    const startOfDay = new Date(now)
    startOfDay.setHours(0, 0, 0, 0)
    const startTime = Math.floor(startOfDay.getTime() / 1000)
    const endTime = Math.floor(now.getTime() / 1000)

    const res = await getOperationLogStats({
      start_time: startTime,
      end_time: endTime,
    })

    const data = res?.data
    if (data) {
      todayStats.value = {
        total: data.total ?? 0,
        users: data.users ?? 0,
        actions: data.actions ?? 0,
        abnormal: data.abnormal ?? 0,
      }
      todayStatsTrend.value = {
        total: calcTrendPct(data.total ?? 0, data.prev_total),
        users: calcTrendPct(data.users ?? 0, data.prev_users),
        actions: calcTrendPct(data.actions ?? 0, data.prev_actions),
        abnormal: calcTrendPct(data.abnormal ?? 0, data.prev_abnormal),
      }
    }
  } catch (error) {
    console.warn('今日统计接口未就绪，等待后端实现:', error)
    todayStats.value = { total: 0, users: 0, actions: 0, abnormal: 0 }
    todayStatsTrend.value = {}
  } finally {
    todayStatsLoading.value = false
  }
}

const formatTime = (val: string | null | undefined) => {
  if (!val) return ''
  return new Date(val).toLocaleString('zh-CN')
}

/** 格式化请求参数，尝试美化 JSON */
const formatParams = (params: string | null) => {
  if (!params) return ''
  try {
    return JSON.stringify(JSON.parse(params), null, 2)
  } catch {
    return params
  }
}

const handleDateRangeChange = (val: [string, string] | null) => {
  if (val) {
    const startDate = new Date(val[0])
    const endDate = new Date(val[1])
    startDate.setHours(0, 0, 0, 0)
    endDate.setHours(23, 59, 59, 999)
    filterForm.value.start_time = Math.floor(startDate.getTime() / 1000)
    filterForm.value.end_time = Math.floor(endDate.getTime() / 1000)
  } else {
    filterForm.value.start_time = undefined
    filterForm.value.end_time = undefined
  }
}

const loadOptions = async () => {
  try {
    const res = await getOperationLogOptions()
    actionOptions.value = res.data.actions
  } catch {
    // 与后端 OperationLog.Action 枚举对齐（fallback）
    actionOptions.value = [
      { label: '查询', value: 'query' },
      { label: '创建', value: 'create' },
      { label: '更新', value: 'update' },
      { label: '删除', value: 'delete' },
      { label: '登录', value: 'login' },
      { label: '登出', value: 'logout' },
      { label: '导出', value: 'export' },
      { label: '导入', value: 'import' },
    ]
  }
}

const loadLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      module: filterForm.value.module || undefined,
      action: filterForm.value.action || undefined,
      start_time: filterForm.value.start_time,
      end_time: filterForm.value.end_time,
    }
    const response = await getOperationLogs(params)
    logsData.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    console.error('获取操作日志失败:', error)
  } finally {
    loading.value = false
  }
}

/** 查看详情 */
const handleViewDetail = async (row: LogItem) => {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = {}
  try {
    const res = await getOperationLogDetail(row.id)
    detailData.value = res.data
  } catch (e) {
    console.error('获取日志详情失败:', e)
  } finally {
    detailLoading.value = false
  }
}

const handleRefresh = () => loadLogs()
const handleSearch = () => {
  pagination.value.current = 1
  loadLogs()
}
const resetFilter = () => {
  filterForm.value = { module: '', action: '', start_time: undefined, end_time: undefined }
  dateRange.value = null
  pagination.value.current = 1
  loadLogs()
}
const handleCurrentChange = (current: number) => {
  pagination.value.current = current
  loadLogs()
}
const handleSizeChange = (size: number) => {
  pagination.value.pageSize = size
  pagination.value.current = 1
  loadLogs()
}

onMounted(() => {
  loadOptions()
  loadLogs()
  fetchTodayStats()
})
</script>

<style scoped lang="scss">
.operation-logs-view {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// ==================== 页头 ====================
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;

  h2 {
    font-size: 22px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title-icon {
  font-size: 22px;
  color: var(--brand-500);
}

.page-description {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.page-actions {
  display: flex;
  gap: 12px;
}

// ==================== 统计卡片 ====================
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

// ==================== 区块标题 ====================
.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

// ==================== 筛选区 ====================
.filter-bar {
  margin-bottom: 16px;
}

.filter-form {
  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.filter-input {
  width: 220px;
}

.filter-select {
  width: 160px;
}

.filter-daterange {
  width: 260px;
}

// ==================== 表格 ====================
.log-table {
  :deep(th) {
    background: var(--bg-hover, #f8fafc) !important;
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 13px;
  }

  :deep(td) {
    font-size: 13px;
  }
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-name {
  font-size: 13px;
  color: var(--text-regular);
  font-weight: 500;
}

.module-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full, 9999px);
  font-size: 12px;
  font-weight: 500;
}

.desc-text {
  color: var(--text-secondary);
  line-height: 1.5;
}

// ==================== 请求方法 tag ====================
.method-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  padding: 2px 8px;
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;

  &.method-get    { background: var(--color-info-50, #eff6ff);    color: var(--color-info-600, #2563eb); }
  &.method-post   { background: var(--color-success-50, #f0fdf4); color: var(--color-success-600, #16a34a); }
  &.method-put    { background: var(--color-warning-50, #fffbeb); color: var(--color-warning-600, #d97706); }
  &.method-patch  { background: var(--color-warning-50, #fffbeb); color: var(--color-warning-600, #d97706); }
  &.method-delete { background: var(--color-danger-50, #fef2f2);  color: var(--color-danger-600, #dc2626); }
}

// ==================== 状态 pill（设计系统规范） ====================
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full, 9999px);
  font-size: 12px;
  font-weight: var(--font-weight-medium, 500);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

  &.is-passed  { background: var(--color-success-50, #f0fdf4);  color: var(--color-success-600, #16a34a); }
  &.is-failed  { background: var(--color-danger-50, #fef2f2);   color: var(--color-danger-600, #dc2626); }
  &.is-blocked { background: var(--gray-100, #f3f4f6);          color: var(--gray-600, #4b5563); }
  &.is-running { background: var(--color-info-50, #eff6ff);     color: var(--color-info-600, #2563eb); }
  &.is-pending { background: var(--color-warning-50, #fffbeb);  color: var(--color-warning-600, #d97706); }
  &.is-done    { background: var(--color-purple-50, #faf5ff);   color: var(--color-purple-600, #9333ea); }
}

.duration-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--text-regular);
}

.ip-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--text-regular);
}

// ==================== 分页 ====================
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}

// ==================== 详情弹框 ====================
:deep(.log-detail-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

.detail-content {
  .params-content {
    background: var(--gray-50, #f9fafb);
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 8px;
    padding: 12px;
    max-height: 400px;
    overflow-y: auto;

    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-all;
      font-size: 13px;
      line-height: 1.6;
      color: var(--text-regular);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
  }
}

.section-title {
  margin: 20px 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.request-params-section {
  margin-top: 8px;
}

@media (max-width: 768px) {
  .stat-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
