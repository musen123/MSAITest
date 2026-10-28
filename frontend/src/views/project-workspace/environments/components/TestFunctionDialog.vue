<template>
  <el-dialog
    :model-value="modelValue"
    width="700px"
    :close-on-click-modal="false"
    class="app-dialog test-function-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">测试函数</h3>
        <p class="dialog-desc">输入参数验证函数执行结果</p>
      </div>
    </template>
    <div v-if="functionData" class="test-dialog">
      <!-- 函数信息 -->
      <div class="function-info">
        <div class="function-header">
          <div class="function-icon" :class="`lang-${functionData.language}`">
            <i class="i-solar-database-bold" />
            <i class="i-solar-document-text-bold" />
          </div>
          <div class="function-details">
            <h3 class="function-title">{{ functionData.display_name }}</h3>
            <div class="function-meta">
              <code class="function-code">{{ functionData.name }}()</code>
              <el-tag size="small" :type="functionData.is_active ? 'success' : 'info'">
                {{ functionData.is_active ? '已启用' : '已禁用' }}
              </el-tag>
            </div>
            <p v-if="functionData.description" class="function-description">
              {{ functionData.description }}
            </p>
          </div>
        </div>

        <!-- 参数说明 -->
        <div v-if="functionData.params && functionData.params.length > 0" class="params-info">
          <div class="info-title">
            <i class="i-solar-list-bold" />
            <span>参数列表</span>
          </div>
          <div class="params-hint-list">
            <div
              v-for="param in functionData.params"
              :key="param.name"
              class="param-hint-item"
            >
              <span class="param-hint-name">{{ param.name }}</span>
              <span class="param-hint-type">{{ param.type }}</span>
              <el-tag v-if="param.required" type="danger" size="small">必填</el-tag>
              <span v-if="param.description" class="param-hint-desc">{{ param.description }}</span>
              <span v-if="!param.required && param.default !== undefined" class="param-hint-default">
                默认: {{ param.default }}
              </span>
            </div>
          </div>
        </div>
        <div v-else class="params-info">
          <el-empty description="此函数无需参数" :image-size="50" />
        </div>
      </div>

      <!-- 参数输入 -->
      <div v-if="functionData.params && functionData.params.length > 0" class="params-input-section">
        <div class="section-title">
          <i class="i-solar-pen-2-linear" />
          <span>输入参数值</span>
        </div>

        <el-form :model="testParams" label-position="top">
          <el-form-item
            v-for="param in functionData.params"
            :key="param.name"
            :label="param.name"
            :required="param.required"
          >
            <div class="param-input-wrapper">
              <!-- 根据参数类型使用不同的输入方式 -->
              <template v-if="param.type === 'bool'">
                <el-switch v-model="testParams[param.name]" />
              </template>

              <template v-else-if="param.type === 'int'">
                <el-input-number
                  v-model="testParams[param.name]"
                  :placeholder="`输入${param.type}类型的值`"
                  :disabled="!param.required && testParams[param.name] === undefined"
                  style="width: 100%"
                />
              </template>

              <template v-else-if="param.type === 'float'">
                <el-input-number
                  v-model="testParams[param.name]"
                  :placeholder="`输入${param.type}类型的值`"
                  :precision="2"
                  :disabled="!param.required && testParams[param.name] === undefined"
                  style="width: 100%"
                />
              </template>

              <template v-else-if="param.type === 'list'">
                <el-input
                  v-model="listInputs[param.name]"
                  type="textarea"
                  :rows="2"
                  placeholder="输入列表，格式: [1, 2, 3] 或 ['a', 'b', 'c']"
                  :disabled="!param.required && testParams[param.name] === undefined"
                  @input="handleListInput(param.name, $event)"
                />
              </template>

              <template v-else-if="param.type === 'dict'">
                <el-input
                  v-model="dictInputs[param.name]"
                  type="textarea"
                  :rows="2"
                  placeholder="输入字典，格式: {'key': 'value'}"
                  :disabled="!param.required && testParams[param.name] === undefined"
                  @input="handleDictInput(param.name, $event)"
                />
              </template>

              <template v-else>
                <el-input
                  v-model="testParams[param.name]"
                  :placeholder="`输入${param.type}类型的值`"
                  :disabled="!param.required && testParams[param.name] === undefined"
                  clearable
                />
              </template>

              <!-- 非必填参数，可以切换是否使用默认值 -->
              <div v-if="!param.required" class="use-default-toggle">
                <el-checkbox
                  :model-value="testParams[param.name] !== undefined"
                  @update:model-value="handleUseDefault(param.name, $event)"
                >
                  覆盖默认值
                </el-checkbox>
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <!-- 测试结果 -->
      <div v-if="testResult" class="test-result-section">
        <div class="section-title">
          <el-icon><DocumentChecked /></el-icon>
          <span>执行结果</span>
          <el-tag
            :type="testResult.success ? 'success' : 'danger'"
            size="small"
          >
            {{ testResult.success ? '成功' : '失败' }}
          </el-tag>
        </div>

        <div v-if="testResult.success" class="result-success">
          <div class="result-item">
            <span class="result-label">返回值:</span>
            <div class="result-value">
              <pre class="result-json">{{ formatResult(testResult.result) }}</pre>
            </div>
          </div>
          <div class="result-item">
            <span class="result-label">执行时间:</span>
            <span class="result-value time">{{ testResult.execution_time }} ms</span>
          </div>
        </div>

        <div v-else class="result-error">
          <div class="error-header">
            <i class="i-solar-close-circle-bold" />
            <span>执行失败</span>
          </div>
          <div class="error-message">{{ testResult.error }}</div>
          <div v-if="testResult.execution_time" class="result-item">
            <span class="result-label">执行时间:</span>
            <span class="result-value time">{{ testResult.execution_time }} ms</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">关闭</el-button>
        <el-button
          type="primary"
          :loading="testing"
          @click="handleTest"
        >
          <i class="i-solar-play-bold mr-1" />
          执行测试
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Coin,
  DocumentCopy,
  Grid,
  Edit,
  DocumentChecked,
  CircleCloseFilled,
  VideoPlay,
} from '@element-plus/icons-vue'
import { environmentApi } from '@/api/environments'
import type {
  GlobalFunction,
  TestFunctionResponse,
  FunctionParam,
} from '@/api/environments'

