/**
 * 角色管理对话框组件
 *
 * AI 智能测试平台 - 创建/编辑角色
 */

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form label-position="top"
      ref="formRef"
      :model="formData"
      :rules="formRules"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="角色名称" prop="name">
        <el-input
          v-model="formData.name"
          placeholder="请输入角色名称"
          maxlength="50"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item label="角色编码" prop="code">
        <el-input
          v-model="formData.code"
          placeholder="请输入角色编码，如：custom_role"
          maxlength="50"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          placeholder="请输入角色描述"
          maxlength="200"
          show-word-limit
          :rows="4"
          clearable
        />
      </el-form-item>

      <el-form-item label="权限配置" prop="permissions">
        <div class="permissions-container">
          <el-checkbox-group v-model="formData.permissions">
            <el-checkbox
              v-for="perm in availablePermissions"
              :key="perm.code"
              :label="perm.code"
            >
              {{ perm.name }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
        <div class="permissions-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>选择角色拥有的权限</span>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ submitButtonText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { usePermissionStore } from '@/stores/permissions'

interface Props {
  modelValue: boolean
  mode: 'create' | 'edit'
  role?: any
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = withDefaults(defineProps<Props>(), {
  role: null,
})

const emit = defineEmits<Emits>()

const permissionStore = usePermissionStore()

// ==================== 状态 ====================

/** 表单引用 */
const formRef = ref<FormInstance>()

/** 加载状态 */
const loading = ref(false)

/** 可用权限列表 */
const availablePermissions = ref([])

// ==================== 计算属性 ====================

/** 对话框标题 */
const dialogTitle = computed(() => {
  return props.mode === 'create' ? '创建角色' : '编辑角色'
})

/** 提交按钮文本 */
const submitButtonText = computed(() => {
  return props.mode === 'create' ? '创建' : '保存'
})

/** 对话框显示状态 */
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

/** 表单数据 */
const formData = reactive({
  name: '',
  code: '',
  description: '',
  permissions: [] as string[],
})

// ==================== 表单验证规则 ====================

/** 验证角色编码格式 */
const validateCode = (_rule: any, value: string, callback: any) => {
  if (!value) {
    return callback(new Error('请输入角色编码'))
  }
  if (!/^[a-zA-Z0-9_]+$/.test(value)) {
    return callback(new Error('角色编码只能包含字母、数字、下划线、中划线'))
  }
  callback()
}

/** 表单验证规则 */
const formRules: FormRules = {
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 2, max: 50, message: '角色名称长度在2-50个字符', trigger: 'blur' },
  ],
  code: [
    { required: true, validator: validateCode, trigger: 'blur' },
    { min: 2, max: 50, message: '角色编码长度在2-50个字符', trigger: 'blur' },
  ],
  description: [
    { max: 200, message: '角色描述最多200个字符', trigger: 'blur' },
  ],
  permissions: [
    { type: 'array', required: true, message: '请选择权限', trigger: 'change' },
  ],
}

// ==================== 方法 ====================

/**
 * 初始化表单数据
 */
const initFormData = () => {
  if (props.mode === 'edit' && props.role) {
    formData.name = props.role.name
    formData.code = props.role.code
    formData.description = props.role.description || ''
    formData.permissions = props.role.permissions || []
  } else {
    formData.name = ''
    formData.code = ''
    formData.description = ''
    formData.permissions = []
  }
}

/**
 * 加载可用权限
 */
const loadAvailablePermissions = async () => {
  const success = await permissionStore.fetchAllPermissions()
  if (success) {
    availablePermissions.value = permissionStore.allPermissions
  }
}

/**
 * 关闭对话框
 */
const handleClose = () => {
  dialogVisible.value = false
}

/**
 * 提交表单
 */
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    loading.value = true

    const success = props.mode === 'create'
      ? await permissionStore.createRole({
          name: formData.name,
          code: formData.code,
          description: formData.description,
          permissions: formData.permissions,
        })
      : await permissionStore.updateRole(props.role.id, {
          name: formData.name,
          description: formData.description,
          permissions: formData.permissions,
        })

    loading.value = false

    if (success) {
      ElMessage.success('保存成功')
      emit('success')
      handleClose()
    }
  } catch (error) {
    console.error('提交失败:', error)
  } finally {
    loading.value = false
  }
}

// ==================== 监听 ====================

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      initFormData()
      loadAvailablePermissions()
    }
  }
)
</script>

<style lang="scss" scoped>
.permissions-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.permissions-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--workspace-fill-color-light);
  border-radius: 4px;

  .el-icon {
    font-size: 16px;
    color: var(--workspace-color-primary);
  }
}

:deep(.el-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

:deep(.el-checkbox) {
  margin-right: 8px;
}
</style>
