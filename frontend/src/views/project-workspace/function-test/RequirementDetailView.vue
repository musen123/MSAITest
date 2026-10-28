<template>
  <div class="req-detail-page" v-loading="loading">
    <!-- 1. 页头 -->
    <AppPageHeader
      :title="req?.title || '需求详情'"
      :breadcrumbs="['功能测试', '需求管理', '需求详情']"
    >
      <template #actions>
        <el-button text @click="goBack">
          <i class="i-solar-arrow-left-linear btn-icon" />
          返回列表
        </el-button>
        <el-button v-if="!editing" v-permission="'test_case:edit'" @click="enterEdit">
          <i class="i-solar-pen-linear btn-icon" />
          编辑
        </el-button>
        <template v-if="editing">
          <el-button @click="cancelEdit">取消</el-button>
          <el-button v-permission="'test_case:edit'" type="primary" :loading="saving" @click="handleSave">
            <i class="i-solar-check-circle-bold btn-icon" />
            保存
          </el-button>
        </template>
        <el-button v-if="!editing" v-permission="'test_case:execute'" type="primary" @click="goGenerateCases">
          <i class="i-solar-cpu-bolt-bold btn-icon" />
          AI 生成用例
        </el-button>
        <el-button
          v-if="!editing && canReview"
          type="success"
          plain
          @click="openReviewDialog('approve')"
        >
          <i class="i-solar-check-circle-bold btn-icon" />
          审核
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 2. 信息条 -->
    <div v-if="req && !editing" class="info-bar">
      <div class="info-left">
        <span class="cell-code">{{ req.code }}</span>
        <span class="prio-pill" :class="`prio-${req.priority}`">
          {{ priorityLabel(req.priority) }}
        </span>
        <span class="status-pill" :class="`status-${req.status}`">
          <span class="status-dot" />
          {{ statusLabel(req.status) }}
        </span>
        <span v-if="req.source === 'ai_generated'" class="cell-badge is-ai">AI 生成</span>
        <span v-else class="cell-badge is-manual">手工创建</span>
      </div>
      <div class="info-right">
        <span class="meta-item">
          <i class="i-solar-clock-circle-linear" />
          创建于 {{ formatDate(req.created_at) }}
        </span>
        <span v-if="req.reviewed_at" class="meta-item">
          <i class="i-solar-user-check-linear" />
          审核于 {{ formatDate(req.reviewed_at) }}
        </span>
      </div>
    </div>

    <!-- 审核意见条 -->
    <div v-if="req?.review_comment && !editing" class="review-comment-bar">
      <i class="i-solar-chat-round-dots-linear" />
      <span>审核意见：{{ req.review_comment }}</span>
    </div>

    <!-- ============ 查看模式：Tab 布局 ============ -->
    <AppSectionCard v-if="req && !editing" class="content-card">
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- Tab: 需求详情 -->
        <el-tab-pane name="detail">
          <template #label>
            <span class="tab-label">
              <i class="i-solar-document-text-bold" />
              需求详情
            </span>
          </template>

          <div class="detail-sections">
            <div class="detail-block">
              <div class="block-title">
                <i class="i-solar-notebook-bold" />
                需求描述
              </div>
              <div
                v-if="req.description"
                class="block-content markdown-body"
                v-html="renderMarkdown(req.description)"
              />
              <div v-else class="block-empty">
                <i class="i-solar-document-text-linear" />
                <span>未填写需求描述</span>
              </div>
            </div>

            <div class="detail-block">
              <div class="block-title">
                <i class="i-solar-checklist-bold" />
                验收标准
              </div>
              <div
                v-if="req.acceptance_criteria"
                class="block-content markdown-body"
                v-html="renderMarkdown(req.acceptance_criteria)"
              />
              <div v-else class="block-empty">
                <i class="i-solar-checklist-linear" />
                <span>未填写验收标准</span>
              </div>
            </div>

            <!-- 附件画廊 -->
            <div v-if="req.attachments && req.attachments.length" class="detail-block">
              <div class="block-title">
                <i class="i-solar-gallery-bold" />
                附件图片
                <span class="block-count">{{ req.attachments.length }} 张</span>
              </div>
              <AttachmentGallery
                v-model="readonlyAttachments"
                :project-id="projectId"
                readonly
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab: AI 理解 -->
        <el-tab-pane name="understand">
          <template #label>
            <span class="tab-label">
              <i class="i-solar-cpu-bolt-bold" />
              AI 理解
              <span v-if="req?.understood_content" class="status-pill status-done">
                <span class="status-dot" />
                已完成
              </span>
            </span>
          </template>

          <div
            v-if="req.understood_content && !showRunPanel"
            class="detail-block"
          >
            <div class="block-title">
              <i class="i-solar-cpu-bolt-bold" />
              AI 整理结果
              <div class="title-actions">
                <template v-if="!understandEditing">
                  <el-button v-permission="'test_case:edit'" text size="small" @click="startEditUnderstand">
                    <i class="i-solar-pen-2-linear btn-icon-sm" />
                    编辑
                  </el-button>
                  <el-button v-permission="'test_case:execute'" text size="small" @click="showRunPanel = true">
                    <i class="i-solar-refresh-linear btn-icon-sm" />
                    重新理解
                  </el-button>
                </template>
                <template v-else>
                  <el-button text size="small" @click="understandEditing = false">
                    取消
                  </el-button>
                  <el-button
                    v-permission="'test_case:edit'"
                    type="primary"
                    size="small"
                    :loading="understandSaving"
                    @click="saveUnderstand"
                  >
                    保存
                  </el-button>
                </template>
              </div>
            </div>
            <template v-if="understandEditing">
              <div class="edit-hint">
                <i class="i-solar-info-circle-linear" />
                保存后将同步更新到「需求详情」的需求描述
              </div>
              <el-input
                v-model="understandDraft"
                type="textarea"
                :rows="20"
                resize="vertical"
                placeholder="Markdown 格式的需求整理内容..."
              />
            </template>
            <div
              v-else
              class="block-content markdown-body"
              v-html="renderMarkdown(stripThink(req.understood_content))"
            />
          </div>

          <RequirementUnderstandPanel
            v-else
            :project-id="projectId"
            :requirement-id="reqId"
            :attachments="req.attachments || []"
            :requirement-description="req.description || ''"
            :requirement-title="req.title"
            @reload="loadDetail"
            @go-generate-cases="goGenerateCases"
          />
        </el-tab-pane>
      </el-tabs>
    </AppSectionCard>

    <!-- ============ 编辑模式：左主右栏 ============ -->
    <el-form
      v-if="req && editing"
      ref="editFormRef"
      :model="editForm"
      :rules="editRules"
      class="edit-layout"
      label-position="top"
      @submit.prevent
    >
      <!-- 左侧主区 -->
      <div class="edit-main">
        <AppSectionCard title="基本信息" class="form-card">
          <el-form-item label="需求标题" prop="title">
            <el-input
              v-model="editForm.title"
              maxlength="200"
              show-word-limit
              size="large"
            />
          </el-form-item>
        </AppSectionCard>

        <!-- 需求描述（手动 / RAG 双模式） -->
        <AppSectionCard class="form-card">
          <template #header>
            <div class="desc-card-header">
              <h2 class="section-title">需求描述</h2>
              <el-radio-group v-model="descMode" size="small">
                <el-radio-button value="manual">
                  <i class="i-solar-pen-linear" />
                  手动编辑
                </el-radio-button>
                <el-radio-button value="rag">
                  <i class="i-solar-magnifer-linear" />
                  知识库检索
                </el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <el-form-item v-if="descMode === 'manual'">
            <el-input
              v-model="editForm.description"
              type="textarea"
              :rows="12"
              placeholder="详细描述需求内容（支持 Markdown）..."
            />
          </el-form-item>

          <div v-else class="rag-panel">
            <div class="rag-search-bar">
              <el-input
                v-model="ragQuery"
                placeholder="输入关键词从知识库检索..."
                size="large"
                :disabled="ragLoading"
                @keydown.enter="handleRagSearch"
              >
                <template #prefix>
                  <i class="i-solar-magnifer-linear" />
                </template>
              </el-input>
              <el-button
                type="primary"
                size="large"
                :loading="ragLoading"
                @click="handleRagSearch"
              >
                检索
              </el-button>
            </div>

            <!-- AI 综合结果（/answer SSE 流式；失败/未配模型静默降级为纯片段列表） -->
            <div v-if="answerVisible" class="rag-answer">
              <div class="rag-answer-header">
                <span class="rag-answer-title">
                  <i class="i-solar-cpu-bolt-bold-duotone" />
                  AI 综合结果
                  <span v-if="answerStreaming" class="rag-answer-status">
                    {{ answerThinking ? '思考中…' : '生成中…' }}
                  </span>
                  <span v-else-if="answerInterrupted" class="rag-answer-status is-warn">
                    已中断
                  </span>
                </span>
                <div class="rag-answer-actions">
                  <el-button v-if="answerStreaming" link size="small" @click="kbAnswer.abort()">
                    停止
                  </el-button>
                  <el-button
                    v-else-if="answerText"
                    type="primary"
                    size="small"
                    @click="handleAdoptAnswer"
                  >
                    添加到需求描述
                  </el-button>
                </div>
              </div>
              <div
                v-if="answerText"
                class="rag-answer-body"
                v-html="renderMarkdown(answerText)"
              ></div>
              <div v-else class="rag-answer-placeholder">正在检索并综合知识库内容…</div>
              <div v-if="answerRefDocs.length" class="rag-answer-refs">
                综合自：{{ answerRefDocs.map((n) => `《${n}》`).join(' ') }}
              </div>
            </div>

            <div v-if="ragResults.length > 0" class="rag-results">
              <div class="rag-results-title">
                检索结果（{{ ragResults.length }}）
                <span class="hint">点击任意片段追加到描述并标记采纳</span>
              </div>
              <div
                v-for="(item, idx) in ragResults"
                :key="item.chunk_id"
                class="rag-result-item"
                :class="{ 'is-adopted': adoptedIds.has(item.chunk_id) }"
                @click="handleSelectRagResult(item)"
              >
                <div class="rag-result-index">{{ idx + 1 }}</div>
                <div class="rag-result-body">
                  <div class="rag-result-meta">
                    <span class="rag-result-doc">{{ item.doc_name }}</span>
                    <span v-if="item.heading_path" class="rag-result-path">
                      {{ item.heading_path }}
                    </span>
                  </div>
                  <div class="rag-result-text">
                    {{ truncateText(item.content, 300) }}
                  </div>
                </div>
                <i
                  v-if="adoptedIds.has(item.chunk_id)"
                  class="i-solar-check-circle-bold rag-result-adopted"
                />
              </div>
            </div>
            <div v-else-if="ragSearched" class="block-empty">
              <i class="i-solar-magnifer-linear" />
              <span>未检索到相关内容</span>
            </div>
            <div v-else class="block-empty">
              <i class="i-solar-magnifer-linear" />
              <span>输入关键词检索项目知识库</span>
            </div>

            <div v-if="editForm.description" class="rag-preview">
              <div class="rag-preview-header">
                <span>当前需求描述</span>
                <el-button link type="danger" size="small" @click="editForm.description = ''">
                  <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                  清空
                </el-button>
              </div>
              <div class="rag-preview-content">{{ editForm.description }}</div>
            </div>
          </div>
        </AppSectionCard>

        <AppSectionCard title="验收标准" class="form-card">
          <el-form-item>
            <el-input
              v-model="editForm.acceptance_criteria"
              type="textarea"
              :rows="5"
              placeholder="每条换行分隔..."
            />
          </el-form-item>
        </AppSectionCard>
      </div>

      <!-- 右侧栏 -->
      <div class="edit-side">
        <AppSectionCard title="需求编号" class="side-card">
          <el-form-item>
            <el-input
              v-model="editForm.code"
              size="large"
              placeholder="留空将不修改"
            />
          </el-form-item>
        </AppSectionCard>

        <AppSectionCard title="优先级" class="side-card">
          <el-form-item>
            <el-select v-model="editForm.priority" size="large" style="width: 100%">
              <el-option label="紧急" value="urgent" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
        </AppSectionCard>

        <AppSectionCard title="状态" class="side-card">
          <el-form-item>
            <el-select v-model="editForm.status" size="large" style="width: 100%">
              <el-option label="草稿" value="draft" />
              <el-option label="待审核" value="pending_review" />
              <el-option label="已审核" value="reviewed" />
              <el-option label="已发布" value="published" />
              <el-option label="已废弃" value="deprecated" />
            </el-select>
          </el-form-item>
        </AppSectionCard>

        <!-- 附件 -->
        <AppSectionCard class="side-card">
          <template #header>
            <div class="side-attach-header">
              <h2 class="section-title">附件图片</h2>
              <span v-if="editForm.attachments.length" class="count-badge">
                {{ editForm.attachments.length }}
              </span>
            </div>
          </template>

          <el-upload
            class="upload-trigger-wrap"
            :auto-upload="true"
            :show-file-list="false"
            accept="image/png,image/jpeg,image/gif,image/webp"
            multiple
            :before-upload="beforeUpload"
            :http-request="handleUpload"
          >
            <div class="upload-trigger">
              <i class="i-solar-add-circle-linear" />
              <span>添加图片</span>
            </div>
          </el-upload>

          <div v-if="editForm.attachments.length > 0" class="preview-grid">
            <div
              v-for="(url, idx) in editForm.attachments"
              :key="url"
              class="preview-item"
            >
              <el-image
                :src="url"
                fit="cover"
                class="preview-img"
                :preview-src-list="editForm.attachments"
                :initial-index="idx"
                preview-teleported
                :z-index="3000"
              >
                <template #error>
                  <div class="preview-error">
                    <i class="i-solar-gallery-bold" />
                  </div>
                </template>
              </el-image>
              <button
                type="button"
                class="preview-remove"
                @click="removeAttachment(idx)"
              >
                <i class="i-solar-close-circle-bold" />
              </button>
            </div>
          </div>
          <div v-else class="upload-hint">
            支持 PNG/JPG/GIF/WEBP，单张最大 20MB
          </div>
        </AppSectionCard>
      </div>
    </el-form>

    <!-- 审核对话框 -->
    <RequirementReviewDialog
      v-model="reviewDialog.visible"
      :project-id="projectId"
      :requirement="req"
      :initial-action="reviewDialog.action"
      @reviewed="loadDetail"
    />

    <!-- AI 生成用例对话框 -->
    <CaseGenerateDialog
      v-model="generateDialog.visible"
      :project-id="projectId"
      :requirement-id="reqId"
      :requirement="req"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  type FormInstance,
  type FormRules,
  type UploadRawFile,
  type UploadRequestOptions,
} from 'element-plus'
import { funcRequirementApi } from '@/api/funcTest'
import { knowledgeApi } from '@/api/knowledge'
import type { KbSearchHit } from '@/api/knowledge'
import CaseGenerateDialog from '@/components/func-test/CaseGenerateDialog.vue'
import RequirementReviewDialog from '@/components/func-test/RequirementReviewDialog.vue'
import type {
  FuncRequirement,
  RequirementPriority,
  RequirementStatus,
} from '@/types/func-test'
import { formatDate } from '@/utils/format'
import { useKbAnswer } from '@/composables/useKbAnswer'
import { useMarkdown } from '@/composables/useMarkdown'
import RequirementUnderstandPanel from '@/components/func-test/RequirementUnderstandPanel.vue'
import AttachmentGallery from '@/components/func-test/AttachmentGallery.vue'
import { AppPageHeader, AppSectionCard } from '@/components/common'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))
const reqId = computed(() => Number(route.params.reqId))

