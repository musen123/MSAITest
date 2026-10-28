<template>
  <div class="suite-detail-page">
    <div v-if="loading" class="loading-container" v-loading="true" />

    <template v-else-if="suite">
      <!-- ============ 概览头 ============ -->
      <div class="suite-overview">
        <div class="overview-header">
          <div class="header-left">
            <div class="suite-title">
              <i class="i-solar-layers-bold-duotone title-icon" />
              <span class="title-text">{{ suite.name }}</span>
              <span class="strategy-pill" :class="`sg-${suite.failure_strategy}`">
                <i :class="suite.failure_strategy === 'stop' ? 'i-solar-stop-circle-bold' : 'i-solar-play-circle-bold'" />
                {{ suite.failure_strategy === 'stop' ? '立即停止' : '继续执行' }}
              </span>
              <span v-if="suite.device_udid" class="device-chip">
                <i class="i-solar-smartphone-2-linear" />{{ suite.device_udid }}
              </span>
            </div>
          </div>
          <div class="header-actions">
            <el-button v-permission="'app_test:execute'" type="primary" @click="openExecute">
              <i class="i-solar-play-bold btn-icon" />执行套件
            </el-button>
            <el-button v-permission="'app_test:edit'" @click="openEdit">
              <i class="i-solar-pen-linear btn-icon" />编辑
            </el-button>
            <el-button text class="back-btn" @click="handleBack">
              <i class="i-solar-arrow-left-linear btn-icon" />返回列表
            </el-button>
          </div>
        </div>

        <div class="overview-content">
          <div class="basic-info">
            <div class="info-row">
              <div class="info-item">
                <span class="info-label">创建时间</span>
                <span class="info-value">{{ formatDateTime(suite.created_at) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">更新时间</span>
                <span class="info-value">{{ formatDateTime(suite.updated_at) }}</span>
              </div>
            </div>
            <div class="info-desc">
              <span class="info-label">描述</span>
              <span class="info-value">{{ suite.description || '暂无描述' }}</span>
            </div>
          </div>

          <div class="stats-cards">
            <div class="stat-card stat-primary">
              <div class="stat-icon"><i class="i-solar-notebook-bookmark-bold" /></div>
              <div class="stat-info">
                <span class="stat-value">{{ cases.length }}</span>
                <span class="stat-label">用例数量</span>
              </div>
            </div>
            <div class="stat-card stat-success">
              <div class="stat-icon"><i class="i-solar-check-circle-bold" /></div>
              <div class="stat-info">
                <span class="stat-value">{{ enabledCount }}</span>
                <span class="stat-label">启用用例</span>
              </div>
            </div>
            <div class="stat-card stat-warning clickable" @click="loadExecutions">
              <div class="stat-icon"><i class="i-solar-history-bold" /></div>
              <div class="stat-info">
                <span class="stat-value">{{ executionsTotal }}</span>
                <span class="stat-label">执行次数</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ============ 内容区：编排 + 执行记录 ============ -->
      <div class="content-area">
        <!-- 用例编排 -->
        <el-card class="cases-card" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <span class="card-title">用例编排</span>
                <el-badge :value="cases.length" type="primary" class="badge" />
                <span class="card-sub">顺序即执行顺序</span>
              </div>
              <div class="header-right">
                <el-button v-permission="'app_test:edit'" type="primary" size="small" @click="openAddCases">
                  <i class="i-solar-add-circle-bold btn-icon-sm" />添加用例
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="!cases.length" class="empty-state">
            <AppEmpty scene="data" description="还没有用例，点击「添加用例」编排" />
          </div>
          <div v-else class="case-list">
            <div
              v-for="(c, i) in cases"
              :key="c.script_id"
              class="case-row"
              :class="{ 'is-disabled': !c.enabled }"
            >
              <span class="case-index">{{ i + 1 }}</span>
              <div class="case-main">
                <span class="case-name" :title="c.name">{{ c.name }}</span>
                <el-tag v-if="c.status !== 'active'" size="small" effect="plain" type="info">
                  {{ c.status === 'draft' ? '草稿' : '停用' }}
                </el-tag>
              </div>
              <div class="case-ops">
                <el-switch
                  :model-value="c.enabled"
                  size="small"
                  :disabled="!canEdit"
                  @change="(v: boolean) => toggleCase(i, v)"
                />
                <el-button size="small" text :disabled="!canEdit || i === 0" @click="moveCase(i, -1)">
                  <i class="i-solar-alt-arrow-up-linear" />
                </el-button>
                <el-button
                  size="small"
                  text
                  :disabled="!canEdit || i === cases.length - 1"
                  @click="moveCase(i, 1)"
                >
                  <i class="i-solar-alt-arrow-down-linear" />
                </el-button>
                <el-button size="small" text type="danger" :disabled="!canEdit" @click="removeCase(i)">
                  <i class="i-solar-close-circle-linear" />
                </el-button>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 套件执行记录 -->
        <el-card class="executions-card" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <span class="card-title">执行记录</span>
                <el-badge :value="executionsTotal" type="warning" class="badge" />
              </div>
              <div class="header-right">
                <el-button size="small" text @click="loadExecutions">
                  <i class="i-solar-refresh-linear btn-icon-sm" />刷新
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="!executions.length" class="empty-state">
            <el-empty description="暂无执行记录" :image-size="60" />
          </div>
          <div v-else class="executions-list">
            <div
              v-for="e in executions"
              :key="e.id"
              class="execution-item"
              @click="goExecution(e)"
            >
              <div class="execution-status">
                <el-tag :type="STATUS_META[e.status]?.type || 'info'" size="small" effect="light">
                  {{ STATUS_META[e.status]?.label || e.status }}
                </el-tag>
              </div>
              <div class="execution-info">
                <div class="execution-stats">
                  <span class="stat-pass">通过 {{ e.passed_count }}</span>
                  <span class="stat-fail">失败 {{ e.failed_count }}</span>
                  <span v-if="e.skipped_count" class="stat-skip">跳过 {{ e.skipped_count }}</span>
                  <span class="stat-trigger">{{ e.trigger_type === 'scheduled' ? '定时' : '手动' }}</span>
                </div>
                <div class="execution-meta">
                  <span class="time">{{ formatDateTime(e.created_at) }}</span>
                  <span class="duration">{{ fmtDuration(e.duration_ms) }}</span>
                </div>
              </div>
              <div class="execution-arrow"><i class="i-solar-alt-arrow-right-linear" /></div>
            </div>
          </div>
        </el-card>
      </div>
    </template>

    <AppEmpty v-else scene="data" title="套件不存在" description="可能已被删除">
      <template #actions>
        <el-button @click="handleBack">返回列表</el-button>
      </template>
    </AppEmpty>

    <!-- ============ 添加用例对话框 ============ -->
    <el-dialog v-model="addDialogVisible" title="添加用例" width="640px">
      <div class="add-cases-filter">
        <el-input
          v-model="libKeyword"
          placeholder="搜索用例名"
          clearable
          @keyup.enter="loadLibrary"
          @clear="loadLibrary"
        >
          <template #prefix><i class="i-solar-magnifer-linear" /></template>
        </el-input>
        <el-button @click="loadLibrary">查询</el-button>
      </div>
      <el-table
        v-loading="libLoading"
        :data="libSelectable"
        max-height="360"
        @selection-change="(rows: any[]) => (libSelected = rows)"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="用例名称" min-width="220" show-overflow-tooltip prop="name" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.status === 'active' ? 'success' : 'info'">
              {{ { active: '启用', draft: '草稿', disabled: '停用' }[row.status as string] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!libSelected.length" :loading="saving" @click="confirmAddCases">
          添加 {{ libSelected.length ? `(${libSelected.length})` : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ============ 编辑套件对话框 ============ -->
    <el-dialog v-model="editDialogVisible" title="编辑测试套件" width="600px">
      <el-form label-position="top" :model="editForm">
        <el-form-item label="套件名称" required>
          <el-input v-model="editForm.name" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="失败策略">
              <el-select v-model="editForm.failure_strategy" style="width: 100%">
                <el-option label="继续执行" value="continue" />
                <el-option label="立即停止" value="stop" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认执行设备">
              <el-select v-model="editForm.device_udid" clearable filterable placeholder="可选" style="width: 100%">
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
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- ============ 执行对话框 ============ -->
    <el-dialog v-model="executeDialogVisible" title="执行测试套件" width="420px">
      <el-form label-position="top">
        <el-form-item label="套件名称">
          <el-text>{{ suite?.name }}（{{ enabledCount }} 条启用用例）</el-text>
        </el-form-item>
        <el-form-item label="选择设备" required>
          <el-select v-model="selectedUdid" placeholder="请选择在线设备" filterable style="width: 100%">
            <el-option
              v-for="d in onlineDevices"
              :key="d.udid"
              :label="`${PLATFORM_LABEL[d.platform || 'android']} · ${d.model || d.serial}（${d.udid}）${d.udid === suite?.device_udid ? ' · 默认' : ''}`"
              :value="d.udid"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="executeDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="executing" :disabled="!selectedUdid" @click="confirmExecute">
          开始执行
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * App 测试套件详情页 —— 与接口自动化 ApiSuiteDetailView 同构。
 *
 * 概览头（标题+策略+设备+操作）+ 基本信息 + 统计卡；左=用例编排卡
 * （添加/启停/调序/移除，每次变更全量替换立即落库），右=套件执行记录卡
 * （点击跳执行记录页自动打开明细）。执行=选设备提交，跳实时查看。
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { AppEmpty } from '@/components/common'
import {
  appTestApi,
  PLATFORM_LABEL,
  type AppScript,
  type AppSuite,
  type AppSuiteExecution,
} from '@/api/appTest'
import { appDeviceApi, type AppDevice } from '@/api/appDevice'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => Number(route.params.id))
const suiteId = computed(() => Number(route.params.suiteId))
const canEdit = computed(() => userStore.hasPermission('app_test:edit'))

const STATUS_META: Record<string, { label: string; type: string }> = {
  pending: { label: '排队中', type: 'info' },
  running: { label: '执行中', type: 'warning' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}

// ==================== 套件 + 编排 ====================
const loading = ref(true)
const suite = ref<AppSuite | null>(null)
const cases = ref<Array<{ script_id: number; name: string; status: string; enabled: boolean }>>([])
const saving = ref(false)
const enabledCount = computed(() => cases.value.filter((c) => c.enabled).length)

async function loadSuite() {
  try {
    const detail = await appTestApi.getSuite(projectId.value, suiteId.value)
    suite.value = detail
    cases.value = (detail.cases || []).map((c) => ({
      script_id: c.script_id,
      name: c.script_name,
      status: c.script_status,
      enabled: c.enabled,
    }))
  } catch {
    suite.value = null
  } finally {
    loading.value = false
  }
}

/** 编排变更立即落库（全量替换语义），失败回滚重载 */
async function persistCases() {
  saving.value = true
  try {
    await appTestApi.replaceSuiteCases(
      projectId.value,
      suiteId.value,
      cases.value.map((c) => ({ script_id: c.script_id, enabled: c.enabled })),
    )
  } catch {
    await loadSuite()
  } finally {
    saving.value = false
  }
}

function toggleCase(i: number, enabled: boolean) {
  cases.value[i]!.enabled = enabled
  void persistCases()
}
function moveCase(i: number, dir: -1 | 1) {
  const j = i + dir
  if (j < 0 || j >= cases.value.length) return
  ;[cases.value[i], cases.value[j]] = [cases.value[j]!, cases.value[i]!]
  void persistCases()
}
function removeCase(i: number) {
  cases.value.splice(i, 1)
  void persistCases()
}

// ==================== 添加用例 ====================
const addDialogVisible = ref(false)
const libLoading = ref(false)
const libKeyword = ref('')
const libScripts = ref<AppScript[]>([])
const libSelected = ref<AppScript[]>([])
const libSelectable = computed(() => {
  const chosen = new Set(cases.value.map((c) => c.script_id))
  return libScripts.value.filter((s) => !chosen.has(s.id))
})

async function loadLibrary() {
  libLoading.value = true
  try {
    const res = await appTestApi.listScripts(projectId.value, {
      keyword: libKeyword.value || undefined,
      page_size: 100,
    })
    libScripts.value = res.items
  } finally {
    libLoading.value = false
  }
}

function openAddCases() {
  libSelected.value = []
  addDialogVisible.value = true
  void loadLibrary()
}

async function confirmAddCases() {
  for (const s of libSelected.value) {
    cases.value.push({ script_id: s.id, name: s.name, status: s.status, enabled: true })
  }
  addDialogVisible.value = false
  await persistCases()
  ElMessage.success(`已添加 ${libSelected.value.length} 条用例`)
}

// ==================== 执行记录 ====================
const executions = ref<AppSuiteExecution[]>([])
const executionsTotal = ref(0)

async function loadExecutions() {
  try {
    const res = await appTestApi.listSuiteExecutions(projectId.value, {
      suite_id: suiteId.value,
      page_size: 10,
    })
    executions.value = res.items
    executionsTotal.value = res.total
  } catch {
    executions.value = []
  }
}

function goExecution(e: AppSuiteExecution) {
  router.push({
    name: 'AppExecutions',
    params: { id: projectId.value },
    query: { view: 'suite', suite_execution_id: e.id },
  })
}

// ==================== 编辑 ====================
const editDialogVisible = ref(false)
const devices = ref<AppDevice[]>([])
const onlineDevices = computed(() => devices.value.filter((d) => d.online))
const editForm = reactive({
  name: '',
  description: '',
  device_udid: '',
  failure_strategy: 'continue' as 'continue' | 'stop',
})

async function ensureDevices() {
  if (devices.value.length) return
  try {
    devices.value = await appDeviceApi.listDevices()
  } catch {
    devices.value = []
  }
}

async function openEdit() {
  if (!suite.value) return
  Object.assign(editForm, {
    name: suite.value.name,
    description: suite.value.description || '',
    device_udid: suite.value.device_udid || '',
    failure_strategy: suite.value.failure_strategy,
  })
  editDialogVisible.value = true
  await ensureDevices()
}

async function saveEdit() {
  if (!editForm.name.trim()) {
    ElMessage.warning('请输入套件名称')
    return
  }
  saving.value = true
  try {
    await appTestApi.updateSuite(projectId.value, suiteId.value, {
      name: editForm.name.trim(),
      description: editForm.description.trim() || undefined,
      device_udid: editForm.device_udid || null,
      failure_strategy: editForm.failure_strategy,
    })
    ElMessage.success('已保存')
    editDialogVisible.value = false
    await loadSuite()
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

// ==================== 执行 ====================
const executeDialogVisible = ref(false)
const selectedUdid = ref('')
const executing = ref(false)

async function openExecute() {
  if (!enabledCount.value) {
    ElMessage.warning('套件没有启用的用例')
    return
  }
  executeDialogVisible.value = true
  await ensureDevices()
  selectedUdid.value = onlineDevices.value.some((d) => d.udid === suite.value?.device_udid)
    ? suite.value?.device_udid || ''
    : ''
}

async function confirmExecute() {
  if (!selectedUdid.value || !suite.value) return
  executing.value = true
  try {
    // 平台不匹配软警告（详情页编排已在手，直接比对；后端仍会兜底 409）
    let force = false
    const devicePlatform =
      onlineDevices.value.find((d) => d.udid === selectedUdid.value)?.platform || 'android'
    const mismatched = (suite.value.cases || [])
      .filter((c) => c.enabled && (c.script_platform || 'android') !== devicePlatform)
      .map((c) => c.script_name)
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
    const res = await appTestApi.runSuite(projectId.value, suiteId.value, selectedUdid.value, force)
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
        title: `套件实时查看 · ${suite.value.name}`,
      },
    })
  } catch {
    /* 拦截器已提示 */
  } finally {
    executing.value = false
  }
}

// ==================== 工具 ====================
function handleBack() {
  router.push({ name: 'AppSuites', params: { id: projectId.value } })
}

function formatDateTime(v?: string) {
  if (!v) return '-'
  const d = new Date(v)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function fmtDuration(ms?: number | null) {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

onMounted(() => {
  loadSuite()
  loadExecutions()
})
</script>

<style scoped lang="scss">
.suite-detail-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: 20px;
}
.loading-container { min-height: 300px; }

.btn-icon { margin-right: 5px; font-size: 15px; vertical-align: -2px; }
.btn-icon-sm { margin-right: 4px; font-size: 14px; vertical-align: -2px; }

/* ============ 概览 ============ */
.suite-overview {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-5) var(--space-6);
}
.overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.suite-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;

  .title-icon { font-size: 24px; color: var(--brand-500); }
  .title-text {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
  }
}
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
.device-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-family: var(--font-mono);
  background: var(--gray-100);
  color: var(--gray-600);
  > i { font-size: 12px; }
}
.header-actions { display: flex; align-items: center; gap: var(--space-2); }

.overview-content {
  display: flex;
  gap: var(--space-6);
  margin-top: var(--space-4);
  flex-wrap: wrap;
}
.basic-info {
  flex: 1;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.info-row { display: flex; gap: var(--space-6); flex-wrap: wrap; }
.info-item, .info-desc { display: flex; flex-direction: column; gap: 4px; }
.info-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
.info-value { font-size: var(--font-size-sm); color: var(--text-primary); }

.stats-cards {
  display: flex;
  gap: var(--space-3);
  flex-shrink: 0;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  min-width: 130px;

  &.clickable { cursor: pointer; &:hover { background: var(--fill-light); } }

  .stat-icon {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
  }
  &.stat-primary .stat-icon { background: var(--brand-50); color: var(--brand-600); }
  &.stat-success .stat-icon { background: var(--color-success-50); color: var(--color-success-600); }
  &.stat-warning .stat-icon { background: var(--color-warning-50); color: var(--color-warning-600); }

  .stat-info { display: flex; flex-direction: column; }
  .stat-value {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
    line-height: 1.2;
  }
  .stat-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
}

/* ============ 内容区 ============ */
.content-area {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-5);
  align-items: start;

  @media (max-width: 1000px) { grid-template-columns: 1fr; }
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .header-left { display: flex; align-items: center; gap: var(--space-2); }
  .card-title { font-weight: var(--font-weight-semibold); color: var(--text-primary); }
  .card-sub { font-size: var(--font-size-xs); color: var(--text-placeholder); }
  .badge { margin-top: 2px; }
}
.empty-state { padding: var(--space-6) 0; }

/* 编排列表 */
.case-list { display: flex; flex-direction: column; gap: 6px; }
.case-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 8px 10px;
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  transition: background 0.15s;
  &:hover { background: var(--fill-light); }
  &.is-disabled .case-name { color: var(--text-placeholder); text-decoration: line-through; }

  .case-index {
    width: 22px;
    height: 22px;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-full);
    background: var(--brand-50);
    color: var(--brand-600);
    font-size: 11px;
    font-weight: var(--font-weight-semibold);
  }
  .case-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .case-name {
    font-size: var(--font-size-sm);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .case-ops {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
    :deep(.el-button) { margin: 0; }
  }
}

/* 执行记录列表 */
.executions-list { display: flex; flex-direction: column; gap: 6px; }
.execution-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px 12px;
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s;
  &:hover { background: var(--brand-50); }

  .execution-info { flex: 1; min-width: 0; }
  .execution-stats {
    display: flex;
    gap: 10px;
    font-size: var(--font-size-sm);
    .stat-pass { color: var(--color-success-600); }
    .stat-fail { color: var(--color-danger-600); }
    .stat-skip { color: var(--text-secondary); }
    .stat-trigger { color: var(--text-placeholder); font-size: var(--font-size-xs); align-self: center; }
  }
  .execution-meta {
    display: flex;
    gap: 10px;
    font-size: var(--font-size-xs);
    color: var(--text-placeholder);
    font-family: var(--font-mono);
    margin-top: 2px;
  }
  .execution-arrow { color: var(--text-placeholder); }
}

/* 添加用例 */
.add-cases-filter {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  :deep(.el-input) { max-width: 320px; }
}
</style>
