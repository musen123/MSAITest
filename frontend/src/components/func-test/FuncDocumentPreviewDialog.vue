<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="1100px"
    top="5vh"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="preview-dialog">
      <!-- 左：原文预览 -->
      <div class="preview-left">
        <div class="panel-title">
          <el-icon><Document /></el-icon>
          <span>原始文档</span>
          <span class="hint" v-if="preview">.{{ preview.file_ext.replace('.', '') }}</span>
        </div>
        <div class="panel-body">
          <template v-if="!preview">
            <el-empty description="加载中..." />
          </template>

          <!-- PDF/图片：iframe / img -->
          <template v-else-if="preview.preview_type === 'url'">
            <template v-if="isImage(preview.file_ext)">
              <img :src="preview.url || undefined" class="preview-img" />
            </template>
            <template v-else>
              <iframe
                v-if="preview.url"
                :src="preview.url"
                class="preview-iframe"
                frameborder="0"
              ></iframe>
            </template>
          </template>

          <!-- Word 已转 HTML -->
          <div
            v-else-if="preview.preview_type === 'html'"
            class="preview-html"
            v-html="sanitizeHtml(preview.content || '')"
          ></div>

          <!-- Markdown -->
          <div
            v-else-if="preview.preview_type === 'markdown'"
            class="preview-md"
            v-html="renderMarkdown(preview.content || '')"
          ></div>

          <!-- 纯文本 -->
          <pre
            v-else-if="preview.preview_type === 'text'"
            class="preview-text"
          >{{ preview.content || '' }}</pre>

          <!-- 不支持 -->
          <div v-else class="unsupported">
            <el-icon :size="48"><WarningFilled /></el-icon>
            <p>该文件格式暂不支持在线预览</p>
            <el-button v-if="preview.url" type="primary" plain @click="downloadFile">
              下载查看
            </el-button>
          </div>
        </div>
      </div>

      <!-- 右：AI 解析后的 Markdown -->
      <div class="preview-right">
        <div class="panel-title parsed-title">
          <el-icon><MagicStick /></el-icon>
          <span>AI 解析结果（Markdown）</span>
          <el-tag v-if="parseStatus === 'parsed'" type="success" size="small">已解析</el-tag>
          <el-tag v-else-if="parseStatus === 'parsing'" type="warning" size="small">解析中</el-tag>
          <el-tag v-else-if="parseStatus === 'failed'" type="danger" size="small">失败</el-tag>
          <el-tag v-else type="info" size="small">未解析</el-tag>
          <div class="title-actions">
            <el-button
              v-if="preview?.parsed_content"
              size="small"
              type="primary"
              plain
              @click="copyParsed"
            >
              <el-icon><CopyDocument /></el-icon>
              复制
            </el-button>
          </div>
        </div>
        <div class="panel-body">
          <template v-if="preview?.parsed_content">
            <div class="preview-md" v-html="renderMarkdown(preview.parsed_content)"></div>
          </template>
          <template v-else>
            <el-empty :image-size="64">
              <template #description>
                <span v-if="parseStatus === 'failed'">解析失败：{{ parseError || '请重试' }}</span>
                <span v-else-if="parseStatus === 'parsing'">正在解析中...</span>
                <span v-else>尚未 AI 解析，点击下方按钮触发解析</span>
              </template>
              <el-button
                v-if="parseStatus !== 'parsing'"
                type="primary"
                :loading="parsing"
                @click="$emit('trigger-parse')"
              >
                <el-icon><MagicStick /></el-icon>
                {{ parseStatus === 'failed' ? '重新解析' : 'AI 解析' }}
              </el-button>
            </el-empty>
          </template>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="footer-hint">提示：AI 解析后的内容可一键导入到「项目知识库」</span>
      <el-button @click="visible = false">关闭</el-button>
      <el-button
        v-if="preview?.parsed_content"
        type="success"
        :loading="ingesting"
        @click="$emit('trigger-ingest')"
      >
        <el-icon><Upload /></el-icon>
        导入知识库
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { sanitizeHtml } from '@/utils/sanitizeHtml'
import {
  Document,
  MagicStick,
  WarningFilled,
  CopyDocument,
  Upload,
} from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import type { FuncDocumentPreview } from '@/types/func-test'

const props = defineProps<{
  modelValue: boolean
  preview: FuncDocumentPreview | null
  loading?: boolean
  parsing?: boolean
  ingesting?: boolean
  parseStatus?: 'pending' | 'parsing' | 'parsed' | 'failed'
  parseError?: string | null
  fileNameTitle?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  'trigger-parse': []
  'trigger-ingest': []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const dialogTitle = computed(() =>
  props.fileNameTitle ? `预览：${props.fileNameTitle}` : '文档预览',
)

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    return sanitizeHtml(md.render(text))
  } catch {
    return ''
  }
}

function isImage(ext: string): boolean {
  return ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'].includes(
    ext.toLowerCase(),
  )
}

function downloadFile() {
  if (props.preview?.url) {
    window.open(props.preview.url, '_blank')
  }
}

async function copyParsed() {
  const text = props.preview?.parsed_content
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制 Markdown')
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.preview-dialog {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  height: 70vh;
}

.preview-left,
.preview-right {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--el-fill-color-blank);
  border-bottom: 1px solid var(--el-border-color-light);
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.panel-title .hint {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  background: var(--el-fill-color);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
}

.parsed-title {
  color: var(--theme-color-6366f1);
}

.title-actions {
  margin-left: auto;
}

.panel-body {
  flex: 1;
  overflow: auto;
  padding: 14px;
  background: var(--el-bg-color);
}

.preview-img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 0 auto;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  min-height: 60vh;
  border: 0;
}

.preview-html,
.preview-md {
  font-size: 14px;
  line-height: 1.75;
  color: var(--el-text-color-primary);
}

.preview-md :deep(h1),
.preview-md :deep(h2),
.preview-md :deep(h3),
.preview-html :deep(h1),
.preview-html :deep(h2),
.preview-html :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
}

.preview-md :deep(code),
.preview-html :deep(code) {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.preview-md :deep(pre),
.preview-html :deep(pre) {
  background: var(--theme-color-1e1e1e);
  color: var(--theme-color-d4d4d4);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
}

.preview-md :deep(table),
.preview-html :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.preview-md :deep(th),
.preview-md :deep(td),
.preview-html :deep(th),
.preview-html :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 6px 10px;
  font-size: 13px;
}

.preview-md :deep(blockquote),
.preview-html :deep(blockquote) {
  border-left: 4px solid var(--el-color-primary-light-5);
  padding-left: 12px;
  color: var(--el-text-color-secondary);
  margin: 8px 0;
}

.preview-text {
  white-space: pre-wrap;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  color: var(--el-text-color-primary);
  margin: 0;
}

.unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--el-text-color-placeholder);
}

.footer-hint {
  margin-right: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