const { render: renderMarkdown } = useMarkdown()

// ---------- 详情数据 ----------
const loading = ref(false)
const saving = ref(false)
const req = ref<FuncRequirement | null>(null)

const activeTab = ref<'detail' | 'understand'>('detail')
const showRunPanel = ref(false)

// ---------- AI 整理结果：编辑与 think 兜底剥离 ----------
const understandEditing = ref(false)
const understandDraft = ref('')
const understandSaving = ref(false)

/** 兜底剥离推理模型混入的 <think> 思考过程（存量数据展示用） */
function stripThink(text: string) {
  return text.replace(/<think[^>]*>[\s\S]*?<\/think\s*>/g, '').trim()
}

function startEditUnderstand() {
  understandDraft.value = stripThink(req.value?.understood_content || '')
  understandEditing.value = true
}

async function saveUnderstand() {
  if (!req.value) return
  understandSaving.value = true
  try {
    // 整理结果即正式需求：同步写入 AI 理解字段与需求描述
    await funcRequirementApi.update(projectId.value, req.value.id, {
      understood_content: understandDraft.value,
      description: understandDraft.value,
    })
    ElMessage.success('已保存，需求描述已同步更新')
    understandEditing.value = false
    await loadDetail()
  } catch (err) {
    console.error(err)
  } finally {
    understandSaving.value = false
  }
}

