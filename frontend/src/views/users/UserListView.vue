/**
 * 用户列表页面
 *
 * AI 智能测试平台 - 用户管理列表
 * 对应需求文档：01-用户与权限管理模块.md - 第2.5节 系统用户管理
 * 对应 API 文档：01-用户与权限管理模块API.md - 第4.1节 获取用户列表
 */

<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useUserManageStore } from '@/stores/userManage'
import { useRoleManageStore } from '@/stores/roleManage'
import type { UserListItem, UserStatus, CreateUserRequest, UpdateUserRequest } from '@/types/user'
import AppSectionCard from '@/components/common/AppSectionCard.vue'
import AppAvatar from '@/components/common/AppAvatar.vue'
import AppStatCard from '@/components/common/AppStatCard.vue'

const userManageStore = useUserManageStore()
const roleManageStore = useRoleManageStore()

// ==================== 状态 ====================
const loading = ref(false)
const tableLoading = ref(false)

// 用户弹框
const userDialogVisible = ref(false)
const userDialogMode = ref<'create' | 'edit'>('create')
const userDialogTitle = computed(() => (userDialogMode.value === 'create' ? '新增用户' : '编辑用户'))
const userFormRef = ref<FormInstance>()
interface UserFormData {
  username: string
  password: string
  email: string
  phone?: string
  real_name?: string
  bio?: string
  role_ids?: number[]
}

const userForm = ref<UserFormData>({
  username: '',
  password: '',
  email: '',
  phone: '',
  real_name: '',
  role_ids: [],
})
const userFormLoading = ref(false)
const roleList = ref<any[]>([])
const currentEditUserId = ref<number | null>(null)

// 用户详情弹框
const userDetailVisible = ref(false)
const userDetailLoading = ref(false)
const currentUserDetail = ref<any>(null)

// 重置密码弹框
const resetPasswordVisible = ref(false)
const resetPasswordLoading = ref(false)
const resetPasswordFormRef = ref<FormInstance>()
const resetPasswordForm = ref({
  new_password: '',
  confirm_password: '',
})
const currentResetUser = ref<UserListItem | null>(null)

// 搜索表单
const searchFormRef = ref<FormInstance>()
const searchForm = ref({
  keyword: '',
  status: '' as UserStatus | '',
  role_id: undefined as number | undefined,
})

// 说明条是否显示
const showNotice = ref(true)

// 分页
const pagination = computed(() => ({
  current: userManageStore.currentPage,
  pageSize: userManageStore.pageSize,
  total: userManageStore.total,
}))

// ==================== 统计数据 ====================

const stats = computed(() => {
  const list = userManageStore.userList
  const total = userManageStore.total
  const activeCount = list.filter(u => u.status === 'active').length
  const disabledCount = list.filter(u => u.status === 'disabled').length
  const adminCount = list.filter(u => u.roles.some(r => r.includes('管理员') || r === 'super_admin' || r === 'admin')).length
  return [
    { label: '用户总数', value: total, icon: 'i-solar-users-group-rounded-bold', color: 'brand' as const },
    { label: '活跃用户', value: activeCount, icon: 'i-solar-user-speak-bold', color: 'success' as const },
    { label: '禁用用户', value: disabledCount, icon: 'i-solar-user-cross-bold', color: 'danger' as const },
    { label: '管理员', value: adminCount, icon: 'i-solar-shield-user-bold', color: 'warning' as const },
  ]
})

// ==================== 方法 ====================

/**
 * 获取用户列表
 */
const fetchUsers = async () => {
  tableLoading.value = true
  const params = {
    ...searchForm.value,
    status: searchForm.value.status || undefined,
  }
  await userManageStore.fetchUserList(params)
  tableLoading.value = false
}

/**
 * 搜索
 */
const handleSearch = () => {
  pagination.value.current = 1
  fetchUsers()
}

/**
 * 重置搜索
 */
const handleReset = () => {
  searchFormRef.value?.resetFields()
  handleSearch()
}

/**
 * 刷新
 */
const handleRefresh = () => {
  fetchUsers()
}

/**
 * 分页变化
 */
