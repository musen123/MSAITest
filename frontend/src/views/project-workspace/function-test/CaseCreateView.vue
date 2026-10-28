<template>
  <div class="case-create-page">
    <!-- 顶部 -->
    <el-card class="header-card" shadow="never">
      <div class="header-bar">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <div class="header-actions">
          <el-button @click="goBack">取消</el-button>
          <el-button
            v-permission="'test_case:create'"
            type="primary"
            :loading="submitting"
            @click="handleSubmit"
          >
            <el-icon><Check /></el-icon>
            {{ submitting ? '提交中...' : '创建用例' }}
          </el-button>
        </div>
      </div>
      <div class="header-title">
        <h2>新建测试用例</h2>
      </div>
    </el-card>

    <!-- 主体 -->
    <el-form
      ref="formRef"
      :model="form"
      :rules="formRules"
      class="edit-layout"
      label-position="top"
      @submit.prevent
    >
      <!-- 左主区 -->
      <div class="edit-main">
        <el-card class="form-card" shadow="never">
          <el-form-item label="用例标题" prop="title" class="card-form-item">
            <el-input
              v-model="form.title"
              placeholder="输入用例标题..."
              maxlength="200"
              show-word-limit
              size="large"
            />
          </el-form-item>
        </el-card>

        <el-card class="form-card" shadow="never">
          <el-form-item label="前置条件" class="card-form-item">
            <el-input
              v-model="form.preconditions"
              type="textarea"
              :rows="4"
              placeholder="测试前置条件（多条建议每行一条）..."
            />
          </el-form-item>
        </el-card>

        <el-card class="form-card" shadow="never">
          <el-form-item label="测试步骤" class="card-form-item">
            <el-input
              v-model="stepsText"
              type="textarea"
              :rows="8"
              placeholder="详细测试步骤（每步一行，如：&#10;1. 打开登录页&#10;2. 输入账号密码&#10;3. 点击登录按钮）"
            />
            <div class="field-hint">
              <el-icon><InfoFilled /></el-icon>
              每行一个步骤；可在「预期结果」中也每行一条，与步骤一一对应
            </div>
          </el-form-item>
        </el-card>

        <el-card class="form-card" shadow="never">
          <el-form-item label="预期结果" class="card-form-item">
            <el-input
              v-model="expectedText"
              type="textarea"
              :rows="6"
              placeholder="预期结果（每行一条，如：&#10;1. 跳转到主页&#10;2. 显示欢迎信息）"
            />
          </el-form-item>
        </el-card>
      </div>

      <!-- 右侧栏 -->
      <div class="edit-side">
        <el-card class="side-card" shadow="never">
          <div class="side-label">用例编号</div>
          <el-form-item class="card-form-item">
            <el-input
              v-model="form.code"
              placeholder="留空将自动生成"
              size="large"
            />
            <div class="field-hint">留空时后端自动按 TC-项目id-序号 生成</div>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">关联需求</div>
          <el-form-item class="card-form-item">
            <el-select
              v-model="form.requirement_id"
              placeholder="选择关联需求"
              clearable
              filterable
              size="large"
              style="width: 100%"
            >
              <el-option
                v-for="r in requirementOptions"
                :key="r.id"
                :label="`${r.code || r.id} · ${r.title}`"
                :value="r.id"
              />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">优先级</div>
          <el-form-item class="card-form-item">
            <el-select v-model="form.priority" size="large" style="width: 100%">
              <el-option label="P0 紧急" value="urgent" />
              <el-option label="P1 高" value="high" />
              <el-option label="P2 中" value="medium" />
              <el-option label="P3 低" value="low" />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">用例类型</div>
          <el-form-item class="card-form-item">
            <el-select v-model="form.case_type" size="large" style="width: 100%">
              <el-option label="功能测试" value="functional" />
              <el-option label="冒烟测试" value="smoke" />
              <el-option label="回归测试" value="regression" />
              <el-option label="探索性测试" value="exploratory" />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">验证层级</div>
          <el-form-item class="card-form-item">
            <el-select
              v-model="form.validation_level"
              size="large"
              style="width: 100%"
            >
              <el-option label="系统测试" value="system" />
              <el-option label="集成测试" value="integration" />
              <el-option label="单元测试" value="unit" />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">标签</div>
          <el-form-item class="card-form-item">
            <el-select
              v-model="form.tags"
              multiple
              filterable
              allow-create
              default-first-option
              :reserve-keyword="false"
              placeholder="输入回车创建标签"
              style="width: 100%"
            >
              <el-option v-for="t in builtinTags" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </el-card>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { ArrowLeft, Check, InfoFilled } from '@element-plus/icons-vue'