// 只读附件用（查看模式渲染 AttachmentGallery 时双向绑定的代理）
const readonlyAttachments = ref<string[]>([])

async function loadDetail() {
  loading.value = true
  try {
    const res = await funcRequirementApi.detail(projectId.value, reqId.value)
    req.value = res.data
    readonlyAttachments.value = [...(res.data.attachments || [])]
    showRunPanel.value = false
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

// ---------- 编辑表单 ----------
const editing = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive({
  title: '',
  code: '',
  priority: 'medium' as RequirementPriority,
  status: 'draft' as RequirementStatus,
  description: '',
  acceptance_criteria: '',
  attachments: [] as string[],
})
const editRules: FormRules = {
  title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }],
}

function enterEdit() {
  if (!req.value) return
  editForm.title = req.value.title
  editForm.code = req.value.code || ''
  editForm.priority = req.value.priority
  editForm.status = req.value.status
  editForm.description = req.value.description || ''
  editForm.acceptance_criteria = req.value.acceptance_criteria || ''
  editForm.attachments = [...(req.value.attachments || [])]
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  descMode.value = 'manual'
}

async function handleSave() {
  if (editFormRef.value) {
    try {
      await editFormRef.value.validate()
    } catch {
      return
    }
  }
  saving.value = true
  try {
    await funcRequirementApi.update(projectId.value, reqId.value, {
      title: editForm.title,
      code: editForm.code || undefined,
      priority: editForm.priority,
      status: editForm.status,
      description: editForm.description,
      acceptance_criteria: editForm.acceptance_criteria,
      attachments: editForm.attachments,
    })
    ElMessage.success('保存成功')
    editing.value = false
    await loadDetail()
  } catch (err) {
    console.error(err)
  } finally {
    saving.value = false
  }
}

