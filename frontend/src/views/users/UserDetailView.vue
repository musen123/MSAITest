/**
 * 用户详情页面
 *
 * AI 智能测试平台 - 用户详情
 * 对应需求文档：01-用户与权限管理模块.md - 第2.4节 用户信息管理
 */

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Edit,
  Lock,
  Unlock,
  Delete,
  User,
  Key,
  Document,
  Calendar,
  Link,
} from '@element-plus/icons-vue'
import { useUserManageStore } from '@/stores/userManage'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/user'
import type { UserDetail, UserStatus } from '@/types/user'

const router = useRouter()
const route = useRoute()
const userManageStore = useUserManageStore()
const userStore = useUserStore()

const userId = Number(route.params.id)
const loading = ref(true)
const userDetail = ref<UserDetail | null>(null)

// ==================== 方法 ====================

/**
 * 获取用户详情
 */
const fetchUserDetail = async () => {
  loading.value = true
  const detail = await userManageStore.fetchUserDetail(userId)
  if (detail) {
    userDetail.value = detail
  }
  loading.value = false
}

/**
 * 返回列表
 */
const goBack = () => {
  router.push('/users')
}

/**
 * 编辑用户
 */
const handleEdit = () => {
  router.push(`/users/${userId}/edit`)
}

/**
 * 修改密码
 */
const handleChangePassword = () => {
  router.push(`/users/${userId}/password`)
}

/**
 * 启用/禁用用户
 */
