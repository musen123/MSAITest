<template>
  <div class="text-block" :class="`status-${block.status}`">
    <div
      v-if="block.content"
      class="text-content markdown-body"
      v-html="renderedContent"
    />
    <span v-if="block.status === 'streaming'" class="cursor">▍</span>
    <div v-if="block.status === 'interrupted'" class="status-tag interrupted">
      <i class="i-solar-info-circle-linear" />
      已中断
    </div>
    <div v-if="block.status === 'error'" class="status-tag error">
      <i class="i-solar-danger-triangle-bold" />
      失败
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMarkdown } from '@/composables/useMarkdown'
import type { UiBlock } from '@/types/chat'

const props = defineProps<{ block: UiBlock }>()

const { render } = useMarkdown()

const renderedContent = computed(() => render(props.block.content || ''))
</script>

<style scoped>
.text-block {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text-primary);
  word-break: break-word;
}

.text-content {
  display: inline;
}

.cursor {
  display: inline-block;
  color: var(--brand-500);
  font-weight: 400;
  animation: blink 1s steps(2, start) infinite;
  margin-left: 2px;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.status-tag.interrupted {
  color: var(--color-warning-600);
  background: var(--color-warning-50);
}

.status-tag.error {
  color: var(--color-danger-600);
  background: var(--color-danger-50);
}

/* Markdown */
.markdown-body :deep(p) {
  margin: 4px 0;
}
.markdown-body :deep(p:first-child) {
  margin-top: 0;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0;
  padding-left: 22px;
}
.markdown-body :deep(li) {
  margin: 2px 0;
}
.markdown-body :deep(code) {
  background: var(--gray-100);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
}
.markdown-body :deep(pre) {
  background: #1e1e2e;
  color: #d4d4d8;
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 6px 0;
}
.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 8px 0 4px;
  font-weight: 600;
}
.markdown-body :deep(h1) {
  font-size: 16px;
}
.markdown-body :deep(h2) {
  font-size: 15px;
}
.markdown-body :deep(h3) {
  font-size: 14px;
}
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--border-light);
  padding: 4px 12px;
  margin: 6px 0;
  color: var(--text-secondary);
  background: var(--gray-50);
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  font-size: 12px;
  margin: 6px 0;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--border-light);
  padding: 4px 8px;
}
.markdown-body :deep(th) {
  background: var(--gray-50);
}
</style>
