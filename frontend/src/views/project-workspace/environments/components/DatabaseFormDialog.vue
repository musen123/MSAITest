<template>
  <el-dialog
    :model-value="modelValue"
    width="640px"
    :close-on-click-modal="false"
    class="app-dialog database-form-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">{{ isEdit ? '编辑数据库连接' : '新建数据库连接' }}</h3>
        <p class="dialog-desc">配置测试用的数据库连接，支持 MySQL、PostgreSQL、Redis 等</p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      class="database-form"
    >
      <el-form-item label="连接名称" prop="name" required>
        <el-input
          v-model="formData.name"
          placeholder="例如：生产环境MySQL"
          maxlength="100"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item label="数据库类型" prop="db_type" required>
        <el-select
          v-model="formData.db_type"
          placeholder="选择数据库类型"
          class="full-width"
          @change="handleDbTypeChange"
        >
          <el-option label="MySQL" value="MySQL" />
          <el-option label="PostgreSQL" value="PostgreSQL" />
          <el-option label="Oracle" value="Oracle" />
          <el-option label="SQLServer" value="SQLServer" />
          <el-option label="MongoDB" value="MongoDB" />
          <el-option label="Redis" value="Redis" />
        </el-select>
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="16">
          <el-form-item label="主机地址" prop="host" required>
            <el-input v-model="formData.host" placeholder="localhost 或 IP 地址" clearable />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="端口" prop="port" required>
            <el-input v-model.number="formData.port" type="number" placeholder="端口号" clearable />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="数据库名" prop="database" required>
        <el-input v-model="formData.database" placeholder="数据库名称" clearable />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="用户名" prop="username" required>
            <el-input v-model="formData.username" placeholder="数据库用户名" clearable />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="密码" prop="password" required>
            <el-input
              v-model="formData.password"
              type="password"
              placeholder="数据库密码"
              show-password
              clearable
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="字符集">
        <el-select v-model="formData.charset" placeholder="选择字符集（可选）" clearable class="full-width">
          <el-option label="UTF-8" value="utf8" />
          <el-option label="UTF-8MB4" value="utf8mb4" />
          <el-option label="GBK" value="gbk" />
          <el-option label="Latin1" value="latin1" />
        </el-select>
      </el-form-item>

      <el-form-item label="额外连接参数">
        <el-input
          v-model="connectionParamsJson"
          type="textarea"
          :rows="4"
          placeholder='{"pool_size": 5, "timeout": 30}'
          class="json-editor"
          @blur="handleConnectionParamsBlur"
        />
        <div class="form-tip">
          <i class="i-solar-question-circle-linear" />
          JSON 格式的额外连接参数，用于配置连接池、超时时间等高级选项
        </div>
      </el-form-item>

      <el-form-item label="允许写操作">
        <el-switch v-model="formData.allow_write" />
        <div class="form-tip form-tip-warn">
          <i class="i-solar-danger-triangle-linear" />
          开启后，脚本与用例 SQL 节点里的写语句（DELETE / UPDATE / INSERT）才能在此连接执行；默认关闭。请仅对测试库开启，切勿指向生产库。
        </div>
      </el-form-item>

      <!-- 测试结果 -->
      <Transition name="result-fade">
        <div v-if="testResult" class="test-result-card" :class="testResult.status === 'connected' ? 'success' : 'error'">
          <i v-if="testResult.status === 'connected'" class="i-solar-check-circle-bold result-icon" />
          <i v-else class="i-solar-close-circle-bold result-icon" />
          <div class="result-body">
            <div class="result-title">{{ testResult.status === 'connected' ? '连接成功' : '连接失败' }}</div>
            <div class="result-message">{{ testResult.message }}</div>
            <div v-if="testResult.status === 'connected' && testResult.response_time" class="result-meta">
              响应时间：{{ testResult.response_time }}ms
            </div>
            <div v-if="testResult.error" class="result-error">{{ testResult.error }}</div>
          </div>
        </div>
      </Transition>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button :loading="testing" @click="handleTest">
        <i class="i-solar-link-circle-bold mr-1" />
        测试连接
      </el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        <i v-if="!submitting" class="i-solar-check-circle-bold mr-1" />
        {{ isEdit ? '保存' : '创建连接' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type { DatabaseConnection, DatabaseType } from '@/api/environments'

interface Props {
  modelValue: boolean
  database?: DatabaseConnection | null
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
const testing = ref(false)
const testResult = ref<{
  status: string
  message: string
  response_time?: number
  error?: string
} | null>(null)

const connectionParamsJson = ref('')
const isEdit = computed(() => !!props.database)

const defaultPorts: Record<DatabaseType, number> = {
  MySQL: 3306, PostgreSQL: 5432, Oracle: 1521,
  SQLServer: 1433, MongoDB: 27017, Redis: 6379,
}

const formData = ref({
  name: '',
  db_type: 'MySQL' as DatabaseType,
  host: 'localhost',
  port: 3306,
  database: '',
  username: '',
  password: '',
  charset: '',
  connection_params: undefined as Record<string, any> | undefined,
  allow_write: false,
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入连接名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' },
  ],
  db_type: [{ required: true, message: '请选择数据库类型', trigger: 'change' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  port: [
    { required: true, message: '请输入端口号', trigger: 'blur' },
    { type: 'number', min: 1, max: 65535, message: '端口号在 1-65535 之间', trigger: 'blur' },
  ],
  database: [{ required: true, message: '请输入数据库名', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, message: '密码不能为空', trigger: 'blur' },
  ],
}

const resetForm = () => {
  formData.value = {
    name: '', db_type: 'MySQL', host: 'localhost', port: 3306,
    database: '', username: '', password: '', charset: '',
    connection_params: undefined, allow_write: false,
  }
  connectionParamsJson.value = ''
  testResult.value = null
  formRef.value?.clearValidate()
}

watch(
  () => props.database,
  (db) => {
    if (db) {
      formData.value = {
        name: db.name,
        db_type: db.db_type,
        host: db.host,
        port: db.port,
        database: db.database,
        username: db.username,
        password: db.password || '',
        charset: db.charset || '',
        connection_params: db.connection_params,
        allow_write: db.allow_write ?? false,
      }
      connectionParamsJson.value = db.connection_params
        ? JSON.stringify(db.connection_params, null, 2)
        : ''
    } else {
      resetForm()
    }
  },
  { immediate: true },
)

const handleDbTypeChange = (dbType: DatabaseType) => { formData.value.port = defaultPorts[dbType] }

const handleConnectionParamsBlur = () => {
  if (!connectionParamsJson.value.trim()) {
    formData.value.connection_params = undefined
    return
  }
  try {
    formData.value.connection_params = JSON.parse(connectionParamsJson.value)
  } catch {
    ElMessage.warning('连接参数 JSON 格式不正确')
    connectionParamsJson.value = formData.value.connection_params
      ? JSON.stringify(formData.value.connection_params, null, 2)
      : ''
  }
}

const handleTest = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  testing.value = true
  testResult.value = null

  try {
    if (!isEdit.value) {
      ElMessage.warning('请先保存后再测试连接')
      return
    }
    const res = await environmentApi.testDatabase(props.projectId, props.database!.id)
    testResult.value = res.data
  } catch (error) {
    testResult.value = {
      status: 'disconnected',
      message: '测试连接失败',
      error: error instanceof Error ? error.message : '未知错误',
    }
  } finally {
    testing.value = false
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (isEdit.value && props.database) {
        await environmentApi.updateDatabase(props.projectId, props.database.id, {
          name: formData.value.name,
          host: formData.value.host,
          port: formData.value.port,
          database: formData.value.database,
          username: formData.value.username,
          password: formData.value.password || undefined,
          charset: formData.value.charset || undefined,
          connection_params: formData.value.connection_params,
          allow_write: formData.value.allow_write,
        })
        ElMessage.success('更新成功')
      } else {
        await environmentApi.createDatabase(props.projectId, {
          name: formData.value.name,
          db_type: formData.value.db_type,
          host: formData.value.host,
          port: formData.value.port,
          database: formData.value.database,
          username: formData.value.username,
          password: formData.value.password,
          charset: formData.value.charset || undefined,
          connection_params: formData.value.connection_params,
          allow_write: formData.value.allow_write,
        })
        ElMessage.success('创建成功')
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
.database-form {
  :deep(.el-form-item) { margin-bottom: var(--space-5); }
}

.full-width { width: 100%; }

.json-editor :deep(.el-textarea__inner) { font-family: 'Consolas', 'Monaco', monospace; }

.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-placeholder);
  line-height: 1.6;
  display: flex;
  align-items: center;
  gap: 4px;

  i { font-size: 14px; }
}

.form-tip-warn {
  color: var(--color-warning-600);
}

.test-result-card {
  display: flex;
  gap: var(--space-3);
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid;
  margin-top: var(--space-2);

  .result-icon { font-size: 22px; flex-shrink: 0; }

  &.success {
    background: var(--color-success-50);
    border-color: var(--color-success-300);
    color: var(--color-success-700);
    .result-icon { color: var(--color-success-600); }
  }
  &.error {
    background: var(--color-danger-50);
    border-color: var(--color-danger-300);
    color: var(--color-danger-700);
    .result-icon { color: var(--color-danger-600); }
  }
}

.result-body {
  flex: 1;
  min-width: 0;
}

.result-title { font-size: 14px; font-weight: var(--font-weight-semibold); }
.result-message { font-size: 13px; margin-top: 2px; }
.result-meta, .result-error { font-size: 12px; margin-top: 4px; opacity: 0.85; }

.result-fade-enter-active, .result-fade-leave-active { transition: all 0.2s ease; }
.result-fade-enter-from, .result-fade-leave-to { opacity: 0; transform: translateY(-4px); }
</style>