interface Props {
  modelValue: boolean
  functionData?: GlobalFunction | null
  projectId: number
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const testing = ref(false)
const testResult = ref<TestFunctionResponse | null>(null)
const testParams = ref<Record<string, any>>({})
const listInputs = ref<Record<string, string>>({})
const dictInputs = ref<Record<string, string>>({})

// 监听 functionData 变化，重置测试状态
watch(
  () => props.functionData,
  (newData) => {
    if (newData) {
      resetTest()
    }
  },
)

// 重置测试状态
const resetTest = () => {
  testResult.value = null
  testParams.value = {}

  // 初始化参数值
  if (props.functionData?.params) {
    props.functionData.params.forEach((param) => {
      if (!param.required) {
        // 非必填参数，默认不传入（使用默认值）
        testParams.value[param.name] = undefined
      } else {
        // 必填参数，初始化为空
        testParams.value[param.name] = getDefaultValue(param.type)
      }
    })
  }

  listInputs.value = {}
  dictInputs.value = {}
}

// 获取参数类型的默认值
const getDefaultValue = (type: string) => {
  switch (type) {
    case 'bool':
      return false
    case 'int':
    case 'float':
      return 0
    case 'list':
      return []
    case 'dict':
      return {}
    default:
      return ''
  }
}

// 处理列表输入
const handleListInput = (paramName: string, value: string) => {
  if (!value || value.trim() === '') {
    testParams.value[paramName] = undefined
    return
  }

  try {
    testParams.value[paramName] = JSON.parse(value)
  } catch {
    testParams.value[paramName] = value
  }
}

// 处理字典输入
const handleDictInput = (paramName: string, value: string) => {
  if (!value || value.trim() === '') {
    testParams.value[paramName] = undefined
    return
  }

  try {
    testParams.value[paramName] = JSON.parse(value)
  } catch {
    testParams.value[paramName] = value
  }
}

// 处理是否使用默认值
const handleUseDefault = (paramName: string, useValue: boolean) => {
  if (useValue) {
    const param = props.functionData?.params?.find((p) => p.name === paramName)
    testParams.value[paramName] = getDefaultValue(param?.type || 'string')
  } else {
    testParams.value[paramName] = undefined
  }
}

// 格式化结果
const formatResult = (result: any): string => {
  if (result === null) {
    return 'null'
  }
  if (result === undefined) {
    return 'undefined'
  }
  if (typeof result === 'string') {
    return result
  }
  return JSON.stringify(result, null, 2)
}

// 执行测试
const handleTest = async () => {
  if (!props.functionData) return

  // 验证必填参数
  if (props.functionData.params) {
    for (const param of props.functionData.params) {
      if (param.required && (testParams.value[param.name] === undefined || testParams.value[param.name] === '')) {
        ElMessage.warning(`请填写必填参数: ${param.name}`)
        return
      }
    }
  }

  testing.value = true
  testResult.value = null

  try {
    // 过滤掉 undefined 的参数
    const params: Record<string, any> = {}
    for (const [key, value] of Object.entries(testParams.value)) {
      if (value !== undefined) {
        params[key] = value
      }
    }

    // 内置函数使用 name 调用，自定义函数使用 id 调用
    const res = props.functionData.is_built_in
      ? await environmentApi.testBuiltinFunction(
          props.projectId,
          props.functionData.name,
          { params },
        )
      : await environmentApi.testFunction(
          props.projectId,
          props.functionData.id!,
          { params },
        )

    testResult.value = res.data

    if (testResult.value.success) {
      ElMessage.success('函数执行成功')
    } else {
      ElMessage.error('函数执行失败')
    }
  } catch (error) {
    console.error('测试函数失败:', error)
    testResult.value = {
      success: false,
      error: '测试请求失败',
      execution_time: 0,
    }
  } finally {
    testing.value = false
  }
}

// 关闭对话框
const handleCancel = () => {
  emit('update:modelValue', false)
}
</script>

<style scoped lang="scss">
.test-dialog {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.function-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: var(--workspace-fill-color-extra-light);
  border-radius: 8px;

  .function-header {
    display: flex;
    gap: 16px;

    .function-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      color: var(--theme-white);
      flex-shrink: 0;

      &.lang-python {
        background: linear-gradient(135deg, var(--theme-color-306998) 0%, var(--theme-color-ffd43b) 100%);
      }

      &.lang-javascript {
        background: linear-gradient(135deg, var(--theme-color-f7df1e) 0%, var(--theme-color-323330) 100%);
      }
    }

    .function-details {
      flex: 1;
      min-width: 0;

      .function-title {
        font-size: 16px;
        font-weight: 600;
        color: var(--workspace-text-primary);
        margin: 0 0 6px 0;
      }

      .function-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .function-code {
          padding: 2px 8px;
          background: var(--workspace-fill-color-light);
          border: 1px solid var(--workspace-border-color-lighter);
          border-radius: 4px;
          font-family: 'Consolas', 'Monaco', monospace;
          font-size: 12px;
          color: var(--workspace-color-primary);
        }
      }

      .function-description {
        font-size: 13px;
        color: var(--workspace-text-secondary);
        margin: 0;
        line-height: 1.6;
      }
    }
  }

  .params-info {
    .info-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 500;
      color: var(--workspace-text-secondary);
      margin-bottom: 12px;
    }

    .params-hint-list {
      display: flex;
      flex-direction: column;
      gap: 8px;

      .param-hint-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        background: var(--workspace-card-bg);
        border: 1px solid var(--workspace-border-color-lighter);
        border-radius: 4px;
        font-size: 12px;

        .param-hint-name {
          font-family: 'Consolas', 'Monaco', monospace;
          font-weight: 500;
          color: var(--workspace-color-primary);
        }

        .param-hint-type {
          color: var(--workspace-text-secondary);
        }

        .param-hint-desc {
          color: var(--workspace-text-regular);
        }

        .param-hint-default {
          margin-left: auto;
          color: var(--workspace-text-secondary);
        }
      }
    }
  }
}

