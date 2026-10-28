<template>
  <div class="variables-panel">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-if="!isFixedEnv"
          v-model="selectedEnvId"
          placeholder="选择环境"
          style="width: 200px"
          @change="handleEnvChange"
        >
          <el-option
            v-for="env in environments"
            :key="env.id"
            :label="env.name"
            :value="env.id"
          >
            <span>{{ env.name }}</span>
            <span v-if="env.is_default" class="env-tag">
              <el-tag size="small" type="success">默认</el-tag>
            </span>
          </el-option>
        </el-select>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索变量名"
          clearable
          :style="{ width: '200px', marginLeft: isFixedEnv ? '0' : '12px' }"
          @input="handleSearch"
        >
          <template #prefix>
            <i class="i-solar-magnifer-linear" />
          </template>
        </el-input>
      </div>
      <div class="toolbar-right">
        <el-button v-permission="'environment:create'" @click="handleImport">
          <i class="i-solar-upload-linear mr-1" />
          导入
        </el-button>
        <el-button @click="handleExport" :disabled="!hasVariables">
          <i class="i-solar-download-linear mr-1" />
          导出
        </el-button>
        <el-button v-permission="'environment:create'" type="primary" @click="handleCreate" :disabled="!selectedEnvId">
          <i class="i-solar-add-circle-bold mr-1" />
          添加变量
        </el-button>
      </div>
    </div>

    <!-- 变量列表 -->
    <div v-loading="loading" class="variables-content">
      <!-- 未选择环境提示 -->
      <div v-if="!selectedEnvId" class="empty-state">
        <el-empty description="请先选择一个测试环境">
          <el-icon :size="80" color="var(--workspace-text-placeholder)">
            <Box />
          </el-icon>
        </el-empty>
      </div>

      <!-- 环境无变量提示 -->
      <div v-else-if="!loading && variables.length === 0" class="empty-state">
        <el-empty description="该环境暂无变量">
          <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
            <i class="i-solar-add-circle-bold mr-1" />
            添加第一个变量
          </el-button>
        </el-empty>
      </div>

      <!-- 变量表格 -->
      <div v-else class="variables-table-wrapper">
        <!-- 批量操作栏 -->
        <div v-if="selectedVariables.length > 0" class="batch-actions">
          <span class="selected-count">已选择 {{ selectedVariables.length }} 项</span>
          <div class="batch-buttons">
            <el-button v-permission="'environment:edit'" size="small" @click="handleBatchActivate">
              批量启用
            </el-button>
            <el-button v-permission="'environment:edit'" size="small" @click="handleBatchInactivate">
              批量禁用
            </el-button>
            <el-button v-permission="'environment:delete'" size="small" type="danger" @click="handleBatchDelete">
              批量删除
            </el-button>
            <el-button size="small" @click="clearSelection">
              取消选择
            </el-button>
          </div>
        </div>

        <el-table
          ref="tableRef"
          :data="variables"
          row-key="id"
          :default-sort="{ prop: 'sort_order', order: 'ascending' }"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="50" align="center" />
          <el-table-column label="序号" type="index" width="60" align="center" />
          <el-table-column
            prop="name"
            label="变量名"
            min-width="150"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <div class="variable-name">
                <el-icon v-if="row.type === 'password'" :size="14"><Lock /></el-icon>
                <el-icon v-else-if="row.type === 'json'" :size="14"><Document /></el-icon>
                <el-icon v-else :size="14"><Key /></el-icon>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="value" label="变量值" min-width="200">
            <template #default="{ row }">
              <div class="variable-value">
                <code v-if="row.type === 'password'">****</code>
                <code v-else class="value-text">{{ row.value }}</code>
                <el-button
                  v-if="row.type === 'password'"
                  text
                  size="small"
                  @click="handleToggleValue(row)"
                >
                  <el-icon :size="14"><View /></el-icon>
                </el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getTypeTagType(row.type)" size="small">
                {{ getTypeLabel(row.type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
          <el-table-column prop="is_active" label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-switch
                v-permission.disable="'environment:edit'"
                v-model="row.is_active"
                @change="handleToggleActive(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  v-permission="'environment:edit'"
                  size="small"
                  @click="handleEdit(row)"
                >
                  <i class="i-solar-pen-2-linear mr-1" />
                  编辑
                </el-button>
                <el-button
                  v-permission="'environment:delete'"
                  type="danger"
                  plain
                  size="small"
                  @click="handleDelete(row)"
                >
                  <i class="i-solar-trash-bin-trash-linear mr-1" />
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 创建/编辑变量对话框 -->
    <VariableFormDialog
      v-if="formDialogVisible"
      v-model="formDialogVisible"
      :variable="currentVariable"
      :env-id="selectedEnvId!"
      :project-id="projectId"
      @success="handleFormSuccess"
    />

    <!-- 导入变量对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入变量"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top"
        ref="importFormRef"
        :model="importForm"
        :rules="importRules"
      >
        <el-form-item label="导入模式" prop="mode">
          <el-radio-group v-model="importForm.mode">
            <el-radio value="merge">合并</el-radio>
            <el-radio value="replace">替换</el-radio>
          </el-radio-group>
          <div class="form-tip">
            <span v-if="importForm.mode === 'merge'">合并模式：保留现有变量，导入新变量</span>
            <span v-else>替换模式：清空现有变量后导入</span>
          </div>
        </el-form-item>
        <el-form-item label="变量数据" prop="content">
          <el-input
            v-model="importForm.content"
            type="textarea"
            :rows="8"
            placeholder='粘贴 JSON 格式的变量数据，例如：&#10;{&#10;  "environment": "测试环境",&#10;  "variables": [&#10;    { "name": "api_key", "value": "xxx", "type": "text" }&#10;  ]&#10;}}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button v-permission="'environment:create'" type="primary" :loading="importing" @click="handleDoImport">
          导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type { Environment, EnvironmentVariable, VariableType } from '@/api/environments'
import VariableFormDialog from './VariableFormDialog.vue'

interface Props {
  projectId: number
  envId?: number  // 固定的环境ID，如果提供则不显示环境选择器
}

const props = defineProps<Props>()

// 数据
const loading = ref(false)
const environments = ref<Environment[]>([])
const variables = ref<EnvironmentVariable[]>([])
const searchKeyword = ref('')

// 选中的环境
const selectedEnvId = ref<number | null>(null)

// 当前编辑的变量
const currentVariable = ref<EnvironmentVariable | null>(null)

// 对话框状态
const formDialogVisible = ref(false)
const importDialogVisible = ref(false)
const importing = ref(false)

// 批量选择
const tableRef = ref()
const selectedVariables = ref<EnvironmentVariable[]>([])

// 导入表单
const importFormRef = ref<FormInstance>()
const importForm = ref({
  mode: 'merge' as 'merge' | 'replace',
  content: '',
})
const importRules: FormRules = {
  content: [{ required: true, message: '请输入变量数据', trigger: 'blur' }],
}

// 计算属性
const hasVariables = computed(() => variables.value.length > 0)
const isFixedEnv = computed(() => !!props.envId)  // 是否为固定环境模式

// 加载环境列表
const loadEnvironments = async () => {
  // 如果是固定环境模式，不需要加载环境列表
  if (isFixedEnv.value) {
    const envIdValue = typeof props.envId === 'number' ? props.envId : Number(props.envId)
    if (isNaN(envIdValue)) {
      console.error('无效的 envId:', props.envId)
      return
    }
    selectedEnvId.value = envIdValue
    await loadVariables()
    return
  }

  loading.value = true
  try {
    const res = await environmentApi.getEnvironmentList(props.projectId)
    environments.value = res.data
    // 自动选择默认环境或第一个环境
    if (environments.value.length > 0) {
      const defaultEnv = environments.value.find(e => e.is_default) || environments.value[0]
      if (!selectedEnvId.value) {
        selectedEnvId.value = defaultEnv.id
        await loadVariables()
      }
    }
  } catch (error) {
    console.error('加载环境列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载变量列表
const loadVariables = async () => {
  if (!selectedEnvId.value) return

  loading.value = true
  try {
    const res = await environmentApi.getVariableList(props.projectId, selectedEnvId.value)
    variables.value = res.data
  } catch (error) {
    console.error('加载变量列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 环境切换
const handleEnvChange = () => {
  searchKeyword.value = ''
  selectedVariables.value = []
  loadVariables()
}

// 搜索
const handleSearch = () => {
  // 可以在这里实现搜索过滤
}

// 创建变量
const handleCreate = () => {
  currentVariable.value = null
  formDialogVisible.value = true
}

// 编辑变量
const handleEdit = (row: EnvironmentVariable) => {
  currentVariable.value = row
  formDialogVisible.value = true
}

// 删除变量
const handleDelete = async (row: EnvironmentVariable) => {
  if (!selectedEnvId.value) {
    ElMessage.warning('请先选择环境')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除变量 "${row.name}" 吗？`, '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await environmentApi.deleteVariable(props.projectId, selectedEnvId.value, row.id)
    ElMessage.success('删除成功')
    loadVariables()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除变量失败:', error)
    }
  }
}

// 切换变量状态
const handleToggleActive = async (row: EnvironmentVariable) => {
  try {
    await environmentApi.updateVariable(props.projectId, selectedEnvId.value!, row.id, {
      is_active: row.is_active,
    })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
    loadVariables()
  } catch (error) {
    console.error('更新变量状态失败:', error)
    // 恢复状态
    row.is_active = !row.is_active
  }
}

// 切换密码显示
const handleToggleValue = (row: EnvironmentVariable) => {
  // 这里可以实现临时显示密码的功能
  ElMessage.info('密码变量已隐藏')
}

// 选择变化
const handleSelectionChange = (selection: EnvironmentVariable[]) => {
  selectedVariables.value = selection
}

// 清除选择
const clearSelection = () => {
  tableRef.value?.clearSelection()
}

// 批量启用
const handleBatchActivate = async () => {
  if (selectedVariables.value.length === 0) return

  try {
    const ids = selectedVariables.value.map(v => v.id)
    await environmentApi.batchUpdateVariables(props.projectId, selectedEnvId.value!, {
      variables: selectedVariables.value.map(v => ({
        id: v.id,
        value: v.value,
        is_active: true,
      })),
    })
    ElMessage.success('批量启用成功')
    clearSelection()
    loadVariables()
  } catch (error) {
    console.error('批量启用失败:', error)
  }
}

// 批量禁用
const handleBatchInactivate = async () => {
  if (selectedVariables.value.length === 0) return

  try {
    const ids = selectedVariables.value.map(v => v.id)
    await environmentApi.batchUpdateVariables(props.projectId, selectedEnvId.value!, {
      variables: selectedVariables.value.map(v => ({
        id: v.id,
        value: v.value,
        is_active: false,
      })),
    })
    ElMessage.success('批量禁用成功')
    clearSelection()
    loadVariables()
  } catch (error) {
    console.error('批量禁用失败:', error)
  }
}

// 批量删除
const handleBatchDelete = async () => {
  if (selectedVariables.value.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedVariables.value.length} 个变量吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    const ids = selectedVariables.value.map(v => v.id)
    await environmentApi.batchDeleteVariables(props.projectId, selectedEnvId.value!, { ids })
    ElMessage.success('批量删除成功')
    clearSelection()
    loadVariables()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
    }
  }
}

// 导入
const handleImport = () => {
  if (!selectedEnvId.value) {
    ElMessage.warning('请先选择环境')
    return
  }
  importForm.value.content = ''
  importDialogVisible.value = true
}

// 执行导入
const handleDoImport = async () => {
  if (!importFormRef.value) return

  await importFormRef.value.validate(async (valid) => {
    if (!valid) return

    importing.value = true
    try {
      let content: any
      try {
        content = JSON.parse(importForm.value.content)
      } catch {
        // 如果不是JSON，尝试解析为纯文本
        content = {
          environment: '',
          variables: importForm.value.content.split('\n').map((line: string) => {
            const [name, value] = line.split('=').map((s: string) => s.trim())
            return { name, value: name ? value || '' : '' }
          }).filter((v: any) => v.name)
        }
      }

      await environmentApi.importVariables(props.projectId, selectedEnvId.value!, {
        content,
        mode: importForm.value.mode,
      })
      ElMessage.success('导入成功')
      importDialogVisible.value = false
      loadVariables()
    } catch (error: any) {
      console.error('导入失败:', error)
    } finally {
      importing.value = false
    }
  })
}

// 导出
const handleExport = async () => {
  if (!hasVariables.value) return

  try {
    const res = await environmentApi.exportVariables(props.projectId, selectedEnvId.value!)
    const data = res.data

    // 创建下载
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `variables_${selectedEnvId}_${new Date().getTime()}.json`
    link.click()
    URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
  }
}

// 表单成功回调
const handleFormSuccess = () => {
  formDialogVisible.value = false
  currentVariable.value = null
  loadVariables()
}

// 获取类型标签类型
const getTypeTagType = (type: VariableType) => {
  const typeMap: Record<VariableType, string> = {
    text: '',
    password: 'warning',
    json: 'success',
    dynamic: 'info',
  }
  return typeMap[type] || ''
}

// 获取类型标签
const getTypeLabel = (type: VariableType) => {
  const labelMap: Record<VariableType, string> = {
    text: '文本',
    password: '密码',
    json: 'JSON',
    dynamic: '动态',
  }
  return labelMap[type] || type
}

// 初始化
onMounted(() => {
  loadEnvironments()
})

// 监听 envId prop 的变化
watch(
  () => props.envId,
  (newEnvId) => {
    const envIdValue = typeof newEnvId === 'number' ? newEnvId : Number(newEnvId)
    if (!isNaN(envIdValue) && envIdValue !== selectedEnvId.value) {
      selectedEnvId.value = envIdValue
      loadVariables()
    }
  },
)
</script>

<style scoped lang="scss">
.variables-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

// ========================================
// 工具栏
// ========================================

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding: 4px 0;

  .toolbar-left {
    display: flex;
    align-items: center;
  }

  .toolbar-right {
    display: flex;
    gap: 12px;
  }
}

// ========================================
// 内容区
// ========================================

.variables-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;

  :deep(.el-empty) {
    padding: 60px 0;
  }
}

.variables-table-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// ========================================
// 批量操作栏
// ========================================

.batch-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--workspace-fill-color-light);
  border: 1px solid var(--workspace-color-primary-light-9);
  border-radius: 8px 8px 0 0;

  .selected-count {
    font-size: 14px;
    color: var(--workspace-text-regular);
    font-weight: 500;
  }

  .batch-buttons {
    display: flex;
    gap: 8px;
  }
}

// ========================================
// 操作列
// ========================================

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

// ========================================
// 变量表格
// ========================================

:deep(.el-table) {
  flex: 1;
  border-radius: 0 0 8px 8px;
  overflow: hidden;

  .el-table__header-wrapper {
    background: var(--workspace-table-header-bg);
  }

  th.el-table__cell {
    background: var(--workspace-table-header-bg);
    color: var(--workspace-table-header-text);
    font-weight: 600;
    border-bottom: 1px solid var(--workspace-table-border);
  }

  td.el-table__cell {
    border-bottom: 1px solid var(--workspace-table-border);
  }

  .el-table__row:hover {
    background: var(--workspace-row-hover-bg);
  }

  .el-table__body tr {
    transition: background-color 0.2s;
  }
}

.variable-name {
  display: flex;
  align-items: center;
  gap: 6px;

  .el-icon {
    flex-shrink: 0;
    color: var(--workspace-color-primary);
  }

  span {
    font-weight: 500;
    color: var(--workspace-text-primary);
  }
}

.variable-value {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;

  code {
    font-family: 'SF Mono', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', monospace;
    font-size: 12px;
    color: var(--workspace-text-primary);
    background: var(--workspace-fill-color-light);
    padding: 4px 8px;
    border-radius: 4px;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;

    &.value-text {
      color: var(--workspace-color-primary);
      background: rgba(var(--theme-rgb-primary), 0.08);
    }
  }
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--workspace-text-secondary);
}

.env-tag {
  margin-left: 8px;
}

// ========================================
// 响应式
// ========================================

@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;

    .toolbar-left {
      flex-direction: column;
      align-items: stretch;
      gap: 12px;

      .el-select {
        width: 100% !important;
      }
    }

    .toolbar-right {
      justify-content: space-between;

      .el-button {
        flex: 1;
      }
    }
  }

  .batch-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;

    .batch-buttons {
      flex-direction: column;
    }
  }
}
</style>
