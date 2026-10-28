/**
 * 项目模块管理页面
 *
 * AI 智能测试平台 - 项目模块管理页面
 * 对应需求文档：02-项目管理模块.md
 * 对应 API 文档：02-项目管理模块API.md
 */

<template>
  <div class="project-modules-page">
    <AppPageHeader
      icon="i-solar-folder-bold"
      :illustration="illustModules"
      title="模块管理"
      description="管理项目功能模块层级结构，支持最多 5 级嵌套"
      :breadcrumbs="['项目配置', '模块管理']"
    >
      <template #actions>
        <el-button @click="handleRefresh">
          <i class="i-solar-refresh-linear btn-icon" />
          刷新
        </el-button>
        <el-button v-permission="'module:add'" type="primary" @click="handleCreateModule(null)">
          <i class="i-solar-add-circle-bold btn-icon" />
          创建根模块
        </el-button>
      </template>
    </AppPageHeader>

    <div class="modules-content">
      <!-- 左侧：模块树 -->
      <AppSectionCard class="tree-card" content-class="tree-card-body">
        <template #header>
          <div class="card-hd">
            <div class="card-hd-left">
              <span class="card-title">模块结构</span>
            </div>
            <button v-permission="'module:add'" class="icon-action" type="button" @click="handleCreateModule(null)">
              <i class="i-solar-add-circle-bold" />
            </button>
          </div>
        </template>

        <div v-loading="loading" class="tree-container">
          <div class="tree-summary">
            <span class="summary-label">
              <i class="i-solar-folder-open-bold" />
              全部模块
            </span>
            <span class="summary-count">{{ moduleCount }}</span>
          </div>

          <el-tree
            v-if="moduleTree.length > 0"
            ref="treeRef"
            :data="moduleTree"
            :props="treeProps"
            :default-expand-all="false"
            :expand-on-click-node="false"
            :highlight-current="true"
            node-key="id"
            class="module-tree"
            @node-click="handleNodeClick"
          >
            <template #default="{ node, data }">
              <div class="tree-node" :class="{ 'is-selected': selectedModule?.id === data.id }">
                <div class="node-content">
                  <i class="i-solar-folder-bold node-icon" />
                  <span class="node-label" :title="node.label">{{ node.label }}</span>
                  <span v-if="data.case_count > 0" class="count-pill">{{ data.case_count }}</span>
                </div>
                <div class="node-actions" @click.stop>
                  <el-dropdown @command="(cmd: string) => handleNodeCommand(cmd, data)" trigger="click">
                    <button class="node-more" type="button">
                      <i class="i-solar-menu-dots-bold" />
                    </button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item v-permission="'module:add'" command="add">
                          <i class="i-solar-add-circle-linear dropdown-icon" />
                          添加子模块
                        </el-dropdown-item>
                        <el-dropdown-item v-permission="'module:edit'" command="edit">
                          <i class="i-solar-pen-linear dropdown-icon" />
                          编辑
                        </el-dropdown-item>
                        <el-dropdown-item command="move">
                          <i class="i-solar-sort-vertical-linear dropdown-icon" />
                          移动
                        </el-dropdown-item>
                        <el-dropdown-item
                          v-permission="'module:delete'"
                          command="delete"
                          :disabled="!canDeleteModule(data)"
                          divided
                        >
                          <i class="i-solar-trash-bin-trash-linear dropdown-icon danger" />
                          删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </template>
          </el-tree>

          <AppEmpty
            v-else-if="!loading"
            class="tree-empty"
            scene="data"
            title="暂无模块"
            description="创建第一个模块后，可以继续添加子模块构建业务层级"
          >
            <template #actions>
              <el-button v-permission="'module:add'" type="primary" @click="handleCreateModule(null)">
                <i class="i-solar-add-circle-bold btn-icon" />
                创建第一个模块
              </el-button>
            </template>
          </AppEmpty>
        </div>
      </AppSectionCard>

      <!-- 右侧：模块详情 -->
      <div class="module-detail-section">
        <AppSectionCard v-if="detailLoading" class="detail-card">
          <el-skeleton :rows="8" animated />
        </AppSectionCard>

        <template v-else-if="selectedModule">
          <!-- 模块概览 -->
          <AppSectionCard title="模块概览" class="overview-card">
            <div class="overview-grid">
              <div class="metric-card info">
                <span class="metric-icon"><i class="i-solar-folder-bold" /></span>
                <div>
                  <div class="metric-value">{{ getChildrenCount(selectedModule) }}</div>
                  <div class="metric-label">子模块数量</div>
                </div>
              </div>
              <div class="metric-card success">
                <span class="metric-icon"><i class="i-solar-document-text-bold" /></span>
                <div>
                  <div class="metric-value">{{ selectedModule.case_count }}</div>
                  <div class="metric-label">用例数量</div>
                </div>
              </div>
              <div class="metric-card warning">
                <span class="metric-icon"><i class="i-solar-code-square-bold" /></span>
                <div>
                  <div class="metric-value">{{ selectedModule.sort_order }}</div>
                  <div class="metric-label">排序顺序</div>
                </div>
              </div>
              <div class="metric-card danger">
                <span class="metric-icon"><i class="i-solar-link-circle-bold" /></span>
                <div>
                  <div class="metric-value">{{ relatedSceneCount }}</div>
                  <div class="metric-label">关联测试场景</div>
                </div>
              </div>
            </div>
          </AppSectionCard>

          <!-- 模块信息 -->
          <AppSectionCard class="info-card">
            <template #header>
              <div class="card-hd compact">
                <span class="card-title">模块信息</span>
                <el-button v-permission="'module:edit'" size="small" @click="handleEditModule(selectedModule)">
                  <i class="i-solar-pen-linear btn-icon" />
                  编辑模块
                </el-button>
              </div>
            </template>

            <div class="info-overview">
              <div class="module-main-info">
                <span class="module-avatar">
                  <i class="i-solar-folder-bold" />
                </span>
                <div class="module-main-text">
                  <div class="module-name-line">
                    <strong>{{ selectedModule.name }}</strong>
                    <span class="level-pill">{{ selectedModule.parent_id ? '子模块' : '根模块' }}</span>
                  </div>
                  <div class="module-code-line mono">{{ moduleCode }}</div>
                </div>
              </div>
              <div class="module-desc-box">
                {{ selectedModule.description || '暂无描述' }}
              </div>
            </div>

            <div class="info-card-grid">
              <div class="info-tile">
                <span class="tile-icon brand-soft"><i class="i-solar-folder-open-bold" /></span>
                <div>
                  <div class="tile-label">父级模块</div>
                  <div class="tile-value">{{ parentModuleName }}</div>
                </div>
              </div>
              <div class="info-tile">
                <span class="tile-icon info-soft"><i class="i-solar-user-bold" /></span>
                <div>
                  <div class="tile-label">创建人</div>
                  <div class="tile-value">系统管理员</div>
                </div>
              </div>
              <div class="info-tile">
                <span class="tile-icon success-soft"><i class="i-solar-calendar-add-bold" /></span>
                <div>
                  <div class="tile-label">创建时间</div>
                  <div class="tile-value mono">{{ formatDate(selectedModule.created_at) }}</div>
                </div>
              </div>
              <div class="info-tile">
                <span class="tile-icon warning-soft"><i class="i-solar-clock-circle-bold" /></span>
                <div>
                  <div class="tile-label">更新时间</div>
                  <div class="tile-value mono">{{ formatDate(selectedModule.updated_at) }}</div>
                </div>
              </div>
            </div>

            <div v-if="!canDeleteModule(selectedModule)" class="warning-tip">
              <i class="i-solar-danger-triangle-bold" />
              <span>该模块无法删除：{{ getDeleteReason(selectedModule) }}</span>
            </div>
          </AppSectionCard>

          <!-- 子模块列表 -->
          <AppSectionCard class="children-card" padless>
            <template #header>
              <div class="card-hd compact">
                <span class="card-title">子模块列表</span>
                <el-dropdown @command="handleBatchCommand">
                  <el-button size="small">
                    批量操作
                    <i class="i-solar-alt-arrow-down-linear btn-icon-right" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-permission="'module:add'" command="create">
                        <i class="i-solar-add-circle-linear dropdown-icon" />
                        新增子模块
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>

            <div class="children-toolbar">
              <el-input
                v-model="childKeyword"
                placeholder="搜索子模块名称"
                clearable
                class="child-search"
              >
                <template #prefix>
                  <i class="i-solar-magnifer-linear" />
                </template>
              </el-input>
            </div>

            <el-table :data="filteredChildren" class="children-table">
              <template #empty>
                <AppEmpty
                  class="table-empty"
                  :scene="childKeyword ? 'search' : 'data'"
                  :title="childKeyword ? '未找到子模块' : '暂无子模块'"
                  :description="childKeyword ? '换个关键词试试' : '当前模块下还没有子模块，可以新增一个子模块'"
                >
                  <template v-if="!childKeyword" #actions>
                    <el-button v-permission="'module:add'" type="primary" @click="handleCreateModule(selectedModule)">
                      <i class="i-solar-add-circle-bold btn-icon" />
                      新增子模块
                    </el-button>
                  </template>
                </AppEmpty>
              </template>
              <el-table-column prop="name" label="模块名称" min-width="160" />
              <el-table-column label="模块标识" min-width="160">
                <template #default="{ row }">
                  <span class="mono muted-text">{{ getModuleCode(row) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="case_count" label="用例数量" width="120" align="center" />
              <el-table-column label="子模块数" width="120" align="center">
                <template #default="{ row }">{{ getChildrenCount(row) }}</template>
              </el-table-column>
              <el-table-column label="关联场景" width="120" align="center">
                <template #default="{ row }">{{ getRelatedSceneCount(row) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="120" align="center">
                <template #default="{ row }">
                  <div class="row-actions">
                    <el-button v-permission="'module:edit'" size="small" @click="handleEditModule(row)">
                      <i class="i-solar-pen-2-linear" />
                    </el-button>
                    <el-dropdown @command="(cmd: string) => handleNodeCommand(cmd, row)">
                      <el-button size="small">
                        <i class="i-solar-menu-dots-bold" />
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item v-permission="'module:add'" command="add">添加子模块</el-dropdown-item>
                          <el-dropdown-item command="move">移动</el-dropdown-item>
                          <el-dropdown-item v-permission="'module:delete'" command="delete" :disabled="!canDeleteModule(row)" divided>删除</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>
                </template>
              </el-table-column>
            </el-table>

            <div class="table-footer">
              <span>共 {{ filteredChildren.length }} 条</span>
            </div>
          </AppSectionCard>
        </template>

        <AppSectionCard v-else class="empty-detail-card">
          <AppEmpty
            scene="data"
            title="请选择模块"
            description="点击左侧模块树节点，查看模块信息、概览统计和子模块列表"
          >
            <template #actions>
              <el-button v-permission="'module:add'" type="primary" @click="handleCreateModule(null)">
                <i class="i-solar-add-circle-bold btn-icon" />
                创建根模块
              </el-button>
            </template>
          </AppEmpty>
        </AppSectionCard>
      </div>
    </div>

    <ModuleFormDialog
      v-model="dialogVisible"
      :mode="dialogMode"
      :project-id="projectId"
      :module="currentModule"
      :parent-module="parentModule"
      :module-tree="moduleTree"
      @success="handleDialogSuccess"
    />

    <ModuleMoveDialog
      v-model="moveDialogVisible"
      :project-id="projectId"
      :module="moduleToMove"
      :module-tree="moduleTree"
      @success="handleMoveSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi } from '@/api/projects'
import type { ProjectModule } from '@/api/projects'
import type { ElTree } from 'element-plus'
import { AppEmpty, AppPageHeader, AppSectionCard, AppStatCard } from '@/components/common'
import ModuleFormDialog from '@/components/project/ModuleFormDialog.vue'
import ModuleMoveDialog from '@/components/project/ModuleMoveDialog.vue'
import illustModules from '@/assets/illustrations/modules.svg'

const route = useRoute()

// ==================== 状态 ====================

/** 项目ID */
const projectId = computed(() => Number(route.params.id))

/** 加载状态 */
const loading = ref(false)

/** 详情加载状态 */
const detailLoading = ref(false)

/** 模块树数据 */
const moduleTree = ref<ProjectModule[]>([])

/** 当前选中的模块 */
const selectedModule = ref<ProjectModule | null>(null)

/** 对话框显示状态 */
const dialogVisible = ref(false)

/** 对话框模式 */
const dialogMode = ref<'create' | 'edit'>('create')

/** 当前操作的模块 */
const currentModule = ref<ProjectModule | null>(null)

/** 父模块（用于创建子模块） */
const parentModule = ref<ProjectModule | null>(null)

/** 移动对话框显示状态 */
const moveDialogVisible = ref(false)

/** 待移动的模块 */
const moduleToMove = ref<ProjectModule | null>(null)

/** 树组件引用 */
const treeRef = ref<InstanceType<typeof ElTree> | null>(null)

/** 树组件配置 */
const treeProps = {
  children: 'children',
  label: 'name',
}

/** 子模块搜索关键词 */
const childKeyword = ref('')

// ==================== 计算属性 ====================

/** 模块总数 */
const moduleCount = computed(() => {
  const countModules = (modules: ProjectModule[]): number => {
    let count = 0
    for (const module of modules) {
      count += 1
      if (module.children && module.children.length > 0) {
        count += countModules(module.children)
      }
    }
    return count
  }
  return countModules(moduleTree.value)
})

/** 模块标识：从 path 提取最后一段 */
const moduleCode = computed(() => {
  if (!selectedModule.value) return '-'
  const parts = selectedModule.value.path.split('/')
  return parts[parts.length - 1]
})

/** 父模块名称 */
const parentModuleName = computed(() => {
  if (!selectedModule.value || !selectedModule.value.parent_id) return '根模块'
  const findName = (modules: ProjectModule[]): string | null => {
    for (const m of modules) {
      if (m.id === selectedModule.value!.parent_id) return m.name
      if (m.children && m.children.length > 0) {
        const found = findName(m.children)
        if (found) return found
      }
    }
    return null
  }
  return findName(moduleTree.value) || '-'
})

/** 关联场景数（模拟计算） */
const relatedSceneCount = computed(() => {
  if (!selectedModule.value) return 0
  // 用例数量的约 1/4 作为关联场景数（模拟数据）
  return Math.floor(selectedModule.value.case_count / 4)
})

/** 过滤后的子模块列表 */
const filteredChildren = computed(() => {
  if (!selectedModule.value?.children) return []
  const keyword = childKeyword.value.trim().toLowerCase()
  if (!keyword) return selectedModule.value.children
  return selectedModule.value.children.filter(m =>
    m.name.toLowerCase().includes(keyword)
  )
})

// ==================== 方法 ====================

/** 子模块的模块标识 */
const getModuleCode = (module: ProjectModule) => {
  const parts = module.path.split('/')
  return parts[parts.length - 1]
}

/** 子模块关联场景数（模拟） */
const getRelatedSceneCount = (module: ProjectModule) => Math.floor(module.case_count / 4)

/**
 * 获取子模块数量
 */
const getChildrenCount = (module: ProjectModule) => {
  return module.children_count ?? module.children?.length ?? 0
}

/**
 * 获取删除原因
 */
const getDeleteReason = (module: ProjectModule) => {
  const reasons = []
  if (module.children && module.children.length > 0) {
    reasons.push('存在子模块')
  }
  if (module.case_count > 0) {
    reasons.push('有关联用例')
  }
  return reasons.join('，')
}

/**
 * 格式化日期
 */
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 检查模块是否可以删除
 */
const canDeleteModule = (module: ProjectModule) => {
  return (
    (!module.children || module.children.length === 0) &&
    module.case_count === 0
  )
}

/**
 * 加载模块树
 */
const loadModuleTree = async () => {
  loading.value = true
  try {
    const response = await projectApi.getModuleTree(projectId.value)
    if (response.code === 200) {
      moduleTree.value = response.data
    }
  } catch (error) {
    console.error('加载模块树失败:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 加载模块详情
 */
const loadModuleDetail = async (moduleId: number) => {
  detailLoading.value = true
  try {
    const response = await projectApi.getModuleDetail(projectId.value, moduleId)
    if (response.code === 200) {
      selectedModule.value = response.data
    }
  } catch (error) {
    console.error('加载模块详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

/**
 * 刷新模块树
 */
const handleRefresh = () => {
  loadModuleTree()
}

/**
 * 点击树节点
 */
const handleNodeClick = (data: ProjectModule) => {
  loadModuleDetail(data.id)
}

/**
 * 批量操作命令
 */
const handleBatchCommand = (command: string) => {
  if (command === 'create' && selectedModule.value) {
    handleCreateModule(selectedModule.value)
  }
}

/**
 * 处理树节点操作命令
 */
const handleNodeCommand = (command: string, data: ProjectModule) => {
  switch (command) {
    case 'add':
      handleCreateModule(data)
      break
    case 'edit':
      handleEditModule(data)
      break
    case 'move':
      handleMoveModule(data)
      break
    case 'delete':
      handleDeleteModule(data)
      break
  }
}

/**
 * 创建模块
 */
const handleCreateModule = (parent: ProjectModule | null) => {
  dialogMode.value = 'create'
  currentModule.value = null
  parentModule.value = parent
  dialogVisible.value = true
}

/**
 * 编辑模块
 */
const handleEditModule = (module: ProjectModule) => {
  dialogMode.value = 'edit'
  currentModule.value = module
  parentModule.value = null
  dialogVisible.value = true
}

/**
 * 移动模块
 */
const handleMoveModule = (module: ProjectModule) => {
  moduleToMove.value = module
  moveDialogVisible.value = true
}

/**
 * 删除模块
 */
const handleDeleteModule = async (module: ProjectModule) => {
  if (!canDeleteModule(module)) {
    ElMessage.warning('该模块存在子模块或关联用例，无法删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除模块「${module.name}」吗？删除后将无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'error',
      }
    )

    loading.value = true
    const response = await projectApi.deleteModule(projectId.value, module.id)
    if (response.code === 200) {
      ElMessage.success('删除成功')
      if (selectedModule.value?.id === module.id) {
        selectedModule.value = null
      }
      await loadModuleTree()
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除模块失败:', error)
    }
  } finally {
    loading.value = false
  }
}

/**
 * 对话框成功回调
 */
const handleDialogSuccess = () => {
  dialogVisible.value = false
  loadModuleTree()
}

/**
 * 移动成功回调
 */
const handleMoveSuccess = () => {
  moveDialogVisible.value = false
  loadModuleTree()
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadModuleTree()
})
</script>

<style scoped lang="scss">
.project-modules-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  height: 100%;
  min-height: 0;
}

.btn-icon {
  margin-right: 6px;
  font-size: 14px;
  vertical-align: -2px;
}

.modules-content {
  display: grid;
  grid-template-columns: 252px minmax(0, 1fr);
  gap: var(--space-4);
  min-height: 0;
  flex: 1;
}

/* ============ 通用卡片头 ============ */
.card-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  &.compact {
    gap: var(--space-3);
  }
}

.card-hd-left {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.section-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;

  &.large {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }

  &.brand-soft {
    background: var(--brand-50);
    color: var(--brand-600);
  }

  &.info-soft {
    background: var(--color-info-50);
    color: var(--color-info-600);
  }
}

.card-title {
  font-size: 15px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: 1.2;
}

.card-subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-secondary);
}

.icon-action,
.node-more {
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.icon-action {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  font-size: 16px;

  &:hover {
    background: var(--brand-50);
    color: var(--brand-600);
  }
}

/* ============ 左侧树 ============ */
.tree-card,
.module-detail-section {
  min-height: 0;
}

.tree-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tree-card-body {
  flex: 1;
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.tree-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-3);
}

.tree-empty {
  min-height: 320px;
}

.tree-empty :deep(.empty-illustration),
.table-empty :deep(.empty-illustration) {
  width: 160px;
  height: 120px;
}

.tree-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: var(--gray-50);
  color: var(--text-secondary);
}

.summary-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: var(--font-weight-medium);
}