.params-input-section {
  padding: 16px;
  background: var(--workspace-fill-color-extra-light);
  border-radius: 8px;

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
    color: var(--workspace-text-primary);
    margin-bottom: 16px;
  }

  .param-input-wrapper {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 6px;

    .use-default-toggle {
      display: flex;
      align-items: center;
      font-size: 12px;
      color: var(--workspace-text-secondary);
    }
  }

  :deep(.el-form-item) {
    margin-bottom: 12px;

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.test-result-section {
  padding: 16px;
  background: var(--workspace-fill-color-extra-light);
  border-radius: 8px;

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
    color: var(--workspace-text-primary);
    margin-bottom: 16px;
  }

  .result-success,
  .result-error {
    display: flex;
    flex-direction: column;
    gap: 12px;

    .result-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;

      .result-label {
        font-size: 13px;
        color: var(--workspace-text-secondary);
        white-space: nowrap;
      }

      .result-value {
        font-size: 13px;
        color: var(--workspace-text-primary);

        &.time {
          font-family: 'Consolas', 'Monaco', monospace;
          color: var(--workspace-color-success);
        }

        .result-json {
          margin: 0;
          padding: 10px 12px;
          background: var(--workspace-card-bg);
          border: 1px solid var(--workspace-border-color-lighter);
          border-radius: 6px;
          font-family: 'Consolas', 'Monaco', monospace;
          font-size: 12px;
          line-height: 1.6;
          color: var(--workspace-text-primary);
          overflow-x: auto;
          white-space: pre-wrap;
          word-break: break-all;
        }
      }
    }
  }

  .result-error {
    .error-header {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      font-weight: 500;
      color: var(--workspace-color-danger);
    }

    .error-message {
      padding: 10px 12px;
      background: rgba(var(--theme-rgb-245-108-108), 0.1);
      border: 1px solid rgba(var(--theme-rgb-245-108-108), 0.3);
      border-radius: 6px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
      color: var(--workspace-text-primary);
      line-height: 1.6;
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

// 暗色模式
[data-theme='dark'] {
  .result-error {
    .error-message {
      background: rgba(var(--theme-rgb-245-108-108), 0.15);
      border-color: rgba(var(--theme-rgb-245-108-108), 0.4);
    }
  }
}
</style>
