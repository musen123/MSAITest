<template>
  <div ref="scrollEl" class="message-list">
    <div v-if="messages.length === 0" class="empty-state">
      <img :src="aiChatIllustration" alt="AI 助手" class="empty-illustration" />
      <div class="empty-title">我是小测，这个平台的智能助手</div>
      <div class="empty-desc">
        查数据、跑测试、生成用例、记缺陷、管定时计划，都可以直接吩咐我
      </div>
      <div class="empty-suggestions">
        <button
          v-for="s in suggestions"
          :key="s"
          class="suggestion"
          @click="$emit('suggest', s)"
        >
          {{ s }}
        </button>
      </div>
    </div>

    <template v-else>
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message-row"
        :class="`role-${msg.role}`"
      >
        <!-- 头像 -->
        <div class="avatar">
          <i v-if="msg.role === 'assistant'" class="i-solar-cpu-bolt-bold" />
          <i v-else-if="msg.role === 'user'" class="i-solar-user-bold" />
          <i v-else class="i-solar-settings-bold" />
        </div>

        <!-- 内容 -->
        <div class="bubble">
          <!-- user / system：纯文本 -->
          <template v-if="msg.role !== 'assistant'">
            <div class="user-content">{{ msg.content }}</div>
          </template>

          <!-- assistant：blocks -->
          <template v-else>
            <div v-if="msg.blocks && msg.blocks.length" class="blocks">
              <template v-for="block in msg.blocks" :key="block.id">
                <ThinkingBlock v-if="block.type === 'thinking'" :block="block" />
                <ToolCallCard v-else-if="block.type === 'tool'" :block="block" />
                <TextBlock v-else :block="block" />
              </template>
            </div>
            <!-- 还在 streaming 但还没有任何块 -->
            <div v-else-if="msg.streaming" class="loading-dots">
              <span></span><span></span><span></span>
            </div>
            <!-- 兜底：纯文本 -->
            <div v-else-if="msg.content" class="text-content">{{ msg.content }}</div>
          </template>

          <div class="meta">
            <span>{{ formatTime(msg.createdAt) }}</span>
            <span v-if="msg.interrupted" class="meta-interrupted">已中断</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import dayjs from 'dayjs'
import TextBlock from './TextBlock.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import type { UiMessage } from '@/types/chat'
import aiChatIllustration from '@/assets/illustrations/ai-chat.svg'

const props = defineProps<{ messages: UiMessage[] }>()
defineEmits<{ (e: 'suggest', text: string): void }>()

const scrollEl = ref<HTMLElement | null>(null)

const suggestions = [
  '看看这个项目的整体情况',
  '最近 7 天的测试执行情况怎么样？',
  '有哪些待评审的用例？',
  '帮我查找 App 测试套件',
]

function formatTime(t: string) {
  return dayjs(t).format('HH:mm')
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight
    }
  })
}

onMounted(scrollToBottom)
watch(
  () => props.messages.length,
  () => scrollToBottom(),
)
watch(
  () => {
    // 监听最后一条消息的总字符变化，触发自动滚动
    const last = props.messages[props.messages.length - 1]
    if (!last) return ''
    const blockText = (last.blocks || [])
      .map((b) => b.content)
      .join('')
    return last.content + blockText
  },
  () => scrollToBottom(),
)
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--gray-50);
}

/* ============ 空状态 ============ */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: var(--text-secondary);
}

.empty-illustration {
  width: 290px;
  max-width: 52%;
  height: auto;
  margin-bottom: 18px;
  filter: drop-shadow(0 12px 28px var(--brand-glow-soft));
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  margin-bottom: 16px;
}

.empty-list {
  margin: 6px 0 16px;
  padding-left: 0;
  list-style: none;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.empty-list li::before {
  content: '· ';
  color: var(--brand-500);
}

.empty-suggestions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  max-width: 320px;
}

.suggestion {
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.suggestion:hover {
  border-color: var(--brand-500);
  background: var(--brand-50);
  color: var(--brand-600);
}

/* ============ 消息行 ============ */
.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message-row.role-user {
  flex-direction: row-reverse;
}

.avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #fff;
  background: var(--text-placeholder);
}

.role-user .avatar {
  background: var(--color-success-500);
}

.role-assistant .avatar {
  background: linear-gradient(135deg, var(--brand-500), var(--brand-600));
}

.role-system .avatar {
  background: var(--text-secondary);
}

.bubble {
  max-width: 88%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

/* assistant 回复固定占对话区 90% 宽度（不随内容收缩） */
.role-assistant .bubble {
  width: 90%;
  max-width: 90%;
}

.role-user .bubble {
  align-items: flex-end;
}

/* user 消息气泡 */
.user-content {
  padding: 10px 14px;
  background: var(--brand-500);
  color: #fff;
  border-radius: 12px 12px 4px 12px;
  font-size: 13.5px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

/* assistant blocks */
.blocks {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px 12px 12px 4px;
  min-width: 100px;
}

.text-content {
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px 12px 12px 4px;
  font-size: 13.5px;
  line-height: 1.6;
  word-break: break-word;
}

/* loading dots */
.loading-dots {
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px 12px 12px 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  background: var(--text-placeholder);
  border-radius: 50%;
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.15s;
}
.loading-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes dot-bounce {
  0%,
  80%,
  100% {
    transform: scale(0.7);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-placeholder);
  padding: 0 4px;
}

.meta-interrupted {
  color: var(--color-warning-600);
}
</style>
