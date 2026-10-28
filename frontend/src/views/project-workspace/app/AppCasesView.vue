<script setup lang="ts">
/**
 * App 自动化用例库（P2）
 *
 * 用例 = Midscene YAML（tasks 段）。列表 + 新建/编辑（CodeEditor 编 YAML）+ 回放
 * （选在线设备 → 提交 run_app_script 任务）+ 删除。录制沉淀走「智能操作台」，这里
 * 做管理与回放入口。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { appTestApi, PLATFORM_LABEL, type AppScript } from '@/api/appTest'
import { appDeviceApi, type AppDevice } from '@/api/appDevice'
import AppPageHeader from '@/components/common/AppPageHeader.vue'
import AppSectionCard from '@/components/common/AppSectionCard.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppStepEditor from './components/AppStepEditor.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => Number(route.params.id))

const canEdit = computed(() => userStore.hasPermission('app_test:edit'))
const canCreate = computed(() => userStore.hasPermission('app_test:create'))
const canDelete = computed(() => userStore.hasPermission('app_test:delete'))
const canExecute = computed(() => userStore.hasPermission('app_test:execute'))

const loading = ref(false)
const scripts = ref<AppScript[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
/** 平台(系统)过滤:'' = 全部 */
const platformFilter = ref('')