// ---------- 描述模式（手动 / RAG） ----------
const descMode = ref<'manual' | 'rag'>('manual')
const ragQuery = ref('')
const ragLoading = ref(false)
const ragSearched = ref(false)
const ragResults = ref<KbSearchHit[]>([])
const ragLogId = ref<number | null>(null)
const adoptedIds = ref(new Set<number>())

// AI 综合结果流（/answer SSE）——与 chunk 检索并行生成，可整段采纳
const kbAnswer = useKbAnswer()
const {
  visible: answerVisible,
  streaming: answerStreaming,
  thinking: answerThinking,
  text: answerText,
  refDocs: answerRefDocs,
  interrupted: answerInterrupted,
} = kbAnswer

onBeforeUnmount(() => kbAnswer.abort())

async function handleRagSearch() {
  const q = ragQuery.value.trim()
  if (!q || ragLoading.value) return
  ragLoading.value = true
  ragSearched.value = false
  ragResults.value = []
  ragLogId.value = null
  adoptedIds.value = new Set()
  // 并行两路：chunk 检索（下方精确采纳）+ AI 综合（顶部整段采纳），综合失败静默
  void kbAnswer.run(projectId.value, { query: q, top_k: 8 })
  try {
    // 自研混合检索：直接返回 chunk 引用列表（doc_name + 章节面包屑可溯源）
    const res = await knowledgeApi.search(projectId.value, {
      query: q,
      top_k: 10,
      consumer: 'requirement',
    })
    ragResults.value = res.data.hits
    ragLogId.value = res.data.log_id ?? null
    ragSearched.value = true
  } catch (err) {
    console.error(err)
    ragSearched.value = true
  } finally {
    ragLoading.value = false
  }
}

