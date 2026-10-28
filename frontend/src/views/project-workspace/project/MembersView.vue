<!--
  项目成员管理页面
  按设计系统重构：去掉硬编码色值的统计卡，成员数内联标题，角色拆成带计数的筛选段，
  表格用 AppSectionCard + AppEmpty，图标统一 i-solar/i-app。成员列表全量加载，筛选在前端完成。
-->
<template>
  <div class="project-members-page">
    <!-- 页头 -->
    <AppPageHeader
      description="管理项目成员及其系统角色"
      :breadcrumbs="['项目管理', '成员管理']"
      icon="i-solar-users-group-rounded-bold"
      :illustration="illustTeam"
      class="members-header"
    >
      <template #title>
        成员管理
        <span class="title-count">{{ memberList.length }}</span>
      </template>
      <template #actions>
        <el-button @click="handleRefresh">
          <i class="i-solar-refresh-linear btn-icon" /> 刷新
        </el-button>
        <el-button v-if="isProjectOwner" type="warning" @click="handleTransferProject">
          <i class="i-solar-square-transfer-horizontal-bold btn-icon" /> 转让项目
        </el-button>
        <el-button v-permission="'member:add'" type="primary" @click="handleAddMember">
          <i class="i-solar-add-circle-bold btn-icon" /> 添加成员
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 工具栏：搜索 + 角色筛选段（带计数） -->
    <div class="member-toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索用户名 / 姓名 / 邮箱"
        clearable
        class="member-search"
      >
        <template #prefix>
          <i class="i-solar-magnifer-linear" />
        </template>
      </el-input>
      <div class="seg-group">
        <button
          v-for="seg in roleSegments"
          :key="seg.value || 'all'"
          type="button"
          class="seg"
          :class="{ 'is-active': roleFilter === seg.value }"
          @click="roleFilter = seg.value"
        >
          {{ seg.label }}
          <span class="seg-count">{{ seg.count }}</span>
        </button>
      </div>
    </div>

    <!-- 成员表格 -->
    <AppSectionCard padless class="table-card">
      <div class="table-wrap">
        <el-table v-loading="loading" :data="filteredMembers" style="width: 100%">
          <el-table-column label="成员" min-width="220">
            <template #default="{ row }">
              <div class="user-info">
                <el-avatar :src="row.user?.avatar" :size="38">
                  {{ row.user?.real_name?.charAt(0) || row.user?.username?.charAt(0) }}
                </el-avatar>
                <div class="user-detail">
                  <div class="user-name">
                    {{ row.user?.real_name || row.user?.username }}
                    <el-tag
                      v-if="row.project_role === 'project_owner'"
                      type="warning"
                      size="small"
                      effect="light"
                      class="owner-tag"
                    >负责人</el-tag>
                  </div>
                  <div class="user-username">@{{ row.user?.username }}</div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="系统角色" min-width="180">
            <template #default="{ row }">
              <template v-if="row.user?.roles?.length">
                <el-tag
                  v-for="r in row.user.roles"
                  :key="r.code"
                  :type="roleTagType(r.code)"
                  size="small"
                  effect="light"
                  class="role-tag"
                >
                  {{ r.name }}
                </el-tag>
              </template>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>

          <el-table-column label="邮箱" min-width="200">
            <template #default="{ row }">
              <span class="muted-text">{{ row.user?.email || '—' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="加入时间" width="170">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDate(row.joined_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="最后活跃" width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatActiveTime(row.last_active_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  v-if="canRemoveMember(row)"
                  v-permission="'member:remove'"
                  size="small"
                  type="danger"
                  plain
                  @click="handleRemoveMember(row)"
                >
                  <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />移除
                </el-button>
                <el-button
                  v-else-if="isCurrentUser(row)"
                  size="small"
                  @click="handleQuitProject"
                >
                  <i class="i-solar-logout-2-linear btn-icon-sm" />退出
                </el-button>
                <span v-else class="text-disabled">—</span>
              </div>
            </template>
          </el-table-column>

          <!-- 空状态 -->
          <template #empty>
            <AppEmpty
              v-if="!loading"
              :scene="hasFilter ? 'search' : 'team'"
              :description="hasFilter ? '没有匹配的成员，试试调整搜索或筛选' : '暂无成员，添加第一个成员开始协作'"
            >
              <template v-if="!hasFilter" #actions>
                <el-button v-permission="'member:add'" type="primary" @click="handleAddMember">
                  <i class="i-solar-add-circle-bold btn-icon" /> 添加第一个成员
                </el-button>
              </template>
            </AppEmpty>
          </template>
        </el-table>
      </div>
    </AppSectionCard>

    <!-- 添加成员对话框 -->
    <AddMemberDialog
      v-model="addDialogVisible"
      :project-id="projectId"
      :existing-members="memberList"
      @success="handleAddSuccess"
    />

    <!-- 转让项目对话框 -->
    <TransferProjectDialog
      v-model="transferDialogVisible"
      :project-id="projectId"
      :members="memberList"
      :current-user-id="currentUserId"
      @success="handleTransferSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi } from '@/api/projects'
import type { ProjectMember, ProjectRole } from '@/api/projects'
import { AppPageHeader, AppSectionCard, AppEmpty } from '@/components/common'
import illustTeam from '@/assets/illustrations/team.svg'
import AddMemberDialog from '@/components/project/AddMemberDialog.vue'
import TransferProjectDialog from '@/components/project/TransferProjectDialog.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ==================== 状态 ====================
const projectId = computed(() => Number(route.params.id))
const currentUserId = computed(() => userStore.userInfo?.id)
const loading = ref(false)
const memberList = ref<ProjectMember[]>([])

const memberPermissions = ref<{
  can_edit_project: boolean
  can_manage_members: boolean
  can_delete_project: boolean
}>({
  can_edit_project: false,
  can_manage_members: false,
  can_delete_project: false,
})

// 筛选（前端过滤）
const keyword = ref('')
const roleFilter = ref<'' | ProjectRole>('')

const addDialogVisible = ref(false)
const transferDialogVisible = ref(false)

// ==================== 计算属性 ====================
const isProjectOwner = computed(() =>
  memberList.value.some(
    (m) => m.project_role === 'project_owner' && m.user?.id === currentUserId.value,
  ),
)

const getMemberCountByRole = (role: ProjectRole) =>
  memberList.value.filter((m) => m.project_role === role).length

/** 角色筛选段（带计数） */
const roleSegments = computed<{ value: '' | ProjectRole; label: string; count: number }[]>(() => [
  { value: '', label: '全部', count: memberList.value.length },
  { value: 'project_owner', label: '负责人', count: getMemberCountByRole('project_owner') },
  { value: 'project_member', label: '成员', count: getMemberCountByRole('project_member') },
])

const hasFilter = computed(() => !!keyword.value.trim() || !!roleFilter.value)

/** 应用 搜索 + 角色 过滤后的成员 */
const filteredMembers = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return memberList.value.filter((m) => {
    if (roleFilter.value && m.project_role !== roleFilter.value) return false
    if (kw) {
      const u = m.user
      const hay = `${u?.real_name || ''} ${u?.username || ''} ${u?.email || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

// ==================== 方法 ====================
const isCurrentUser = (member: ProjectMember) => member.user?.id === currentUserId.value

const canRemoveMember = (member: ProjectMember) =>
  memberPermissions.value.can_manage_members && !isCurrentUser(member)

/** 系统角色标签颜色 */
const roleTagType = (code?: string): 'success' | 'warning' | 'danger' | 'info' => {
  switch (code) {
    case 'super_admin':
      return 'danger'
    case 'admin':
    case 'project_admin':
      return 'warning'
    case 'tester':
    case 'developer':
      return 'success'
    default:
      return 'info'
  }
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatActiveTime = (dateStr?: string) => {
  if (!dateStr) return '从未活跃'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    const hours = Math.floor(diff / (1000 * 60 * 60))
    if (hours === 0) {
      const minutes = Math.floor(diff / (1000 * 60))
      return minutes === 0 ? '刚刚活跃' : `${minutes}分钟前活跃`
    }
    return `${hours}小时前活跃`
  } else if (days < 7) {
    return `${days}天前活跃`
  }
  return formatDate(dateStr)
}

/** 加载成员列表（全量） */
const loadMembers = async () => {
  loading.value = true
  try {
    const response = await projectApi.getProjectMembers(projectId.value)
    if (response.code === 200) {
      memberList.value = response.data
    }
  } catch (error) {
    console.error('加载成员列表失败:', error)
  } finally {
    loading.value = false
  }
}

/** 加载用户权限信息 */
const loadPermissions = async () => {
  try {
    const response = await projectApi.getMemberPermissions(projectId.value)
    if (response.code === 200) {
      memberPermissions.value = {
        can_edit_project: response.data.can_edit_project,
        can_manage_members: response.data.can_manage_members,
        can_delete_project: response.data.can_delete_project,
      }
    }
  } catch (error) {
    console.error('加载权限信息失败:', error)
  }
}

const handleRefresh = () => {
  loadMembers()
  loadPermissions()
}

const handleAddMember = () => {
  if (!memberPermissions.value.can_manage_members) {
    ElMessage.warning('您没有管理成员的权限')
    return
  }
  addDialogVisible.value = true
}

const handleRemoveMember = async (member: ProjectMember) => {
  try {
    await ElMessageBox.confirm(
      `确定要移除成员「${member.user?.real_name || member.user?.username}」吗？`,
      '移除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )

    loading.value = true
    const response = await projectApi.removeProjectMember(projectId.value, member.id)
    if (response.code === 200) {
      ElMessage.success('移除成功')
      loadMembers()
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('移除成员失败:', error)
    }
  } finally {
    loading.value = false
  }
}

const handleQuitProject = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要退出该项目吗？退出后需要重新邀请才能加入。',
      '退出确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )

    loading.value = true
    const response = await projectApi.quitProject(projectId.value)
    if (response.code === 200) {
      ElMessage.success('已退出项目')
      router.push({ name: 'workspace' })
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('退出项目失败:', error)
    }
  } finally {
    loading.value = false
  }
}

const handleAddSuccess = () => {
  addDialogVisible.value = false
  loadMembers()
}

const handleTransferProject = () => {
  transferDialogVisible.value = true
}

const handleTransferSuccess = () => {
  transferDialogVisible.value = false
  loadMembers()
  loadPermissions()
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadMembers()
  loadPermissions()
})
</script>

<style scoped lang="scss">
.project-members-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.members-header {
  margin-bottom: 0;
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

/* ============ 操作列按钮 ============ */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ============ 标题内联计数 ============ */
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

/* ============ 工具栏 ============ */
.member-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.member-search {
  width: 300px;
}

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

/* ============ 表格 ============ */
.table-card {
  overflow: hidden;
}
.table-wrap {
  padding: var(--space-3) var(--space-2) var(--space-2);
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.user-detail {
  flex: 1;
  min-width: 0;
}
.user-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.user-username {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  margin-top: 2px;
}
.owner-tag {
  height: 20px;
  padding: 0 6px;
}
.role-tag {
  margin-right: 4px;
}

.muted-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.text-muted {
  color: var(--text-secondary);
}
.text-disabled {
  color: var(--text-placeholder);
  font-size: 13px;
}

/* 表头 Token 化 */
:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  td.el-table__cell {
    padding: 12px 0;
    font-size: var(--font-size-sm);
  }
}

/* ============ 响应式 ============ */
@media (max-width: 600px) {
  .member-search {
    flex: 1;
    width: auto;
  }
}
</style>
