<template>
  <div class="encoder-page">
    <!-- 页头 -->
    <AppPageHeader
      icon="i-solar-link-bold"
      :illustration="illustTools"
      title="编解码工具"
      description="URL / Base64 / Hex / Unicode / HTML 编解码"
      :breadcrumbs="['工具箱', '编解码工具']"
    />

    <!-- 编码类型选择 -->
    <div class="codec-tabs">
      <div
        v-for="c in codecs"
        :key="c.name"
        class="codec-tab"
        :class="{ active: activeTab === c.name }"
        @click="activeTab = c.name"
      >
        <i :class="codecIcons[c.name]" />
        <span>{{ c.name }}</span>
      </div>
    </div>

    <!-- 编码区 -->
    <AppSectionCard class="codec-content" content-class="codec-body">
      <template #header>
        <div class="panel-hd">
          <div class="panel-hd-left">
            <i class="i-solar-import-bold hd-icon" />
            <span class="hd-title">{{ activeCodec.name }} 输入</span>
            <span v-if="io[activeTab].input" class="hd-meta">
              {{ io[activeTab].input.length }} 字符
            </span>
          </div>
          <el-button size="small" link @click="io[activeTab].input = ''; io[activeTab].output = ''">
            <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
            清空
          </el-button>
        </div>
      </template>
      <el-input
        v-model="io[activeTab].input"
        type="textarea"
        :rows="6"
        :placeholder="activeCodec.placeholder"
        resize="none"
        class="io-textarea"
      />
    </AppSectionCard>

    <!-- 操作行 -->
    <div class="action-row">
      <el-button type="primary" @click="encode(activeTab)">
        <i class="i-solar-lock-password-bold btn-icon" />
        {{ activeCodec.encodeLabel }}
        <i class="i-solar-alt-arrow-right-bold btn-icon-right" />
      </el-button>
      <el-button @click="decode(activeTab)">
        <i class="i-solar-unlock-bold btn-icon" />
        {{ activeCodec.decodeLabel }}
      </el-button>
      <el-button @click="swap(activeTab)">
        <i class="i-solar-swap-horizontal-bold btn-icon" />
        交换
      </el-button>
      <div style="flex:1" />
      <el-button v-if="io[activeTab].output" type="success" plain @click="copy(io[activeTab].output)">
        <i class="i-solar-copy-bold btn-icon" />
        复制结果
      </el-button>
    </div>

    <!-- 输出区 -->
    <AppSectionCard class="codec-content" content-class="codec-body">
      <template #header>
        <div class="panel-hd">
          <div class="panel-hd-left">
            <i class="i-solar-export-bold hd-icon" />
            <span class="hd-title">{{ activeCodec.name }} 输出</span>
            <span v-if="io[activeTab].output" class="hd-meta">
              {{ io[activeTab].output.length }} 字符
            </span>
          </div>
        </div>
      </template>
      <pre v-if="io[activeTab].output" class="output-text">{{ io[activeTab].output }}</pre>
      <div v-else class="output-placeholder">
        <i class="i-solar-document-text-linear placeholder-icon" />
        <span>结果将在此显示</span>
      </div>
    </AppSectionCard>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { AppPageHeader, AppSectionCard } from '@/components/common'
import illustTools from '@/assets/illustrations/tools.svg'

const codecs = [
  { name: 'URL', encodeLabel: 'URL 编码', decodeLabel: 'URL 解码', placeholder: '输入 URL 或文本...' },
  { name: 'Base64', encodeLabel: 'Base64 编码', decodeLabel: 'Base64 解码', placeholder: '输入文本或 Base64 字符串...' },
  { name: 'Hex', encodeLabel: '文本 → Hex', decodeLabel: 'Hex → 文本', placeholder: '输入文本或 Hex 字符串（如 48 65 6c 6c 6f）...' },
  { name: 'Unicode', encodeLabel: 'Unicode 编码', decodeLabel: 'Unicode 解码', placeholder: '输入文本或 \\uXXXX 字符串...' },
  { name: 'HTML', encodeLabel: 'HTML 编码', decodeLabel: 'HTML 解码', placeholder: '输入 <div>HTML</div> 文本...' },
]

