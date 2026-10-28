<template>
  <div class="functions-view">
    <AppPageHeader
      icon="i-solar-code-bold"
      :illustration="illustEnvironment"
      title="全局函数"
      description="管理和复用自定义函数，提升测试脚本编写效率"
    >
      <template #actions>
        <el-button v-permission="'environment:create'" @click="aiDialogVisible = true">
          <i class="i-solar-cpu-bolt-bold mr-1" />
          AI 生成
        </el-button>
        <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
          <i class="i-solar-add-circle-bold mr-1" />
          新建函数
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 统计 -->
    <div class="stat-row">
      <AppStatCard
        label="函数总数"
        :value="allFunctions.length"
        icon-name="i-solar-shield-keyhole-bold"
        color="brand"
      />
      <AppStatCard
        label="内置函数"
        :value="builtinCount"
        icon-name="i-solar-medal-ribbon-bold"
        color="info"
      />
      <AppStatCard
        label="自定义函数"
        :value="customCount"
        icon-name="i-solar-pen-bold"
        color="success"
      />
      <AppStatCard
        label="已启用"
        :value="activeCount"
        icon-name="i-solar-check-circle-bold"
        color="warning"
      />
    </div>

    <!-- 筛选栏 -->
    <AppSectionCard>
      <div class="filter-bar">
        <el-select
          v-model="filters.type"
          placeholder="函数类型"
          clearable
          class="filter-select"
          @change="handleSearch"
        >
          <el-option label="全部类型" value="" />
          <el-option label="内置函数" value="built-in" />
          <el-option label="自定义函数" value="custom" />
        </el-select>

        <el-select
          v-model="filters.language"
          placeholder="编程语言"
          clearable
          class="filter-select"
          @change="handleSearch"
        >
          <el-option label="全部语言" value="" />
          <el-option label="Python" value="python" />
          <el-option label="JavaScript" value="javascript" />
        </el-select>

        <el-input
          v-model="filters.keyword"
          placeholder="搜索函数名称或描述"
          clearable
          class="filter-input"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <i class="i-solar-magnifer-linear" />
          </template>
        </el-input>

        <el-button @click="handleSearch">
          <i class="i-solar-magnifer-linear mr-1" /> 搜索
        </el-button>
        <el-button @click="handleReset">
          <i class="i-solar-refresh-linear mr-1" /> 重置
        </el-button>

        <div class="filter-spacer" />

        <el-button-group>
          <el-button
            :type="viewMode === 'card' ? 'primary' : 'default'"
            @click="viewMode = 'card'"
          >
            <i class="i-solar-widget-2-bold" />
          </el-button>
          <el-button
            :type="viewMode === 'table' ? 'primary' : 'default'"
            @click="viewMode = 'table'"
          >
            <i class="i-solar-list-bold" />
          </el-button>
        </el-button-group>
      </div>
    </AppSectionCard>

    <!-- 函数列表 -->
    <div v-loading="loading" class="functions-list">
      <AppEmpty
        v-if="!loading && allFunctions.length === 0"
        scene="data"
        title="暂无函数"
        description="创建第一个全局函数开始使用"
      >
        <template #actions>
          <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
            <i class="i-solar-add-circle-bold mr-1" />
            创建函数
          </el-button>
        </template>
      </AppEmpty>

      <!-- 卡片视图 -->
      <div v-else-if="viewMode === 'card'" class="card-grid">
        <div
          v-for="func in allFunctions"
          :key="func.name"
          class="function-card"
          :class="{ 'built-in': func.is_built_in, disabled: !func.is_active }"
        >
          <!-- 卡片头部 -->
          <div class="card-header">
            <div class="function-info">
              <div class="function-name-row">
                <h3 class="function-name">{{ func.display_name }}</h3>
                <span v-if="func.is_built_in" class="soft-pill pill-info">内置</span>
                <span class="soft-pill" :class="func.is_active ? 'pill-success' : 'pill-warning'">
                  <span v-if="func.is_active" class="status-dot" />
                  {{ func.is_active ? '已启用' : '已禁用' }}
                </span>
              </div>
              <code class="function-code-name">{{ func.name }}()</code>
            </div>
            <el-dropdown trigger="click" @command="handleCommand($event as string, func)">
              <el-button text size="small" class="more-btn">
                <i class="i-solar-menu-dots-bold" />
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="test">
                    <i class="i-solar-play-bold mr-1" /> 测试运行
                  </el-dropdown-item>
                  <el-dropdown-item command="edit" :disabled="func.is_built_in">
                    <i class="i-solar-pen-2-linear mr-1" /> 编辑
                  </el-dropdown-item>
                  <el-dropdown-item command="toggle">
                    <i :class="func.is_active ? 'i-solar-eye-closed-linear' : 'i-solar-eye-linear'" class="mr-1" />
                    {{ func.is_active ? '禁用' : '启用' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" :disabled="func.is_built_in" divided>
                    <i class="i-solar-trash-bin-trash-linear mr-1" /> 删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 卡片内容 -->
          <div class="card-content">
            <div v-if="func.description" class="description">
              {{ func.description }}
            </div>
            <div v-else class="description placeholder">暂无描述</div>
          </div>

          <!-- 卡片底部 -->
          <div class="card-footer">
            <span class="language-tag" :class="`lang-${func.language}`">
              <i class="i-solar-code-file-bold mr-1" />
              {{ func.language === 'python' ? 'Python' : 'JS' }}
            </span>
            <div class="footer-actions">
              <el-button
                size="small"
                :loading="testingIds.has(func.name)"
                @click="handleTest(func)"
              >
                <i class="i-solar-play-bold mr-1" /> 测试
              </el-button>
              <el-button
                v-permission="'environment:edit'"
                size="small"
                class="edit-soft-btn"
                :disabled="func.is_built_in"
                @click="handleEdit(func)"
              >
                <i class="i-solar-pen-2-linear mr-1" /> 编辑
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 表格视图 -->
      <AppSectionCard v-else padless>
        <el-table :data="allFunctions" class="function-table" @row-click="handleRowClick">
          <el-table-column label="函数名" min-width="220">
            <template #default="{ row }">
              <div class="table-name-cell">
                <span class="table-display-name">{{ row.display_name }}</span>
                <code class="table-code-name">{{ row.name }}()</code>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="语言" width="110" align="center">
            <template #default="{ row }">
              <span class="soft-pill" :class="row.language === 'python' ? 'pill-brand' : 'pill-warning'">
                <i :class="row.language === 'python' ? 'i-solar-python-bold' : 'i-solar-code-file-bold'" class="mr-1" />
                {{ row.language === 'python' ? 'Python' : 'JS' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.is_built_in" class="soft-pill pill-info">内置</span>
              <span v-else class="soft-pill pill-success">自定义</span>
            </template>
          </el-table-column>
          <el-table-column label="描述" min-width="260">
            <template #default="{ row }">
              <span class="table-desc">{{ row.description || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120" align="center">
            <template #default="{ row }">
              <span class="soft-pill" :class="row.is_active ? 'pill-success' : 'pill-warning'">
                <span v-if="row.is_active" class="status-dot" />
                {{ row.is_active ? '启用' : '禁用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="290" align="center" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  type="primary"
                  plain
                  size="small"
                  :loading="testingIds.has(row.name)"
                  @click.stop="handleTest(row)"
                >
                  <i class="i-solar-play-bold mr-1" />
                  测试
                </el-button>
                <el-button
                  v-permission="'environment:edit'"
                  size="small"
                  :disabled="row.is_built_in"
                  @click.stop="handleEdit(row)"
                >
                  <i class="i-solar-pen-2-linear mr-1" />
                  编辑
                </el-button>
                <el-button
                  v-permission="'environment:delete'"
                  type="danger"
                  plain
                  size="small"
                  :disabled="row.is_built_in"
                  @click.stop="handleDelete(row)"
                >
                  <i class="i-solar-trash-bin-trash-linear mr-1" />
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </AppSectionCard>
    </div>

    <!-- 创建/编辑函数对话框 -->
    <FunctionFormDialog
      v-model="formDialogVisible"
      :function-data="currentFunction"
      :project-id="projectId"
      @success="handleFormSuccess"
    />

    <!-- 测试函数对话框 -->
    <TestFunctionDialog
      v-model="testDialogVisible"
      :function-data="currentFunction"
      :project-id="projectId"
    />

    <!-- AI 生成函数对话框 -->
    <AiGenerateFunctionDialog
      v-model="aiDialogVisible"
      :project-id="projectId"
      @success="handleAiGenerateSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type {
  GlobalFunction,
  ScriptLanguage,
} from '@/api/environments'
import FunctionFormDialog from './components/FunctionFormDialog.vue'
import TestFunctionDialog from './components/TestFunctionDialog.vue'
import AiGenerateFunctionDialog from './components/AiGenerateFunctionDialog.vue'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import illustEnvironment from '@/assets/illustrations/environment.svg'

const route = useRoute()

// 项目ID
const projectId = computed(() => {
  const id = Number(route.params.id)
  return isNaN(id) ? 0 : id
})

// 视图模式
const viewMode = ref<'card' | 'table'>('card')

// 数据
const loading = ref(false)
const builtinFunctions = ref<GlobalFunction[]>([])
const customFunctions = ref<GlobalFunction[]>([])
const testingIds = ref<Set<string>>(new Set())

// 筛选条件
const filters = ref<{
  type: 'built-in' | 'custom' | ''
  language: ScriptLanguage | ''
  keyword: string
}>({
  type: '',
  language: '',
  keyword: '',
})

// 所有函数（合并和筛选）
const allFunctions = computed(() => {
  let functions = [...builtinFunctions.value, ...customFunctions.value]

  // 类型筛选
  if (filters.value.type === 'built-in') {
    functions = functions.filter((f) => f.is_built_in)
  } else if (filters.value.type === 'custom') {
    functions = functions.filter((f) => !f.is_built_in)
  }

  // 语言筛选
  if (filters.value.language) {
    functions = functions.filter((f) => f.language === filters.value.language)
  }

  // 关键词搜索
  if (filters.value.keyword) {
    const keyword = filters.value.keyword.toLowerCase()
    functions = functions.filter(
      (f) =>
        f.name.toLowerCase().includes(keyword) ||
        f.display_name.toLowerCase().includes(keyword) ||
        (f.description && f.description.toLowerCase().includes(keyword)),
    )
  }

  return functions
})

// 统计
const builtinCount = computed(() => builtinFunctions.value.length)
const customCount = computed(() => customFunctions.value.length)
const activeCount = computed(() =>
  allFunctions.value.filter((f) => f.is_active).length,
)

// 对话框状态
const formDialogVisible = ref(false)
const testDialogVisible = ref(false)
const aiDialogVisible = ref(false)
const currentFunction = ref<GlobalFunction | null>(null)

// 加载函数列表
const loadFunctions = async () => {
  loading.value = true
  try {
    const params: { language?: ScriptLanguage } = {}
    if (filters.value.language) {
      params.language = filters.value.language
    }

    const res = await environmentApi.getFunctionList(projectId.value, params)
    builtinFunctions.value = res.data.built_in || []
    customFunctions.value = res.data.custom || []
  } catch (error) {
    console.error('加载函数列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => { loadFunctions() }
const handleReset = () => {
  filters.value = { type: '', language: '', keyword: '' }
  loadFunctions()
}

// 表格行点击
const handleRowClick = (row: GlobalFunction) => {
  currentFunction.value = row
}

// 创建函数
const handleCreate = () => {
  currentFunction.value = null
  formDialogVisible.value = true
}

// 编辑函数
const handleEdit = (func: GlobalFunction) => {
  currentFunction.value = func
  formDialogVisible.value = true
}

// 测试函数
const handleTest = (func: GlobalFunction) => {
  currentFunction.value = func
  testDialogVisible.value = true
}

// 删除函数
const handleDelete = async (func: GlobalFunction) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除函数 "${func.display_name}" 吗？删除后将无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    if (!func.id) return
    await environmentApi.deleteFunction(projectId.value, func.id)
    ElMessage.success('删除成功')
    loadFunctions()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除函数失败:', error)
    }
  }
}

// 切换启用状态
const handleToggleStatus = async (func: GlobalFunction) => {
  try {
    if (!func.id) return
    await environmentApi.toggleFunctionStatus(projectId.value, func.id, {
      is_active: !func.is_active,
    })
    ElMessage.success(func.is_active ? '已禁用' : '已启用')
    loadFunctions()
  } catch (error) {
    console.error('更新函数状态失败:', error)
  }
}

const handleDropdownCommand = (command: string | number | object, func: GlobalFunction) => {
  handleCommand(String(command), func)
}

// 处理下拉菜单命令
const handleCommand = (command: string, func: GlobalFunction) => {
  switch (command) {
    case 'test':
      handleTest(func)
      break
    case 'edit':
      handleEdit(func)
      break
    case 'toggle':
      handleToggleStatus(func)
      break
    case 'delete':
      handleDelete(func)
      break
  }
}

// 表单成功回调
const handleFormSuccess = () => {
  formDialogVisible.value = false
  loadFunctions()
}

// AI 生成成功回调
const handleAiGenerateSuccess = () => {
  ElMessage.success('函数已生成并保存')
  loadFunctions()
}

// 初始化
onMounted(() => {
  loadFunctions()
})
</script>

<style scoped lang="scss">
.functions-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-bottom: var(--space-5);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);

  .filter-select { width: 160px; }
  .filter-input { width: 240px; }
  .filter-spacer { flex: 1; }
}

.functions-list {
  min-height: 400px;
  flex: 1;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

/* 函数卡片 - 无边框，用阴影区分 */
.function-card {
  background: var(--bg-card);
  border: 0;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: var(--transition-base);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 220px;
  max-height: 260px;

  &:hover {
    box-shadow: var(--shadow-hover);
  }

  &.disabled {
    opacity: 0.65;
  }
}

/* 卡片头部 */
.function-card .card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-light);

  .more-btn { margin-left: auto; flex-shrink: 0; }
}

.function-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.function-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.function-name {
  font-size: 15px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.function-code-name {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'Consolas', 'Monaco', monospace;
}

/* 卡片内容 */
.function-card .card-content {
  flex: 1;
  padding: var(--space-4);
}

.description {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;

  &.placeholder {
    color: var(--text-placeholder);
    font-style: italic;
  }
}

/* 卡片底部 */
.function-card .card-footer {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--gray-50);

  .footer-actions {
    display: flex;
    gap: var(--space-2);
    margin-left: auto;
    flex-shrink: 0;
  }
}

.edit-soft-btn {
  --el-button-bg-color: var(--brand-50);
  --el-button-border-color: var(--brand-50);
  --el-button-text-color: var(--brand-600);
  --el-button-hover-bg-color: var(--brand-100);
  --el-button-hover-border-color: var(--brand-100);
  --el-button-hover-text-color: var(--brand-700);
  box-shadow: none !important;
}

/* 语言标签 */
.language-tag {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  padding: 2px 8px;
  border-radius: var(--radius-sm);

  &.lang-python,
  &.lang-javascript {
    background: var(--brand-50);
    color: var(--brand-600);
  }
}

/* 软色 pill */
.soft-pill {
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;

  &.pill-brand { background: var(--brand-50); color: var(--brand-600); }
  &.pill-info { background: var(--color-info-50); color: var(--color-info-600); }
  &.pill-success { background: var(--color-success-50); color: var(--color-success-600); }
  &.pill-warning { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.pill-danger { background: var(--color-danger-50); color: var(--color-danger-600); }
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;

  .pill-success & {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-success-500) 20%, transparent);
  }
}

/* 表格 */
.function-table {
  :deep(th.el-table__cell) {
    background: var(--gray-50);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
  }
}

.table-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.table-display-name {
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.table-code-name {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'Consolas', 'Monaco', monospace;
}

.table-desc {
  font-size: 13px;
  color: var(--text-primary);
}

/* 表格操作列 */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 响应式 */
@media (max-width: 768px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .card-grid { grid-template-columns: 1fr; }
  .filter-bar { flex-wrap: wrap; }
  .filter-select, .filter-input { width: 100%; }
}
</style>