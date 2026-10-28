<template>
  <div class="chat-panel">
    <!-- 头部 -->
    <div class="panel-header">
      <div class="header-left">
        <el-tooltip content="历史会话">
          <el-button
            text
            size="small"
            :class="{ active: showDrawer }"
            @click="showDrawer = !showDrawer"
          >
            <i class="i-solar-sidebar-code-linear" />
          </el-button>
        </el-tooltip>
        <div class="title">
          <i class="i-solar-cpu-bolt-bold title-icon" />
          <span>{{ chatStore.activeConversation?.title || '小测' }}</span>
        </div>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          plain
          size="small"
          @click="handleNewConversation"
        >
          <i class="i-solar-add-circle-linear" style="margin-right: 4px" />
          新建会话
        </el-button>
        <slot name="header-actions" />
      </div>
    </div>

    <!-- 主体：左侧历史会话栏 + 消息列表 -->
    <div class="panel-body">
      <!-- 历史会话栏（左侧，默认展开，点头部按钮折叠） -->
      <Transition name="drawer">
        <div v-if="showDrawer" class="conv-drawer">
          <div class="drawer-toolbar">
            <span class="drawer-title">历史会话</span>
            <el-button text size="small" @click="loadConversations">
              <i class="i-solar-refresh-linear" />
            </el-button>
          </div>
          <div v-if="chatStore.loadingList" class="drawer-loading">
            <i class="i-solar-refresh-linear rotating" />
          </div>
          <div v-else-if="chatStore.conversations.length === 0" class="drawer-empty">
            暂无历史会话
          </div>
          <div v-else class="conv-list">
            <div
              v-for="conv in chatStore.conversations"
              :key="conv.id"
              class="conv-item"
              :class="{ active: conv.id === chatStore.activeConvId }"
              @click="switchConversation(conv.id)"
            >
              <div class="conv-item-main">
                <div class="conv-title">{{ conv.title }}</div>
                <div class="conv-time">{{ formatDate(conv.updated_at) }}</div>
              </div>
              <el-popconfirm
                :title="`删除会话「${conv.title}」?`"
                @confirm="deleteConversation(conv.id)"
              >
                <template #reference>
                  <el-button
                    text
                    size="small"
                    class="conv-delete"
                    @click.stop
                  >
                    <i class="i-solar-trash-bin-trash-linear" />
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </Transition>

      <!-- 消息流 -->
      <div class="message-area">
        <MessageList
          :messages="chatStore.messages"
          @suggest="onSuggest"
        />

        <!-- 输入框 -->
        <div class="input-area">
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 5 }"
              placeholder="发消息给小测（Enter 发送，Shift + Enter 换行）"
              :disabled="!chatStore.activeConvId || chatStore.streaming"
              resize="none"
              @keydown.enter.exact.prevent="onEnter"
              @keydown.meta.enter.prevent="sendMessage"
              @keydown.ctrl.enter.prevent="sendMessage"
            />
            <div class="input-actions">
              <span v-if="!chatStore.activeConvId" class="hint">
                暂无会话，点击右上「新建会话」
              </span>
              <el-button
                v-if="chatStore.streaming"
                type="danger"
                plain
                size="small"
                @click="handleInterrupt"
              >
                <i class="i-solar-close-circle-linear" />
                中断
              </el-button>
              <el-button
                v-else
                type="primary"
                size="small"
                :disabled="!inputText.trim() || !chatStore.activeConvId"
                @click="sendMessage"
              >
                <i class="i-solar-plain-2-bold" />
              发送
            </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { useChatStore } from '@/stores/chat'
import MessageList from './MessageList.vue'

const props = defineProps<{
  projectId: number
}>()

const chatStore = useChatStore()

const inputText = ref('')
const showDrawer = ref(true)

// ─────────────────────────────────────────────────────────
// 初始化
// ─────────────────────────────────────────────────────────

async function initialize() {
  // 切换项目时清理旧 state
  if (chatStore.activeProjectId !== props.projectId) {
    chatStore.reset()
  }
  await chatStore.loadConversations(props.projectId)
  // 自动选择最新的会话或新建一个
  const latest = chatStore.conversations[0]
  if (latest) {
    if (!chatStore.activeConvId) {
      await switchConversation(latest.id)
    }
  } else {
    // 自动创建第一个会话
    const conv = await chatStore.createConversation(props.projectId, '新对话')
    await switchConversation(conv.id)
  }
}

