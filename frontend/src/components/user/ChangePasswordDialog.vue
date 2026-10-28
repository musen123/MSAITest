/**
 * 修改密码对话框组件
 *
 * AI 智能测试平台 - 修改密码
 * 对应需求文档：01-用户与权限管理模块.md - 第2.3节 密码管理
 */

<template>
  <el-dialog
    v-model="dialogVisible"
    :width="520"
    :close-on-click-modal="false"
    align-center
    class="change-password-dialog"
    @close="handleClose"
  >
    <!-- 自定义标题（使用 EP title 钩子） -->
    <template #header="{ titleId, titleClass }">
      <span :id="titleId" :class="titleClass">
        <i class="i-solar-shield-keyhole-bold" />
        <span>修改密码</span>
      </span>
    </template>

    <!-- 表单区域 -->
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="password-form"
    >
      <el-form-item label="原密码" prop="old_password" class="form-item-required">
        <el-input
          v-model="form.old_password"
          type="password"
          show-password
          placeholder="请输入当前使用的密码"
          clearable
          autocomplete="current-password"
        />
      </el-form-item>

      <el-form-item label="新密码" prop="new_password" class="form-item-required">
        <el-input
          v-model="form.new_password"
          type="password"
          show-password
          placeholder="请输入新密码（8-20 位，包含字母和数字）"
          clearable
          maxlength="20"
          autocomplete="new-password"
        />
        <!-- 密码强度条 -->
        <div v-if="form.new_password" class="password-strength">
          <div class="strength-bar">
            <div
              class="strength-fill"
              :class="`is-${passwordStrength.level}`"
              :style="{ width: `${passwordStrength.percent}%` }"
            />
          </div>
          <span class="strength-text" :class="`is-${passwordStrength.level}`">
            强度：{{ passwordStrength.label }}
          </span>
        </div>
      </el-form-item>

      <el-form-item label="确认新密码" prop="confirm_password" class="form-item-required">
        <el-input
          v-model="form.confirm_password"
          type="password"
          show-password
          placeholder="请再次输入新密码以确认"
          clearable
          maxlength="20"
          autocomplete="new-password"
        />
        <div v-if="form.confirm_password" class="confirm-hint">
          <i
            :class="form.confirm_password === form.new_password
              ? 'i-solar-check-circle-bold is-match'
              : 'i-solar-close-circle-bold is-mismatch'"
          />
          <span :class="form.confirm_password === form.new_password ? 'is-match' : 'is-mismatch'">
            {{ form.confirm_password === form.new_password ? '两次密码一致' : '两次密码不一致' }}
          </span>
        </div>
      </el-form-item>

      <!-- 密码要求提示 -->
      <div class="password-tips">
        <div class="tips-header">
          <i class="i-solar-info-circle-bold" />
          <span>密码要求</span>
        </div>
        <ul class="tips-list">
          <li :class="{ met: form.new_password.length >= 8 && form.new_password.length <= 20 }">
            <i :class="form.new_password.length >= 8 && form.new_password.length <= 20
              ? 'i-solar-check-circle-bold' : 'i-solar-record-circle-bold'" />
            长度为 8-20 个字符
          </li>
          <li :class="{ met: /[A-Za-z]/.test(form.new_password) && /\d/.test(form.new_password) }">
            <i :class="/[A-Za-z]/.test(form.new_password) && /\d/.test(form.new_password)
              ? 'i-solar-check-circle-bold' : 'i-solar-record-circle-bold'" />
            必须包含字母和数字
          </li>
          <li>
            <i class="i-solar-record-circle-bold" />
            不能与最近 3 次密码相同
          </li>
        </ul>
      </div>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button class="btn-cancel" @click="handleClose">取消</el-button>
        <el-button
          type="primary"
          :loading="loading"
          class="btn-primary"
          @click="handleSubmit"
        >
          <i class="i-solar-shield-check-bold" />
          确认修改
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<Emits>()

const userStore = useUserStore()
const router = useRouter()

// ==================== 状态 ====================
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

// ==================== 计算属性 ====================
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