function handleSelectRagResult(item: KbSearchHit) {
  const source = item.heading_path
    ? `（来源：《${item.doc_name}》 ${item.heading_path}）`
    : `（来源：《${item.doc_name}》）`
  const block = `${item.content}\n${source}`
  editForm.description = editForm.description ? `${editForm.description}\n\n${block}` : block
  ElMessage.success('已追加到需求描述')
  // 采纳回写检索日志（质量反馈闭环），失败静默不打扰编辑
  if (ragLogId.value !== null && !adoptedIds.value.has(item.chunk_id)) {
    adoptedIds.value.add(item.chunk_id)
    knowledgeApi
      .feedback(projectId.value, {
        log_id: ragLogId.value,
        adopted_chunk_ids: [item.chunk_id],
      })
      .catch(() => {})
  }
}

function handleAdoptAnswer() {
  const content = answerText.value.trim()
  if (!content) return
  const docs = answerRefDocs.value
  const source = docs.length
    ? `（来源：AI 综合自 ${docs.map((n) => `《${n}》`).join('、')}）`
    : '（来源：知识库 AI 综合）'
  const block = `${content}\n${source}`
  editForm.description = editForm.description ? `${editForm.description}\n\n${block}` : block
  ElMessage.success('已添加到需求描述')
  // 整段采纳 → 对 answer 检索日志回写正反馈（质量闭环），失败静默
  if (kbAnswer.logId.value !== null) {
    knowledgeApi
      .feedback(projectId.value, { log_id: kbAnswer.logId.value, feedback: 1 })
      .catch(() => {})
  }
}

