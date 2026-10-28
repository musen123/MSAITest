/**
 * 修改密码页面（工作台版本）
 *
 * AI 智能测试平台 - 修改密码
 * 对应需求文档：01-用户与权限管理模块.md - 第2.3节 密码管理
 */

<template>
  <div class="change-password-view">
    <el-page-header title="个人中心" @back="handleBack" class="page-header">
      <template #content>
        <div class="page-title">修改密码</div>
      </template>
    </el-page-header>

    <el-card shadow="hover" class="form-card">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        class="password-form"
      >
        <el-form-item label="原密码" prop="old_password">
          <el-input
            v-model="form.old_password"
            type="password"
            show-password
            placeholder="请输入原密码"
            clearable
          />
        </el-form-item>

        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            show-password
            placeholder="请输入新密码（8-20位，包含字母和数字）"
            clearable
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSubmit">
            确认修改
          </el-button>
          <el-button @click="handleBack">取消</el-button>
        </el-form-item>
      </el-form>

      <!-- 密码要求提示 -->
      <el-alert
        title="密码要求"
        type="info"
        :closable="false"
        show-icon
        class="password-tips"
      >
        <template #default>
          <ul class="password-requirements">
            <li>长度为 8-20 个字符</li>
            <li>必须包含字母和数字</li>
            <li>不能与最近 3 次密码相同</li>
          </ul>
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// ==================== 状态 ====================
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

// ==================== 表单验证规则 ====================
const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
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
    { min: 8, max: 20, message: '密码为8-20个字符', trigger: 'blur' },
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
 * 返回上一页
 */
const handleBack = () => {
  router.back()
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
    // TODO: 调用修改密码 API
    // await authApi.changePassword({
    //   old_password: form.old_password,
    //   new_password: form.new_password,
    // })

    ElMessage.success('密码修改成功，请重新登录')

    // 登出
    await userStore.logout()
    router.push('/login')
  } catch (error: any) {
    console.error('修改密码失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.change-password-view {
  width: 100%;
}

.page-header {
  margin-bottom: 20px;
  background: var(--theme-transparent);
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.form-card {
  max-width: 600px;
}

.password-form {
  padding: 20px 0;
}

.password-tips {
  margin-top: 20px;
}

.password-requirements {
  margin: 8px 0 0 0;
  padding-left: 20px;

  li {
    font-size: 14px;
    color: var(--el-text-color-regular);
    line-height: 1.8;
  }
}
</style>