onMounted(initialize)

watch(
  () => props.projectId,
  (newId, oldId) => {
    if (newId !== oldId) {
      initialize()
    }
  },
)

// ─────────────────────────────────────────────────────────
// 会话切换
// ─────────────────────────────────────────────────────────

async function switchConversation(convId: number) {
  showDrawer.value = false
  await chatStore.connect(props.projectId, convId)
}

async function loadConversations() {
  await chatStore.loadConversations(props.projectId)
}

async function handleNewConversation() {
  // 免弹框直接创建，标题由首条消息自动命名
  const conv = await chatStore.createConversation(props.projectId, '新对话')
  await switchConversation(conv.id)
}

async function deleteConversation(convId: number) {
  await chatStore.deleteConversation(props.projectId, convId)
  ElMessage.success('已删除')
  // 删除当前活跃会话后自动切换
  const nextConversation = chatStore.conversations[0]
  if (chatStore.activeConvId === null && nextConversation) {
    await switchConversation(nextConversation.id)
  } else if (chatStore.conversations.length === 0) {
    const conv = await chatStore.createConversation(props.projectId, '新对话')
    await switchConversation(conv.id)
  }
}

// ─────────────────────────────────────────────────────────
// 发送消息
// ─────────────────────────────────────────────────────────

function onEnter(ev: KeyboardEvent) {
  // 单 Enter 直接发送；Shift+Enter 走 textarea 原生换行（exact 不会命中此处）
  // 输入法组合态的 Enter 是在确认候选词，不发送
  if (ev.isComposing) return
  sendMessage()
}

function sendMessage() {
  const text = inputText.value.trim()
  if (!text || !chatStore.activeConvId) return
  // 全新会话的首条消息自动当作会话标题（替代弹框输入）
  const conv = chatStore.activeConversation
  if (conv && conv.title === '新对话' && !chatStore.hasMessages) {
    chatStore
      .renameConversation(props.projectId, conv.id, text.slice(0, 20))
      .catch(() => {})
  }
  chatStore.sendMessage(text)
  inputText.value = ''
}

function handleInterrupt() {
  chatStore.interrupt()
}

function onSuggest(text: string) {
  inputText.value = text
}

function formatDate(t: string) {
  const d = dayjs(t)
  const now = dayjs()
  if (now.isSame(d, 'day')) return d.format('HH:mm')
  if (now.diff(d, 'day') < 7) return d.format('MM-DD HH:mm')
  return d.format('YYYY-MM-DD')
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-card);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.title-icon {
  color: var(--brand-500);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-actions :deep(.active) {
  color: var(--brand-600);
  background: var(--brand-50);
}

/* ============ 主体 ============ */
.panel-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}

/* 左侧历史会话栏 */
.conv-drawer {
  width: 220px;
  border-right: 1px solid var(--border-light);
  background: var(--gray-50);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.drawer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-light);
}

.drawer-title {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
}

.drawer-loading,
.drawer-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
}

.rotating {
  animation: rotate 1.2s linear infinite;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.conv-item:hover {
  background: var(--bg-card);
}

.conv-item.active {
  background: var(--brand-50);
  box-shadow: var(--shadow-sm);
}

.conv-item-main {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.conv-delete {
  opacity: 0;
  color: var(--color-danger-600) !important;
}

.conv-item:hover .conv-delete {
  opacity: 1;
}

/* 消息区 */
.message-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

.input-area {
  border-top: 1px solid var(--border-light);
  padding: 10px 12px;
  background: var(--bg-card);
  flex-shrink: 0;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.input-row :deep(.el-textarea) {
  flex: 1;
  min-width: 0;
}

.input-area :deep(.el-textarea__inner) {
  border-radius: 8px;
  font-size: 13px;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding-bottom: 4px;
}

.input-actions .hint {
  font-size: 11px;
  color: var(--text-secondary);
}

/* 抽屉动画 */
.drawer-enter-active,
.drawer-leave-active {
  transition: all 0.2s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}
</style>
