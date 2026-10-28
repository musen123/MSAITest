<template>
  <el-drawer
    :model-value="visible"
    :title="fileName"
    size="50%"
    destroy-on-close
    class="preview-drawer"
    @close="handleClose"
  >
    <div v-loading="loading" class="preview-container">
      <!-- PDF -->
      <iframe
        v-if="fileType === 'pdf'"
        :src="pdfBlobUrl + '#toolbar=1&navpanes=0'"
        class="preview-iframe"
      />

      <!-- 图片 -->
      <div v-else-if="fileType === 'image'" class="preview-image">
        <el-image :src="fileUrl" fit="contain" />
      </div>

      <!-- Markdown -->
      <div v-else-if="fileType === 'markdown'" class="preview-markdown" v-html="renderedContent" />

      <!-- Word -->
      <div v-else-if="fileType === 'word'" class="preview-word" v-html="renderedContent" />

      <!-- 代码类 (JSON / SQL / TXT 等) -->
      <div v-else-if="fileType === 'code'" class="preview-code">
        <codemirror
          :model-value="textContent"
          :style="{ height: '100%' }"
          :extensions="codeExtensions"
          readonly
        />
      </div>

      <!-- 不支持的类型 -->
      <div v-else class="preview-unsupported">
        <el-empty :description="`暂不支持预览 ${ext} 格式文件`">
          <el-button type="primary" @click="handleDownload">下载文件</el-button>
        </el-empty>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Codemirror as codemirror } from 'vue-codemirror'
import { json } from '@codemirror/lang-json'
import { sql } from '@codemirror/lang-sql'
import { markdown } from '@codemirror/lang-markdown'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { oneDark } from '@codemirror/theme-one-dark'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { sanitizeHtml } from '@/utils/sanitizeHtml'

const props = defineProps<{
  visible: boolean
  fileUrl: string
  fileName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const loading = ref(false)
const textContent = ref('')
const renderedContent = ref('')
const pdfBlobUrl = ref('')

const ext = computed(() => {
  const name = props.fileName || ''
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
})

const fileType = computed(() => {
  const e = ext.value
  if (e === '.pdf') return 'pdf'
  if (['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(e)) return 'image'
  if (e === '.md') return 'markdown'
  if (['.doc', '.docx'].includes(e)) return 'word'
  if (['.json', '.sql', '.txt', '.py', '.js', '.ts', '.html', '.css', '.yaml', '.yml', '.xml', '.sh', '.bash', '.md'].includes(e)) return 'code'
  return 'unknown'
})

const codeExtensions = computed(() => {
  const e = ext.value
  const exts: any[] = []
  if (e === '.json') exts.push(json())
  else if (e === '.sql') exts.push(sql())
  else if (e === '.md') exts.push(markdown())
  else if (e === '.py') exts.push(python())
  else if (['.js', '.ts'].includes(e)) exts.push(javascript())
  return exts
})

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(str: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch { /* fallback */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  },
})

async function loadContent() {
  if (!props.fileUrl) return

  const type = fileType.value
  if (type === 'image' || type === 'unknown') return

  loading.value = true
  try {
    if (type === 'pdf') {
      const resp = await fetch(props.fileUrl)
      const blob = await resp.blob()
      pdfBlobUrl.value = URL.createObjectURL(blob)
    } else if (type === 'word') {
      const resp = await fetch(props.fileUrl)
      const blob = await resp.blob()
      const mammoth = await import('mammoth')
      const result = await mammoth.default.convertToHtml({ arrayBuffer: await blob.arrayBuffer() })
      renderedContent.value = sanitizeHtml(result.value || '<p>文档内容为空</p>')
    } else if (type === 'markdown') {
      const resp = await fetch(props.fileUrl)
      const text = await resp.text()
      renderedContent.value = sanitizeHtml(md.render(text))
    } else {
      // code 类型
      const resp = await fetch(props.fileUrl)
      textContent.value = await resp.text()
    }
  } catch (err) {
    console.error('文档加载失败:', err)
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (val) => {
  if (val && props.fileUrl) loadContent()
})

function handleClose() {
  if (pdfBlobUrl.value) {
    URL.revokeObjectURL(pdfBlobUrl.value)
    pdfBlobUrl.value = ''
  }
  emit('update:visible', false)
}

function handleDownload() {
  if (props.fileUrl) {
    window.open(props.fileUrl, '_blank')
  }
}
</script>

<style lang="scss">
.preview-drawer {
  .el-drawer__body {
    padding: 0 !important;
  }
}
</style>

<style scoped lang="scss">
.preview-container {
  height: 100%;
  overflow: auto;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.preview-image {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;

  .el-image {
    max-width: 100%;
    max-height: 100%;
  }
}

.preview-markdown {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px 32px;
  line-height: 1.8;
  font-size: 15px;
  color: var(--theme-text-strong);

  :deep(h1) { font-size: 24px; margin: 24px 0 16px; border-bottom: 1px solid var(--el-border-color-light); padding-bottom: 8px; }
  :deep(h2) { font-size: 20px; margin: 20px 0 12px; border-bottom: 1px solid var(--el-border-color-light); padding-bottom: 6px; }
  :deep(h3) { font-size: 17px; margin: 16px 0 10px; }
  :deep(h4) { font-size: 15px; margin: 14px 0 8px; }

  :deep(p) { margin: 8px 0; }

  :deep(ul), :deep(ol) { padding-left: 24px; margin: 8px 0; }
  :deep(li) { margin: 4px 0; }

  :deep(code) {
    background: var(--el-fill-color-light);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    color: var(--theme-color-e11d48);
  }

  :deep(pre) {
    background: var(--theme-text-strong);
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    margin: 12px 0;

    code {
      background: none;
      color: var(--el-border-color-light);
      padding: 0;
      font-size: 13px;
      line-height: 1.6;
    }
  }

  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;

    th, td {
      border: 1px solid var(--el-border-color-light);
      padding: 8px 12px;
      text-align: left;
    }

    th { background: var(--el-fill-color-extra-light); font-weight: 600; }
    tr:nth-child(even) { background: var(--theme-color-fafbfc); }
  }

  :deep(blockquote) {
    border-left: 4px solid var(--theme-color-3b82f6);
    padding: 8px 16px;
    margin: 12px 0;
    background: var(--theme-info-bg);
    color: var(--el-text-color-regular);
  }

  :deep(a) { color: var(--theme-color-2563eb); text-decoration: none; }
  :deep(a:hover) { text-decoration: underline; }

  :deep(hr) { border: none; border-top: 1px solid var(--el-border-color-light); margin: 20px 0; }
}

.preview-word {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px 32px;
  line-height: 1.8;
  font-size: 15px;
  color: var(--theme-text-strong);

  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;

    th, td {
      border: 1px solid var(--el-border-color-light);
      padding: 6px 12px;
    }
  }

  :deep(img) { max-width: 100%; }
}

.preview-code {
  height: 100%;

  :deep(.cm-editor) {
    height: 100%;
    font-size: 14px;
  }

  :deep(.cm-scroller) {
    font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  }
}

.preview-unsupported {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