const handlePageChange = (page: number) => {
  userManageStore.currentPage = page
  fetchUsers()
}

/**
 * 每页数量变化
 */
const handleSizeChange = (size: number) => {
  userManageStore.pageSize = size
  pagination.value.current = 1
  fetchUsers()
}

/**
 * 新增用户
 */
const handleAdd = async () => {
  await roleManageStore.fetchRoleList()
  roleList.value = roleManageStore.roleList

  userDialogMode.value = 'create'
  resetUserForm()
  userDialogVisible.value = true
}

/**
 * 编辑用户
 */
const handleEdit = async (row: UserListItem) => {
  await roleManageStore.fetchRoleList()
  roleList.value = roleManageStore.roleList

  const userDetail = await userManageStore.fetchUserDetail(row.id)
  if (!userDetail) {
    return
  }

  userDialogMode.value = 'edit'
  currentEditUserId.value = row.id
  userForm.value = {
    username: '',
    password: '',
    email: userDetail.email,
    phone: userDetail.phone || '',
    real_name: userDetail.real_name || '',
    role_ids: userDetail.roles?.map((r: any) => r.id) || [],
  }
  userDialogVisible.value = true
}

/**
 * 重置用户表单
 */
const resetUserForm = () => {
  userForm.value = {
    username: '',
    password: '',
    email: '',
    phone: '',
    real_name: '',
    role_ids: [],
  }
  currentEditUserId.value = null
  userFormRef.value?.clearValidate()
}

/**
 * 关闭用户弹框
 */
const handleUserDialogClose = () => {
  resetUserForm()
  userDialogVisible.value = false
}

/**
 * 提交用户表单
 */
const handleSubmitUser = async () => {
  if (!userFormRef.value) return

  try {
    await userFormRef.value.validate()
  } catch {
    return
  }

  userFormLoading.value = true
  let success = false

  if (userDialogMode.value === 'create') {
    const data = userForm.value as CreateUserRequest
    success = await userManageStore.createUser(data)
  } else {
    if (!currentEditUserId.value) {
      ElMessage.error('无法获取用户信息')
      userFormLoading.value = false
      return
    }
    const data = userForm.value as UpdateUserRequest
    success = await userManageStore.updateUser(currentEditUserId.value, data)

    if (success && userForm.value.role_ids) {
      success = await roleManageStore.assignRolesToUser(
        currentEditUserId.value,
        userForm.value.role_ids,
      )
    }
  }

  userFormLoading.value = false

  if (success) {
    userDialogVisible.value = false
  }
}

/**
 * 查看详情
 */
const handleView = async (row: UserListItem) => {
  userDetailLoading.value = true
  userDetailVisible.value = true

  try {
    const userDetail = await userManageStore.fetchUserDetail(row.id)
    if (userDetail) {
      currentUserDetail.value = userDetail
    } else {
      userDetailVisible.value = false
    }
  } catch (error) {
    console.error('获取用户详情失败:', error)
    userDetailVisible.value = false
  } finally {
    userDetailLoading.value = false
  }
}

/**
 * 关闭详情弹框
 */
const handleDetailClose = () => {
  userDetailVisible.value = false
  currentUserDetail.value = null
}

/**
 * 启用/禁用用户
 */
