<template>
  <el-dialog
    :model-value="modelValue"
    width="560px"
    :close-on-click-modal="!generating"
    :close-on-press-escape="!generating"
    class="app-dialog ai-generate-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="handleClosed"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">AI 生成函数</h3>
        <p class="dialog-desc">用自然语言描述你的需求，AI 自动生成可用的测试函数</p>
      </div>
    </template>

    <!-- 生成结果展示 -->
    <div v-if="generatedFunc" class="result-panel">
      <i class="i-solar-check-circle-bold result-icon" />
      <div class="result-info">
        <div class="result-title">函数生成成功</div>
        <div class="result-meta">
          <span class="func-display-name">{{ generatedFunc.display_name }}</span>
          <code class="func-name">{{ generatedFunc.name }}()</code>
        </div>
        <div v-if="generatedFunc.description" class="result-desc">
          {{ generatedFunc.description }}
        </div>
      </div>
    </div>

    <!-- 输入表单 -->
    <div v-else class="generate-form">
      <el-form label-position="top">
        <el-form-item label="需求描述" required>
          <el-input
            v-model="requirement"
            type="textarea"
            :rows="5"
            placeholder="描述你需要的函数功能，越具体越好。&#10;例如：生成一个随机手机号码&#10;例如：对字符串进行 MD5 加密&#10;例如：获取当前时间戳（毫秒级）"
            :disabled="generating"
            resize="none"
          />
        </el-form-item>

        <el-form-item label="快速示例">
          <div class="example-tags">
            <span
              v-for="ex in exampleList"
              :key="ex"
              class="example-tag"
              @click="requirement = ex"
            >{{ ex }}</span>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <template v-if="generatedFunc">
        <el-button type="primary" @click="handleClose">完成</el-button>
      </template>
      <template v-else>
        <el-button :disabled="generating" @click="handleClose">取消</el-button>
        <el-button
          type="primary"
          :loading="generating"
          :disabled="!requirement.trim()"
          @click="handleGenerate"
        >
          <i v-if="!generating" class="i-solar-cpu-bolt-bold mr-1" />
          {{ generating ? '生成中...' : '开始生成' }}
        </el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { environmentApi } from '@/api/environments'
import type { GlobalFunction } from '@/api/environments'

const props = defineProps<{
  modelValue: boolean
  projectId: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: [func: GlobalFunction]
}>()

const requirement = ref('')
const generating = ref(false)
const generatedFunc = ref<GlobalFunction | null>(null)

const exampleList = [
  '生成随机手机号',
  '获取毫秒级时间戳',
  'MD5 加密字符串',
  '生成随机 UUID',
  '生成指定长度随机字符串',
]

const handleGenerate = async () => {
  const req = requirement.value.trim()
  if (!req) return

  generating.value = true
  try {
    const res = await environmentApi.aiGenerateFunction(props.projectId, { requirement: req })
    generatedFunc.value = res.data
    emit('success', res.data)
  } catch (error: any) {
    console.error('AI 生成函数失败', error)
  } finally {
    generating.value = false
  }
}

const handleClose = () => emit('update:modelValue', false)

const handleClosed = () => {
  requirement.value = ''
  generating.value = false
  generatedFunc.value = null
}
</script>

<style scoped lang="scss">
.generate-form {
  :deep(.el-form-item) { margin-bottom: var(--space-4); }
}

.example-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.example-tag {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: var(--brand-50);
    border-color: var(--brand-300);
    color: var(--brand-600);
  }
}

.result-panel {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: var(--color-success-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-success-300);

  .result-icon {
    font-size: 32px;
    color: var(--color-success-600);
    flex-shrink: 0;
  }

  .result-info {
    flex: 1;
    min-width: 0;

    .result-title {
      font-size: 14px;
      font-weight: var(--font-weight-semibold);
      color: var(--text-primary);
      margin-bottom: 8px;
    }

    .result-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      flex-wrap: wrap;

      .func-display-name {
        font-size: 15px;
        font-weight: var(--font-weight-medium);
        color: var(--text-primary);
      }

      .func-name {
        font-size: 12px;
        color: var(--brand-600);
        background: var(--bg-card);
        padding: 2px 8px;
        border-radius: 4px;
        font-family: 'Consolas', 'Monaco', monospace;
      }
    }

    .result-desc {
      font-size: 13px;
      color: var(--text-secondary);
      line-height: 1.6;
    }
  }
}
</style>