function truncateText(text: string, max: number) {
  if (text.length <= max) return text
  return text.slice(0, max) + '…'
}

// ---------- 附件 ----------
function beforeUpload(file: UploadRawFile): boolean {
  const allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 png / jpg / gif / webp 格式')
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 20MB')
    return false
  }
  return true
}

async function handleUpload(options: UploadRequestOptions) {
  try {
    const res = await funcRequirementApi.uploadAttachment(
      projectId.value,
      options.file as File,
    )
    editForm.attachments.push(res.data.url)
    ElMessage.success('上传成功')
  } catch (err) {
    console.error(err)
  }
}

function removeAttachment(idx: number) {
  editForm.attachments.splice(idx, 1)
}

// ---------- 审核（弹框逻辑在 RequirementReviewDialog 组件内） ----------
const reviewDialog = reactive({
  visible: false,
  action: 'approve' as 'approve' | 'reject',
})

const canReview = computed(
  () =>
    req.value &&
    (req.value.status === 'draft' || req.value.status === 'pending_review'),
)

function openReviewDialog(defaultAction: 'approve' | 'reject') {
  reviewDialog.action = defaultAction
  reviewDialog.visible = true
}

// ---------- 跳转 ----------
function goBack() {
  router.push({ name: 'FuncTestRequirements', params: { id: projectId.value } })
}

// AI 用例生成对话框
const generateDialog = reactive({ visible: false })

function goGenerateCases() {
  generateDialog.visible = true
}

// ---------- 工具 ----------
function priorityLabel(p: string) {
  return ({ urgent: '紧急', high: '高', medium: '中', low: '低' } as Record<string, string>)[p] || p
}

