<template>
  <div class="requirement-create-page">
    <!-- 顶部操作栏 -->
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
            {{ submitting ? '提交中...' : '创建需求' }}
          </el-button>
        </div>
      </div>
      <div class="header-title">
        <h2>新建需求</h2>
        <p class="header-desc">填写需求基本信息，支持手动编辑或从知识库检索描述</p>
      </div>
    </el-card>

    <!-- 主体：左主右栏 -->
    <el-form
      ref="formRef"
      :model="form"
      :rules="formRules"
      class="edit-layout"
      label-position="top"
      @submit.prevent
    >
      <!-- 左侧主区 -->
      <div class="edit-main">
        <!-- 需求标题 -->
        <el-card class="form-card" shadow="never">
          <el-form-item label="需求标题" prop="title" class="card-form-item">
            <el-input
              v-model="form.title"
              placeholder="如：用户注册功能"
              maxlength="200"
              show-word-limit
              size="large"
            />
          </el-form-item>
        </el-card>

        <!-- 需求描述（手动 / RAG 双模式） -->
        <el-card class="form-card desc-card" shadow="never">
          <div class="desc-card-header">
            <span class="form-label">需求描述</span>
            <el-radio-group v-model="descMode" size="small">
              <el-radio-button value="manual">
                <el-icon><Edit /></el-icon>
                手动编辑
              </el-radio-button>
              <el-radio-button value="rag">
                <el-icon><Search /></el-icon>
                知识库检索
              </el-radio-button>
            </el-radio-group>
          </div>

          <!-- 手动模式 -->
          <el-form-item v-if="descMode === 'manual'" prop="description" class="card-form-item">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="14"
              placeholder="详细描述需求内容，包括功能要求、业务规则等（支持 Markdown）..."
            />
          </el-form-item>

          <!-- RAG 检索模式 -->
          <div v-else class="rag-panel">
            <div class="rag-search-bar">
              <el-input
                v-model="ragQuery"
                placeholder="输入关键词从知识库检索需求内容..."
                size="large"
                :disabled="ragLoading"
                @keydown.enter="handleRagSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
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
                  <div class="rag-result-text">{{ truncateText(item.content, 300) }}</div>
                </div>
                <i
                  v-if="adoptedIds.has(item.chunk_id)"
                  class="i-solar-check-circle-bold rag-result-adopted"
                />
              </div>
            </div>
            <el-empty
              v-else-if="ragSearched"
              description="未检索到相关内容，请尝试更换关键词"
              :image-size="60"
            />
            <el-empty
              v-else
              description="输入关键词检索项目知识库"
              :image-size="60"
            />

            <!-- 当前描述预览 -->
            <div v-if="form.description" class="rag-preview">
              <div class="rag-preview-header">
                <span>当前需求描述</span>
                <el-button
                  link
                  type="danger"
                  size="small"
                  @click="form.description = ''"
                >
                  <el-icon><Delete /></el-icon>
                  清空
                </el-button>
              </div>
              <div class="rag-preview-content">{{ form.description }}</div>
            </div>
          </div>
        </el-card>

        <!-- 验收标准 -->
        <el-card class="form-card" shadow="never">
          <el-form-item label="验收标准" class="card-form-item">
            <el-input
              v-model="form.acceptance_criteria"
              type="textarea"
              :rows="5"
              placeholder="每条换行分隔..."
            />
          </el-form-item>
        </el-card>
      </div>

      <!-- 右侧栏 -->
      <div class="edit-side">
        <!-- 需求编号 -->
        <el-card class="side-card" shadow="never">
          <div class="side-label required">需求编号</div>
          <el-form-item class="card-form-item">
            <div class="req-id-row">
              <el-input
                v-model="form.code"
                placeholder="可留空自动生成"
                size="large"
              />
              <el-tooltip content="重新生成">
                <el-button
                  size="large"
                  @click="form.code = generateCode()"
                >
                  <el-icon><RefreshRight /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
            <div class="field-hint">留空时后端自动按项目分配序号</div>
          </el-form-item>
        </el-card>

        <!-- 优先级 -->
        <el-card class="side-card" shadow="never">
          <div class="side-label">优先级</div>
          <el-form-item class="card-form-item">
            <el-select v-model="form.priority" size="large" style="width: 100%">
              <el-option label="紧急" value="urgent">
                <span class="select-with-tag">
                  <el-tag type="danger" size="small">紧急</el-tag>
                </span>
              </el-option>
              <el-option label="高" value="high">
                <span class="select-with-tag">
                  <el-tag type="warning" size="small">高</el-tag>
                </span>
              </el-option>
              <el-option label="中" value="medium">
                <span class="select-with-tag">
                  <el-tag size="small">中</el-tag>
                </span>
              </el-option>
              <el-option label="低" value="low">
                <span class="select-with-tag">
                  <el-tag type="info" size="small">低</el-tag>
                </span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-card>

        <!-- 附件 -->
        <el-card class="side-card" shadow="never">
          <div class="side-label">
            <el-icon><Picture /></el-icon>
            附件图片
            <span v-if="form.attachments.length" class="count-badge">
              {{ form.attachments.length }}
            </span>
          </div>

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
              <el-icon><Plus /></el-icon>
              <span>添加图片</span>
            </div>
          </el-upload>

          <div v-if="form.attachments.length > 0" class="preview-grid">
            <div
              v-for="(url, idx) in form.attachments"
              :key="url"
              class="preview-item"
            >
              <el-image
                :src="url"
                fit="cover"
                class="preview-img"
                :preview-src-list="form.attachments"
                :initial-index="idx"
                preview-teleported
                :z-index="3000"
              >
                <template #error>
                  <div class="preview-error">
                    <el-icon><PictureFilled /></el-icon>
                  </div>
                </template>
              </el-image>
              <button
                type="button"
                class="preview-remove"
                @click="removeAttachment(idx)"
              >
                <el-icon><Close /></el-icon>
              </button>
            </div>
          </div>
          <div v-else class="upload-hint">
            支持 PNG/JPG/GIF/WEBP，单张最大 20MB
          </div>
        </el-card>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  type FormInstance,
  type FormRules,
  type UploadRawFile,
  type UploadRequestOptions,
} from 'element-plus'
import {
  ArrowLeft,
  Check,
  Edit,
  Search,
  Delete,
  Plus,
  Close,
  RefreshRight,
  Picture,
  PictureFilled,
} from '@element-plus/icons-vue'
import { funcRequirementApi } from '@/api/funcTest'
import { knowledgeApi } from '@/api/knowledge'
import type { KbSearchHit } from '@/api/knowledge'
import { useKbAnswer } from '@/composables/useKbAnswer'
import { useMarkdown } from '@/composables/useMarkdown'
import type { RequirementPriority } from '@/types/func-test'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ---------- 表单 ----------
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  title: '',
  code: '',
  priority: 'medium' as RequirementPriority,
  description: '',
  acceptance_criteria: '',
  attachments: [] as string[],
})