.summary-count,
.count-pill {
  min-width: 22px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  background: var(--brand-50);
  color: var(--brand-600);
}

.module-tree {
  --el-tree-node-content-height: 34px;
  background: transparent;
}

.module-tree :deep(.el-tree-node__content) {
  height: 34px;
  border-radius: var(--radius-md);
  transition: all 0.18s ease;

  &:hover {
    background: var(--gray-50);
  }
}

.module-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: var(--brand-50);
}

.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  min-width: 0;

  &.is-selected {
    .node-label,
    .node-icon {
      color: var(--brand-600);
    }

    .node-label {
      font-weight: var(--font-weight-semibold);
    }
  }

  &:hover .node-actions {
    opacity: 1;
  }
}

.node-content {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.node-icon {
  flex-shrink: 0;
  font-size: 15px;
  color: var(--text-secondary);
}

.node-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-primary);
}

.node-actions {
  opacity: 0;
  flex-shrink: 0;
  transition: opacity 0.18s ease;
}

.node-more {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-xs);

  &:hover {
    background: var(--bg-card);
    color: var(--brand-600);
  }
}

.dropdown-icon {
  margin-right: 6px;
  font-size: 14px;
  vertical-align: -2px;

  &.danger {
    color: var(--color-danger-600);
  }
}