/** 密码强度 */
const passwordStrength = computed(() => {
  const pwd = form.new_password
  if (!pwd) return { level: 0, percent: 0, label: '' }

  let score = 0
  if (pwd.length >= 8) score++
  if (pwd.length >= 12) score++
  if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score++
  if (/\d/.test(pwd)) score++
  if (/[^\w\s]/.test(pwd)) score++

  if (score <= 1) return { level: 'weak', percent: 33, label: '弱' }
  if (score <= 3) return { level: 'medium', percent: 66, label: '中' }
  return { level: 'strong', percent: 100, label: '强' }
})

// ==================== 表单验证规则 ====================
const validateConfirmPassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== form.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  old_password: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 20, message: '密码为 8-20 个字符', trigger: 'blur' },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
      message: '密码必须包含字母和数字',
      trigger: 'blur',
    },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

// ==================== 方法 ====================

/**
 * 关闭对话框
 */
const handleClose = () => {
  dialogVisible.value = false
  formRef.value?.resetFields()
}

/**
 * 提交修改密码
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
    const userId = userStore.currentUserId
    if (!userId) {
      ElMessage.error('用户未登录')
      return
    }
    await authApi.changePassword(userId, {
      old_password: form.old_password,
      new_password: form.new_password,
    })

    ElMessage.success('密码修改成功，请重新登录')
    emit('success')

    // 登出并跳转
    setTimeout(async () => {
      await userStore.logout()
      router.push('/login')
    }, 800)
  } catch (error: unknown) {
    console.error('修改密码失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
:deep(.change-password-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

// 表单
.password-form {
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }

  :deep(.el-form-item__label) {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    padding-bottom: 6px;
    line-height: 1.4;
  }
}

:deep(.form-item-required .el-form-item__label) {
  &::before {
    content: '*';
    color: var(--color-danger-500);
    margin-right: 4px;
    font-weight: 600;
  }
}

// 输入框
:deep(.password-form .el-input__wrapper) {
  padding: 4px 12px;
  border-radius: 8px;
  background: var(--bg-card);
  box-shadow: 0 0 0 1px var(--border-color) inset;
  transition: all 0.2s;

  &:hover {
    box-shadow: 0 0 0 1px var(--brand-300) inset;
  }

  &.is-focus {
    box-shadow: 0 0 0 1px var(--brand-500) inset, 0 0 0 3px var(--brand-50);
  }
}

:deep(.password-form .el-input__inner) {
  height: 36px;
  font-size: 14px;
  color: var(--text-primary);
}

// 错误提示
:deep(.password-form .el-form-item__error) {
  padding-top: 4px;
  font-size: 12px;
}

// 密码强度条
.password-strength {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.strength-bar {
  flex: 1;
  height: 4px;
  background: var(--bg-section, rgba(0, 0, 0, 0.04));
  border-radius: 2px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s, background 0.3s;

  &.is-weak {
    background: var(--color-danger-500);
  }

  &.is-medium {
    background: var(--color-warning-500);
  }

  &.is-strong {
    background: var(--color-success-500);
  }
}

.strength-text {
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;

  &.is-weak {
    color: var(--color-danger-500);
  }

  &.is-medium {
    color: var(--color-warning-500);
  }

  &.is-strong {
    color: var(--color-success-500);
  }
}

// 确认密码提示
.confirm-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  font-weight: 500;

  i {
    font-size: 14px;
  }

  .is-match {
    color: var(--color-success-500);
  }

  .is-mismatch {
    color: var(--color-danger-500);
  }
}

// 密码要求提示
.password-tips {
  margin-top: 4px;
  padding: 14px 16px;
  background: var(--bg-section, rgba(0, 0, 0, 0.02));
  border: 1px solid var(--border-light);
  border-radius: 10px;
}

.tips-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;

  i {
    color: var(--brand-500);
    font-size: 14px;
  }
}

.tips-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;

  li {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-placeholder);
    line-height: 1.5;
    transition: color 0.2s;

    i {
      font-size: 14px;
      color: var(--text-placeholder);
      flex-shrink: 0;
    }

    &.met {
      color: var(--text-secondary);

      i {
        color: var(--color-success-500);
      }
    }
  }
}
</style>
