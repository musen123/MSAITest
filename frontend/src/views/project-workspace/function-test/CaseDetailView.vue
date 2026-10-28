<template>
  <div class="case-detail-page" v-loading="loading">
    <!-- 头部 -->
    <el-card class="header-card" shadow="never">
      <div class="header-bar">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <div class="header-actions">
          <template v-if="!editing">
            
            <el-button v-permission="'test_case:delete'" @click="confirmDelete">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
            <el-button v-permission="'test_case:edit'" type="primary" @click="enterEdit">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
          </template>
          <template v-else>
            <el-button @click="cancelEdit">取消</el-button>
            <el-button
              v-permission="'test_case:edit'"
              type="primary"
              :loading="saving"
              @click="handleSave"
            >
              <el-icon><Check /></el-icon>
              {{ saving ? '保存中...' : '保存修改' }}
            </el-button>
          </template>
        </div>
      </div>

      <div v-if="caseDetail && !editing" class="case-header">
        <div class="title-row">
          <span class="case-code">{{ caseDetail.code || `#${caseDetail.id}` }}</span>
          <el-tag :type="priorityTag(caseDetail.priority)" size="small">
            {{ priorityLabel(caseDetail.priority) }}
          </el-tag>
          <el-tag :type="statusTag(caseDetail.status)" size="small">
            {{ statusLabel(caseDetail.status) }}
          </el-tag>
          <el-tag
            v-if="caseDetail.source === 'ai_generated'"
            type="warning"
            size="small"
            effect="plain"
          >
            AI 生成
          </el-tag>
        </div>
        <h1 class="case-title">{{ caseDetail.title }}</h1>
        <div class="meta-row">
          <span class="meta-item">
            <el-icon><Clock /></el-icon>
            创建于 {{ formatDate(caseDetail.created_at) }}
          </span>
          <span class="meta-item">
            <el-icon><Calendar /></el-icon>
            更新于 {{ formatDate(caseDetail.updated_at) }}
          </span>
          <span v-if="caseDetail.requirement_id" class="meta-item">
            <el-icon><Link /></el-icon>
            <el-link
              type="primary"
              @click="goRequirement(caseDetail.requirement_id)"
            >
              {{ linkedRequirementLabel }}
            </el-link>
          </span>
        </div>
      </div>
    </el-card>

    <!-- ============ 查看模式 ============ -->
    <template v-if="caseDetail && !editing">
      <el-tabs v-model="activeTab" class="tabs-card">
        <!-- Tab: 用例内容 -->
        <el-tab-pane name="content">
          <template #label>
            <span class="tab-label">
              <el-icon><Document /></el-icon>
              用例内容
            </span>
          </template>

          <!-- 概览信息 -->
          <el-card shadow="never" class="overview-card">
            <el-descriptions :column="4" border size="small">
              <el-descriptions-item label="用例编号">
                <span class="mono">{{ caseDetail.code || '—' }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="优先级">
                {{ priorityLabel(caseDetail.priority) }}
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                {{ statusLabel(caseDetail.status) }}
              </el-descriptions-item>
              <el-descriptions-item label="类型">
                {{ caseTypeLabel(caseDetail.case_type) }}
              </el-descriptions-item>
              <el-descriptions-item label="验证层级">
                {{ validationLevelLabel(caseDetail.validation_level) }}
              </el-descriptions-item>
              <el-descriptions-item label="来源">
                {{ caseDetail.source === 'ai_generated' ? 'AI 生成' : '手工创建' }}
              </el-descriptions-item>
              <el-descriptions-item label="UI 自动化">
                <el-tag
                  v-if="caseDetail.ui_automatable === true"
                  type="success"
                  size="small"
                >适合</el-tag>
                <el-tag
                  v-else-if="caseDetail.ui_automatable === false"
                  type="danger"
                  size="small"
                  title="属于业务或服务层验证"
                >不适合</el-tag>
                <span v-else class="text-muted">未评估</span>
              </el-descriptions-item>
              <el-descriptions-item label="标签" :span="2">
                <el-tag
                  v-for="tag in caseDetail.tags || []"
                  :key="tag"
                  size="small"
                  effect="plain"
                  class="tag-pill"
                >
                  {{ tag }}
                </el-tag>
                <span v-if="!caseDetail.tags?.length" class="text-muted">—</span>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <!-- AI 评审信息 -->
          <el-card
            v-if="caseDetail.review_info"
            shadow="never"
            class="ai-review-card"
          >
            <div class="block-title">
              <el-icon><MagicStick /></el-icon>
              AI 评审结果
              <el-tag
                :type="caseDetail.review_info.review_result === '通过' ? 'success' : 'danger'"
                size="small"
              >
                {{ caseDetail.review_info.review_result }}
              </el-tag>
            </div>
            <div v-if="caseDetail.review_info.review_decs" class="review-decs">
              {{ caseDetail.review_info.review_decs }}
            </div>
          </el-card>

          <!-- 人工评审信息 -->
          <el-card
            v-if="caseDetail.reviewed_at"
            shadow="never"
            class="ai-review-card"
          >
            <div class="block-title">
              <el-icon><CircleCheck /></el-icon>
              人工评审
              <el-tag
                :type="caseDetail.status === 'reviewed' ? 'success' : 'danger'"
                size="small"
              >
                {{ caseDetail.status === 'reviewed' ? '已通过' : '已驳回' }}
              </el-tag>
              <span class="review-meta">
                {{ formatDate(caseDetail.reviewed_at) }}
              </span>
            </div>
            <div v-if="caseDetail.review_comment" class="review-decs">
              {{ caseDetail.review_comment }}
            </div>
          </el-card>

          <!-- 前置条件 -->
          <el-card shadow="never" class="block-card">
            <div class="block-head">
              <div class="block-title">
                <el-icon><Select /></el-icon>
                前置条件
              </div>
              <el-button
                v-if="caseDetail.preconditions"
                link
                size="small"
                @click="copyText(caseDetail.preconditions, '前置条件')"
              >
                <el-icon><CopyDocument /></el-icon>
                复制
              </el-button>
            </div>
            <div v-if="caseDetail.preconditions" class="block-content preline">
              {{ caseDetail.preconditions }}
            </div>
            <el-empty v-else description="暂无前置条件" :image-size="50" />
          </el-card>

          <!-- 测试步骤 ↔ 预期结果 左右对照 -->
          <el-card shadow="never" class="steps-card">
            <div class="block-head">
              <div class="block-title">
                <el-icon><Aim /></el-icon>
                测试步骤
                <span class="muted">与</span>
                预期结果
              </div>
              <el-button
                v-if="caseDetail.steps?.length || caseDetail.expected_result?.length"
                link
                size="small"
                @click="copyStepsAndExpected"
              >
                <el-icon><CopyDocument /></el-icon>
                复制
              </el-button>
            </div>

            <!-- 都为空 -->
            <el-empty
              v-if="!caseDetail.steps?.length && !caseDetail.expected_result?.length"
              description="暂无测试步骤"
              :image-size="50"
            />

            <!-- 左右对照（推荐展示） -->
            <div v-else class="steps-pair">
              <!-- 左：步骤 -->
              <div class="steps-col">
                <div class="col-header">
                  <el-icon><List /></el-icon>
                  执行步骤
                  <span class="count">{{ caseDetail.steps?.length || 0 }}</span>
                </div>
                <ol v-if="caseDetail.steps?.length" class="step-list">
                  <li
                    v-for="step in caseDetail.steps"
                    :key="step.step_no"
                    class="step-item"
                  >
                    <span class="step-no">{{ step.step_no }}</span>
                    <span class="step-text">{{ step.action }}</span>
                  </li>
                </ol>
                <div v-else class="empty-col">—</div>
              </div>

              <!-- 中：箭头 -->
              <div class="steps-arrow">
                <el-icon><ArrowRight /></el-icon>
              </div>

              <!-- 右：预期 -->
              <div class="steps-col">
                <div class="col-header">
                  <el-icon><CircleCheck /></el-icon>
                  预期结果
                  <span class="count">{{ effectiveExpected.length }}</span>
                </div>
                <ol v-if="effectiveExpected.length" class="step-list">
                  <li
                    v-for="(expect, i) in effectiveExpected"
                    :key="i"
                    class="step-item expected"
                  >
                    <span class="step-no expect">{{ i + 1 }}</span>
                    <span class="step-text">{{ expect }}</span>
                  </li>
                </ol>
                <div v-else class="empty-col">—</div>
              </div>
            </div>
          </el-card>

          <!-- 测试数据 -->
          <el-card
            v-if="caseDetail.test_data && Object.keys(caseDetail.test_data).length"
            shadow="never"
            class="block-card"
          >
            <div class="block-head">
              <div class="block-title">
                <el-icon><DataLine /></el-icon>
                测试数据
              </div>
            </div>
            <pre class="json-block">{{ formatJson(caseDetail.test_data) }}</pre>
          </el-card>
        </el-tab-pane>

        <!-- Tab: 执行历史 -->
        <el-tab-pane name="executions">
          <template #label>
            <span class="tab-label">
              <el-icon><Clock /></el-icon>
              执行历史
              <el-badge
                v-if="executions.length"
                :value="executionTotal"
                :max="99"
                class="tab-badge"
              />
            </span>
          </template>

          <el-card shadow="never" class="executions-card">
            <div class="executions-toolbar">
              <el-button v-permission="'test_case:execute'" type="primary" @click="openExecuteDialog">
                <el-icon><CirclePlus /></el-icon>
                提交执行结果
              </el-button>
            </div>

            <el-table
              v-loading="execLoading"
              :data="executions"
              stripe
              size="small"
              empty-text="暂无执行记录"
            >
              <el-table-column label="执行结果" width="120">
                <template #default="{ row }">
                  <el-tag :type="resultTag(row.execute_result)" size="small">
                    {{ resultLabel(row.execute_result) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="环境" width="140">
                <template #default="{ row }">
                  <span v-if="row.environment_id">#{{ row.environment_id }}</span>
                  <span v-else class="text-muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="100">
                <template #default="{ row }">
                  <span v-if="row.duration">{{ row.duration }} 秒</span>
                  <span v-else class="text-muted">—</span>
                </template>
              </el-table-column>
              <el-table-column prop="notes" label="备注" min-width="200" show-overflow-tooltip>
                <template #default="{ row }">
                  <span v-if="row.notes">{{ row.notes }}</span>
                  <span v-else class="text-muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="执行人" width="100">
                <template #default="{ row }">
                  #{{ row.executor_id }}
                </template>
              </el-table-column>
              <el-table-column label="执行时间" width="160">
                <template #default="{ row }">
                  {{ formatDate(row.executed_at) }}
                </template>
              </el-table-column>
            </el-table>

            <div v-if="executionTotal > execQuery.page_size" class="pagination-wrap">
              <el-pagination
                v-model:current-page="execQuery.page"
                v-model:page-size="execQuery.page_size"
                :page-sizes="[10, 20, 50]"
                :total="executionTotal"
                layout="total, sizes, prev, pager, next"
                @size-change="loadExecutions"
                @current-change="loadExecutions"
              />
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- ============ 编辑模式（左主右栏） ============ -->
    <el-form
      v-if="caseDetail && editing"
      ref="editFormRef"
      :model="editForm"
      :rules="editRules"
      class="edit-layout"
      label-position="top"
      @submit.prevent
    >
      <div class="edit-main">
        <el-card class="form-card" shadow="never">
          <el-form-item label="用例标题" prop="title" class="card-form-item">
            <el-input
              v-model="editForm.title"
              maxlength="200"
              show-word-limit
              size="large"
            />
          </el-form-item>
        </el-card>

        <el-card class="form-card" shadow="never">
          <el-form-item label="前置条件" class="card-form-item">
            <el-input
              v-model="editForm.preconditions"
              type="textarea"
              :rows="4"
              placeholder="测试前置条件..."
            />
          </el-form-item>
        </el-card>

        <el-card class="form-card" shadow="never">
          <el-form-item label="测试步骤" class="card-form-item">
            <el-input
              v-model="editStepsText"
              type="textarea"
              :rows="8"
              placeholder="每行一个步骤..."
            />
          </el-form-item>
        </el-card>

        <el-card class="form-card" shadow="never">
          <el-form-item label="预期结果" class="card-form-item">
            <el-input
              v-model="editExpectedText"
              type="textarea"
              :rows="6"
              placeholder="每行一条..."
            />
          </el-form-item>
        </el-card>
      </div>

      <div class="edit-side">
        <el-card class="side-card" shadow="never">
          <div class="side-label">用例编号</div>
          <div class="readonly-field">
            <el-icon><Document /></el-icon>
            <span class="mono">{{ caseDetail.code || '—' }}</span>
          </div>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">关联需求</div>
          <el-form-item class="card-form-item">
            <el-select
              v-model="editForm.requirement_id"
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
            <el-select v-model="editForm.priority" size="large" style="width: 100%">
              <el-option label="P0 紧急" value="urgent" />
              <el-option label="P1 高" value="high" />
              <el-option label="P2 中" value="medium" />
              <el-option label="P3 低" value="low" />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">状态</div>
          <el-form-item class="card-form-item">
            <el-select v-model="editForm.status" size="large" style="width: 100%">
              <el-option label="草稿" value="draft" />
              <el-option label="待审核" value="pending_review" />
              <el-option label="已审核" value="reviewed" />
              <el-option label="已废弃" value="deprecated" />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">用例类型</div>
          <el-form-item class="card-form-item">
            <el-select v-model="editForm.case_type" size="large" style="width: 100%">
              <el-option label="功能测试" value="functional" />
              <el-option label="冒烟测试" value="smoke" />
              <el-option label="回归测试" value="regression" />
              <el-option label="探索性测试" value="exploratory" />
            </el-select>
          </el-form-item>
        </el-card>

        <el-card class="side-card" shadow="never">
          <div class="side-label">标签</div>
          <el-form-item class="card-form-item">
            <el-select
              v-model="editForm.tags"
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

    <!-- 提交执行结果对话框 -->
    <el-dialog
      v-model="execDialog.visible"
      title="提交执行结果"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="执行结果">
          <el-radio-group v-model="execDialog.result">
            <el-radio value="passed">
              <el-tag type="success" size="small">通过</el-tag>
            </el-radio>
            <el-radio value="failed">
              <el-tag type="danger" size="small">失败</el-tag>
            </el-radio>
            <el-radio value="blocked">
              <el-tag type="warning" size="small">阻塞</el-tag>
            </el-radio>
            <el-radio value="skipped">
              <el-tag type="info" size="small">跳过</el-tag>
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="耗时（秒）">
          <el-input-number
            v-model="execDialog.duration"
            :min="0"
            placeholder="可选"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="execDialog.notes"
            type="textarea"
            :rows="3"
            placeholder="失败原因 / 缺陷链接 / 备注..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="execDialog.visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="execDialog.submitting"
          @click="submitExecution"
        >
          确认提交
        </el-button>
      </template>
    </el-dialog>

    
  </div>
</template>

<script setup lang="ts">import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useClipboard } from '@vueuse/core';
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, } from 'element-plus';
import { ArrowLeft, ArrowRight, Edit, Check, Delete, Clock, Calendar, Link, Document, Select, Aim, List, CircleCheck, CopyDocument, MagicStick, DataLine, CirclePlus, } from '@element-plus/icons-vue';
import { funcTestCaseApi, funcRequirementApi, } from '@/api/funcTest';
import type { FuncTestCase, FuncCaseExecution, FuncRequirement, CasePriority, CaseType, CaseStatus, ValidationLevel, CaseStep, CaseExecuteResult, } from '@/types/func-test';
import { formatDate } from '@/utils/format';
const route = useRoute();
const router = useRouter();
const projectId = computed(() => Number(route.params.id));
const caseId = computed(() => Number(route.params.caseId));
const builtinTags = ['正向', '反向', '边界值', '异常', '权限', '性能'];
// ---------- 详情数据 ----------
const loading = ref(false);
const saving = ref(false);
const caseDetail = ref<FuncTestCase | null>(null);
const activeTab = ref<'content' | 'executions'>('content');
const requirementOptions = ref<FuncRequirement[]>([]);
const linkedRequirementLabel = computed(() => {
    if (!caseDetail.value?.requirement_id)
        return '';
    const r = requirementOptions.value.find((r) => r.id === caseDetail.value!.requirement_id);
    return r
        ? `${r.code || r.id} · ${r.title}`
        : `需求 #${caseDetail.value.requirement_id}（已删除）`;
});
/**
 * 实际有效的预期结果：
 * - 优先使用独立的 expected_result 字段
 * - 否则从 steps 中提取 expected
 */
const effectiveExpected = computed<string[]>(() => {
    if (!caseDetail.value)
        return [];
    if (caseDetail.value.expected_result?.length) {
        return caseDetail.value.expected_result.map(String);
    }
    if (caseDetail.value.steps?.length) {
        return caseDetail.value.steps
            .map((s) => s.expected || '')
            .filter((v) => v.length > 0);
    }
    return [];
});
async function loadDetail() {
    loading.value = true;
    try {
        const res = await funcTestCaseApi.detail(projectId.value, caseId.value);
        caseDetail.value = res.data;
    }
    catch (err) {
        console.error(err);
    }
    finally {
        loading.value = false;
    }
}
async function loadRequirements() {
    try {
        const res = await funcRequirementApi.list(projectId.value, {
            page: 1,
            page_size: 200,
        });
        requirementOptions.value = res.data.items;
    }
    catch (err) {
        console.error(err);
    }
}
// ---------- 编辑模式 ----------
const editing = ref(false);
const editFormRef = ref<FormInstance>();
const editForm = reactive({
    title: '',
    preconditions: '',
    priority: 'medium' as CasePriority,
    case_type: 'functional' as CaseType,
    validation_level: 'system' as ValidationLevel,
    status: 'draft' as CaseStatus,
    requirement_id: undefined as number | undefined,
    tags: [] as string[],
});
const editStepsText = ref('');
const editExpectedText = ref('');
const editRules: FormRules = {
    title: [{ required: true, message: '请输入用例标题', trigger: 'blur' }],
};
function enterEdit() {
    if (!caseDetail.value)
        return;
    editForm.title = caseDetail.value.title;
    editForm.preconditions = caseDetail.value.preconditions || '';
    editForm.priority = caseDetail.value.priority;
    editForm.case_type = caseDetail.value.case_type;
    editForm.validation_level = caseDetail.value.validation_level;
    editForm.status = caseDetail.value.status;
    editForm.requirement_id = caseDetail.value.requirement_id || undefined;
    editForm.tags = [...(caseDetail.value.tags || [])];
    editStepsText.value = (caseDetail.value.steps || [])
        .map((s) => `${s.step_no}. ${s.action}`)
        .join('\n');
    editExpectedText.value = effectiveExpected.value
        .map((v, i) => `${i + 1}. ${v}`)
        .join('\n');
    editing.value = true;
}
function cancelEdit() {
    editing.value = false;
}
function parseSteps(stepsText: string, expectedText: string): {
    steps: CaseStep[];
    expected: string[];
} {
    const stripNo = (line: string) => line.replace(/^[（(]?\d+[）)\.、\s]+/, '').trim();
    const stepLines = stepsText
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0);
    const expectedLines = expectedText
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0);
    const steps: CaseStep[] = stepLines.map((line, i) => ({
        step_no: i + 1,
        action: stripNo(line),
        expected: expectedLines[i] ? stripNo(expectedLines[i]) : '',
    }));
    const expected = expectedLines.map(stripNo);
    return { steps, expected };
}
async function handleSave() {
    if (!editFormRef.value)
        return;
    try {
        await editFormRef.value.validate();
    }
    catch {
        return;
    }
    saving.value = true;
    try {
        const { steps, expected } = parseSteps(editStepsText.value, editExpectedText.value);
        await funcTestCaseApi.update(projectId.value, caseId.value, {
            title: editForm.title,
            preconditions: editForm.preconditions,
            priority: editForm.priority,
            case_type: editForm.case_type,
            validation_level: editForm.validation_level,
            status: editForm.status,
            requirement_id: editForm.requirement_id,
            tags: editForm.tags,
            steps: steps.length ? steps : undefined,
            expected_result: expected.length ? expected : undefined,
        });
        ElMessage.success('保存成功');
        editing.value = false;
        await loadDetail();
    }
    catch (err) {
        console.error(err);
    }
    finally {
        saving.value = false;
    }
}
// ---------- 删除 ----------
async function confirmDelete() {
    if (!caseDetail.value)
        return;
    try {
        await ElMessageBox.confirm(`确定要删除用例「${caseDetail.value.title}」吗？`, '提示', { type: 'warning' });
        await funcTestCaseApi.remove(projectId.value, caseId.value);
        ElMessage.success('删除成功');
        goBack();
    }
    catch {
        // 取消
    }
}
// ---------- 复制 ----------
const { copy } = useClipboard({ legacy: true });
async function copyText(text: string, label: string) {
    await copy(text);
    ElMessage.success(`${label}已复制`);
}
async function copyStepsAndExpected() {
    if (!caseDetail.value)
        return;
    const lines: string[] = [];
    const steps = caseDetail.value.steps || [];
    const expected = effectiveExpected.value;
    if (steps.length) {
        lines.push('【执行步骤】');
        steps.forEach((s) => lines.push(`${s.step_no}. ${s.action}`));
    }
    if (expected.length) {
        if (lines.length)
            lines.push('');
        lines.push('【预期结果】');
        expected.forEach((v, i) => lines.push(`${i + 1}. ${v}`));
    }
    await copy(lines.join('\n'));
    ElMessage.success('已复制步骤与预期结果');
}
// ---------- 执行历史 ----------
const executions = ref<FuncCaseExecution[]>([]);
const executionTotal = ref(0);
const execLoading = ref(false);
const execQuery = reactive({ page: 1, page_size: 20 });
async function loadExecutions() {
    execLoading.value = true;
    try {
        const res = await funcTestCaseApi.listExecutions(projectId.value, caseId.value, execQuery);
        executions.value = res.data.items;
        executionTotal.value = res.data.total;
    }
    catch (err) {
        console.error(err);
    }
    finally {
        execLoading.value = false;
    }
}
const execDialog = reactive({
    visible: false,
    submitting: false,
    result: 'passed' as CaseExecuteResult,
    duration: undefined as number | undefined,
    notes: '',
});
function openExecuteDialog() {
    execDialog.result = 'passed';
    execDialog.duration = undefined;
    execDialog.notes = '';
    execDialog.visible = true;
}
async function submitExecution() {
    execDialog.submitting = true;
    try {
        await funcTestCaseApi.submitExecution(projectId.value, caseId.value, {
            execute_result: execDialog.result,
            duration: execDialog.duration,
            notes: execDialog.notes || undefined,
        });
        ElMessage.success('已记录执行结果');
        execDialog.visible = false;
        await loadExecutions();
    }
    catch (err) {
        console.error(err);
    }
    finally {
        execDialog.submitting = false;
    }
}
// ---------- 跳转 ----------
function goBack() {
    router.push({ name: 'FuncTestCases', params: { id: projectId.value } });
}
function goRequirement(reqId: number) {
    router.push({
        name: 'FuncTestRequirementDetail',
        params: { id: projectId.value, reqId },
    });
}
// ---------- 工具 ----------
function priorityLabel(p: string): string {
    return ({ urgent: 'P0 紧急', high: 'P1 高', medium: 'P2 中', low: 'P3 低' } as Record<string, string>)[p] || p;
}
function priorityTag(p: string): 'danger' | 'warning' | 'primary' | 'info' {
    return ({ urgent: 'danger', high: 'warning', medium: 'primary', low: 'info' } as Record<string, 'danger' | 'warning' | 'primary' | 'info'>)[p] || 'info';
}
function statusLabel(s: string): string {
    return ({
        draft: '草稿',
        pending_review: '待审核',
        reviewed: '已审核',
        deprecated: '已废弃',
    } as Record<string, string>)[s] || s;
}
function statusTag(s: string): 'info' | 'warning' | 'primary' | 'danger' {
    return ({
        draft: 'info',
        pending_review: 'warning',
        reviewed: 'primary',
        deprecated: 'danger',
    } as Record<string, 'info' | 'warning' | 'primary' | 'danger'>)[s] || 'info';
}
function caseTypeLabel(t: string): string {
    return ({
        functional: '功能测试',
        smoke: '冒烟测试',
        regression: '回归测试',
        exploratory: '探索性测试',
    } as Record<string, string>)[t] || t;
}
function validationLevelLabel(v: string): string {
    return ({
        system: '系统测试',
        integration: '集成测试',
        unit: '单元测试',
    } as Record<string, string>)[v] || v;
}
function resultLabel(r: string): string {
    return ({ passed: '通过', failed: '失败', blocked: '阻塞', skipped: '跳过' } as Record<string, string>)[r] || r;
}
function resultTag(r: string): 'success' | 'danger' | 'warning' | 'info' {
    return ({ passed: 'success', failed: 'danger', blocked: 'warning', skipped: 'info' } as Record<string, 'success' | 'danger' | 'warning' | 'info'>)[r] || 'info';
}
function formatJson(obj: unknown): string {
    try {
        return JSON.stringify(obj, null, 2);
    }
    catch {
        return String(obj);
    }
}
onMounted(async () => {
    await Promise.all([loadDetail(), loadRequirements()]);
    loadExecutions();
});
</script>

