/**
 * 用户信息编辑对话框组件
 *
 * AI 智能测试平台 - 个人中心信息编辑
 * 使用已有的 API 封装：userApi
 */

<template>
  <el-dialog
    v-model="dialogVisible"
    :width="600"
    :close-on-click-modal="false"
    align-center
    class="profile-edit-dialog"
    @close="handleClose"
  >
    <!-- 自定义标题（使用 EP title 钩子） -->
    <template #header="{ titleId, titleClass }">
      <span :id="titleId" :class="titleClass">
        <i class="i-solar-user-circle-bold" />
        <span>编辑个人资料</span>
      </span>
    </template>

    <!-- 头像上传区（顶部行） -->
    <div class="avatar-row">
      <div class="avatar-preview">
        <el-avatar
          v-if="form.avatar"
          :size="72"
          :src="form.avatar"
          class="avatar-img"
        />
        <div v-else class="avatar-placeholder">
          <i class="i-solar-user-bold" />
        </div>
      </div>
      <div class="avatar-meta">
        <div class="avatar-title">个人头像</div>
        <div class="avatar-desc">支持 PNG / JPG / GIF 格式，文件不超过 2MB，建议 200x200 像素</div>
        <div class="avatar-actions">
          <el-button size="small" :icon="Upload" plain @click="triggerUpload">
            选择图片
          </el-button>
          <el-button
            v-if="form.avatar"
            size="small"
            :icon="Delete"
            type="danger"
            plain
            @click="handleRemoveAvatar"
          >
            移除头像
          </el-button>
        </div>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/gif"
          style="display: none"
          @change="handleFileChange"
        />
      </div>
    </div>

    <!-- 表单区域 -->
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="profile-form"
    >
      <el-form-item label="真实姓名" prop="real_name" class="form-item-required">
        <el-input
          v-model="form.real_name"
          placeholder="请输入真实姓名"
          clearable
          maxlength="50"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="邮箱地址" prop="email" class="form-item-required">
        <el-input
          v-model="form.email"
          type="email"
          placeholder="请输入邮箱地址，用于接收通知"
          clearable
          maxlength="80"
        />
      </el-form-item>

      <el-form-item label="手机号" prop="phone">
        <el-input
          v-model="form.phone"
          placeholder="请输入手机号（可选）"
          clearable
          maxlength="11"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="用户名">
        <el-input :model-value="form.username" disabled placeholder="登录用户名不可修改" />
      </el-form-item>
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
          <i class="i-solar-check-circle-bold" />
          保存修改
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules, type UploadProps, type UploadRawFile } from 'element-plus'
import { Upload, Delete } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/user'

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<Emits>()

const userStore = useUserStore()

// ==================== 状态 ====================
const formRef = ref<FormInstance>()
const fileInputRef = ref<HTMLInputElement>()
const loading = ref(false)
const avatarUploading = ref(false)

const form = reactive({
  avatar: '',
  username: '',
  real_name: '',
  email: '',
  phone: '',
})

// ==================== 计算属性 ====================
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// ==================== 表单验证规则 ====================
const validateEmail = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) {
    callback()
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(value)) {
    callback(new Error('请输入正确的邮箱地址'))
  } else {
    callback()
  }
}

const validatePhone = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) {
    callback()
    return
  }
  const phoneRegex = /^1[3-9]\d{9}$/
  if (!phoneRegex.test(value)) {
    callback(new Error('请输入正确的手机号'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
    { min: 2, max: 50, message: '姓名长度为 2-50 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { validator: validateEmail, trigger: 'blur' },
  ],
  phone: [{ validator: validatePhone, trigger: 'blur' }],
}

// ==================== 方法 ====================
/**
 * 初始化表单数据
 */
const initForm = () => {
  if (userStore.userInfo) {
    form.avatar = userStore.userInfo.avatar || ''
    form.username = userStore.userInfo.username || ''
    form.real_name = userStore.userInfo.real_name || ''
    form.email = userStore.userInfo.email || ''
    form.phone = userStore.userInfo.phone || ''
  }
}

/**
 * 上传前校验
 */
const beforeAvatarUpload: UploadProps['beforeUpload'] = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件！')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB！')
    return false
  }
  return true
}

/**
 * 触发文件选择
 */
const triggerUpload = () => {
  fileInputRef.value?.click()
}

/**
 * 文件选择变化
 */
const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    // 包装为 UploadRawFile 兼容类型
    const rawFile = Object.assign(file, { uid: Date.now() }) as UploadRawFile
    uploadAvatar(rawFile)
  }
  // 重置 input，允许重复选择同一文件
  target.value = ''
}

/**
 * 上传头像
 */
const uploadAvatar = async (file: UploadRawFile) => {
  if (!beforeAvatarUpload(file)) {
    return
  }

  const userId = userStore.currentUserId
  if (!userId) {
    ElMessage.error('用户未登录')
    return
  }

  avatarUploading.value = true
  try {
    const res = await userApi.uploadAvatar(userId, file)
    if (res.code === 200) {
      form.avatar = res.data.url
      ElMessage.success('头像上传成功')
    }
  } catch (error: unknown) {
    console.error('头像上传失败:', error)
  } finally {
    avatarUploading.value = false
  }
}

/**
 * 删除头像
 */
const handleRemoveAvatar = () => {
  form.avatar = ''
  ElMessage.success('已移除头像')
}

/**
 * 提交表单
 */
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  const userId = userStore.currentUserId
  if (!userId) {
    ElMessage.error('用户未登录')
    return
  }

  loading.value = true
  try {
    const res = await userApi.update(userId, {
      real_name: form.real_name,
      email: form.email,
      phone: form.phone || undefined,
    })

    if (res.code === 200) {
      // 刷新用户信息
      const userRes = await userApi.getDetail(userId)
      if (userRes.code === 200) {
        userStore.setUserInfo(userRes.data)
      }
      ElMessage.success('个人信息更新成功')
      emit('success')
      handleClose()
    }
  } catch (error: unknown) {
    console.error('更新个人信息失败:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 关闭对话框
 */
const handleClose = () => {
  dialogVisible.value = false
  formRef.value?.resetFields()
}

// ==================== 监听 ====================
watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      initForm()
    }
  },
  { immediate: true },
)
</script>

<style lang="scss" scoped>
:deep(.profile-edit-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

// 头像行
.avatar-row {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px 20px;
  background: var(--bg-section, rgba(0, 0, 0, 0.02));
  border: 1px solid var(--border-light);
  border-radius: 12px;
  margin-bottom: 20px;
}

.avatar-preview {
  flex-shrink: 0;
  position: relative;
}

.avatar-img {
  border: 2px solid var(--bg-card);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.avatar-placeholder {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--brand-50);
  color: var(--brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  border: 2px dashed var(--brand-200, #bfdbfe);
}

.avatar-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.avatar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.avatar-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.avatar-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

// 表单
.profile-form {
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
:deep(.profile-form .el-input__wrapper) {
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

:deep(.profile-form .el-input.is-disabled .el-input__wrapper) {
  background: var(--bg-section, rgba(0, 0, 0, 0.02));
  box-shadow: 0 0 0 1px var(--border-light) inset;
}

:deep(.profile-form .el-input__inner) {
  height: 36px;
  font-size: 14px;
  color: var(--text-primary);
}

// 字数统计
:deep(.profile-form .el-input__count) {
  background: transparent;
  color: var(--text-placeholder);
  font-size: 12px;
  right: 10px;
  bottom: 2px;
}

// 错误提示
:deep(.profile-form .el-form-item__error) {
  padding-top: 4px;
  font-size: 12px;
}
</style>
