<template>
  <div class="understand-panel">
    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="action-info">
        <el-icon class="action-icon"><MagicStick /></el-icon>
        <div class="action-text">
          <div class="title">AI 需求理解</div>
          <div class="subtitle">
            VLM 逐张理解附件图片，再由 LLM 整合为结构化 Markdown 需求
          </div>
        </div>
      </div>
      <div class="action-buttons">
        <el-button
          v-if="understand.phase.value === 'running'"
          type="danger"
          plain
          @click="understand.abort"
        >
          <el-icon><Close /></el-icon>
          中止
        </el-button>
        <el-button
          v-else
          :type="understand.phase.value === 'done' ? 'success' : 'primary'"
          :loading="false"
          :disabled="!canStart"
          @click="handleStart"
        >
          <el-icon><MagicStick /></el-icon>
          {{
            understand.phase.value === 'done' || understand.phase.value === 'error'
              ? '重新理解'
              : '开始理解'
          }}
        </el-button>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="understand.phase.value !== 'idle'" class="progress-section">
      <div class="progress-header">
        <span class="progress-label">
          <span v-if="understand.phase.value === 'running'">理解进度</span>
          <span v-else-if="understand.phase.value === 'done'">已完成</span>
          <span v-else-if="understand.phase.value === 'error'">失败</span>
          <span v-else-if="understand.phase.value === 'aborted'">已中止</span>
        </span>
        <span class="progress-stat">
          {{ understand.doneImages.value }}/{{ understand.totalImages.value || '?' }}
          张图片
          <span v-if="understand.summaryStatus.value !== 'idle'" class="step-sep">
            ·
          </span>
          <span v-if="understand.summaryStatus.value === 'streaming'">总结中...</span>
          <span v-else-if="understand.summaryStatus.value === 'done'">总结完成</span>
          <el-link
            v-if="understand.taskId.value != null"
            type="primary"
            :underline="false"
            class="task-link"
            @click="goTaskDetail"
          >
            <el-icon><TopRight /></el-icon>
            任务中心查看
          </el-link>
        </span>
      </div>
      <el-progress
        :percentage="understand.progress.value"
        :status="progressStatus"
        :stroke-width="8"
      />
    </div>

    <!-- 错误提示 -->
    <el-alert
      v-if="understand.phase.value === 'error'"
      :title="understand.errorMessage.value"
      type="error"
      show-icon
      :closable="false"
      class="error-alert"
    />

    <!-- 无附件 -->
    <el-empty
      v-if="understand.phase.value === 'idle' && attachments.length === 0 && !requirementDescription"
      description="该需求暂无描述和附件，请先编辑需求或上传图片附件"
    />

    <!-- 图片理解卡片列表 -->
    <div v-if="understand.images.value.length > 0" class="images-section">
      <div class="section-title">
        <el-icon><Picture /></el-icon>
        图片理解
      </div>
      <div class="image-cards">
        <el-card
          v-for="img in understand.images.value"
          :key="img.index"
          shadow="never"
          class="image-card"
        >
          <div class="image-card-header">
            <el-image
              :src="img.url"
              fit="cover"
              class="image-thumb"
              :preview-src-list="[img.url]"
              preview-teleported
              :z-index="3000"
            >
              <template #error>
                <div class="image-error">
                  <el-icon><PictureFilled /></el-icon>
                </div>
              </template>
            </el-image>
            <div class="image-info">
              <div class="image-title">
                图片 {{ img.index + 1 }}
                <span class="image-index">/ {{ understand.totalImages.value }}</span>
              </div>
              <div class="image-status">
                <el-tag :type="imgStatusTag(img.status)" size="small">
                  <el-icon v-if="img.status === 'streaming'" class="rotating">
                    <Loading />
                  </el-icon>
                  <el-icon v-else-if="img.status === 'done'">
                    <CircleCheckFilled />
                  </el-icon>
                  <el-icon v-else-if="img.status === 'error'">
                    <CircleCloseFilled />
                  </el-icon>
                  {{ imgStatusLabel(img.status) }}
                </el-tag>
                <span v-if="img.status === 'streaming'" class="streaming-hint">
                  正在识别...
                </span>
              </div>
            </div>
          </div>
          <div
            v-if="img.content"
            class="image-content markdown-body"
            v-html="renderMarkdown(img.content)"
          />
        </el-card>
      </div>
    </div>

    <!-- LLM 总结区 -->
    <div v-if="understand.summaryStatus.value !== 'idle'" class="summary-section">
      <div class="section-title">
        <el-icon><EditPen /></el-icon>
        AI 整理后的需求
        <el-tag
          v-if="understand.summaryStatus.value === 'streaming'"
          type="warning"
          size="small"
        >
          <el-icon class="rotating"><Loading /></el-icon>
          整理中...
        </el-tag>
        <el-tag v-else-if="understand.summaryStatus.value === 'done'" type="success" size="small">
          完成
        </el-tag>
      </div>
      <el-card shadow="never" class="summary-card">
        <div
          v-if="understand.summaryContent.value"
          class="summary-content markdown-body"
          v-html="renderMarkdown(understand.summaryContent.value)"
        />
        <el-empty
          v-else-if="understand.summaryStatus.value === 'streaming'"
          description="等待第一个 token..."
          :image-size="60"
        />
      </el-card>
    </div>

    <!-- 完成后的操作 -->
    <div v-if="understand.phase.value === 'done'" class="footer-actions">
      <el-alert
        title="AI 理解结果已自动保存到「understood_content」字段"
        type="success"
        :closable="false"
        show-icon
      />
      <div class="footer-buttons">
        <el-button @click="$emit('reload')">
          <el-icon><Refresh /></el-icon>
          刷新需求
        </el-button>
        <el-button type="primary" @click="$emit('go-generate-cases')">
          <el-icon><MagicStick /></el-icon>
          基于此理解生成用例
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  MagicStick,
  Picture,
  PictureFilled,
  Close,
  Loading,
  CircleCheckFilled,
  CircleCloseFilled,
  EditPen,
  Refresh,
  TopRight,
} from '@element-plus/icons-vue'
import { useRequirementUnderstand, type ImageItemStatus } from '@/composables/useRequirementUnderstand'
import { useMarkdown } from '@/composables/useMarkdown'

