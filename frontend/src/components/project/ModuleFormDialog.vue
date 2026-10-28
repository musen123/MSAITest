/**
 * 模块表单对话框组件
 *
 * 用于创建和编辑项目模块
 */

<template>
  <el-dialog
    v-model="visible"
    width="520px"
    :close-on-click-modal="false"
    class="app-dialog module-form-dialog"
    @close="handleClose"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">{{ dialogTitle }}</h3>
        <p class="dialog-desc">
          {{ isCreateMode ? '填写模块基础信息，构建项目功能层级' : '更新模块名称、排序与描述信息' }}
        </p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      class="module-form"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="模块名称" prop="name" required>
        <el-input
          v-model="formData.name"
          placeholder="请输入模块名称"
          maxlength="100"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item v-if="isCreateMode" label="父模块">
        <el-cascader
          v-model="parentPath"
          :options="parentModuleOptions"
          :props="cascaderProps"
          placeholder="选择父模块（不选则为根模块）"
          clearable
          filterable
          :show-all-levels="false"
          class="full-field"
        />
      </el-form-item>

      <el-form-item label="排序">
        <el-input-number
          v-model="formData.sort_order"
          :min="0"
          :max="9999"
          placeholder="排序号"
          class="full-field"
        />
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="3"
          placeholder="请输入模块描述"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        <i class="i-solar-check-circle-bold mr-1" />
        {{ isCreateMode ? '创建模块' : '保存修改' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { projectApi } from '@/api/projects'
import type { ProjectModule, CreateModuleRequest, UpdateModuleRequest } from '@/api/projects'

// ==================== Props ====================

interface Props {
  modelValue: boolean
  mode: 'create' | 'edit'
  projectId: number
  module?: ProjectModule | null
  parentModule?: ProjectModule | null
  moduleTree?: ProjectModule[]
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  mode: 'create',
  module: null,
  parentModule: null,
  moduleTree: () => [],
})

// ==================== Emits ====================

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': []
}>()

// ==================== 状态 ====================

/** 表单引用 */
const formRef = ref<FormInstance | null>(null)

/** 提交状态 */
const submitting = ref(false)

type ModuleFormData = CreateModuleRequest & UpdateModuleRequest

/** 表单数据 */
const formData = ref<ModuleFormData>({
  name: '',
  parent_id: null,
  sort_order: 0,
  description: '',
})

/** 父模块ID（用于级联选择器） */
const parentPath = ref<number | null>(null)

/** 父模块选项（用于级联选择器） */
const parentModuleOptions = ref<any[]>([])

// ==================== 计算属性 ====================

/** 对话框显示状态 */
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

/** 对话框标题 */
const dialogTitle = computed(() => {
  if (props.mode === 'create') {
    return props.parentModule
      ? `创建子模块 - ${props.parentModule.name}`
      : '创建根模块'
  }
  return '编辑模块'
})

/** 是否为创建模式 */
const isCreateMode = computed(() => props.mode === 'create')

/** 级联选择器配置 */
const cascaderProps = {
  value: 'id',
  label: 'name',
  children: 'children',
  emitPath: false,
  checkStrictly: true,
}

// ==================== 表单验证规则 ====================

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入模块名称', trigger: 'blur' },
    { min: 2, max: 100, message: '模块名称长度为2-100个字符', trigger: 'blur' },
  ],
}

// ==================== 方法 ====================

/**
 * 重置表单
 */
const resetForm = () => {
  formData.value = {
    name: '',
    parent_id: null,
    sort_order: 0,
    description: '',
  }
  parentPath.value = null
  formRef.value?.clearValidate()
}

/**
 * 初始化表单数据
 */
const initFormData = () => {
  resetForm()

  if (props.mode === 'create') {
    // 创建模式：设置默认父模块
    if (props.parentModule) {
      formData.value.parent_id = props.parentModule.id
      formData.value.sort_order = 0
    }
  } else if (props.mode === 'edit' && props.module) {
    // 编辑模式：填充模块数据
    formData.value = {
      name: props.module.name,
      parent_id: props.module.parent_id,
      sort_order: props.module.sort_order,
      description: props.module.description || '',
    }
  }
}

/**
 * 构建父模块选项树
 * 在编辑模式下，需要排除当前模块及其所有子孙模块
 */
const buildParentModuleOptions = () => {
  // 如果是编辑模式，需要排除当前模块及其子孙模块
  if (props.mode === 'edit' && props.module) {
    const excludedIds = new Set<number>([props.module.id])

    // 递归收集所有子孙模块ID
    const collectChildrenIds = (modules: ProjectModule[]) => {
      for (const m of modules) {
        excludedIds.add(m.id)
        if (m.children && m.children.length > 0) {
          collectChildrenIds(m.children)
        }
      }
    }

    if (props.module.children && props.module.children.length > 0) {
      collectChildrenIds(props.module.children)
    }

    // 过滤掉被排除的模块
    const filterModules = (modules: ProjectModule[]): ProjectModule[] => {
      return modules
        .filter((m) => !excludedIds.has(m.id))
        .map((m) => ({
          ...m,
          children: m.children ? filterModules(m.children) : [],
        }))
    }

    parentModuleOptions.value = filterModules(props.moduleTree || [])
  } else {
    // 创建模式：直接使用模块树
    parentModuleOptions.value = props.moduleTree || []
  }
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

  submitting.value = true

  try {
    // 处理父模块ID
    let submitData = { ...formData.value }

    if (props.mode === 'create' && parentPath.value !== null) {
      submitData.parent_id = parentPath.value
    }

    if (props.mode === 'create') {
      const response = await projectApi.createModule(
        props.projectId,
        submitData as CreateModuleRequest
      )
      if (response.code === 200) {
        ElMessage.success('创建成功')
        emit('success')
        handleClose()
      }
    } else {
      const response = await projectApi.updateModule(
        props.projectId,
        props.module!.id,
        submitData as UpdateModuleRequest
      )
      if (response.code === 200) {
        ElMessage.success('保存成功')
        emit('success')
        handleClose()
      }
    }
  } catch (error) {
    console.error('提交失败:', error)
  } finally {
    submitting.value = false
  }
}

/**
 * 关闭对话框
 */
const handleClose = () => {
  visible.value = false
}

// ==================== 监听 ====================

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      buildParentModuleOptions()
      initFormData()
      nextTick(() => {
        formRef.value?.clearValidate()
      })
    }
  }
)

watch(
  () => parentPath.value,
  (val) => {
    formData.value.parent_id = val
  }
)
</script>

<style scoped lang="scss">
.module-form {
  :deep(.el-form-item) { margin-bottom: var(--space-5); }
}

.full-field { width: 100%; }
</style>
