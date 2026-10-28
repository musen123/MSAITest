<template>
  <div class="environments-view">
    <AppPageHeader
      icon="i-solar-server-bold"
      :illustration="illustEnvironment"
      description="管理测试环境的配置信息"
    >
      <template #title>
        环境管理
        <span class="title-count">{{ environments.length }}</span>
      </template>
      <template #actions>
        <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
          <i class="i-solar-add-circle-bold mr-1" />
          创建环境
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 工具栏：搜索 + 类型段 + 视图切换 -->
    <div class="env-toolbar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索环境名称或描述"
        clearable
        class="env-search"
      >
        <template #prefix>
          <i class="i-solar-magnifer-linear" />
        </template>
      </el-input>
      <div class="seg-group">
        <button
          v-for="seg in typeSegments"
          :key="seg.label"
          type="button"
          class="seg"
          :class="{ 'is-active': filterEnvType === seg.value }"
          @click="filterEnvType = seg.value"
        >
          {{ seg.label }}
          <span class="seg-count">{{ seg.count }}</span>
        </button>
      </div>
      <div class="toolbar-spacer" />
      <el-button-group>
        <el-button
          :type="viewMode === 'card' ? 'primary' : ''"
          @click="viewMode = 'card'"
        >
          <i class="i-solar-widget-2-bold" />
        </el-button>
        <el-button
          :type="viewMode === 'table' ? 'primary' : ''"
          @click="viewMode = 'table'"
        >
          <i class="i-solar-list-bold" />
        </el-button>
      </el-button-group>
    </div>

    <!-- 环境列表 -->
    <div v-loading="loading" class="environment-list">
      <AppEmpty
        v-if="!loading && environments.length === 0"
        scene="data"
        title="暂无环境"
        description="创建第一个测试环境开始管理配置"
      >
        <template #actions>
          <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
            <i class="i-solar-add-circle-bold mr-1" />
            创建环境
          </el-button>
        </template>
      </AppEmpty>

      <AppEmpty
        v-else-if="!loading && filteredEnvironments.length === 0"
        scene="search"
        title="没有匹配的环境"
        description="试试调整搜索关键词或类型筛选"
      />

      <!-- 卡片视图 -->
      <div v-else-if="viewMode === 'card'" class="card-grid">
        <div
          v-for="env in filteredEnvironments"
          :key="env.id"
          class="env-card"
          :class="{ 'is-default': env.is_default }"
        >
          <div class="env-card-header">
            <div class="env-card-icon" :class="env.env_type === 2 ? 'ui-type' : 'api-type'">
              <i :class="env.env_type === 2 ? 'i-solar-monitor-bold' : 'i-solar-code-bold'" />
            </div>
            <div class="env-card-title">
              <h3>{{ env.name }}</h3>
              <div class="env-card-tags">
                <span class="soft-pill" :class="env.env_type === 2 ? 'pill-warning' : 'pill-info'">
                  {{ env.env_type === 2 ? 'UI测试' : '接口测试' }}
                </span>
                <span v-if="env.is_default" class="soft-pill pill-success">默认</span>
                <span v-if="env.is_global" class="soft-pill pill-brand">全局</span>
              </div>
            </div>
          </div>

          <div class="env-card-body">
            <div class="env-info-item">
              <span class="env-info-label">Base URL</span>
              <code class="env-info-url">{{ env.base_url }}</code>
            </div>
            <div v-if="env.description" class="env-info-item">
              <span class="env-info-label">描述</span>
              <span class="env-info-desc">{{ env.description }}</span>
            </div>
            <div class="env-info-item">
              <span class="env-info-label">变量</span>
              <span class="env-info-value">{{ env.variable_count }} 个</span>
            </div>
          </div>

          <div class="env-card-footer">
            <el-button size="small" @click="handleViewDetail(env)">
              <i class="i-solar-eye-linear mr-1" /> 详情
            </el-button>
            <el-button v-permission="'environment:edit'" size="small" @click="handleEdit(env)">
              <i class="i-solar-pen-2-linear mr-1" /> 编辑
            </el-button>
            <el-button
              v-permission="'environment:edit'"
              size="small"
              type="primary"
              plain
              :disabled="env.is_default"
              @click="handleSetDefault(env)"
            >
              <i class="i-solar-star-linear mr-1" /> 设默认
            </el-button>
            <el-button v-permission="'environment:create'" size="small" @click="handleCloneDialog(env)">
              <i class="i-solar-copy-linear mr-1" /> 克隆
            </el-button>
            <el-button
              v-permission="'environment:delete'"
              size="small"
              type="danger"
              plain
              :disabled="env.is_default"
              @click="handleDelete(env)"
            >
              <i class="i-solar-trash-bin-trash-linear mr-1" /> 删除
            </el-button>
          </div>
        </div>
      </div>

      <!-- 表格视图 -->
      <AppSectionCard v-else padless>
        <el-table :data="filteredEnvironments">
          <el-table-column label="名称" min-width="160">
            <template #default="{ row }">
              <div class="table-name-cell">
                <span class="table-env-name">{{ row.name }}</span>
                <div class="table-tags">
                  <span v-if="row.is_default" class="soft-pill pill-success">默认</span>
                  <span v-if="row.is_global" class="soft-pill pill-brand">全局</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="100" align="center">
            <template #default="{ row }">
              <span class="soft-pill" :class="row.env_type === 2 ? 'pill-warning' : 'pill-info'">
                {{ row.env_type === 2 ? 'UI测试' : '接口测试' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="Base URL" min-width="240">
            <template #default="{ row }">
              <code class="table-url">{{ row.base_url }}</code>
            </template>
          </el-table-column>
          <el-table-column label="描述" min-width="200">
            <template #default="{ row }">
              {{ row.description || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="变量" width="90" align="center">
            <template #default="{ row }">
              {{ row.variable_count }} 个
            </template>
          </el-table-column>
          <el-table-column label="操作" width="480" align="center" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" @click.stop="handleViewDetail(row)">
                  <i class="i-solar-eye-linear mr-1" /> 详情
                </el-button>
                <el-button v-permission="'environment:edit'" size="small" @click.stop="handleEdit(row)">
                  <i class="i-solar-pen-2-linear mr-1" /> 编辑
                </el-button>
                <el-button
                  v-permission="'environment:edit'"
                  size="small"
                  type="primary"
                  plain
                  :disabled="row.is_default"
                  @click.stop="handleSetDefault(row)"
                >
                  <i class="i-solar-star-linear mr-1" /> 设默认
                </el-button>
                <el-button v-permission="'environment:create'" size="small" @click.stop="handleCloneDialog(row)">
                  <i class="i-solar-copy-linear mr-1" /> 克隆
                </el-button>
                <el-button
                  v-permission="'environment:delete'"
                  size="small"
                  type="danger"
                  plain
                  :disabled="row.is_default"
                  @click.stop="handleDelete(row)"
                >
                  <i class="i-solar-trash-bin-trash-linear mr-1" /> 删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </AppSectionCard>
    </div>

    <!-- 创建/编辑环境对话框 -->
    <EnvironmentFormDialog
      v-if="formDialogVisible"
      v-model="formDialogVisible"
      :environment="currentEnvironment"
      :project-id="projectId"
      @success="handleFormSuccess"
      @update:model-value="handleDialogClose"
    />

    <!-- 克隆环境对话框 -->
    <el-dialog
      v-model="cloneDialogVisible"
      title="克隆环境"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top"
        ref="cloneFormRef"
        :model="cloneForm"
        :rules="cloneRules"
      >
        <el-form-item label="新环境名称" prop="name">
          <el-input
            v-model="cloneForm.name"
            placeholder="请输入新环境的名称"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>
        <el-alert
          :title="`将复制环境 &quot;${sourceEnvironment?.name}&quot; 的所有配置和变量`"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button @click="cloneDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleClone">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type { Environment, EnvType } from '@/api/environments'
import EnvironmentFormDialog from './components/EnvironmentFormDialog.vue'
import { AppPageHeader, AppSectionCard, AppEmpty } from '@/components/common'
import illustEnvironment from '@/assets/illustrations/environment.svg'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => Number(route.params.id))
const viewMode = ref<'card' | 'table'>('card')

const loading = ref(false)
const environments = ref<Environment[]>([])
const searchKeyword = ref('')
const filterEnvType = ref<EnvType | null>(null)
const currentEnvironment = ref<Environment | null>(null)
const sourceEnvironment = ref<Environment | null>(null)

const formDialogVisible = ref(false)
const cloneDialogVisible = ref(false)
const submitting = ref(false)

const cloneFormRef = ref<FormInstance>()
const cloneForm = ref({ name: '' })
const cloneRules: FormRules = {
  name: [
    { required: true, message: '请输入环境名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' },
  ],
}

// 类型计数（用于筛选段）
const apiEnvCount = computed(() => environments.value.filter((e) => e.env_type === 1).length)
const uiEnvCount = computed(() => environments.value.filter((e) => e.env_type === 2).length)

const typeSegments = computed<{ value: EnvType | null; label: string; count: number }[]>(() => [
  { value: null, label: '全部', count: environments.value.length },
  { value: 1, label: '功能测试', count: apiEnvCount.value },
  { value: 2, label: 'UI 测试', count: uiEnvCount.value },
])

// 前端过滤：搜索 + 类型
const filteredEnvironments = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  return environments.value.filter((e) => {
    if (filterEnvType.value && e.env_type !== filterEnvType.value) return false
    if (kw) {
      const hay = `${e.name || ''} ${e.description || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

const loadEnvironments = async () => {
  loading.value = true
  try {
    const res = await environmentApi.getEnvironmentList(projectId.value)
    environments.value = res.data
  } catch (error) {
    console.error('加载环境列表失败:', error)
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  currentEnvironment.value = null
  formDialogVisible.value = true
}

const handleViewDetail = (env: Environment) => {
  router.push({ name: 'EnvironmentDetail', params: { id: projectId.value, envId: env.id } })
}

const handleSetDefault = async (env: Environment) => {
  try {
    await environmentApi.setDefaultEnvironment(projectId.value, env.id)
    ElMessage.success('已设置为默认环境')
    loadEnvironments()
  } catch (error) {
    console.error('设置默认环境失败:', error)
  }
}

const handleEdit = (env: Environment) => {
  currentEnvironment.value = env
  formDialogVisible.value = true
}

const handleCloneDialog = (env: Environment) => {
  sourceEnvironment.value = env
  cloneForm.value.name = `${env.name} - 副本`
  cloneDialogVisible.value = true
}

const handleClone = async () => {
  if (!cloneFormRef.value) return
  await cloneFormRef.value.validate(async (valid) => {
    if (!valid || !sourceEnvironment.value) return
    submitting.value = true
    try {
      await environmentApi.cloneEnvironment(projectId.value, sourceEnvironment.value.id, {
        name: cloneForm.value.name,
      })
      ElMessage.success('克隆成功')
      cloneDialogVisible.value = false
      loadEnvironments()
    } catch (error) {
      console.error('克隆环境失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (env: Environment) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除环境 "${env.name}" 吗？删除后将无法恢复。`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
    await environmentApi.deleteEnvironment(projectId.value, env.id)
    ElMessage.success('删除成功')
    loadEnvironments()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除环境失败:', error)
    }
  }
}

const handleFormSuccess = () => {
  formDialogVisible.value = false
  currentEnvironment.value = null
  loadEnvironments()
}

const handleDialogClose = (value: boolean) => {
  if (!value) currentEnvironment.value = null
}

onMounted(() => { loadEnvironments() })
</script>

<style scoped lang="scss">
.environments-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-bottom: var(--space-5);
}

/* 标题内联计数 */
.title-count {
  margin-left: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  background: var(--gray-100);
  padding: 1px 10px;
  border-radius: var(--radius-full);
  vertical-align: middle;
}

/* 工具栏 */
.env-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);

  .env-search { width: 280px; }
  .toolbar-spacer { flex: 1; }
}