const codecIcons: Record<string, string> = {
  URL: 'i-solar-link-bold',
  Base64: 'i-solar-key-bold',
  Hex: 'i-solar-hash-bold',
  Unicode: 'i-solar-code-bold',
  HTML: 'i-solar-code-circle-bold',
}

const activeTab = ref('URL')
const io = reactive<Record<string, { input: string; output: string }>>(
  Object.fromEntries(codecs.map(c => [c.name, { input: '', output: '' }]))
)

const activeCodec = computed(() => codecs.find(c => c.name === activeTab.value)!)

function copy(t: string) { navigator.clipboard.writeText(t).then(() => ElMessage.success('已复制')) }

function encode(name: string) {
  const v = io[name].input
  if (!v) { io[name].output = ''; return }
  try {
    switch (name) {
      case 'URL': io[name].output = encodeURI(v); break
      case 'Base64': io[name].output = btoa(unescape(encodeURIComponent(v))); break
      case 'Hex': io[name].output = Array.from(new TextEncoder().encode(v)).map(b => b.toString(16).padStart(2, '0')).join(' '); break
      case 'Unicode': io[name].output = v.split('').map(c => c.charCodeAt(0) > 127 ? '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0') : c).join(''); break
      case 'HTML': { const d = document.createElement('div'); d.textContent = v; io[name].output = d.innerHTML; break }
    }
  } catch { ElMessage.error('编码失败，请检查输入') }
}

function decode(name: string) {
  const v = io[name].input
  if (!v) { io[name].output = ''; return }
  try {
    switch (name) {
      case 'URL': io[name].output = decodeURIComponent(v); break
      case 'Base64': io[name].output = decodeURIComponent(escape(atob(v))); break
      case 'Hex': {
        const parts = v.trim().split(/\s+/)
        const bytes = parts.map(h => { const n = parseInt(h, 16); if (isNaN(n)) throw new Error(); return n })
        io[name].output = new TextDecoder().decode(new Uint8Array(bytes))
        break
      }
      case 'Unicode': io[name].output = JSON.parse('"' + v.replace(/"/g, '\\"') + '"'); break
      case 'HTML': { const d = document.createElement('div'); d.innerHTML = v; io[name].output = d.textContent || ''; break }
    }
  } catch { ElMessage.error('解码失败，请检查输入格式是否正确') }
}

function swap(name: string) {
  const t = io[name].input
  io[name].input = io[name].output
  io[name].output = t
}
</script>

<style scoped lang="scss">
.encoder-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
}

.btn-icon {
  margin-right: 6px;
  font-size: 14px;
  vertical-align: -2px;
}
.btn-icon-right {
  margin-left: 4px;
  font-size: 14px;
  vertical-align: -2px;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 编码类型 Tabs ============ */
.codec-tabs {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.codec-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.18s ease;

  i { font-size: 14px; }

  &:hover {
    color: var(--brand-500);
    border-color: var(--brand-300);
  }

  &.active {
    background: var(--color-brand-50);
    border-color: var(--brand-500);
    color: var(--brand-600);
    font-weight: var(--font-weight-semibold);
  }
}

/* ============ 卡片内容 ============ */
.codec-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.codec-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  min-height: 0;
}

/* ============ 面板头 ============ */
.panel-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.panel-hd-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.hd-icon {
  font-size: 16px;
  color: var(--brand-500);
}
.hd-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.hd-meta {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: var(--font-weight-regular);
}

/* ============ 输入框 ============ */
.io-textarea {
  flex: 1;
  display: flex;
}
.io-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: var(--space-3) var(--space-4);
  height: 100% !important;
}

/* ============ 输出框 ============ */
.output-text {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  flex: 1;
  background: var(--bg-card);
}

.output-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-placeholder);
  font-size: 13px;
  padding: var(--space-6);
}
.placeholder-icon {
  font-size: 36px;
  color: var(--gray-300);
}

/* ============ 操作行 ============ */
.action-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
</style>