<style scoped>
.case-detail-page {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card,
.tabs-card,
.overview-card,
.ai-review-card,
.block-card,
.steps-card,
.executions-card,
.form-card,
.side-card {
  border-radius: 8px;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.case-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.case-code {
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--theme-color-f0f3f7);
  padding: 2px 8px;
  border-radius: 4px;
}

.case-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}

.meta-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tab-badge {
  margin-left: 6px;
}

/* 各区块 */
.overview-card,
.block-card,
.ai-review-card,
.steps-card {
  margin-bottom: 16px;
}

.block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.block-title .muted {
  font-weight: 400;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin: 0 4px;
}

.block-content {
  padding: 14px 16px;
  background: var(--theme-color-fafbfc);
  border-radius: 6px;
  border: 1px solid var(--theme-color-f0f0f0);
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-primary);
}

.block-content.preline {
  white-space: pre-wrap;
}

.mono {
  font-family: 'JetBrains Mono', Menlo, monospace;
}

.text-muted {
  color: var(--el-text-color-disabled);
}

.tag-pill {
  margin: 0 4px 4px 0;
}

.review-meta {
  margin-left: auto;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-placeholder);
}
.review-decs {
  padding: 10px 14px;
  background: var(--theme-warning-bg);
  border-left: 3px solid var(--el-color-warning);
  border-radius: 4px;
  font-size: 13px;
  color: var(--theme-color-b88230);
}