/* 类型筛选段 */
.seg-group {
  display: inline-flex;
  gap: var(--space-2);
}
.seg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-regular);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: var(--transition-fast);

  &:hover {
    border-color: var(--brand-300);
    color: var(--brand-600);
  }
  &.is-active {
    background: var(--brand-50);
    border-color: var(--brand-200);
    color: var(--brand-600);
    font-weight: var(--font-weight-medium);
  }
}
.seg-count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  color: var(--text-secondary);
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.seg.is-active .seg-count {
  background: var(--brand-100);
  color: var(--brand-700);
}

/* 环境列表 */
.environment-list {
  min-height: 400px;
  flex: 1;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: var(--space-4);
}

/* 环境卡片 */
.env-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: var(--transition-base);
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &:hover {
    box-shadow: var(--shadow-hover);
  }

  &.is-default {
    border-color: var(--color-success-300);
  }
}

.env-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-light);

  .more-btn { margin-left: auto; flex-shrink: 0; }
}

.env-card-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;

  &.api-type {
    background: var(--color-info-50);
    color: var(--color-info-600);
  }
  &.ui-type {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }
}

.env-card-title {
  flex: 1;
  min-width: 0;

  h3 {
    font-size: 15px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    margin: 0 0 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.env-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.env-card-body {
  flex: 1;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.env-info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.env-info-label {
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

.env-info-url {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--gray-50);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.env-info-desc {
  color: var(--text-primary);
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.env-info-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}

.env-card-footer {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light);
  background: var(--gray-50);

  .el-button {
    margin: 0;
  }
}

/* 软色 pill */
.soft-pill {
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: var(--font-weight-semibold);

  &.pill-brand { background: var(--brand-50); color: var(--brand-600); }
  &.pill-info { background: var(--color-info-50); color: var(--color-info-600); }
  &.pill-success { background: var(--color-success-50); color: var(--color-success-600); }
  &.pill-warning { background: var(--color-warning-50); color: var(--color-warning-600); }
}

/* 表格 */
.table-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.table-env-name {
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.table-tags {
  display: flex;
  gap: 4px;
}

.table-url {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--gray-50);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

/* 操作列按钮容器 */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 响应式 */
@media (max-width: 768px) {
  .card-grid { grid-template-columns: 1fr; }
  .env-toolbar { flex-wrap: wrap; }
  .env-toolbar .env-search { width: 100%; }
}
</style>
