<template>
  <el-dialog
    v-model="visible"
    title="AI 生成用例"
    width="640px"
    :close-on-click-modal="false"
    :destroy-on-close="false"
    @open="handleOpen"
  >
    <div class="case-generate-dialog">
      <template v-if="selectedRequirement">
        <!-- 目标需求信息条 -->
        <div class="req-target">
          <div class="req-icon">
            <i class="i-solar-clipboard-list-bold" />
          </div>
          <div class="req-info">
            <div class="req-meta">
              <span class="req-code">
                {{ selectedRequirement.code || `#${selectedRequirement.id}` }}
              </span>
              <el-tag :type="priorityTag(selectedRequirement.priority)" size="small">
                {{ priorityLabel(selectedRequirement.priority) }}
              </el-tag>
              <el-tag :type="statusTag(selectedRequirement.status)" size="small">
                {{ statusLabel(selectedRequirement.status) }}
              </el-tag>
            </div>
            <div class="req-title">{{ selectedRequirement.title }}</div>
          </div>
          <button
            v-if="selectedRequirement.description"
            class="desc-toggle"
            type="button"
            @click="descOpen = !descOpen"
          >
            <i
              :class="descOpen
                ? 'i-solar-alt-arrow-up-linear'
                : 'i-solar-alt-arrow-down-linear'"
            />
            {{ descOpen ? '收起描述' : '查看描述' }}
          </button>
        </div>

        <!-- 需求描述（展开） -->
        <pre v-if="descOpen && selectedRequirement.description" class="req-desc">{{ selectedRequirement.description }}</pre>

        <!-- 生成流程提示 -->
        <div
          class="flow-banner"
          :class="existCasesCount > 0 ? 'is-supplement' : 'is-first'"
        >
          <i
            :class="existCasesCount > 0
              ? 'i-solar-add-square-bold'
              : 'i-solar-cpu-bolt-bold'"
            class="banner-icon"
          />
          <span v-if="loadingExistCases">查询已有用例中...</span>
          <span v-else-if="existCasesCount > 0">
            该需求已有 <b>{{ existCasesCount }}</b> 条用例，本次走<b>补充生成</b>流程，只针对缺失场景补充
          </span>
          <span v-else>
            该需求暂无用例，本次走<b>初次生成</b>流程，完整覆盖需求测试点
          </span>
        </div>
      </template>
      <el-empty v-else description="未指定需求" :image-size="80" />

      <!-- 生成配置 -->
      <div class="section-label">生成配置</div>
      <div class="setting-list">
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-title">生成后自动 AI 评审</div>
            <div class="setting-desc">生成完成后自动派发独立评审任务，结论写入用例评审信息（只标注不删除，人工终审）</div>
          </div>
          <el-switch v-model="form.enable_review" />
        </div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-title">引用项目知识库</div>
            <div class="setting-desc">检索本项目需求/接口/设计文档片段注入生成上下文（零命中零影响）</div>
          </div>
          <el-switch v-model="form.use_knowledge_base" />
        </div>
        <div class="setting-desc" style="padding: 4px 2px 0">
          生成采用分批流水线：先分解测试点，再按批生成、逐批入库——任务中途失败已保存的用例不丢，
          重试自动进入补充模式只补缺口；测试点覆盖情况在任务结果中对账展示。
        </div>
      </div>

      <!-- 自定义提示词 -->
      <div class="section-label">
        自定义提示词 <span class="optional">可选</span>
      </div>
      <el-input
        v-model="form.custom_prompt"
        type="textarea"
        :rows="3"
        placeholder="附加引导，如：请重点生成边界值测试和异常场景..."
        maxlength="500"
        show-word-limit
      />
    </div>

    <!-- 底部按钮：提交后跳转统一 AI 任务详情页查看进度 -->
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        type="primary"
        :disabled="!form.requirement_id"
        :loading="submitting"
        @click="handleStart"
      >
        <el-icon><MagicStick /></el-icon>
        {{ submitting ? '提交中...' : '开始生成用例' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { funcRequirementApi, funcTestCaseApi } from '@/api/funcTest'
import { aiTaskApi } from '@/api/aiTask'
import type { FuncRequirement } from '@/types/func-test'

const props = defineProps<{
  modelValue: boolean
  projectId: number
  requirementId?: number | null
  /** 可选：直接传入需求对象，避免再次请求 */
  requirement?: FuncRequirement | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
}>()

const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// ---------- 配置表单 ----------
const form = reactive({
  requirement_id: undefined as number | undefined,
  enable_review: true,
  use_knowledge_base: true,
  custom_prompt: '',
})

const submitting = ref(false)
const selectedRequirement = ref<FuncRequirement | null>(null)
const descOpen = ref(false)

async function loadRequirementDetail(reqId: number) {
  try {
    const { data } = await funcRequirementApi.detail(props.projectId, reqId)
    selectedRequirement.value = data
  } catch (err) {
    console.error(err)
  }
}

// ---------- 已有用例 ----------
const existCasesCount = ref(0)
const loadingExistCases = ref(false)

async function loadExistCases(reqId: number) {
  loadingExistCases.value = true
  try {
    const { data } = await funcTestCaseApi.list(props.projectId, {
      requirement_id: reqId,
      page: 1,
      page_size: 1,
    })
    existCasesCount.value = data.total
  } catch (err) {
    console.error(err)
  } finally {
    loadingExistCases.value = false
  }
}

// ---------- 提交 ----------
async function handleStart() {
  if (!form.requirement_id) return
  submitting.value = true
  try {
    // 提交统一 AI 任务（异步执行，进度在 AI 任务中心实时查看）
    const { data } = await aiTaskApi.submit(props.projectId, {
      task_type: 'generate_case',
      params: {
        requirement_id: form.requirement_id,
        requirement_title: selectedRequirement.value?.title,
        custom_prompt: form.custom_prompt || undefined,
        enable_review: form.enable_review,
        use_knowledge_base: form.use_knowledge_base,
      },
      biz_ref_type: 'requirement',
      biz_ref_id: form.requirement_id,
    })
    ElMessage.success('用例生成任务已提交')
    visible.value = false
    // 跳转统一任务详情页，实时查看进度与产出
    router.push({
      name: 'AiTaskDetail',
      params: { id: props.projectId, taskId: data.id },
    })
  } catch (err) {
    console.error(err)
  } finally {
    submitting.value = false
  }
}

// ---------- 工具 ----------
function priorityLabel(p: string) {
  return (
    { urgent: 'P0 紧急', high: 'P1 高', medium: 'P2 中', low: 'P3 低' } as Record<string, string>
  )[p] || p
}

function priorityTag(p: string): 'danger' | 'warning' | 'primary' | 'info' {
  return (
    { urgent: 'danger', high: 'warning', medium: 'primary', low: 'info' } as Record<
      string,
      'danger' | 'warning' | 'primary' | 'info'
    >
  )[p] || 'info'
}

function statusLabel(s: string): string {
  return (
    {
      draft: '草稿',
      pending_review: '待审核',
      reviewed: '已审核',
      published: '已发布',
      deprecated: '已废弃',
    } as Record<string, string>
  )[s] || s
}

function statusTag(s: string): 'info' | 'warning' | 'primary' | 'success' | 'danger' {
  return (
    {
      draft: 'info',
      pending_review: 'warning',
      reviewed: 'primary',
      published: 'success',
      deprecated: 'danger',
    } as Record<string, 'info' | 'warning' | 'primary' | 'success' | 'danger'>
  )[s] || 'info'
}

// ---------- 生命周期 ----------
function handleOpen() {
  // 重置可调配置（保留用户上次的偏好可改这里）
  form.enable_review = true
  form.enable_coverage_check = true
  form.use_knowledge_base = true
  form.max_supplement_rounds = 2
  form.custom_prompt = ''
  descOpen.value = false

  // 接收外部传入的需求 id
  form.requirement_id = props.requirementId ?? undefined
  selectedRequirement.value = props.requirement ?? null

  if (form.requirement_id) {
    if (!selectedRequirement.value) {
      loadRequirementDetail(form.requirement_id)
    }
    loadExistCases(form.requirement_id)
  } else {
    selectedRequirement.value = null
    existCasesCount.value = 0
  }
}
</script>

<style scoped lang="scss">
.case-generate-dialog {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 4px;
}

/* 目标需求信息条 */
.req-target {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--el-fill-color-light);
  border-radius: 10px;

  .req-icon {
    width: 40px;
    height: 40px;
    border-radius: 9px;
    background: var(--brand-50);
    color: var(--brand-500);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 21px;
    flex-shrink: 0;
  }

  .req-info {
    flex: 1;
    min-width: 0;
  }

  .req-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }

  .req-code {
    font-family: 'JetBrains Mono', Menlo, monospace;
    font-size: 12px;
    background: var(--el-bg-color);
    padding: 1px 8px;
    border-radius: 4px;
    color: var(--text-secondary);
  }

  .req-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .desc-toggle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    border: none;
    background: none;
    padding: 4px 6px;
    font-size: 12.5px;
    color: var(--brand-600);
    cursor: pointer;
    border-radius: 6px;

    &:hover {
      background: var(--brand-50);
    }
  }
}

/* 需求描述 */
.req-desc {
  margin: 0;
  padding: 12px 14px;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-regular);
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  max-height: 180px;
  overflow-y: auto;
}

/* 生成流程提示条 */
.flow-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 8px;
  font-size: 13px;

  .banner-icon {
    font-size: 16px;
    flex-shrink: 0;
  }

  b {
    font-weight: 600;
  }

  &.is-first {
    background: var(--color-success-50, #ecfdf5);
    color: var(--color-success-600, #059669);
  }

  &.is-supplement {
    background: var(--color-warning-50, #fffbeb);
    color: var(--color-warning-600, #d97706);
  }
}

/* 小节标题 */
.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: -6px;

  .optional {
    font-weight: 400;
    font-size: 11px;
    color: var(--text-placeholder);
    margin-left: 2px;
  }
}

/* 配置行 */
.setting-list {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  overflow: hidden;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  transition: opacity 0.2s;

  & + .setting-row {
    border-top: 1px solid var(--el-border-color-lighter);
  }

  &.is-disabled {
    opacity: 0.5;
  }

  .setting-info {
    flex: 1;
    min-width: 0;
  }

  .setting-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.4;
  }

  .setting-desc {
    margin-top: 2px;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
  }
}
</style>
