<template>
  <el-dialog
    v-model="visible"
    width="650px"
    :close-on-click-modal="false"
    class="app-dialog insert-function-dialog"
    @close="handleClose"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">插入内置函数</h3>
        <p class="dialog-desc">选择一个内置函数生成调用代码插入到光标位置</p>
      </div>
    </template>

    <!-- 搜索 -->
    <div class="search-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索函数名称或描述..."
        clearable
      >
        <template #prefix>
          <i class="i-solar-magnifer-linear" />
        </template>
      </el-input>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 函数列表 -->
    <div v-else class="function-list">
      <div
        v-for="func in filteredFunctions"
        :key="func.name"
        class="function-item"
        :class="{ 'is-selected': selectedFunction?.name === func.name }"
        @click="selectFunction(func)"
      >
        <div class="function-header">
          <span class="function-name">{{ func.name }}</span>
          <el-tag size="small" type="success">{{ func.display_name }}</el-tag>
        </div>
        <div v-if="func.description" class="function-desc">{{ func.description }}</div>
        <div v-if="func.params && func.params.length > 0" class="function-params">
          <span class="params-label">参数:</span>
          <span
            v-for="param in func.params"
            :key="param.name"
            class="param-tag"
          >
            {{ param.name }}: {{ param.type }}
            <span v-if="param.default !== undefined && param.default !== null" class="param-default">
              = {{ JSON.stringify(param.default) }}
            </span>
            <span v-if="param.required" class="param-required">*</span>
          </span>
        </div>
      </div>

      <el-empty v-if="filteredFunctions.length === 0" description="没有找到匹配的函数" :image-size="80" />
    </div>

    <!-- 预览区 -->
    <div v-if="selectedFunction" class="preview-section">
      <div class="preview-header">
        <span>代码预览</span>
        <el-tag size="small" type="info">将插入到光标位置</el-tag>
      </div>
      <pre class="preview-code"><code>{{ previewCode }}</code></pre>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :disabled="!selectedFunction" @click="handleConfirm">
        插入函数
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { environmentApi } from '@/api/environments'
import type { GlobalFunction, FunctionParam } from '@/api/environments'

const props = defineProps<{
  modelValue: boolean
  projectId: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'insert': [code: string]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const loading = ref(false)
const keyword = ref('')
const functions = ref<GlobalFunction[]>([])
const selectedFunction = ref<GlobalFunction | null>(null)

const filteredFunctions = computed(() => {
  if (!keyword.value) return functions.value
  const kw = keyword.value.toLowerCase()
  return functions.value.filter(
    (f) =>
      f.name.toLowerCase().includes(kw) ||
      f.display_name.toLowerCase().includes(kw) ||
      (f.description && f.description.toLowerCase().includes(kw))
  )
})

const generateCallCode = (func: GlobalFunction): string => {
  const params = func.params || []
  const callPrefix = `res = global_function.${func.name}`

  if (params.length === 0) return `${callPrefix}()`

  const paramParts = params.map((p: FunctionParam) => {
    if (p.default !== undefined && p.default !== null) {
      const defaultVal = typeof p.default === 'string' ? `"${p.default}"` : JSON.stringify(p.default)
      return `${p.name}=${defaultVal}`
    }
    return `${p.name}=?`
  })

  return `${callPrefix}(${paramParts.join(', ')})`
}

const previewCode = computed(() => {
  if (!selectedFunction.value) return ''
  return generateCallCode(selectedFunction.value)
})

const selectFunction = (func: GlobalFunction) => { selectedFunction.value = func }

const loadFunctions = async () => {
  if (!props.projectId) return
  try {
    loading.value = true
    const response = await environmentApi.getBuiltinFunctionList(props.projectId)
    functions.value = response.data || []
  } catch {
    functions.value = []
  } finally {
    loading.value = false
  }
}

const handleConfirm = () => {
  if (!selectedFunction.value) return
  emit('insert', generateCallCode(selectedFunction.value))
  handleClose()
}

const handleClose = () => {
  visible.value = false
  selectedFunction.value = null
  keyword.value = ''
}

watch(visible, (val) => { if (val) loadFunctions() })
</script>

<style scoped lang="scss">
.insert-function-dialog {
  .search-bar { margin-bottom: var(--space-3); }

  .loading-container { padding: 16px 0; }

  .function-list {
    max-height: 350px;
    overflow-y: auto;
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);

    .function-item {
      padding: 12px 16px;
      cursor: pointer;
      border-bottom: 1px solid var(--border-light);
      transition: all 0.2s;

      &:last-child { border-bottom: none; }
      &:hover { background: var(--gray-50); }

      &.is-selected {
        background: var(--brand-50);
        border-left: 3px solid var(--brand-500);
      }

      .function-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;

        .function-name {
          font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
          font-size: 14px;
          font-weight: var(--font-weight-semibold);
          color: var(--brand-600);
        }
      }

      .function-desc {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 4px;
        line-height: 1.4;
      }

      .function-params {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px;

        .params-label {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .param-tag {
          font-size: 11px;
          padding: 2px 6px;
          background: var(--gray-100);
          border-radius: 4px;
          font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
          color: var(--text-primary);

          .param-default { color: var(--text-secondary); }
          .param-required { color: var(--color-danger-500); font-weight: bold; }
        }
      }
    }
  }

  .preview-section {
    margin-top: var(--space-3);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    overflow: hidden;

    .preview-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: var(--gray-50);
      font-size: 13px;
      font-weight: var(--font-weight-medium);
      color: var(--text-primary);
    }

    .preview-code {
      margin: 0;
      padding: 12px 16px;
      background: var(--gray-900);
      color: var(--gray-100);
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
      font-size: 13px;
      line-height: 1.6;
      overflow-x: auto;

      code {
        color: inherit;
        font-family: inherit;
      }
    }
  }
}
</style>