<template>
  <el-dialog
    :model-value="modelValue"
    width="800px"
    :close-on-click-modal="false"
    class="app-dialog function-form-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="handleClosed"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">{{ isEdit ? '编辑函数' : '新建函数' }}</h3>
        <p class="dialog-desc">创建一个可在测试用例中复用的自定义函数</p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      @submit.prevent="handleSubmit"
      class="function-form"
    >
      <el-tabs v-model="activeTab" class="function-tabs">
        <!-- 基本信息 -->
        <el-tab-pane name="basic">
          <template #label>
            <span class="tab-label"><i class="i-solar-info-circle-linear" /> 基本信息</span>
          </template>
          <div class="tab-content">
            <el-form-item label="函数名称" prop="name" required>
              <el-input
                v-model="formData.name"
                placeholder="如：random_string"
                :disabled="isEdit"
                clearable
              />
            </el-form-item>

            <el-form-item label="显示名称" prop="display_name" required>
              <el-input
                v-model="formData.display_name"
                placeholder="如：随机字符串"
                clearable
              />
            </el-form-item>

            <el-form-item label="编程语言" prop="language" required>
              <el-select
                v-model="formData.language"
                placeholder="选择编程语言"
                :disabled="isEdit"
                class="full-width"
              >
                <el-option label="Python" value="python" />
                <el-option label="JavaScript" value="javascript" />
              </el-select>
            </el-form-item>

            <el-form-item label="描述">
              <el-input
                v-model="formData.description"
                type="textarea"
                :rows="3"
                placeholder="请输入函数描述"
                clearable
              />
            </el-form-item>

            <el-form-item label="启用状态">
              <el-switch v-model="formData.is_active" />
              <span class="form-hint">启用后可在测试用例中调用此函数</span>
            </el-form-item>
          </div>
        </el-tab-pane>

        <!-- 函数代码 -->
        <el-tab-pane name="code">
          <template #label>
            <span class="tab-label"><i class="i-solar-code-bold" /> 函数代码</span>
          </template>
          <div class="tab-content">
            <el-form-item prop="code">
              <CodeEditor
                v-model="formData.code"
                :language="formData.language"
                :min-height="'300px'"
                :max-height="'450px'"
                :show-line-count="true"
              />
            </el-form-item>

            <div v-if="formData.language === 'python'" class="code-hint">
              <i class="i-solar-danger-triangle-bold" />
              <span>代码中必须定义一个与函数名称相同的函数，例如 <code>def random_string():</code></span>
            </div>
          </div>
        </el-tab-pane>

        <!-- 参数配置 -->
        <el-tab-pane name="params">
          <template #label>
            <span class="tab-label">
              <i class="i-solar-list-bold" /> 参数配置
              <el-tag v-if="formData.params?.length" size="small" type="info" class="param-count">
                {{ formData.params.length }}
              </el-tag>
            </span>
          </template>
          <div class="tab-content">
            <div class="params-header">
              <el-button size="small" @click="handleAddParam">
                <i class="i-solar-add-circle-bold mr-1" /> 添加参数
              </el-button>
            </div>

            <div v-if="formData.params && formData.params.length > 0" class="params-list">
              <div
                v-for="(param, index) in formData.params"
                :key="index"
                class="param-item"
              >
                <div class="param-row">
                  <el-input v-model="param.name" placeholder="参数名" class="param-input" />
                  <el-select v-model="param.type" placeholder="类型" class="param-type-select">
                    <el-option label="string" value="string" />
                    <el-option label="int" value="int" />
                    <el-option label="float" value="float" />
                    <el-option label="bool" value="bool" />
                    <el-option label="list" value="list" />
                    <el-option label="dict" value="dict" />
                  </el-select>
                  <el-switch v-model="param.required" active-text="必填" inactive-text="可选" />
                  <el-button type="danger" text @click="handleRemoveParam(index)">
                    <i class="i-solar-trash-bin-trash-linear" />
                  </el-button>
                </div>
                <div class="param-detail">
                  <el-input v-model="param.description" placeholder="参数描述" size="small" />
                  <el-input
                    v-if="!param.required"
                    v-model="param.default"
                    placeholder="默认值"
                    size="small"
                    class="default-input"
                  />
                </div>
              </div>
            </div>
            <el-empty
              v-else
              description="暂无参数，点击上方按钮添加"
              :image-size="60"
              class="params-empty"
            />
          </div>
        </el-tab-pane>

        <!-- 返回值与示例 -->
        <el-tab-pane name="output">
          <template #label>
            <span class="tab-label"><i class="i-solar-back-bold" /> 返回值与示例</span>
          </template>
          <div class="tab-content">
            <el-form-item label="返回类型">
              <el-input
                v-model="formData.return_type"
                placeholder="如：string, int, list, dict"
                clearable
              />
            </el-form-item>

            <el-form-item label="使用示例">
              <CodeEditor
                v-model="formData.example"
                :language="formData.language"
                :min-height="'100px'"
                :max-height="'200px'"
              />
            </el-form-item>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '创建函数' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import CodeEditor from '@/components/common/CodeEditor.vue'
