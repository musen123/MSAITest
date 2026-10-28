/**
 * 项目创建/编辑对话框组件
 *
 * AI 智能测试平台 - 项目创建/编辑对话框
 * 对应需求文档：02-项目管理模块.md
 */

<template>
  <el-dialog
    v-model="dialogVisible"
    :width="600"
    :close-on-click-modal="false"
    align-center
    class="app-dialog project-create-dialog"
    @close="handleClose"
  >
    <!-- 自定义标题 -->
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">{{ dialogTitle }}</h3>
        <p class="dialog-desc">
          {{ mode === 'create' ? '创建一个新项目以管理测试用例和团队协作' : '更新项目的基础信息和配置' }}
        </p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      class="project-form"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="项目名称" prop="name" class="form-item-required">
        <el-input
          v-model="formData.name"
          placeholder="请输入项目名称，便于团队识别"
          maxlength="100"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item label="项目标识" prop="code" class="form-item-required">
        <el-input
          v-model="formData.code"
          placeholder="系统自动生成，无需编辑"
          readonly
          disabled
        />
      </el-form-item>

      <el-form-item label="项目描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          placeholder="简单介绍项目目标、范围等（选填）"
          maxlength="500"
          show-word-limit
          :rows="3"
          clearable
        />
      </el-form-item>

      <el-form-item label="项目周期" prop="start_date">
        <el-date-picker
          v-model="formData.start_date"
          type="date"
          placeholder="选择开始日期"
          value-format="YYYY-MM-DD"
          :clearable="true"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="计划结束" prop="end_date">
        <el-date-picker
          v-model="formData.end_date"
          type="date"
          placeholder="选择结束日期"
          value-format="YYYY-MM-DD"
          :clearable="true"
          style="width: 100%"
        />
      </el-form-item>

      <!-- 高级设置 -->
      <el-form-item label="公开项目">
        <div class="switch-row">
          <el-switch v-model="formData.is_public" />
          <span class="form-hint">开启后所有用户可查看此项目（仍需权限才能编辑）</span>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        <i class="i-solar-check-circle-bold mr-1" />
        {{ submitButtonText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useProjectStore } from '@/stores/projects'
import type { Project, CreateProjectRequest } from '@/api/projects'

/**
 * 生成项目标识
 * 格式：project_ + 10 位时间戳（10 位 = 秒级时间戳）
 */
const generateProjectCode = (): string => {
  return `project_${Math.floor(Date.now() / 1000)}`
}

interface Props {
  modelValue: boolean
  mode: 'create' | 'edit'
  project?: Project | null
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = withDefaults(defineProps<Props>(), {
  project: null,
})

const emit = defineEmits<Emits>()

const projectStore = useProjectStore()

// ==================== 状态 ====================

/** 表单引用 */
const formRef = ref<FormInstance>()

/** 加载状态 */
const loading = ref(false)

/** 表单数据 */
const formData = reactive<CreateProjectRequest>({
  name: '',
  code: '',
  description: '',
  start_date: '',
  end_date: '',
  is_public: false,
})

// ==================== 计算属性 ====================

/** 对话框标题 */
const dialogTitle = computed(() => {
  return props.mode === 'create' ? '创建项目' : '编辑项目'
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

// ==================== 表单验证规则 ====================

/** 验证结束日期 */
const validateEndDate = (_rule: any, value: string, callback: any) => {
  if (value && formData.start_date && new Date(value) < new Date(formData.start_date)) {
    return callback(new Error('结束日期不能早于开始日期'))
  }
  callback()
}

/** 表单验证规则 */
const formRules: FormRules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 100, message: '项目名称长度在2-100个字符', trigger: 'blur' },
  ],
  description: [
    { max: 500, message: '项目描述最多500个字符', trigger: 'blur' },
  ],
  end_date: [
    { validator: validateEndDate, trigger: 'change' },
  ],
}

// ==================== 方法 ====================

/**
 * 初始化表单数据
 */
const initFormData = () => {
  if (props.mode === 'edit' && props.project) {
    formData.name = props.project.name
    formData.code = props.project.code
    formData.description = props.project.description || ''
    formData.start_date = props.project.start_date || ''
    formData.end_date = props.project.end_date || ''
    formData.is_public = props.project.is_public
  } else {
    formData.name = ''
    formData.code = generateProjectCode()
    formData.description = ''
    formData.start_date = ''
    formData.end_date = ''
    formData.is_public = false
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

    // 清理空字符串字段，转换为 undefined 以便不发送到后端
    const cleanData: CreateProjectRequest = {
      name: formData.name,
      code: formData.code,
      description: formData.description || undefined,
      start_date: formData.start_date || undefined,
      end_date: formData.end_date || undefined,
      is_public: formData.is_public,
    }

    const success = props.mode === 'create'
      ? await projectStore.createProject(cleanData)
      : await projectStore.updateProject(props.project!.id, cleanData)

    if (success) {
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
      // 重置表单验证
      formRef.value?.clearValidate()
    }
  },
)
</script>

<style lang="scss" scoped>
.project-form {
  :deep(.form-item-required .el-form-item__label)::before {
    content: '*';
    color: var(--color-danger-500, #f56c6c);
    margin-right: 4px;
    font-weight: 600;
  }

  :deep(.el-form-item) {
    margin-bottom: var(--space-5);

    &:last-child {
      margin-bottom: 0;
    }
  }

  :deep(.el-form-item__label) {
    padding: 0 0 6px;
    font-size: 13px;
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    line-height: 1.4;
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner) {
    border-radius: 8px;
    transition: all 0.2s;
  }

  :deep(.el-input__wrapper.is-focus),
  :deep(.el-textarea__inner:focus) {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand-500) 12%, transparent);
  }
}

// 字段提示
.field-tip {
  font-size: 12px;
  color: var(--text-placeholder);
  line-height: 1.5;
  margin-top: 6px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-top: 4px;
}

.form-hint {
  font-size: 12px;
  color: var(--text-placeholder);
}
</style>
