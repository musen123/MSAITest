<template>
  <el-dialog
    :model-value="modelValue"
    width="560px"
    :close-on-click-modal="false"
    class="app-dialog variable-form-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">{{ isEdit ? '编辑变量' : '添加变量' }}</h3>
        <p class="dialog-desc">为当前环境配置可在脚本中引用的变量</p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      class="variable-form"
    >
      <el-form-item label="变量名称" prop="name" required>
        <el-input
          v-model="formData.name"
          placeholder="例如：api_key、base_url"
          maxlength="100"
          clearable
        />
        <div class="form-tip">用于在脚本和测试中引用此变量</div>
      </el-form-item>

      <el-form-item label="变量值" prop="value" required>
        <el-input
          v-model="formData.value"
          type="textarea"
          :rows="3"
          placeholder="请输入变量值"
          maxlength="1000"
          show-word-limit
        />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="变量类型" prop="type">
            <el-select v-model="formData.type" placeholder="选择类型" class="full-width">
              <el-option label="文本" value="text" />
              <el-option label="密码" value="password" />
              <el-option label="JSON" value="json" />
              <el-option label="动态" value="dynamic" />
            </el-select>
            <div class="form-tip">密码类型将隐藏显示</div>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="状态">
            <el-switch v-model="formData.is_active" />
            <span class="form-tip">{{ formData.is_active ? '已启用' : '已禁用' }}</span>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="变量描述">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="2"
          placeholder="简要描述该变量的用途"
          maxlength="500"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '添加变量' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type { EnvironmentVariable, VariableType } from '@/api/environments'

interface Props {
  modelValue: boolean
  variable?: EnvironmentVariable | null
  envId: number
  projectId: number
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const isEdit = computed(() => !!props.variable)

const formData = ref({
  name: '',
  value: '',
  type: 'text' as VariableType,
  description: '',
  is_active: true,
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入变量名称', trigger: 'blur' },
    { pattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/, message: '只能以字母/下划线开头,只含字母数字下划线', trigger: 'blur' },
  ],
  value: [
    { required: true, message: '请输入变量值', trigger: 'blur' },
    { max: 1000, message: '最多 1000 个字符', trigger: 'blur' },
  ],
  type: [{ required: true, message: '请选择变量类型', trigger: 'change' }],
}

const resetForm = () => {
  formData.value = { name: '', value: '', type: 'text', description: '', is_active: true }
  formRef.value?.clearValidate()
}

watch(
  () => props.variable,
  (variable) => {
    if (variable) {
      formData.value = {
        name: variable.name,
        value: variable.value,
        type: variable.type,
        description: variable.description || '',
        is_active: variable.is_active,
      }
    } else {
      resetForm()
    }
  },
  { immediate: true },
)

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (isEdit.value && props.variable) {
        await environmentApi.updateVariable(
          props.projectId, props.envId, props.variable.id,
          {
            value: formData.value.value,
            type: formData.value.type,
            description: formData.value.description || undefined,
            is_active: formData.value.is_active,
          },
        )
        ElMessage.success('更新成功')
      } else {
        await environmentApi.createVariable(props.projectId, props.envId, {
          name: formData.value.name,
          value: formData.value.value,
          type: formData.value.type,
          description: formData.value.description || undefined,
          is_active: formData.value.is_active,
        })
        ElMessage.success('添加成功')
      }
      emit('success')
    } catch (error) {
      console.error('提交失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

const handleCancel = () => emit('update:modelValue', false)
</script>

<style scoped lang="scss">
.variable-form {
  :deep(.el-form-item) { margin-bottom: var(--space-5); }
}

.full-width { width: 100%; }

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-placeholder);
}
</style>