async function load() {
  loading.value = true
  try {
    const res = await appTestApi.listScripts(projectId.value, {
      keyword: keyword.value || undefined,
      platform: platformFilter.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    scripts.value = res.items
    total.value = res.total
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
load()

const STATUS_META: Record<string, { label: string; type: string }> = {
  draft: { label: '草稿', type: 'info' },
  active: { label: '启用', type: 'success' },
  disabled: { label: '停用', type: 'warning' },
}

function stepCount(s: AppScript): number {
  return (s.yaml_content.match(/- ai[A-Z]/g) || []).length
}

// ==================== 新建 / 编辑 ====================
const editDialog = ref(false)
const editing = ref<AppScript | null>(null)
const form = ref({
  name: '',
  platform: 'android',
  target_app: '',
  status: 'active',
  yaml_content: '',
})
const saving = ref(false)

const YAML_TEMPLATE = `tasks:
  - name: 示例任务
    flow:
      - aiTap: 定位描述（如 屏幕上的搜索按钮）
      - sleep: 800`

function openCreate() {
  editing.value = null
  form.value = {
    name: '',
    platform: 'android',
    target_app: '',
    status: 'active',
    yaml_content: YAML_TEMPLATE,
  }
  editDialog.value = true
}

function openEdit(s: AppScript) {
  editing.value = s
  form.value = {
    name: s.name,
    platform: s.platform || 'android',
    target_app: s.target_app || '',
    status: s.status,
    yaml_content: s.yaml_content,
  }
  editDialog.value = true
}

async function saveScript() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入用例名称')
    return
  }
  if (!form.value.yaml_content.trim()) {
    ElMessage.warning('YAML 内容不能为空')
    return
  }
  saving.value = true
  try {
    const body = {
      name: form.value.name.trim(),
      platform: form.value.platform,
      target_app: form.value.target_app.trim() || undefined,
      status: form.value.status as AppScript['status'],
      yaml_content: form.value.yaml_content,
    }
    if (editing.value) {
      await appTestApi.updateScript(projectId.value, editing.value.id, body)
      ElMessage.success('用例已更新')
    } else {
      await appTestApi.createScript(projectId.value, body)
      ElMessage.success('用例已创建')
    }
    editDialog.value = false
    await load()
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

async function handleDelete(s: AppScript) {
  try {
    await ElMessageBox.confirm(`确定删除用例「${s.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await appTestApi.deleteScript(projectId.value, s.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// ==================== 回放 ====================
const runDialog = ref(false)
const runTarget = ref<AppScript | null>(null)
const runDevices = ref<AppDevice[]>([])
const runUdid = ref('')
const running = ref(false)

async function openRun(s: AppScript) {
  runTarget.value = s
  runUdid.value = ''
  runDialog.value = true
  try {
    const list = await appDeviceApi.listDevices()
    runDevices.value = list.filter((d) => d.online)
  } catch {
    runDevices.value = []
  }
}

/** 所选设备与用例平台不一致（软警告：语义步骤可跨平台，launch/shell 步骤必失败） */
const runMismatch = computed(() => {
  const device = runDevices.value.find((d) => d.udid === runUdid.value)
  if (!runTarget.value || !device) return false
  return (device.platform || 'android') !== (runTarget.value.platform || 'android')
})

async function confirmRun() {
  if (!runTarget.value || !runUdid.value) {
    ElMessage.warning('请选择一台在线设备')
    return
  }
  if (runMismatch.value) {
    try {
      await ElMessageBox.confirm(
        `用例是${PLATFORM_LABEL[runTarget.value.platform] || runTarget.value.platform}平台的，` +
          '所选设备平台不一致——launch/系统 shell 类步骤会失败，纯语义步骤（aiTap 等）可以跨平台。确定仍要回放？',
        '平台不匹配',
        { type: 'warning', confirmButtonText: '仍要回放', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  running.value = true
  try {
    const res = await appTestApi.runScript(
      projectId.value,
      runTarget.value.id,
      runUdid.value,
      runMismatch.value,
    )
    ElMessage.success('回放任务已提交')
    runDialog.value = false
    // 直达 AI 任务详情页:观战直播 + 阶段/日志/产出一页全有(替代旧的执行记录页实时弹框)
    router.push({
      name: 'AiTaskDetail',
      params: { id: projectId.value, taskId: res.task_id },
    })
  } catch {
    /* 拦截器已提示 */
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div class="cases-page">
    <AppPageHeader
      icon="i-app-test-case"
      title="App 自动化用例"
      description="管理录制沉淀的用例（Midscene YAML），选设备一键回放"
      :breadcrumbs="['App 自动化', '测试用例']"
    >
      <template #actions>
        <el-button @click="router.push({ name: 'AppConsole', params: { id: projectId } })">
          <i class="i-solar-cpu-bolt-bold btn-icon" />去操作台录制
        </el-button>
        <el-button v-if="canCreate" type="primary" @click="openCreate">
          <i class="i-solar-add-circle-bold btn-icon" />新建用例
        </el-button>
      </template>
    </AppPageHeader>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索用例名 / 目标应用"
        clearable
        class="tb-search"
        @keyup.enter="((page = 1), load())"
        @clear="((page = 1), load())"
      >
        <template #prefix><i class="i-solar-magnifer-linear" /></template>
      </el-input>
      <el-select
        v-model="platformFilter"
        class="tb-platform"
        placeholder="全部系统"
        clearable
        @change="((page = 1), load())"
      >
        <el-option label="安卓" value="android" />
        <el-option label="鸿蒙" value="harmony" />
        <el-option label="iOS" value="ios" />
      </el-select>
      <el-button @click="((page = 1), load())">查询</el-button>
    </div>

    <AppSectionCard>
      <el-table v-loading="loading" :data="scripts" class="cases-table">
        <el-table-column label="用例名称" min-width="220">
          <template #default="{ row }">
            <div class="cell-name">
              <i class="i-app-mobile cell-icon" />
              <div>
                <div class="name-main">
                  {{ row.name }}
                  <span class="platform-chip" :class="`is-${row.platform || 'android'}`">
                    {{ PLATFORM_LABEL[row.platform] || row.platform || '安卓' }}
                  </span>
                </div>
                <div v-if="row.target_app" class="name-sub">{{ row.target_app }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="步骤" width="80" align="center">
          <template #default="{ row }">
            <span class="step-badge">{{ stepCount(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="STATUS_META[row.status]?.type || 'info'" size="small" effect="light">
              {{ STATUS_META[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span class="muted">{{ row.updated_at?.replace('T', ' ').slice(0, 19) || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canExecute"
              type="primary"
              size="small"
              text
              @click="openRun(row)"
            >
              <i class="i-solar-play-circle-bold btn-icon-sm" />回放
            </el-button>
            <el-button size="small" text @click="openEdit(row)">
              <i class="i-solar-pen-linear btn-icon-sm" />{{ canEdit ? '编辑' : '查看' }}
            </el-button>
            <el-button v-if="canDelete" type="danger" size="small" text @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <AppEmpty
            v-if="!loading"
            scene="data"
            description="还没有用例。去「智能操作台」用自然语言录一条，或手动新建。"
          />
        </template>
      </el-table>

      <div v-if="total > pageSize" class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          background
          @current-change="load"
        />
      </div>
    </AppSectionCard>

    <!-- 新建 / 编辑 -->
    <el-dialog v-model="editDialog" :title="editing ? '编辑用例' : '新建用例'" width="900px" top="6vh">
      <div class="edit-form">
        <div class="ef-row">
          <el-input v-model="form.name" placeholder="用例名称" maxlength="128" class="ef-name" />
          <el-select v-model="form.platform" class="ef-platform">
            <el-option label="安卓" value="android" />
            <el-option label="鸿蒙" value="harmony" />
            <el-option label="iOS" value="ios" />
          </el-select>
          <el-input v-model="form.target_app" placeholder="目标应用（可选）" class="ef-app" />
          <el-select v-model="form.status" class="ef-status">
            <el-option label="启用" value="active" />
            <el-option label="草稿" value="draft" />
            <el-option label="停用" value="disabled" />
          </el-select>
        </div>
        <div class="ef-label">用例步骤</div>
        <AppStepEditor v-model="form.yaml_content" :readonly="!canEdit" :platform="form.platform" />
      </div>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button v-if="canEdit" type="primary" :loading="saving" @click="saveScript">保存</el-button>
      </template>
    </el-dialog>

    <!-- 回放选设备 -->
    <el-dialog v-model="runDialog" title="回放用例" width="440px">
      <div class="run-body">
        <p class="run-tip">
          用例「<b>{{ runTarget?.name }}</b>」将在所选设备上回放，执行过程可在「执行记录」查看。
        </p>
        <el-select v-model="runUdid" placeholder="选择在线设备" filterable style="width: 100%">
          <el-option
            v-for="d in runDevices"
            :key="d.udid"
            :label="`${PLATFORM_LABEL[d.platform || 'android']} · ${d.model || d.serial}（${d.udid}）`"
            :value="d.udid"
          />
        </el-select>
        <el-alert
          v-if="runMismatch"
          type="warning"
          :closable="false"
          show-icon
          title="所选设备与用例平台不一致，launch/系统 shell 类步骤会失败"
        />
        <el-empty v-if="!runDevices.length" description="暂无在线设备" :image-size="60" />
      </div>
      <template #footer>
        <el-button @click="runDialog = false">取消</el-button>
        <el-button type="primary" :loading="running" :disabled="!runUdid" @click="confirmRun">
          开始回放
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.cases-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.btn-icon { margin-right: 4px; }
.btn-icon-sm { margin-right: 3px; }
.toolbar {
  display: flex;
  gap: 12px;
  .tb-search { max-width: 320px; }
  .tb-platform { width: 132px; flex-shrink: 0; }
}
.cell-name {
  display: flex;
  align-items: center;
  gap: 10px;
  .cell-icon { font-size: 20px; color: var(--brand-500); }
  .name-main { font-weight: var(--font-weight-medium); color: var(--text-primary); }
  .name-sub { font-size: var(--font-size-xs); color: var(--text-secondary); }
}
.platform-chip {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  line-height: 18px;
  vertical-align: 1px;
  &.is-android { background: var(--brand-50); color: var(--brand-600); }
  &.is-harmony { background: var(--color-info-50); color: var(--color-info-600); }
  &.is-ios { background: var(--gray-100); color: var(--gray-700); }
}
.step-badge {
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
.muted { color: var(--text-placeholder); font-size: var(--font-size-sm); }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }

.edit-form { display: flex; flex-direction: column; gap: 12px; }
.ef-row { display: flex; gap: 10px; }
.ef-name { flex: 1; }
.ef-platform { width: 100px; }
.ef-app { width: 180px; }
.ef-status { width: 110px; }
.ef-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}
.run-body { display: flex; flex-direction: column; gap: 12px; }
.run-tip { font-size: var(--font-size-sm); color: var(--text-regular); margin: 0; line-height: 1.6; }
</style>