const handleToggleStatus = async () => {
  if (!userDetail.value) return

  const newStatus: UserStatus = userDetail.value.status === 'active' ? 'disabled' : 'active'
  const action = newStatus === 'active' ? '启用' : '禁用'

  try {
    await ElMessageBox.confirm(
      `确认要${action}用户 "${userDetail.value.username}" 吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    const success = await userManageStore.updateUserStatus(userId, newStatus)
    if (success) {
      await fetchUserDetail()
    }
  } catch {
    // 用户取消
  }
}

/**
 * 删除用户
 */
const handleDelete = async () => {
  if (!userDetail.value) return

  try {
    await ElMessageBox.confirm(
      `确认要删除用户 "${userDetail.value.username}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    const success = await userManageStore.deleteUser(userId)
    if (success) {
      ElMessage.success('删除成功')
      router.push('/users')
    }
  } catch {
    // 用户取消
  }
}

/**
 * 状态标签颜色
 */
const getStatusType = (status: UserStatus) => {
  switch (status) {
    case 'active':
      return 'success'
    case 'disabled':
      return 'info'
    case 'locked':
      return 'danger'
    default:
      return ''
  }
}

/**
 * 状态文本
 */
const getStatusText = (status: UserStatus) => {
  switch (status) {
    case 'active':
      return '启用'
    case 'disabled':
      return '禁用'
    case 'locked':
      return '锁定'
    default:
      return status
  }
}

/**
 * 格式化时间
 */
const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 组件挂载时获取数据
onMounted(() => {
  fetchUserDetail()
})
</script>

<template>
  <div class="user-detail-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" circle @click="goBack" />
        <div class="title-wrapper">
          <h2 class="page-title">用户详情</h2>
          <el-tag v-if="userDetail" :type="getStatusType(userDetail.status)" size="large">
            {{ getStatusText(userDetail.status) }}
          </el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button v-permission="'user:edit'" :icon="Edit" @click="handleEdit">编辑</el-button>
        <el-button
          v-permission="'user:edit'"
          :icon="userDetail?.status === 'active' ? Lock : Unlock"
          @click="handleToggleStatus"
        >
          {{ userDetail?.status === 'active' ? '禁用' : '启用' }}
        </el-button>
        <el-button v-permission="'user:delete'" type="danger" :icon="Delete" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-wrapper">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 详情内容 -->
    <div v-else-if="userDetail" class="detail-content">
      <!-- 基本信息 -->
      <div class="info-section">
        <div class="section-header">
          <el-icon :size="20"><User /></el-icon>
          <h3>基本信息</h3>
        </div>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">头像</span>
            <div class="avatar-wrapper">
              <el-avatar v-if="userDetail.avatar" :src="userDetail.avatar" :size="80" />
              <el-avatar v-else :size="80">
                <el-icon :size="40"><User /></el-icon>
              </el-avatar>
            </div>
          </div>
          <div class="info-item">
            <span class="label">用户名</span>
            <span class="value">{{ userDetail.username }}</span>
          </div>
          <div class="info-item">
            <span class="label">邮箱</span>
            <span class="value">{{ userDetail.email }}</span>
          </div>
          <div class="info-item">
            <span class="label">手机号</span>
            <span class="value">{{ userDetail.phone || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">真实姓名</span>
            <span class="value">{{ userDetail.real_name || '-' }}</span>
          </div>
          <div class="info-item full-width">
            <span class="label">个人简介</span>
            <span class="value">{{ userDetail.bio || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">账户状态</span>
            <el-tag :type="getStatusType(userDetail.status)" size="large">
              {{ getStatusText(userDetail.status) }}
            </el-tag>
          </div>
          <div class="info-item">
            <span class="label">创建时间</span>
            <span class="value">{{ formatTime(userDetail.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="label">更新时间</span>
            <span class="value">{{ formatTime(userDetail.updated_at) }}</span>
          </div>
          <div class="info-item">
            <span class="label">最后登录</span>
            <span class="value">
              {{ userDetail.last_login_at ? formatTime(userDetail.last_login_at) : '从未登录' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 角色信息 -->
      <div class="info-section">
        <div class="section-header">
          <el-icon :size="20"><Key /></el-icon>
          <h3>角色信息</h3>
        </div>
        <div class="role-list">
          <el-tag
            v-for="role in userDetail.roles"
            :key="role.id"
            size="large"
            :type="role.is_system ? 'warning' : ''"
          >
            {{ role.name }}
          </el-tag>
          <el-tag v-if="userDetail.roles.length === 0" type="info">暂无角色</el-tag>
        </div>
      </div>

      <!-- 权限列表 -->
      <div class="info-section">
        <div class="section-header">
          <el-icon :size="20"><Document /></el-icon>
          <h3>权限列表</h3>
        </div>
        <div class="permission-list">
          <el-tag
            v-for="permission in userDetail.permissions"
            :key="permission"
            size="small"
            class="permission-tag"
          >
            {{ permission }}
          </el-tag>
          <div v-if="userDetail.permissions.length === 0" class="empty-text">暂无权限</div>
        </div>
      </div>

      <!-- 参与项目 -->
      <div v-if="userDetail.projects && userDetail.projects.length > 0" class="info-section">
        <div class="section-header">
          <el-icon :size="20"><Link /></el-icon>
          <h3>参与项目</h3>
        </div>
        <div class="project-list">
          <div v-for="project in userDetail.projects" :key="project.id" class="project-item">
            <div class="project-info">
              <span class="project-name">{{ project.name }}</span>
              <el-tag size="small">{{ project.role }}</el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.user-detail-container {
  padding: 20px;
}

// ==================== 页面头部 ====================
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

// ==================== 加载状态 ====================
.loading-wrapper {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 40px;
  box-shadow: 0 2px 8px rgba(var(--theme-rgb-black), 0.06);
}

// ==================== 详情内容 ====================
.detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// ==================== 信息区块 ====================
.info-section {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(var(--theme-rgb-black), 0.06);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0;
  }

  .el-icon {
    color: var(--theme-color-667eea);
  }
}

// ==================== 信息网格 ====================
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;

  &.full-width {
    grid-column: 1 / -1;
  }

  .label {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    font-weight: 500;
  }

  .value {
    font-size: 16px;
    color: var(--el-text-color-primary);
    font-weight: 500;
  }
}

.avatar-wrapper {
  display: flex;
  justify-content: center;
}

// ==================== 角色列表 ====================
.role-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

// ==================== 权限列表 ====================
.permission-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.permission-tag {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.empty-text {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

// ==================== 项目列表 ====================
.project-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.project-item {
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  transition: all 0.3s;

  &:hover {
    background: var(--theme-color-ecf5ff);
  }
}

.project-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.project-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

// ==================== 响应式 ====================
@media (max-width: 768px) {
  .user-detail-container {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-actions {
    flex-direction: column;

    .el-button {
      width: 100%;
    }
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
