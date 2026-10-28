/**
 * 修改密码页面
 *
 * AI 智能测试平台 - 修改密码
 * 对应需求文档：01-用户与权限管理模块.md - 第2.3节 密码管理
 * 对应 API 文档：01-用户与权限管理模块API.md - 第4.5节 修改密码
 */

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { ArrowLeft, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/user'
import type { ChangePasswordRequest } from '@/types/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// ==================== 状态 ====================
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = ref<ChangePasswordRequest>({
  old_password: '',
  new_password: '',
})
const showPassword = ref({
  old: false,
  new: false,
})

// ==================== 计算属性 ====================
const isCurrentUserId = computed(() => {
  const userId = Number(route.params.id)
  return userId === userStore.userId || !route.params.id
})

// ==================== 表单验证规则 ====================
const rules: FormRules = {
  old_password: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' },
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 20, message: '密码为8-20个字符', trigger: 'blur' },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
      message: '密码必须包含字母和数字',
      trigger: 'blur',
    },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value && value === form.value.old_password) {
          callback(new Error('新密码不能与原密码相同'))
        } else {
          callback()
        }
      },
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
 * 提交修改
 */
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const userId = isCurrentUserId.value ? userStore.userId : Number(route.params.id)
    const success = await userApi.changePassword(userId, form.value)

    if (success) {
      ElMessage.success('密码修改成功，请重新登录')

      // 如果是修改自己的密码，需要重新登录
      if (isCurrentUserId.value) {
        await userStore.logout()
        router.push('/login')
      } else {
        goBack()
      }
    }
  } catch (error) {
    console.error('修改密码失败:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 密码强度提示
 */
const getPasswordHint = (field: 'old' | 'new') => {
  const hints = {
    old: '请输入当前密码',
    new: '8-20位，包含字母和数字',
  }
  return hints[field]
}
</script>

<template>
  <div class="change-password-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" circle @click="goBack" />
        <div class="title-wrapper">
          <h2 class="page-title">修改密码</h2>
          <p class="page-description">为了账户安全，请定期修改密码</p>
        </div>
      </div>
    </div>

    <!-- 表单区域 -->
    <div class="form-wrapper">
      <div class="form-header">
        <el-icon :size="32" color="#667eea">
          <Lock />
        </el-icon>
        <h3>修改密码</h3>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        label-position="top"
        class="password-form"
      >
        <el-form-item label="原密码" prop="old_password">
          <el-input
            v-model="form.old_password"
            type="password"
            :placeholder="getPasswordHint('old')"
            :show-password="!showPassword.old"
            @click:show-password="() => (showPassword.old = !showPassword.old)"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            :placeholder="getPasswordHint('new')"
            :show-password="!showPassword.new"
            @click:show-password="() => (showPassword.new = !showPassword.new)"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="submit-button"
            @click="handleSubmit"
          >
            {{ loading ? '提交中...' : '确 定' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 安全提示 -->
      <div class="security-tips">
        <h4>安全提示</h4>
        <ul>
          <li>密码长度应为 8-20 个字符</li>
          <li>密码必须包含字母和数字</li>
          <li>新密码不能与原密码相同</li>
          <li>建议定期更换密码以保障账户安全</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.change-password-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 100vh;
  padding: 20px;
  background: linear-gradient(135deg, var(--el-fill-color-light) 0%, var(--theme-color-e8ecf1) 100%);
}

.page-header {
  width: 100%;
  max-width: 500px;
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
  margin: 0 0 8px 0;
}

.page-description {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

// ==================== 表单包装器 ====================
.form-wrapper {
  width: 100%;
  max-width: 500px;
  background: var(--el-bg-color);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(var(--theme-rgb-black), 0.1);
  padding: 40px;
}

.form-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);

  h3 {
    font-size: 20px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0;
  }
}

.password-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: var(--el-text-color-regular);
  }

  :deep(.el-input__wrapper) {
    border-radius: 8px;
    box-shadow: 0 0 0 1px var(--el-border-color) inset;
    transition: all 0.3s;

    &:hover {
      box-shadow: 0 0 0 1px var(--el-text-color-disabled) inset;
    }

    &.is-focused {
      box-shadow: 0 0 0 1px var(--theme-color-667eea) inset;
    }
  }

  .submit-button {
    width: 100%;
    height: 44px;
    font-size: 16px;
    font-weight: 500;
    border-radius: 8px;
    background: linear-gradient(135deg, var(--theme-color-667eea) 0%, var(--theme-color-764ba2) 100%);
    border: none;
    transition: all 0.3s;

    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(var(--theme-rgb-102-126-234), 0.4);
    }

    &:active:not(:disabled) {
      transform: translateY(0);
    }
  }
}

// ==================== 安全提示 ====================
.security-tips {
  margin-top: 32px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  border-left: 3px solid var(--theme-color-667eea);

  h4 {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 12px 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  ul {
    margin: 0;
    padding-left: 20px;
    list-style: disc;

    li {
      font-size: 13px;
      color: var(--el-text-color-regular);
      line-height: 1.6;
      margin-bottom: 4px;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}

// ==================== 响应式 ====================
@media (max-width: 480px) {
  .change-password-container {
    padding: 12px;
  }

  .form-wrapper {
    padding: 24px;
  }
}
</style>