const formRules: FormRules = {
  title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }],
}

function generateCode() {
  return `REQ-${projectId.value}-${Math.floor(Date.now() / 1000)
    .toString()
    .slice(-6)}`
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
const { render: renderMarkdown } = useMarkdown()

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
  form.description = form.description ? `${form.description}\n\n${block}` : block
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
  form.description = form.description ? `${form.description}\n\n${block}` : block
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

// ---------- 附件上传 ----------
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
    form.attachments.push(res.data.url)
    ElMessage.success('上传成功')
  } catch (err) {
    console.error(err)
  }
}

function removeAttachment(idx: number) {
  form.attachments.splice(idx, 1)
}

// ---------- 提交 ----------
async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const res = await funcRequirementApi.create(projectId.value, {
      title: form.title,
      code: form.code || undefined,
      priority: form.priority,
      description: form.description || undefined,
      acceptance_criteria: form.acceptance_criteria || undefined,
      attachments: form.attachments.length ? form.attachments : undefined,
    })
    ElMessage.success('需求创建成功')
    // 创建成功后跳转到详情页
    router.push({
      name: 'FuncTestRequirementDetail',
      params: { id: projectId.value, reqId: res.data.id },
    })
  } catch (err) {
    console.error(err)
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'FuncTestRequirements', params: { id: projectId.value } })
}
</script>

<style scoped>
.requirement-create-page {
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
  margin: 0 0 4px 0;
}

.header-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

/* 主体布局 */
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