import { environmentApi } from '@/api/environments'
import type {
  GlobalFunction,
  CreateFunctionRequest,
  UpdateFunctionRequest,
} from '@/api/environments'

interface Props {
  modelValue: boolean
  functionData?: GlobalFunction | null
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
const activeTab = ref('basic')

const isEdit = computed(() => !!props.functionData)

const formData = ref<CreateFunctionRequest>({
  name: '',
  display_name: '',
  language: 'python',
  description: '',
  code: '',
  params: [],
  return_type: '',
  example: '',
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入函数名称', trigger: 'blur' },
    { pattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/, message: '只能以字母/下划线开头,只含字母数字下划线', trigger: 'blur' },
  ],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  language: [{ required: true, message: '请选择编程语言', trigger: 'change' }],
  code: [
    { required: true, message: '请输入函数代码', trigger: 'blur' },
    { min: 10, message: '函数代码至少 10 个字符', trigger: 'blur' },
  ],
}

const resetForm = () => {
  formData.value = {
    name: '', display_name: '', language: 'python',
    description: '', code: '', params: [],
    return_type: '', example: '',
  }
  activeTab.value = 'basic'
  formRef.value?.clearValidate()
}

watch(
  () => props.functionData,
  (newData) => {
    if (newData) {
      formData.value = {
        name: newData.name,
        display_name: newData.display_name,
        language: newData.language,
        description: newData.description || '',
        code: newData.code,
        params: newData.params || [],
        return_type: newData.return_type || '',
        example: newData.example || '',
      }
    } else {
      resetForm()
    }
  },
  { immediate: true },
)

const handleAddParam = () => {
  if (!formData.value.params) formData.value.params = []
  formData.value.params.push({
    name: '', type: 'string', description: '', required: false, default: undefined,
  })
}

const handleRemoveParam = (index: number) => { formData.value.params?.splice(index, 1) }

const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }

  submitting.value = true
  try {
    if (isEdit.value && props.functionData) {
      const updateData: UpdateFunctionRequest = {
        display_name: formData.value.display_name,
        description: formData.value.description,
        code: formData.value.code,
        params: formData.value.params,
        return_type: formData.value.return_type,
        example: formData.value.example,
      }
      await environmentApi.updateFunction(props.projectId, props.functionData.id, updateData)
      ElMessage.success('函数更新成功')
    } else {
      await environmentApi.createFunction(props.projectId, formData.value)
      ElMessage.success('函数创建成功')
    }
    emit('success')
    emit('update:modelValue', false)
  } catch (error) {
    console.error('提交函数失败:', error)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => emit('update:modelValue', false)
const handleClosed = () => resetForm()
</script>

<style scoped lang="scss">
.function-form {
  :deep(.el-form-item) { margin-bottom: var(--space-5); }
}

.full-width { width: 100%; }

.form-hint {
  font-size: 12px;
  color: var(--text-placeholder);
  margin-left: var(--space-2);
}

.function-tabs {
  :deep(.el-tabs__header) { margin-bottom: 0; }
  :deep(.el-tabs__item) {
    height: 44px;
    line-height: 44px;
    font-size: 14px;
    padding: 0 20px;
  }
  :deep(.el-tabs__content) {
    max-height: 60vh;
    overflow-y: auto;
  }
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  i { font-size: 16px; }

  .param-count { margin-left: 2px; transform: scale(0.85); }
}

.tab-content {
  padding: var(--space-4) 4px 0;
}

.code-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
  margin-top: 12px;
  background: var(--color-warning-50);
  border: 1px solid var(--color-warning-300);
  border-radius: 6px;
  font-size: 13px;
  color: var(--color-warning-700);

  i { margin-top: 1px; }

  code {
    padding: 2px 8px;
    background: var(--gray-100);
    border-radius: 4px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    color: var(--brand-600);
  }
}

.params-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.params-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.param-item {
  padding: 14px;
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  border-radius: 8px;

  .param-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;

    .param-input { flex: 1; }
    .param-type-select { width: 110px; }
  }

  .param-detail {
    display: flex;
    gap: 10px;

    .default-input { width: 140px; }
  }
}

.params-empty { padding: 30px 0; }

@media (max-width: 768px) {
  .param-item {
    .param-row {
      flex-wrap: wrap;

      .param-input { flex-basis: 100%; margin-bottom: 8px; }
      .param-type-select { width: 100%; }
    }
  }
}
</style>