const handleToggleStatus = async (row: UserListItem) => {
  if (row.status === 'active' && row.username === 'admin') {
    ElMessage.warning('系统管理员账号不能被禁用')
    return
  }

  const newStatus: UserStatus = row.status === 'active' ? 'disabled' : 'active'
  const action = newStatus === 'active' ? '启用' : '禁用'

  try {
    await ElMessageBox.confirm(
      `确认要${action}用户 "${row.username}" 吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    const success = await userManageStore.updateUserStatus(row.id, newStatus)
    if (success) {
      ElMessage.success(`${action}成功`)
    }
  } catch {
    // 用户取消
  }
}

/**
 * 删除用户
 */
const handleDelete = async (row: UserListItem) => {
  try {
    await ElMessageBox.confirm(
      `确认要删除用户 "${row.username}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    const success = await userManageStore.deleteUser(row.id)
    if (success) {
      ElMessage.success('删除成功')
    }
  } catch {
    // 用户取消
  }
}

/**
 * 重置密码
 */
const handleResetPassword = (row: UserListItem) => {
  currentResetUser.value = row
  resetPasswordForm.value = {
    new_password: '',
    confirm_password: '',
  }
  resetPasswordVisible.value = true
}

/**
 * 关闭重置密码弹框
 */
const handleResetPasswordClose = () => {
  resetPasswordVisible.value = false
  resetPasswordForm.value = {
    new_password: '',
    confirm_password: '',
  }
  currentResetUser.value = null
  resetPasswordFormRef.value?.clearValidate()
}

/**
 * 提交重置密码
 */
const handleSubmitResetPassword = async () => {
  if (!resetPasswordFormRef.value || !currentResetUser.value) return

  try {
    await resetPasswordFormRef.value.validate()
  } catch {
    return
  }

  resetPasswordLoading.value = true
  try {
    const success = await userManageStore.resetPassword(
      currentResetUser.value.id,
      resetPasswordForm.value.new_password,
    )
    if (success) {
      handleResetPasswordClose()
    }
  } finally {
    resetPasswordLoading.value = false
  }
}

/**
 * 状态标签颜色（ElTag type 校验严格，不能返回空字符串/null/undefined）
 */
const getStatusType = (status: UserStatus | undefined): 'success' | 'danger' | 'warning' | 'info' => {
  switch (status) {
    case 'active':
      return 'success'
    case 'disabled':
      return 'danger'
    case 'locked':
      return 'warning'
    default:
      return 'info'
  }
}

/**
 * 状态 pill class（遵循设计系统 status-pill 规范）
 */
const getStatusClass = (status: UserStatus) => {
  switch (status) {
    case 'active':
      return 'is-passed'
    case 'disabled':
      return 'is-failed'
    case 'locked':
      return 'is-blocked'
    default:
      return 'is-blocked'
  }
}

/**
 * 状态文本
 */
const getStatusText = (status: UserStatus) => {
  switch (status) {
    case 'active':
      return '正常'
    case 'disabled':
      return '禁用'
    case 'locked':
      return '锁定'
    default:
      return status
  }
}

/**
 * 角色标签颜色（ElTag type 校验严格，不能返回空字符串/null/undefined）
 */
const getRoleTagType = (role: string | null | undefined): 'success' | 'warning' | 'danger' | 'info' => {
  if (!role) return 'info'
  if (role.includes('超级管理员') || role === 'super_admin') return 'info'
  if (role.includes('测试') || role === 'tester') return 'success'
  if (role.includes('开发') || role === 'developer') return 'warning'
  if (role.includes('运维') || role === 'ops') return 'danger'
  if (role.includes('访客') || role === 'guest') return 'info'
  return 'info'
}

/**
 * 检查用户是否是超级管理员
 */
const isSuperAdmin = (row: UserListItem): boolean => {
  return row.roles.includes('super_admin') || row.roles.includes('超级管理员')
}

/**
 * 检查角色是否是超级管理员
 */
const isSuperAdminRole = (role: any): boolean => {
  return role.code === 'super_admin' || role.name === '超级管理员'
}

/**
 * 表单验证规则
 */
const userFormRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 20, message: '用户名长度在4-20个字符', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9_]+$/,
      message: '用户名只能包含字母、数字和下划线',
      trigger: 'blur',
    },
  ],
  password: [
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (userDialogMode.value === 'create' && !value) {
          callback(new Error('请输入密码'))
        } else if (value && value.length < 8) {
          callback(new Error('密码至少8个字符'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  phone: [
    {
      pattern: /^1[3-9]\d{9}$/,
      message: '请输入正确的手机号',
      trigger: 'blur',
    },
  ],
}

/**
 * 重置密码表单验证规则
 */
const resetPasswordFormRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 20, message: '密码长度在8-20个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== resetPasswordForm.value.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

// 权限门控改用 v-permission 指令（与后端 users 端点的 require_permission 同口径）

// 组件挂载时获取数据
onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div class="user-list-view">
    <!-- 页头 -->
    <div class="page-header">
      <div class="page-title">
        <div class="title-row">
          <i class="i-solar-users-group-rounded-bold title-icon" />
          <h2>用户管理</h2>
        </div>
        <p class="page-description">管理平台用户账号、角色及配置信息</p>
      </div>
      <div class="page-actions">
        <el-button @click="handleRefresh">
          <i class="i-solar-refresh-bold" />
          刷新
        </el-button>
        <el-button v-permission="'user:create'" type="primary" @click="handleAdd">
          <i class="i-solar-add-circle-bold" />
          新增用户
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <AppStatCard
        v-for="stat in stats"
        :key="stat.label"
        :label="stat.label"
        :value="stat.value"
        :icon-name="stat.icon"
        :color="stat.color"
      />
    </div>

    <!-- 筛选区 -->
    <AppSectionCard>
      <div class="filter-bar">
        <el-form ref="searchFormRef" :model="searchForm" inline class="filter-form">
          <el-form-item>
            <el-input
              v-model="searchForm.keyword"
              placeholder="搜索用户名/邮箱/手机号"
              clearable
              class="filter-input"
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <i class="i-solar-magnifer-linear" />
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-select
              v-model="searchForm.status"
              placeholder="全部状态"
              clearable
              class="filter-select"
              @change="handleSearch"
            >
              <el-option label="正常" value="active" />
              <el-option label="禁用" value="disabled" />
              <el-option label="锁定" value="locked" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleSearch">
              搜索
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 数据表格 -->
      <el-table
        v-loading="tableLoading"
        :data="userManageStore.userList"
        class="user-table"
      >
        <el-table-column label="用户" min-width="200">
          <template #default="{ row }">
            <div class="user-cell">
              <AppAvatar :name="row.real_name || row.username" :src="row.avatar" :size="36" />
              <div class="user-info">
                <span class="user-name">{{ row.username }}</span>
                <span class="user-email">{{ row.email }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="phone" label="手机号" width="130">
          <template #default="{ row }">
            {{ row.phone || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="real_name" label="真实姓名" width="120">
          <template #default="{ row }">
            {{ row.real_name || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <template v-if="Array.isArray(row.roles) && row.roles.length">
              <el-tag
                v-for="(role, index) in row.roles.slice(0, 2)"
                :key="index"
                size="small"
                :type="getRoleTagType(role)"
                class="role-tag"
              >
                {{ role }}
              </el-tag>
              <el-tag v-if="row.roles.length > 2" size="small" type="info">
                +{{ row.roles.length - 2 }}
              </el-tag>
            </template>
            <span v-else class="role-empty">-</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <span class="status-pill" :class="getStatusClass(row.status)">● {{ getStatusText(row.status) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">
            {{ row.last_login_at ? new Date(row.last_login_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="480" fixed="right" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click="handleView(row)">
                <i class="i-solar-eye-linear btn-icon-sm" />
                查看
              </el-button>
              <el-button
                v-permission="'user:edit'"
                size="small"
                @click="handleEdit(row)"
              >
                <i class="i-solar-pen-2-linear btn-icon-sm" />
                编辑
              </el-button>
              <el-button
                v-if="!isSuperAdmin(row)"
                v-permission="'user:reset_pwd'"
                size="small"
                @click="handleResetPassword(row)"
              >
                <i class="i-solar-lock-password-linear btn-icon-sm" />
                重置密码
              </el-button>
              <el-button
                v-if="!isSuperAdmin(row)"
                v-permission="'user:edit'"
                size="small"
                @click="handleToggleStatus(row)"
              >
                <i class="i-solar-power-linear btn-icon-sm" />
                {{ row.status === 'active' ? '禁用' : '启用' }}
              </el-button>
              <el-button
                v-if="!isSuperAdmin(row)"
                v-permission="'user:delete'"
                size="small"
                type="danger"
                plain
                @click="handleDelete(row)"
              >
                <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                删除
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
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </AppSectionCard>

    <!-- 底部说明 -->
    <div v-if="showNotice" class="config-notice">
      <i class="i-solar-info-circle-bold" />
      <span>用户状态为禁用时，将无法登录系统。超级管理员拥有所有权限，请谨慎操作。</span>
      <button class="notice-close" @click="showNotice = false">
        <i class="i-solar-close-circle-linear" />
      </button>
    </div>

    <!-- 用户创建/编辑弹框 -->
    <el-dialog
      v-model="userDialogVisible"
      :width="600"
      :close-on-click-modal="false"
      align-center
      class="user-dialog"
      @close="handleUserDialogClose"
    >
      <template #header="{ titleId, titleClass }">
        <span :id="titleId" :class="titleClass">
          <i :class="userDialogMode === 'create' ? 'i-solar-user-plus-bold' : 'i-solar-pen-2-bold'" />
          <span>{{ userDialogTitle }}</span>
        </span>
      </template>

      <el-form
        ref="userFormRef"
        :model="userForm"
        :rules="userFormRules"
        label-position="top"
        class="user-form"
      >
        <el-form-item
          v-if="userDialogMode === 'create'"
          label="用户名"
          prop="username"
        >
          <el-input
            v-model="userForm.username"
            placeholder="请输入用户名（字母、数字、下划线）"
            maxlength="20"
            show-word-limit
            clearable
          />
        </el-form-item>

        <el-form-item
          v-if="userDialogMode === 'create'"
          label="密码"
          prop="password"
        >
          <el-input
            v-model="userForm.password"
            type="password"
            placeholder="请输入密码（至少8个字符）"
            maxlength="20"
            show-word-limit
            clearable
            show-password
          />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="userForm.email"
            placeholder="请输入邮箱"
            clearable
          />
        </el-form-item>

        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="userForm.phone"
            placeholder="请输入手机号"
            maxlength="11"
            show-word-limit
            clearable
          />
        </el-form-item>

        <el-form-item label="真实姓名">
          <el-input
            v-model="userForm.real_name"
            placeholder="请输入真实姓名"
            maxlength="50"
            show-word-limit
            clearable
          />
        </el-form-item>

        <el-form-item label="角色">
          <el-select
            v-model="userForm.role_ids"
            multiple
            placeholder="请选择角色"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="role in roleList"
              :key="role.id"
              :label="role.name"
              :value="role.id"
              :disabled="isSuperAdminRole(role)"
            />
          </el-select>
          <div v-if="roleList.some(isSuperAdminRole)" class="role-tip">
            超级管理员角色不可分配
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="handleUserDialogClose">取消</el-button>
        <el-button type="primary" :loading="userFormLoading" @click="handleSubmitUser">
          <i class="i-solar-check-circle-bold" />
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 用户详情弹框 -->
    <el-dialog
      v-model="userDetailVisible"
      :width="700"
      align-center
      class="user-dialog"
      @close="handleDetailClose"
    >
      <template #header="{ titleId, titleClass }">
        <span :id="titleId" :class="titleClass">
          <i class="i-solar-user-id-bold" />
          <span>用户详情</span>
        </span>
      </template>

      <div v-loading="userDetailLoading" class="user-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="用户名">
            {{ currentUserDetail?.username }}
          </el-descriptions-item>
          <el-descriptions-item label="邮箱">
            {{ currentUserDetail?.email }}
          </el-descriptions-item>
          <el-descriptions-item label="手机号">
            {{ currentUserDetail?.phone || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="真实姓名">
            {{ currentUserDetail?.real_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentUserDetail?.status)" size="small">
              {{ getStatusText(currentUserDetail?.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ currentUserDetail?.created_at ? new Date(currentUserDetail.created_at).toLocaleString() : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="最后登录">
            {{ currentUserDetail?.last_login_at ? new Date(currentUserDetail.last_login_at).toLocaleString() : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="个人简介" :span="2">
            {{ currentUserDetail?.bio || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="角色" :span="2">
            <el-tag
              v-for="role in currentUserDetail?.roles"
              :key="role.id"
              size="small"
              class="role-tag"
            >
              {{ role.name }}
            </el-tag>
            <span v-if="!currentUserDetail?.roles || currentUserDetail.roles.length === 0">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="权限" :span="2">
            <div class="permissions-list">
              <el-tag
                v-for="permission in currentUserDetail?.permissions"
                :key="permission"
                size="small"
                type="info"
                class="perm-tag"
              >
                {{ permission }}
              </el-tag>
              <span v-if="!currentUserDetail?.permissions || currentUserDetail.permissions.length === 0">-</span>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <template #footer>
        <el-button type="primary" @click="handleDetailClose">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码弹框 -->
    <el-dialog
      v-model="resetPasswordVisible"
      :width="500"
      :close-on-click-modal="false"
      align-center
      class="user-dialog"
      @close="handleResetPasswordClose"
    >
      <template #header="{ titleId, titleClass }">
        <span :id="titleId" :class="titleClass">
          <i class="i-solar-lock-keyhole-bold" />
          <span>重置密码</span>
        </span>
      </template>

      <el-alert
        :title="`正在重置用户「${currentResetUser?.username}」的密码`"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />
      <el-form
        ref="resetPasswordFormRef"
        :model="resetPasswordForm"
        :rules="resetPasswordFormRules"
        label-position="top"
        class="reset-form"
      >
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetPasswordForm.new_password"
            type="password"
            placeholder="请输入新密码（8-20个字符）"
            maxlength="20"
            show-word-limit
            clearable
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="resetPasswordForm.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            maxlength="20"
            clearable
            show-password
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="handleResetPasswordClose">取消</el-button>
        <el-button
          type="primary"
          :loading="resetPasswordLoading"
          @click="handleSubmitResetPassword"
        >
          <i class="i-solar-check-circle-bold" />
          确定重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.user-list-view {
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
    margin: 0 0 4px;
  }

  .page-description {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
  }
}

.page-actions {
  display: flex;
  gap: 12px;
}

// ==================== 标题图标 ====================
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

// ==================== 统计卡片 ====================

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
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
  width: 260px;
}

.filter-select {
  width: 140px;
}

// ==================== 表格 ====================

.user-table {
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

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.user-email {
  font-size: 12px;
  color: var(--text-placeholder);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.role-empty {
  color: var(--text-placeholder);
  font-size: 13px;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

// ==================== 状态 pill（设计系统规范） ====================

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 4px 10px;
  border-radius: var(--radius-full, 9999px);
  font-size: 12px;
  font-weight: var(--font-weight-medium, 500);

  &.is-passed  { background: var(--color-success-50, #f0fdf4);  color: var(--color-success-600, #16a34a); }
  &.is-failed  { background: var(--color-danger-50, #fef2f2);   color: var(--color-danger-600, #dc2626); }
  &.is-blocked { background: var(--gray-100, #f3f4f6);          color: var(--gray-600, #4b5563); }
  &.is-running { background: var(--color-info-50, #eff6ff);     color: var(--color-info-600, #2563eb); }
  &.is-pending { background: var(--color-warning-50, #fffbeb);  color: var(--color-warning-600, #d97706); }
  &.is-done    { background: var(--color-purple-50, #faf5ff);   color: var(--color-purple-600, #9333ea); }
}

// ==================== 分页 ====================

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}

// ==================== 底部说明 ====================

.config-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--color-success-50, #f0fdf4);
  border: 1px solid var(--color-success-200, #bbf7d0);
  border-radius: 10px;
  font-size: 13px;
  color: var(--color-success-700, #15803d);

  > i {
    font-size: 16px;
    flex-shrink: 0;
  }

  .notice-close {
    margin-left: auto;
    background: none;
    border: none;
    padding: 2px;
    cursor: pointer;
    color: var(--color-success-500, #22c55e);
    font-size: 16px;
    display: flex;
    align-items: center;
    border-radius: 4px;
    transition: color 0.2s;

    &:hover {
      color: var(--text-primary);
    }
  }
}

// ==================== 弹框 ====================

:deep(.user-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

.user-form,
.reset-form {
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }

  :deep(.el-form-item__label) {
    padding: 0 0 6px;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-regular);
  }

  :deep(.el-input__wrapper) {
    border-radius: 8px;
  }
}

.role-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-placeholder);
}

// ==================== 用户详情 ====================

.user-detail {
  .permissions-list {
    max-height: 200px;
    overflow-y: auto;
  }

  :deep(.el-descriptions__label) {
    width: 100px;
  }
}

.perm-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}
</style>