/* 卡片内 label */
.form-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.side-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
}

.side-label.required::after {
  content: '*';
  color: var(--el-color-danger);
  margin-left: 2px;
}

.count-badge {
  margin-left: auto;
  padding: 1px 8px;
  background: var(--theme-color-ecf5ff);
  color: var(--el-color-info);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 描述卡 */
.desc-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

/* RAG 面板 */
.rag-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rag-search-bar {
  display: flex;
  gap: 8px;
}

.rag-search-bar .el-input {
  flex: 1;
}

/* AI 综合结果卡片 */
.rag-answer {
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  padding: 12px 14px;
}

.rag-answer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.rag-answer-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.rag-answer-status {
  font-weight: normal;
  color: var(--el-text-color-secondary);
}

.rag-answer-status.is-warn {
  color: var(--el-color-warning);
}

.rag-answer-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-primary);
  overflow-wrap: anywhere;
}

.rag-answer-body :deep(p) {
  margin: 0 0 8px;
}

.rag-answer-body :deep(ul),
.rag-answer-body :deep(ol) {
  margin: 0 0 8px;
  padding-left: 18px;
}

.rag-answer-body :deep(h1),
.rag-answer-body :deep(h2),
.rag-answer-body :deep(h3),
.rag-answer-body :deep(h4) {
  font-size: 13px;
  font-weight: 700;
  margin: 10px 0 6px;
}

.rag-answer-body :deep(table) {
  border-collapse: collapse;
  margin: 6px 0;
}

.rag-answer-body :deep(th),
.rag-answer-body :deep(td) {
  border: 1px solid var(--el-border-color-lighter);
  padding: 4px 8px;
  font-size: 12px;
}

.rag-answer-body :deep(pre) {
  background: var(--theme-color-fafbfc);
  border-radius: 6px;
  padding: 8px;
  overflow-x: auto;
  margin: 6px 0;
}

.rag-answer-body :deep(code) {
  font-size: 12px;
}

.rag-answer-placeholder {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.rag-answer-refs {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.rag-results-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.rag-results-title .hint {
  font-weight: normal;
  color: var(--el-text-color-secondary);
}

.rag-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rag-result-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  cursor: pointer;
  background: var(--theme-color-fafbfc);
  transition: all 0.2s;
}

.rag-result-item:hover {
  border-color: var(--el-color-info);
  background: var(--theme-color-f5f9ff);
  box-shadow: 0 2px 6px rgba(var(--theme-rgb-64-158-255), 0.1);
}

.rag-result-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--theme-color-ecf5ff);
  color: var(--el-color-info);
  font-size: 11px;
  font-weight: 700;
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
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
  white-space: pre-wrap;
}

.rag-result-item.is-adopted {
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}

.rag-result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  min-width: 0;
}

.rag-result-doc {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rag-result-path {
  font-size: 11px;
  color: var(--el-color-info);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.rag-result-adopted {
  flex-shrink: 0;
  align-self: center;
  font-size: 16px;
  color: var(--el-color-success);
}

.rag-preview {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
  background: var(--theme-color-fafbfc);
}

.rag-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: var(--theme-color-f7f8fa);
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.rag-preview-content {
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  max-height: 180px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* 需求编号 */
.req-id-row {
  display: flex;
  gap: 6px;
  width: 100%;
}

.req-id-row > :first-child {
  flex: 1;
}

/* 附件上传 */
.upload-trigger-wrap {
  width: 100%;
}

.upload-trigger-wrap :deep(.el-upload) {
  width: 100%;
}

.upload-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 10px;
  border: 1.5px dashed var(--el-text-color-disabled);
  border-radius: 6px;
  background: var(--theme-color-fafbfc);
  color: var(--el-text-color-regular);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-trigger:hover {
  border-color: var(--el-color-info);
  color: var(--el-color-info);
  background: var(--theme-color-f5f9ff);
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 10px;
}

.preview-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
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
  background: var(--theme-color-f7f8fa);
  color: var(--el-text-color-disabled);
  font-size: 26px;
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
  background: rgba(var(--theme-rgb-black), 0.5);
  color: var(--theme-white);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.preview-item:hover .preview-remove {
  opacity: 1;
}

.upload-hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.select-with-tag {
  display: inline-flex;
  align-items: center;
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