function priorityTag(p: string): 'danger' | 'warning' | 'primary' | 'info' {
  return (
    { urgent: 'danger', high: 'warning', medium: 'primary', low: 'info' } as Record<
      string,
      'danger' | 'warning' | 'primary' | 'info'
    >
  )[p] || 'info'
}

function statusLabel(s: string) {
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

onMounted(loadDetail)
</script>

<style scoped lang="scss">
.req-detail-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 信息条 ============ */
.info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-6);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  flex-wrap: wrap;
}
.info-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.info-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.cell-code {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

.cell-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);

  &.is-ai {
    background: var(--color-purple-50);
    color: var(--color-purple-600);
  }
  &.is-manual {
    background: var(--color-info-50);
    color: var(--color-info-600);
  }
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);

  > i { font-size: 14px; }
}

/* 优先级药丸 */
.prio-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);

  &.prio-urgent { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.prio-high   { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.prio-medium { background: var(--color-info-50);    color: var(--color-info-600); }
  &.prio-low    { background: var(--gray-100);         color: var(--gray-600); }
}

/* 状态药丸 */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  &.status-draft          { background: var(--gray-100);         color: var(--gray-600); }
  &.status-pending_review { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.status-reviewed       { background: var(--color-info-50);    color: var(--color-info-600); }
  &.status-published      { background: var(--color-success-50); color: var(--color-success-600); }
  &.status-deprecated     { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.status-done           { background: var(--color-success-50); color: var(--color-success-600); }
}

/* 审核意见条 */
.review-comment-bar {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--color-warning-50);
  border-left: 3px solid var(--color-warning-500);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-warning-600);

  > i { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
}

/* ============ 内容区 Tabs ============ */
.content-card {
  min-height: 400px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  > i { font-size: 14px; }
}

.detail-sections {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);

  > i { font-size: 16px; color: var(--brand-500); }

  .title-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.edit-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--space-2);
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  background: var(--color-info-50, #eff6ff);
  color: var(--color-info-600, #2563eb);
  font-size: var(--font-size-xs);

  > i { font-size: 14px; flex-shrink: 0; }
}

.block-count {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-regular);
  color: var(--text-secondary);
  margin-left: var(--space-1);
}

.block-content {
  padding: var(--space-4) var(--space-5);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
  color: var(--text-primary);
}

.block-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-4);
  color: var(--text-placeholder);
  font-size: var(--font-size-sm);
  text-align: center;

  > i { font-size: 32px; opacity: 0.5; }
}

.ml-auto { margin-left: auto; }

/* ============ 编辑模式 ============ */
.edit-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--space-4);
  align-items: start;
}

.edit-main {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.edit-side {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  position: sticky;
  top: var(--space-4);
}

.form-card {
  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.desc-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.side-attach-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  background: var(--brand-50);
  color: var(--brand-600);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
}

/* RAG */
.rag-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.rag-search-bar {
  display: flex;
  gap: var(--space-2);

  .el-input { flex: 1; }
}

/* AI 综合结果卡片 */
.rag-answer {
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  padding: var(--space-3) 14px;
}

.rag-answer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.rag-answer-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--el-color-primary);
}

.rag-answer-status {
  font-weight: normal;
  color: var(--el-text-color-secondary);

  &.is-warn { color: var(--el-color-warning); }
}

.rag-answer-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-primary);
  overflow-wrap: anywhere;

  :deep(p) { margin: 0 0 8px; }

  :deep(ul),
  :deep(ol) {
    margin: 0 0 8px;
    padding-left: 18px;
  }

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4) {
    font-size: 13px;
    font-weight: 700;
    margin: 10px 0 6px;
  }

  :deep(table) {
    border-collapse: collapse;
    margin: 6px 0;
  }

  :deep(th),
  :deep(td) {
    border: 1px solid var(--el-border-color-lighter);
    padding: 4px 8px;
    font-size: 12px;
  }

  :deep(pre) {
    background: var(--theme-color-fafbfc);
    border-radius: 6px;
    padding: 8px;
    overflow-x: auto;
    margin: 6px 0;
  }

  :deep(code) { font-size: 12px; }
}

