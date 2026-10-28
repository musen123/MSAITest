<template>
  <div class="json-editor-wrapper">
    <div class="editor-header">
      <div class="header-left">
        <el-icon><Document /></el-icon>
        <span class="title">{{ title || 'JSON 编辑器' }}</span>
        <el-tag v-if="isValid === true" type="success" size="small">格式正确</el-tag>
        <el-tag v-else-if="isValid === false" type="danger" size="small">格式错误</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="small" :icon="Refresh" @click="handleFormat">
          格式化
        </el-button>
        <el-button size="small" :icon="CopyDocument" @click="handleCopy">
          复制
        </el-button>
        <el-switch
          v-model="isReadonly"
          size="small"
          inline-prompt
          active-text="编辑"
          inactive-text="只读"
        />
      </div>
    </div>
    <CodeEditor
      ref="codeEditorRef"
      v-model="editorValue"
      language="json"
      :theme="theme"
      :readonly="isReadonly"
      :auto-height="autoHeight"
      :show-line-count="true"
      :show-language-selector="false"
      @change="handleEditorChange"
    />
    <div v-if="errorMessage" class="error-message">
      <el-icon><WarningFilled /></el-icon>
      <span>{{ errorMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Refresh, CopyDocument, WarningFilled } from '@element-plus/icons-vue'
import CodeEditor from './CodeEditor.vue'

interface Props {
  modelValue: string | Record<string, any>
  title?: string
  theme?: 'light' | 'dark'
  readonly?: boolean
  autoFormat?: boolean
  /** 自适应高度：编辑器随内容撑开，交给外层容器滚动（只读查看场景） */
  autoHeight?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'valid', isValid: boolean): void
  (e: 'error', error?: string): void
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  theme: 'light',
  readonly: false,
  autoFormat: true,
  autoHeight: false,
})

const emit = defineEmits<Emits>()

const codeEditorRef = ref()
const isReadonly = ref(props.readonly)
const isValid = ref<boolean | null>(null)
const errorMessage = ref('')

// 编辑器值（字符串格式）
const editorValue = computed({
  get: () => {
    if (typeof props.modelValue === 'string') {
      return props.modelValue
    }
    return JSON.stringify(props.modelValue, null, 2)
  },
  set: (value: string) => {
    // 尝试解析 JSON 字符串为对象
    try {
      const parsed = JSON.parse(value)
      emit('update:modelValue', parsed)
    } catch {
      // 如果解析失败，可能是无效的 JSON，保持字符串格式
      emit('update:modelValue', value)
    }
  },
})

// 处理编辑器内容变化，确保 emit 正确的值
const handleEditorValueChange = (value: string) => {
  try {
    const parsed = JSON.parse(value)
    emit('update:modelValue', parsed)
  } catch {
    emit('update:modelValue', value)
  }
}

// 验证 JSON 格式
const validateJson = (value: string): { valid: boolean; error?: string } => {
  if (!value.trim()) {
    return { valid: true }
  }

  try {
    JSON.parse(value)
    return { valid: true }
  } catch (error) {
    if (error instanceof SyntaxError) {
      return {
        valid: false,
        error: `JSON 格式错误: ${error.message}`,
      }
    }
    return {
      valid: false,
      error: '未知错误',
    }
  }
}

// 处理编辑器内容变化，同时验证和发射 update:modelValue
const handleEditorChange = (value: string) => {
  // 验证 JSON 格式
  const result = validateJson(value)
  isValid.value = result.valid
  errorMessage.value = result.error || ''
  emit('valid', result.valid)
  if (!result.valid) {
    emit('error', result.error)
  }
  // 同时发射 update:modelValue（解析为对象或保持字符串）
  handleEditorValueChange(value)
}

// 格式化 JSON
const handleFormat = () => {
  try {
    const parsed = JSON.parse(editorValue.value)
    const formatted = JSON.stringify(parsed, null, 2)
    emit('update:modelValue', formatted)
    isValid.value = true
    errorMessage.value = ''
    ElMessage.success('格式化成功')
  } catch (error) {
    isValid.value = false
    errorMessage.value = '无法格式化：JSON 格式不正确'
    ElMessage.error(errorMessage.value)
  }
}

// 复制内容
const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(editorValue.value)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

// 监听 readonly prop 变化
watch(
  () => props.readonly,
  (value) => {
    isReadonly.value = value
  },
)

// 监听 modelValue 变化，仅用于验证和同步状态，不发射 update:modelValue 避免无限循环
watch(
  () => props.modelValue,
  (value) => {
    const strValue = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    // 仅验证 JSON 格式，不发射 update:modelValue
    const result = validateJson(strValue)
    isValid.value = result.valid
    errorMessage.value = result.error || ''
  },
  { immediate: true },
)

// 暴露方法
defineExpose({
  format: handleFormat,
  validate: () => validateJson(editorValue.value),
  getValue: () => {
    try {
      return JSON.parse(editorValue.value)
    } catch {
      return editorValue.value
    }
  },
  setValue: (value: any) => {
    const strValue = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    emit('update:modelValue', strValue)
  },
})
</script>

<style scoped lang="scss">
// ========================================
// 容器样式
// ========================================

.json-editor-wrapper {
  border: 1px solid var(--workspace-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
  background: var(--workspace-card-bg);
}

// ========================================
// 头部
// ========================================

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--workspace-fill-color-extra-light);
  border-bottom: 1px solid var(--workspace-border-color-lighter);

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;

    .el-icon {
      font-size: 16px;
      color: var(--workspace-color-primary);
    }

    .title {
      font-size: 14px;
      font-weight: 500;
      color: var(--workspace-text-primary);
    }
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

// ========================================
// 错误信息
// ========================================

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(var(--theme-rgb-danger), 0.1);
  border-top: 1px solid rgba(var(--theme-rgb-danger), 0.2);
  color: var(--el-color-danger);
  font-size: 13px;

  .el-icon {
    font-size: 16px;
  }
}

// ========================================
// 暗色模式
// ========================================

[data-theme='dark'] {
  .error-message {
    background: rgba(var(--theme-rgb-danger), 0.15);
    color: var(--el-color-danger-light-3);
  }
}

// ========================================
// 响应式设计
// ========================================

@media (max-width: 768px) {
  .editor-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;

    .header-left,
    .header-actions {
      justify-content: center;
    }

    .header-actions {
      :deep(.el-switch) {
        margin-left: auto;
      }
    }
  }
}
</style>