const props = defineProps<{
  projectId: number
  requirementId: number
  attachments: string[]
  requirementDescription: string
  requirementTitle?: string
}>()

const emit = defineEmits<{
  (e: 'reload'): void
  (e: 'go-generate-cases'): void
}>()
// 显式声明 emit 用于 v-on 调用，让 typescript 不警告
void emit

const router = useRouter()

const understand = useRequirementUnderstand(
  () => props.projectId,
  () => props.requirementId,
  () => props.attachments,
  () => props.requirementTitle || '',
)

function goTaskDetail() {
  if (understand.taskId.value == null) return
  router.push({
    name: 'AiTaskDetail',
    params: { id: props.projectId, taskId: understand.taskId.value },
  })
}

const { render: renderMarkdown } = useMarkdown()

const canStart = computed(() => {
  return (
    props.attachments.length > 0 || (props.requirementDescription || '').trim().length > 0
  )
})

const progressStatus = computed<'success' | 'exception' | undefined>(() => {
  if (understand.phase.value === 'done') return 'success'
  if (understand.phase.value === 'error') return 'exception'
  return undefined
})

async function handleStart() {
  await understand.start({})
}

// ---------- 工具 ----------
function imgStatusLabel(s: ImageItemStatus) {
  return (
    { pending: '等待', streaming: '识别中', done: '已完成', error: '失败' } as Record<
      string,
      string
    >
  )[s] || s
}

function imgStatusTag(s: ImageItemStatus): 'info' | 'warning' | 'success' | 'danger' {
  return (
    {
      pending: 'info',
      streaming: 'warning',
      done: 'success',
      error: 'danger',
    } as Record<string, 'info' | 'warning' | 'success' | 'danger'>
  )[s] || 'info'
}
</script>

<style scoped>
.understand-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: linear-gradient(135deg, var(--theme-color-f0f7ff) 0%, var(--theme-color-f7faff) 100%);
  border-radius: 8px;
  border: 1px solid var(--theme-color-e3edff);
}

.action-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-icon {
  font-size: 28px;
  color: var(--el-color-info);
  background: white;
  padding: 8px;
  border-radius: 50%;
}

.action-text .title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 2px;
}

.action-text .subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.progress-section {
  padding: 12px 16px;
  background: white;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.progress-stat {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.step-sep {
  margin: 0 6px;
  color: var(--el-border-color);
}

.task-link {
  margin-left: 10px;
  font-size: 12px;
  vertical-align: baseline;
}

.error-alert {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
}

.images-section {
  display: flex;
  flex-direction: column;
}

.image-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.image-card {
  border-radius: 8px;
}

.image-card-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.image-thumb {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  flex-shrink: 0;
  cursor: zoom-in;
}

.image-error {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-color-f7f8fa);
  color: var(--el-text-color-disabled);
  font-size: 28px;
  border-radius: 6px;
}

.image-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.image-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.image-index {
  font-weight: 400;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 4px;
}

.image-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.streaming-hint {
  font-size: 12px;
  color: var(--el-color-warning);
}

.image-content {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--theme-color-fafbfc);
  border-radius: 6px;
  border: 1px solid var(--theme-color-f0f0f0);
  font-size: 13px;
  line-height: 1.7;
  max-height: 280px;
  overflow-y: auto;
}

.summary-section {
  display: flex;
  flex-direction: column;
}

.summary-card {
  border-radius: 8px;
  background: var(--theme-color-fafbfc);
}

.summary-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}

.footer-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.footer-buttons {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.rotating {
  animation: rotate 1.2s linear infinite;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}

/* Markdown 样式 */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.markdown-body :deep(p) {
  margin: 6px 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 6px 0;
  padding-left: 22px;
}

.markdown-body :deep(li) {
  margin: 2px 0;
}

.markdown-body :deep(code) {
  background: var(--theme-color-f0f3f7);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
}

.markdown-body :deep(pre) {
  background: var(--theme-color-f7f8fa);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 4px 8px;
  font-size: 12px;
}

.markdown-body :deep(th) {
  background: var(--theme-color-f7f8fa);
  font-weight: 600;
}
</style>