/* ============ 右侧详情（贴近参考图） ============ */
.module-detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
  min-height: 0;
}

.detail-card,
.empty-detail-card {
  flex: 1;
  min-height: 0;
}

.overview-card,
.info-card,
.children-card {
  flex-shrink: 0;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.metric-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 72px;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--gray-50);
  border: 1px solid transparent;

  &.info .metric-icon { background: var(--color-info-50); color: var(--color-info-600); }
  &.success .metric-icon { background: var(--color-success-50); color: var(--color-success-600); }
  &.warning .metric-icon { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.danger .metric-icon { background: var(--color-danger-50); color: var(--color-danger-600); }
}

.metric-icon {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.metric-value {
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1;
}

.metric-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.info-overview {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.module-main-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--brand-50), var(--bg-card));
}

.module-avatar {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-500);
  color: #fff;
  font-size: 21px;
  flex-shrink: 0;
}

.module-main-text {
  min-width: 0;
}

.module-name-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;

  strong {
    font-size: 16px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.level-pill {
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
}

.module-code-line {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.module-desc-box {
  min-height: 74px;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--gray-50);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.info-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.info-tile {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.tile-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;

  &.brand-soft { background: var(--brand-50); color: var(--brand-600); }
  &.info-soft { background: var(--color-info-50); color: var(--color-info-600); }
  &.success-soft { background: var(--color-success-50); color: var(--color-success-600); }
  &.warning-soft { background: var(--color-warning-50); color: var(--color-warning-600); }
}

.tile-label {
  margin-bottom: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.tile-value {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: var(--font-weight-semibold);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono {
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
}

.muted-text {
  color: var(--text-secondary);
}

.children-toolbar {
  padding: var(--space-3) var(--space-4) 0;
}

.child-search {
  max-width: 260px;
}

.children-table {
  margin-top: var(--space-2);
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4) var(--space-4);
  color: var(--text-secondary);
  font-size: 12px;
}

.btn-icon-right {
  margin-left: 4px;
  font-size: 13px;
  vertical-align: -2px;
}

.warning-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: var(--space-4);
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-warning-50);
  color: var(--color-warning-600);
  font-size: 13px;
  line-height: 1.5;
}

.empty-detail-card {
  flex: 1;
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-detail-card :deep(.section-body) {
  width: 100%;
}

.table-empty {
  min-height: 260px;
  padding-top: var(--space-6);
  padding-bottom: var(--space-6);
}

.children-table :deep(.el-table__empty-block) {
  min-height: 280px;
}

.children-table :deep(.el-table__empty-text) {
  width: 100%;
}

@media (max-width: 1200px) {
  .modules-content {
    grid-template-columns: 1fr;
  }

  .tree-card {
    min-height: 360px;
  }

  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .info-overview,
  .info-card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