.rag-answer-placeholder {
  font-size: var(--font-size-xs);
  color: var(--el-text-color-secondary);
}

.rag-answer-refs {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.rag-results-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-regular);
  margin-bottom: var(--space-2);

  .hint {
    font-weight: var(--font-weight-regular);
    color: var(--text-secondary);
  }
}

.rag-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.rag-result-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  background: var(--bg-card);
  transition: var(--transition-fast);

  &:hover {
    border-color: var(--brand-300);
    background: var(--brand-50);
    box-shadow: var(--shadow-sm);
  }
}

.rag-result-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 11px;
  font-weight: var(--font-weight-bold);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rag-result-body {
  flex: 1;
  min-width: 0;
}

.rag-result-text {
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--text-primary);
  white-space: pre-wrap;
}

.rag-result-item.is-adopted {
  border-color: color-mix(in srgb, var(--success-500, #22c55e) 40%, transparent);
  background: color-mix(in srgb, var(--success-500, #22c55e) 6%, transparent);
}

.rag-result-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
  min-width: 0;
}

.rag-result-doc {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rag-result-path {
  font-size: 11px;
  color: var(--brand-600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.rag-result-adopted {
  flex-shrink: 0;
  align-self: center;
  font-size: 16px;
  color: var(--success-600, #16a34a);
}

.rag-preview {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
}

.rag-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-regular);
}

.rag-preview-content {
  padding: var(--space-3);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--text-regular);
  max-height: 180px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* 附件上传 */
.upload-trigger-wrap {
  width: 100%;

  :deep(.el-upload) { width: 100%; }
}

.upload-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: var(--space-3);
  border: 1.5px dashed var(--gray-300);
  border-radius: var(--radius-md);
  background: var(--gray-50);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: var(--transition-fast);

  > i { font-size: 16px; }

  &:hover {
    border-color: var(--brand-400);
    color: var(--brand-600);
    background: var(--brand-50);
  }
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.preview-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.preview-img {
  width: 100%;
  height: 100%;
  cursor: zoom-in;
}

.preview-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-50);
  color: var(--text-placeholder);
  font-size: 24px;
}

.preview-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 14px;
}

.preview-item:hover .preview-remove {
  opacity: 1;
}

.upload-hint {
  margin-top: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
  text-align: center;
}

/* Markdown 样式 */
.markdown-body {
  :deep(h1), :deep(h2), :deep(h3) {
    margin-top: var(--space-4);
    margin-bottom: var(--space-2);
    font-weight: var(--font-weight-semibold);
  }
  :deep(h1) { font-size: var(--font-size-xl); }
  :deep(h2) { font-size: var(--font-size-lg); }
  :deep(h3) { font-size: var(--font-size-md); }

  :deep(p) { margin: var(--space-2) 0; }

  :deep(ul), :deep(ol) {
    margin: var(--space-2) 0;
    padding-left: 22px;
  }
  :deep(li) { margin: 3px 0; }

  :deep(code) {
    background: var(--gray-100);
    padding: 1px 5px;
    border-radius: var(--radius-xs);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }
  :deep(pre) {
    background: var(--gray-50);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    overflow-x: auto;
  }

  :deep(table) {
    border-collapse: collapse;
    margin: var(--space-2) 0;
    width: 100%;
  }
  :deep(th), :deep(td) {
    border: 1px solid var(--border-base);
    padding: 6px 10px;
    font-size: var(--font-size-sm);
  }
  :deep(th) {
    background: var(--gray-50);
    font-weight: var(--font-weight-semibold);
  }

  :deep(blockquote) {
    border-left: 4px solid var(--brand-300);
    margin: var(--space-2) 0;
    padding: var(--space-1) var(--space-3);
    color: var(--text-secondary);
    background: var(--brand-50);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }
}

/* 响应式 */
@media (max-width: 1024px) {
  .edit-layout {
    grid-template-columns: 1fr;
  }
  .edit-side {
    position: static;
  }
}
</style>
