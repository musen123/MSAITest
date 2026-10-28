<template>
  <div class="thinking-block" :class="`status-${block.status}`">
    <div class="thinking-header" @click="expanded = !expanded">
      <i
        v-if="block.status === 'streaming'"
        class="i-solar-refresh-linear thinking-icon rotating"
      />
      <i
        v-else-if="block.status === 'success'"
        class="i-solar-check-circle-bold thinking-icon"
      />
      <i v-else class="i-solar-info-circle-linear thinking-icon" />
      <span class="thinking-title">
        {{ block.status === 'streaming' ? '思考中...' : '已完成思考' }}
      </span>
      <span class="thinking-duration">{{ durationText }}</span>
      <i class="i-solar-alt-arrow-down-bold expand-icon" :class="{ expanded }" />
    </div>
    <div v-if="expanded && block.content" class="thinking-content">
      <pre>{{ block.content }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { UiBlock } from '@/types/chat'

const props = defineProps<{ block: UiBlock }>()

const expanded = ref(false)

const durationText = computed(() => {
  if (!props.block.endedAt) return '...'
  const ms = props.block.endedAt - props.block.startedAt
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
})
</script>

<style scoped>
.thinking-block {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--gray-50);
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.thinking-header:hover {
  background: var(--bg-card);
}

.thinking-icon {
  font-size: 14px;
  color: var(--text-secondary);
}

.status-streaming .thinking-icon {
  color: var(--brand-500);
}

.status-success .thinking-icon {
  color: var(--color-success-600);
}

.rotating {
  animation: rotate 1.2s linear infinite;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}

.thinking-title {
  flex: 1;
  font-size: 12.5px;
  color: var(--text-secondary);
  font-weight: 500;
}

.thinking-duration {
  font-size: 11px;
  color: var(--text-secondary);
}

.expand-icon {
  font-size: 12px;
  color: var(--text-placeholder);
  transition: transform 0.2s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.thinking-content {
  padding: 8px 12px 10px;
  border-top: 1px dashed var(--border-light);
  background: var(--gray-50);
}

.thinking-content pre {
  margin: 0;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}
</style>
