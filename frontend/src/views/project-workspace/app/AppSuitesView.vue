<template>
  <div class="app-suites-page">
    <!-- ============ 页头 ============ -->
    <AppPageHeader
      icon="i-app-test-suite"
      :illustration="illustTestApp"
      title="测试套件"
      description="管理 App 测试套件，组织用例、批量回放；配合定时任务做无人值守回归"
      :breadcrumbs="['App 自动化', '测试套件']"
    >
      <template #actions>
        <el-button v-permission="'app_test:create'" type="primary" @click="handleCreate">
          <i class="i-solar-add-circle-bold btn-icon" />
          创建套件
        </el-button>
      </template>
    </AppPageHeader>

    <!-- ============ 统计卡 ============ -->
    <div class="stat-grid">
      <AppStatCard label="套件总数" :value="pagination.total" color="brand">
        <template #icon><i class="i-solar-box-minimalistic-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="编排用例数" :value="statsCases" color="info">
        <template #icon><i class="i-solar-notebook-bookmark-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="失败继续" :value="statsByStrategy.continue" color="success">
        <template #icon><i class="i-solar-play-circle-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="遇错中断" :value="statsByStrategy.stop" color="warning">
        <template #icon><i class="i-solar-stop-circle-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <!-- ============ 筛选区 ============ -->
    <div class="filter-bar">
      <div class="filter-fields">
        <div class="filter-field filter-search">
          <label>关键词</label>
          <el-input
            v-model="keyword"
            placeholder="搜索套件名称"
            clearable
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <i class="i-solar-magnifer-linear" />
            </template>
          </el-input>
        </div>
      </div>
      <div class="filter-actions">
        <el-button @click="handleResetFilter">
          <i class="i-solar-refresh-linear btn-icon" />
          重置
        </el-button>
        <el-button type="primary" @click="handleSearch">
          <i class="i-solar-magnifer-bold btn-icon" />
          查询
        </el-button>
      </div>
    </div>

    <!-- ============ 表格 ============ -->
    <AppSectionCard padless>
      <el-table v-loading="loading" :data="suiteList" style="width: 100%" row-class-name="suite-row">
        <el-table-column label="套件" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="cell-suite">
              <div class="cell-suite-icon">
                <i class="i-solar-layers-bold-duotone" />
              </div>
              <div class="cell-suite-info">
                <span class="cell-suite-name name-link" @click="handleViewDetail(row)">
                  {{ row.name }}
                </span>
                <span v-if="row.description" class="cell-suite-desc">{{ row.description }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="用例数" width="90" align="center">
          <template #default="{ row }">
            <span class="count-badge">{{ row.case_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="失败策略" width="120">
          <template #default="{ row }">
            <span class="strategy-pill" :class="`sg-${row.failure_strategy}`">
              <i :class="row.failure_strategy === 'stop' ? 'i-solar-stop-circle-bold' : 'i-solar-play-circle-bold'" />
              {{ getFailureStrategyLabel(row.failure_strategy) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="默认执行设备" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.device_udid" class="mono-text">{{ row.device_udid }}</span>
            <span v-else class="muted-text">未配置</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span class="mono-text">{{ formatDateTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click="handleViewDetail(row)">
                <i class="i-solar-eye-linear btn-icon-sm" />详情
              </el-button>
              <el-button
                v-permission="'app_test:execute'"
                size="small"
                type="primary"
                plain
                @click="handleExecute(row)"
              >
                <i class="i-solar-play-bold btn-icon-sm" />执行
              </el-button>
              <el-button v-permission="'app_test:edit'" size="small" @click="handleEdit(row)">
                <i class="i-solar-pen-linear btn-icon-sm" />编辑
              </el-button>
              <el-popconfirm
                v-permission="'app_test:delete'"
                :title="`确定删除套件「${row.name}」?`"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="handleDelete(row)"
              >
                <template #reference>
                  <el-button size="small" type="danger" plain>
                    <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <AppEmpty v-if="!loading" scene="data" description="还没有测试套件，开始创建吧">
            <template #actions>
              <el-button v-permission="'app_test:create'" type="primary" @click="handleCreate">
                <i class="i-solar-add-circle-bold btn-icon" />
                立即创建
              </el-button>
            </template>
          </AppEmpty>
        </template>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="loadSuiteList"
          @current-change="loadSuiteList"
        />
      </div>
    </AppSectionCard>

    <!-- ============ 创建/编辑对话框 ============ -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑测试套件' : '创建测试套件'"
      width="600px"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" label-position="top" :model="formData" :rules="formRules">
        <el-form-item label="套件名称" prop="name" required>
          <el-input v-model="formData.name" placeholder="请输入套件名称" maxlength="128" show-word-limit />
        </el-form-item>

        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入套件描述"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="失败策略" prop="failure_strategy">
              <el-select v-model="formData.failure_strategy" style="width: 100%">
                <el-option label="继续执行" value="continue" />
                <el-option label="立即停止" value="stop" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认执行设备" prop="device_udid">
              <el-select
                v-model="formData.device_udid"
                clearable
                filterable
                placeholder="可选；定时执行时使用"
                style="width: 100%"
              >
                <el-option
                  v-for="d in devices"
                  :key="d.udid"
                  :label="`${d.model || d.serial}（${d.udid}）${d.online ? '' : ' · 离线'}`"
                  :value="d.udid"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ submitting ? '提交中...' : '确定' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ============ 执行套件对话框 ============ -->
    <el-dialog v-model="executeDialogVisible" title="执行测试套件" width="420px">
      <el-form label-position="top">
        <el-form-item label="套件名称">
          <el-text>{{ currentExecuteSuite?.name }}（{{ currentExecuteSuite?.case_count }} 条用例）</el-text>
        </el-form-item>
        <el-form-item label="选择设备" required>
          <el-select v-model="selectedUdid" placeholder="请选择在线设备" filterable style="width: 100%">
            <el-option
              v-for="d in onlineDevices"
              :key="d.udid"
              :label="`${PLATFORM_LABEL[d.platform || 'android']} · ${d.model || d.serial}（${d.udid}）`"
              :value="d.udid"
            >
              <span>{{ PLATFORM_LABEL[d.platform || 'android'] }} · {{ d.model || d.serial }}（{{ d.udid }}）</span>
              <el-text
                v-if="d.udid === currentExecuteSuite?.device_udid"
                type="primary"
                size="small"
                style="margin-left: 8px"
              >
                (默认)
              </el-text>
            </el-option>
          </el-select>
        </el-form-item>
        <el-alert
          v-if="!onlineDevices.length"
          type="warning"
          :closable="false"
          show-icon
          title="暂无在线设备"
        />
      </el-form>
      <template #footer>
        <el-button @click="executeDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="isExecuting" :disabled="!selectedUdid" @click="handleConfirmExecute">
          {{ isExecuting ? '提交中...' : '开始执行' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * App 测试套件列表页 —— 与接口自动化 ApiSuitesView 同构。
 *
 * 统计卡 + 筛选区 + padless 表格 + 详情路由（AppSuiteDetail，编排在详情页）。
 * App 特有：执行选设备（非环境，默认设备预选）；提交后跳执行记录页自动打开
 * 实时查看（观战直播 + 日志直播）。
 */
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import { appTestApi, PLATFORM_LABEL, type AppSuite } from '@/api/appTest'
import { appDeviceApi, type AppDevice } from '@/api/appDevice'
import illustTestApp from '@/assets/illustrations/test-app.svg'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ==================== 数据状态 ====================
const loading = ref(false)
const suiteList = ref<AppSuite[]>([])
const keyword = ref('')
const devices = ref<AppDevice[]>([])
const onlineDevices = computed(() => devices.value.filter((d) => d.online))

const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

// ==================== 统计卡 ====================
const statsCases = computed(() => suiteList.value.reduce((sum, s) => sum + (s.case_count || 0), 0))
const statsByStrategy = computed(() => {
  const r = { continue: 0, stop: 0 }
  for (const s of suiteList.value) {
    if (s.failure_strategy in r) r[s.failure_strategy as keyof typeof r]++
  }
  return r
})

// ==================== 加载 ====================
const loadSuiteList = async () => {
  try {
    loading.value = true
    const res = await appTestApi.listSuites(projectId.value, {
      keyword: keyword.value || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    suiteList.value = res.items
    pagination.total = res.total
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const loadDevices = async () => {
  try {
    devices.value = await appDeviceApi.listDevices()
  } catch {
    devices.value = []
  }
}

// ==================== 搜索 ====================
const handleSearch = () => {
  pagination.page = 1
  loadSuiteList()
}

function handleResetFilter() {
  keyword.value = ''
  handleSearch()
}

// ==================== 创建/编辑 ====================
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const currentSuiteId = ref<number | null>(null)

const formData = reactive({
  name: '',
  description: '',
  device_udid: '',
  failure_strategy: 'continue' as 'continue' | 'stop',
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入套件名称', trigger: 'blur' },
    { min: 2, max: 128, message: '长度在 2 到 128 个字符', trigger: 'blur' },
  ],
}

const handleCreate = () => {
  isEdit.value = false
  currentSuiteId.value = null
  Object.assign(formData, { name: '', description: '', device_udid: '', failure_strategy: 'continue' })
  dialogVisible.value = true
}

const handleEdit = (row: AppSuite) => {
  isEdit.value = true
  currentSuiteId.value = row.id
  Object.assign(formData, {
    name: row.name,
    description: row.description || '',
    device_udid: row.device_udid || '',
    failure_strategy: row.failure_strategy,
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      submitting.value = true
      const body = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        device_udid: formData.device_udid || null,
        failure_strategy: formData.failure_strategy,
      }
      if (isEdit.value && currentSuiteId.value) {
        await appTestApi.updateSuite(projectId.value, currentSuiteId.value, body)
        ElMessage.success('更新成功')
      } else {
        await appTestApi.createSuite(projectId.value, body)
        ElMessage.success('创建成功，去详情页编排用例')
      }
      dialogVisible.value = false
      loadSuiteList()
    } catch {
      /* 拦截器已提示 */
    } finally {
      submitting.value = false
    }
  })
}

const handleDialogClose = () => {
  formRef.value?.resetFields()
  currentSuiteId.value = null
}

// ==================== 详情/删除 ====================
const handleViewDetail = (row: AppSuite) => {
  router.push({ name: 'AppSuiteDetail', params: { id: projectId.value, suiteId: row.id } })
}

async function handleDelete(row: AppSuite) {
  try {
    await appTestApi.deleteSuite(projectId.value, row.id)
    ElMessage.success('删除成功')
    loadSuiteList()
  } catch {
    /* 拦截器已提示 */
  }
}

// ==================== 执行 ====================
const executeDialogVisible = ref(false)
const currentExecuteSuite = ref<AppSuite | null>(null)
const selectedUdid = ref('')
const isExecuting = ref(false)

const handleExecute = async (row: AppSuite) => {
  if (!row.case_count) {
    ElMessage.warning('套件还没有用例，先去详情页编排')
    return
  }
  currentExecuteSuite.value = row
  executeDialogVisible.value = true
  await loadDevices()
  selectedUdid.value = onlineDevices.value.some((d) => d.udid === row.device_udid)
    ? row.device_udid || ''
    : ''
}

const handleConfirmExecute = async () => {
  if (!currentExecuteSuite.value || !selectedUdid.value) {
    ElMessage.warning('请选择一台在线设备')
    return
  }
  isExecuting.value = true
  try {
    // 平台不匹配软警告：拉编排比对用例平台（拉取失败不拦，后端仍会兜底 409）
    let force = false
    const devicePlatform =
      onlineDevices.value.find((d) => d.udid === selectedUdid.value)?.platform || 'android'
    let mismatched: string[] = []
    try {
      const detail = await appTestApi.getSuite(projectId.value, currentExecuteSuite.value.id)
      mismatched = (detail.cases || [])
        .filter((c) => c.enabled && (c.script_platform || 'android') !== devicePlatform)
        .map((c) => c.script_name)
    } catch {
      /* 详情拉取失败：跳过前置检查 */
    }
    if (mismatched.length) {
      const preview = mismatched.slice(0, 3).join('、') + (mismatched.length > 3 ? '…' : '')
      try {
        await ElMessageBox.confirm(
          `${mismatched.length} 条启用用例（${preview}）与所选设备平台不一致，` +
            'launch/系统 shell 类步骤会失败，纯语义步骤可跨平台。确定仍要执行？',
          '平台不匹配',
          { type: 'warning', confirmButtonText: '仍要执行', cancelButtonText: '取消' },
        )
        force = true
      } catch {
        return
      }
    }
    const res = await appTestApi.runSuite(
      projectId.value,
      currentExecuteSuite.value.id,
      selectedUdid.value,
      force,
    )
    ElMessage.success('套件执行任务已提交')
    executeDialogVisible.value = false
    router.push({
      name: 'AppExecutions',
      params: { id: projectId.value },
      query: {
        view: 'suite',
        suite_execution_id: res.suite_execution_id,
        live: '1',
        task_id: res.task_id,
        udid: selectedUdid.value,
        title: `套件实时查看 · ${currentExecuteSuite.value.name}`,
      },
    })
  } catch {
    /* 拦截器已提示 */
  } finally {
    isExecuting.value = false
  }
}

// ==================== 工具函数 ====================
function formatDateTime(dateString?: string) {
  if (!dateString) return '-'
  const d = new Date(dateString)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function getFailureStrategyLabel(strategy: string) {
  return { continue: '继续执行', stop: '立即停止' }[strategy] || strategy
}

onMounted(() => {
  loadSuiteList()
  loadDevices()
})
</script>

<style scoped lang="scss">
.app-suites-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 统计卡 ============ */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.dash-card-icon { font-size: 26px; }

@media (max-width: 1100px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px)  { .stat-grid { grid-template-columns: 1fr; } }

/* ============ 筛选区 ============ */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.filter-fields {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-4);
}
.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
  }
  :deep(.el-select),
  :deep(.el-input) { width: 100%; }
}
.filter-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
@media (max-width: 900px) {
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-actions { justify-content: flex-end; }
}

/* ============ 表格 ============ */
.cell-suite {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.cell-suite-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  background: var(--brand-50);
  color: var(--brand-600);
}
.cell-suite-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cell-suite-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: 1.4;
}
.name-link {
  cursor: pointer;
  &:hover { color: var(--brand-600); text-decoration: underline; }
}
.cell-suite-desc {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}

.count-badge {
  display: inline-flex;
  min-width: 24px;
  height: 20px;
  padding: 0 6px;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
}

/* 失败策略 */
.strategy-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  > i { font-size: 12px; }

  &.sg-continue { background: var(--color-info-50);   color: var(--color-info-600); }
  &.sg-stop     { background: var(--color-danger-50); color: var(--color-danger-600); }
}

.mono-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.muted-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

/* 操作列 */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  :deep(.el-button) { margin: 0; }
}

/* 分页 */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) var(--space-2);
  border-top: 1px solid var(--border-light);
}

/* 表格头 */
:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
    letter-spacing: 0.5px;
  }
  td.el-table__cell {
    padding: 14px 0;
    font-size: var(--font-size-sm);
  }
}
</style>
