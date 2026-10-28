/**
 * 模块移动对话框组件
 *
 * 用于移动模块到其他父模块下
 */

<template>
  <el-dialog
    v-model="visible"
    width="520px"
    :close-on-click-modal="false"
    class="app-dialog module-move-dialog"
    @close="handleClose"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">移动模块</h3>
        <p class="dialog-desc">选择新的父模块并调整排序位置</p>
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
      <div class="current-module-card">
        <span class="current-icon">
          <i class="i-solar-folder-bold" />
        </span>
        <div>
          <div class="current-label">当前模块</div>
          <div class="current-name">{{ module?.name || '-' }}</div>
        </div>
      </div>

      <el-form-item label="目标父模块">
        <el-cascader
          v-model="parentPath"
          :options="availableParentOptions"
          :props="cascaderProps"
          placeholder="选择目标父模块"
          clearable
          filterable
          :show-all-levels="false"
          class="full-field"
        >
          <template #default="{ data }">
            <span>{{ data.name }}</span>
            <span v-if="data.children && data.children.length > 0" class="module-count">
              {{ data.children.length }} 个子模块
            </span>
          </template>
        </el-cascader>
        <div class="form-tip">不选则移动到根目录</div>
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
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        <i class="i-solar-check-circle-bold mr-1" />
        确认移动
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { projectApi } from '@/api/projects'
import type { ProjectModule, MoveModuleRequest } from '@/api/projects'

// ==================== Props ====================

interface Props {
  modelValue: boolean
  projectId: number
  module?: ProjectModule | null
  moduleTree?: ProjectModule[]
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  module: null,
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

/** 表单数据 */
const formData = ref<MoveModuleRequest>({
  parent_id: null,
  sort_order: 0,
})

/** 父模块ID（用于级联选择器） */
const parentPath = ref<number | null>(null)

// ==================== 计算属性 ====================

/** 对话框显示状态 */
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

/** 级联选择器配置 */
const cascaderProps = {
  value: 'id',
  label: 'name',
  children: 'children',
  emitPath: false,
  checkStrictly: true,
}

/**
 * 获取不可选择的模块ID集合（包括自身及其所有子孙模块）
 */
const disabledIds = computed(() => {
  if (!props.module) return new Set<number>()

  const ids = new Set<number>([props.module.id])

  // 递归获取所有子孙模块ID
  const collectChildrenIds = (modules: ProjectModule[]) => {
    for (const m of modules) {
      ids.add(m.id)
      if (m.children && m.children.length > 0) {
        collectChildrenIds(m.children)
      }
    }
  }

  if (props.module.children && props.module.children.length > 0) {
    collectChildrenIds(props.module.children)
  }

  return ids
})

/**
 * 构建可用的父模块选项
 * 排除当前模块及其所有子孙模块
 */
const availableParentOptions = computed(() => {
  const filterModules = (modules: ProjectModule[]): ProjectModule[] => {
    return modules
      .filter((m) => !disabledIds.value.has(m.id))
      .map((m) => ({
        ...m,
        children: m.children ? filterModules(m.children) : [],
      }))
  }

  return filterModules(props.moduleTree || [])
})

// ==================== 表单验证规则 ====================

const formRules: FormRules = {}

// ==================== 方法 ====================

/**
 * 重置表单
 */
const resetForm = () => {
  formData.value = {
    parent_id: null,
    sort_order: 0,
  }
  parentPath.value = null
  formRef.value?.clearValidate()
}

/**
 * 初始化表单数据
 */
const initFormData = () => {
  resetForm()
  if (props.module) {
    formData.value.sort_order = props.module.sort_order
    // 不填充 parent_id，让用户主动选择
  }
}

/**
 * 提交表单
 */
const handleSubmit = async () => {
  if (!formRef.value || !props.module) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true

  try {
    // 处理父模块ID
    const submitData: MoveModuleRequest = {
      parent_id: parentPath.value,
      sort_order: formData.value.sort_order,
    }

    const response = await projectApi.moveModule(
      props.projectId,
      props.module.id,
      submitData
    )

    if (response.code === 200) {
      ElMessage.success('移动成功')
      emit('success')
      handleClose()
    }
  } catch (error) {
    console.error('移动失败:', error)
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

.current-module-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--gray-50);
}

.current-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--brand-50);
  color: var(--brand-600);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.current-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.current-name {
  margin-top: 3px;
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.full-field { width: 100%; }

.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-placeholder);
}

.module-count {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