import { funcTestCaseApi, funcRequirementApi } from '@/api/funcTest'
import type {
  CasePriority,
  CaseType,
  ValidationLevel,
  CaseStep,
  FuncRequirement,
} from '@/types/func-test'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ---------- 表单 ----------
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  title: '',
  code: '',
  requirement_id: undefined as number | undefined,
  priority: 'medium' as CasePriority,
  case_type: 'functional' as CaseType,
  validation_level: 'system' as ValidationLevel,
  preconditions: '',
  tags: [] as string[],
})

// 步骤/预期结果用 textarea 输入，按行解析
const stepsText = ref('')
const expectedText = ref('')

const formRules: FormRules = {
  title: [{ required: true, message: '请输入用例标题', trigger: 'blur' }],
}

const builtinTags = ['正向', '反向', '边界值', '异常', '权限', '性能']

// ---------- 关联需求 ----------
const requirementOptions = ref<FuncRequirement[]>([])

async function loadRequirements() {
  try {
    const res = await funcRequirementApi.list(projectId.value, {
      page: 1,
      page_size: 200,
    })
    requirementOptions.value = res.data.items
  } catch (err) {
    console.error(err)
  }
}

// ---------- 从 URL query 预填关联需求 ----------
onMounted(async () => {
  await loadRequirements()
  const reqIdQuery = route.query.reqId
  if (reqIdQuery) form.requirement_id = Number(reqIdQuery)
})

// ---------- 提交 ----------
function parseSteps(text: string): CaseStep[] {
  const stepLines = text
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  const expectedLines = expectedText.value
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  // 去掉行首的序号（"1." "1、" "(1)" 等）
  const stripNo = (line: string) =>
    line.replace(/^[（(]?\d+[）)\.、\s]+/, '').trim()

  return stepLines.map((line, i) => ({
    step_no: i + 1,
    action: stripNo(line),
    expected: expectedLines[i] ? stripNo(expectedLines[i]) : '',
  }))
}

function parseExpectedRest(steps: CaseStep[]): string[] {
  // 预期结果数量 > 步骤数量时，把多余的预期作为独立列表
  const expectedLines = expectedText.value
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  const stripNo = (line: string) =>
    line.replace(/^[（(]?\d+[）)\.、\s]+/, '').trim()
  return expectedLines.map(stripNo)
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const steps = parseSteps(stepsText.value)
    const expected = parseExpectedRest(steps)

    const res = await funcTestCaseApi.create(projectId.value, {
      title: form.title,
      code: form.code || undefined,
      requirement_id: form.requirement_id,
      priority: form.priority,
      case_type: form.case_type,
      validation_level: form.validation_level,
      preconditions: form.preconditions || undefined,
      steps: steps.length ? steps : undefined,
      expected_result: expected.length ? expected : undefined,
      tags: form.tags.length ? form.tags : undefined,
    })
    ElMessage.success('用例创建成功')
    router.push({
      name: 'FuncTestCaseDetail',
      params: { id: projectId.value, caseId: res.data.id },
    })
  } catch (err) {
    console.error(err)
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'FuncTestCases', params: { id: projectId.value } })
}
</script>

<style scoped>
.case-create-page {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card {
  border-radius: 8px;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.header-title {
  margin-top: 12px;
}

.header-title h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}

.edit-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  align-items: start;
}

.edit-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.edit-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 16px;
}

.form-card,
.side-card {
  border-radius: 8px;
}

.card-form-item {
  margin-bottom: 0;
}

.side-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
}

.field-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 1024px) {
  .edit-layout {
    grid-template-columns: 1fr;
  }
  .edit-side {
    position: static;
  }
}
</style>
