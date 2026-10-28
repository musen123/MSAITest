/**
 * 个人中心页面
 *
 * AI 智能测试平台 - 个人中心
 * 对应需求文档：01-用户与权限管理模块.md - 第2.4节 用户信息管理
 */

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Edit,
  Lock,
  User,
  Key,
  Document,
  Calendar,
  Male,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api/auth'
import type { ChangePasswordRequest } from '@/types/auth'

const router = useRouter()
const userStore = useUserStore()

// ==================== 状态 ====================
const loading = ref(false)
const activeTab = ref('profile')

// 修改密码对话框
const passwordDialogVisible = ref(false)
const passwordFormRef = ref()
const passwordForm = ref<ChangePasswordRequest>({
  old_password: '',
  new_password: '',
})
const passwordLoading = ref(false)

// ==================== 计算属性 ====================
const userInfo = computed(() => userStore.userInfo)
const isLoggedIn = computed(() => userStore.isLoggedIn)

// ==================== 表单验证规则 ====================
const passwordRules = {
  old_password: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 20, message: '密码为8-20个字符', trigger: 'blur' },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
      message: '密码必须包含字母和数字',
      trigger: 'blur',
    },
  ],
}

// ==================== 方法 ====================

/**
 * 返回
 */
const goBack = () => {
  router.back()
}

/**
 * 编辑资料
 */
const handleEditProfile = () => {
  router.push('/profile/edit')
}

/**
 * 修改密码
 */
const handleChangePassword = () => {
  passwordDialogVisible.value = true
}

/**
 * 提交修改密码
 */
const handleSubmitPassword = async () => {
  if (!passwordFormRef.value) return

  try {
    await passwordFormRef.value.validate()
  } catch {
    return
  }

  passwordLoading.value = true
  try {
    // TODO: 调用修改密码 API
    ElMessage.success('密码修改成功，请重新登录')
    passwordDialogVisible.value = false
    passwordFormRef.value?.resetFields()

    // 登出
    await userStore.logout()
    router.push('/login')
  } catch (error) {
    console.error('修改密码失败:', error)
  } finally {
    passwordLoading.value = false
  }
}

/**
 * 关闭对话框
 */
const handleClosePasswordDialog = () => {
  passwordFormRef.value?.resetFields()
}

/**
 * 退出登录
 */
const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确认要退出登录吗？', '确认退出', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    await userStore.logout()
    router.push('/login')
  } catch {
    // 用户取消
  }
}

/**
 * 格式化时间
 */
const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 组件挂载时检查登录状态
onMounted(() => {
  if (!isLoggedIn.value) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return
  }
})
</script>

<template>
  <div class="profile-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" circle @click="goBack" />
        <div class="title-wrapper">
          <h2 class="page-title">个人中心</h2>
        </div>
      </div>
      <div class="header-actions">
        <el-button :icon="Edit" @click="handleEditProfile">编辑资料</el-button>
        <el-button :icon="Lock" @click="handleChangePassword">修改密码</el-button>
        <el-button :icon="ArrowLeft" @click="handleLogout">退出登录</el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-wrapper">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 内容区域 -->
    <div v-else-if="userInfo" class="content-wrapper">
      <el-tabs v-model="activeTab">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="profile">
          <div class="info-section">
            <div class="profile-header">
              <el-avatar v-if="userInfo.avatar" :src="userInfo.avatar" :size="100" />
              <el-avatar v-else :size="100">
                <el-icon :size="50"><User /></el-icon>
              </el-avatar>
              <div class="profile-info">
                <h3 class="username">{{ userInfo.username }}</h3>
                <el-tag v-if="userInfo.status === 'active'" type="success">正常</el-tag>
                <el-tag v-else type="danger">{{ userInfo.status }}</el-tag>
              </div>
            </div>

            <div class="info-grid">
              <div class="info-item">
                <div class="label">
                  <el-icon><Male /></el-icon>
                  用户名
                </div>
                <div class="value">{{ userInfo.username }}</div>
              </div>
              <div class="info-item">
                <div class="label">
                  <el-icon><Document /></el-icon>
                  邮箱
                </div>
                <div class="value">{{ userInfo.email }}</div>
              </div>
              <div class="info-item">
                <div class="label">
                  <el-icon><Male /></el-icon>
                  真实姓名
                </div>
                <div class="value">{{ userInfo.real_name || '-' }}</div>
              </div>
              <div class="info-item">
                <div class="label">
                  <el-icon><Key /></el-icon>
                  用户ID
                </div>
                <div class="value">{{ userInfo.id }}</div>
              </div>
              <div class="info-item">
                <div class="label">
                  <el-icon><Calendar /></el-icon>
                  注册时间
                </div>
                <div class="value">{{ formatTime(userInfo.created_at) }}</div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 角色权限 -->
        <el-tab-pane label="角色权限" name="roles">
          <div class="info-section">
            <div class="section-title">
              <h3>我的角色</h3>
            </div>
            <div class="role-list">
              <el-tag
                v-for="role in userInfo.roles"
                :key="typeof role === 'string' ? role : role.code"
                size="large"
                class="role-tag"
              >
                {{ typeof role === 'string' ? role : role.name }}
              </el-tag>
            </div>
          </div>

          <div class="info-section">
            <div class="section-title">
              <h3>我的权限</h3>
            </div>
            <div class="permission-list">
              <el-tag
                v-for="permission in userStore.permissions"
                :key="permission"
                class="permission-tag"
              >
                {{ permission }}
              </el-tag>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="passwordDialogVisible"
      title="修改密码"
      width="450px"
      :close-on-click-modal="false"
      @close="handleClosePasswordDialog"
    >
      <el-form label-position="top"
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
      >
        <el-form-item label="原密码" prop="old_password">
          <el-input
            v-model="passwordForm.old_password"
            type="password"
            show-password
            placeholder="请输入原密码"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            show-password
            placeholder="请输入新密码（8-20位，包含字母和数字）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="handleClosePasswordDialog">取消</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="handleSubmitPassword">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.profile-container {
  padding: 20px;
}

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

.loading-wrapper {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 40px;
  box-shadow: 0 2px 8px rgba(var(--theme-rgb-black), 0.06);
}

.content-wrapper {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(var(--theme-rgb-black), 0.06);
}

// ==================== 个人信息 ====================
.profile-header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 32px 0;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.profile-info {
  .username {
    font-size: 20px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 8px 0;
  }
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.info-item {
  .label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: var(--el-text-color-secondary);
    margin-bottom: 8px;

    .el-icon {
      color: var(--theme-color-667eea);
    }
  }

  .value {
    font-size: 16px;
    color: var(--el-text-color-primary);
    font-weight: 500;
  }
}

// ==================== 区块 ====================
.info-section {
  margin-bottom: 32px;

  &:last-child {
    margin-bottom: 0;
  }
}

.section-title {
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 16px 0;
  }
}

.role-list,
.permission-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.role-tag {
  font-size: 14px;
  padding: 8px 16px;
}

.permission-tag {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

@media (max-width: 768px) {
  .profile-container {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  .header-actions {
    flex-direction: column;

    .el-button {
      width: 100%;
    }
  }

  .profile-header {
    flex-direction: column;
    text-align: center;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