/* 步骤左右对照 */
.steps-pair {
  display: grid;
  grid-template-columns: 1fr 28px 1fr;
  gap: 12px;
  align-items: start;
}

.steps-col {
  background: var(--theme-color-fafbfc);
  border: 1px solid var(--theme-color-f0f0f0);
  border-radius: 8px;
  padding: 12px;
}

.col-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-bottom: 10px;
}

.col-header .count {
  background: var(--theme-color-ecf5ff);
  color: var(--el-color-info);
  padding: 0 6px;
  border-radius: 8px;
  font-size: 11px;
  margin-left: 4px;
}

.step-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 13px;
  line-height: 1.6;
}

.step-no {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-color-info);
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
}

.step-no.expect {
  background: var(--el-color-success);
}

.step-text {
  flex: 1;
  color: var(--el-text-color-primary);
}

.steps-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 36px;
  color: var(--el-text-color-disabled);
  font-size: 18px;
}

.empty-col {
  text-align: center;
  color: var(--el-text-color-disabled);
  font-size: 12px;
  padding: 8px 0;
}

.json-block {
  margin: 0;
  padding: 12px;
  background: var(--theme-color-f7f8fa);
  border-radius: 6px;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 320px;
  overflow-y: auto;
}

/* 执行历史 */
.executions-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

/* 编辑模式 */
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

.card-form-item {
  margin-bottom: 0;
}

.side-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
}

.readonly-field {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: var(--theme-color-f7f8fa);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

@media (max-width: 1024px) {
  .edit-layout {
    grid-template-columns: 1fr;
  }
  .edit-side {
    position: static;
  }
  .steps-pair {
    grid-template-columns: 1fr;
  }
  .steps-arrow {
    transform: rotate(90deg);
    padding: 8px 0;
  }
}
</style>
