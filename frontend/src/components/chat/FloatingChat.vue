<template>
  <Teleport to="body">
    <!-- ============ FAB ============ -->
    <Transition name="fab">
      <button
        v-if="floatingStore.isFabVisible && projectId"
        ref="fabRef"
        class="fab"
        :class="{ dragging: fabDragging, near: nearEdge }"
        :style="fabStyle"
        :title="floatingStore.unreadCount > 0 ? '有新消息' : 'AI 助手'"
        @mousedown="onFabMouseDown"
      >
        <!-- 机器人 SVG -->
        <RobotAvatar :talking="chatStore.streaming" class="robot" />
        <span v-if="floatingStore.unreadCount > 0" class="fab-badge">
          {{ floatingStore.unreadCount > 99 ? '99+' : floatingStore.unreadCount }}
        </span>
        <span class="fab-ring" />
      </button>
    </Transition>

    <!-- ============ 浮窗 ============ -->
    <Transition name="float">
      <div
        v-if="floatingStore.isOpen && projectId"
        ref="windowRef"
        class="float-panel"
        :class="{
          maximized: floatingStore.phase === 'maximized',
          dragging,
          resizing: resizeActive,
        }"
        :style="panelStyle"
      >
        <!-- 顶部拖拽栏 + 操作 -->
        <div class="float-header" @mousedown="onDragStart">
          <div class="float-title">
            <div class="title-avatar">
              <RobotAvatar :talking="chatStore.streaming" />
            </div>
            <div class="title-text">
              <div class="title-name">小测</div>
              <div class="title-sub">AI 测试助手</div>
            </div>
          </div>
          <div class="float-actions" @mousedown.stop>
            <el-tooltip content="最小化">
              <el-button
                text
                size="small"
                class="header-btn"
                @click="floatingStore.minimize"
              >
                <i class="i-solar-minimize-square-3-linear" />
              </el-button>
            </el-tooltip>
            <el-tooltip
              :content="
                floatingStore.phase === 'maximized' ? '还原' : '最大化'
              "
            >
              <el-button
                text
                size="small"
                class="header-btn"
                @click="floatingStore.toggleMaximize"
              >
                <i
                  v-if="floatingStore.phase !== 'maximized'"
                  class="i-solar-maximize-square-3-linear"
                />
                <i v-else class="i-solar-minimize-square-3-linear" />
              </el-button>
            </el-tooltip>
            <el-tooltip content="跳转到独立页面">
              <el-button
                text
                size="small"
                class="header-btn"
                @click="goFullPage"
              >
                <i class="i-solar-square-top-down-linear" />
              </el-button>
            </el-tooltip>
            <el-tooltip content="关闭">
              <el-button
                text
                size="small"
                class="header-btn"
                @click="floatingStore.close"
              >
                <i class="i-solar-close-circle-linear" />
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <!-- 对话面板 -->
        <div class="float-body">
          <ChatPanel v-if="projectId" :project-id="projectId" />
        </div>

        <!-- ===== 8 个 resize 手柄 ===== -->
        <template v-if="floatingStore.phase !== 'maximized'">
          <div class="resize-handle top" @mousedown="onResizeStart($event, 'top')" />
          <div class="resize-handle bottom" @mousedown="onResizeStart($event, 'bottom')" />
          <div class="resize-handle left" @mousedown="onResizeStart($event, 'left')" />
          <div class="resize-handle right" @mousedown="onResizeStart($event, 'right')" />
          <div class="resize-handle corner top-left" @mousedown="onResizeStart($event, 'top-left')" />
          <div class="resize-handle corner top-right" @mousedown="onResizeStart($event, 'top-right')" />
          <div class="resize-handle corner bottom-left" @mousedown="onResizeStart($event, 'bottom-left')" />
          <div class="resize-handle corner bottom-right" @mousedown="onResizeStart($event, 'bottom-right')" />
        </template>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useFloatingChatStore,
  WIN_MIN_WIDTH,
  WIN_MIN_HEIGHT,
  WIN_EDGE,
  FAB_SIZE,
  FAB_EDGE,
} from '@/stores/floatingChat'
import { useChatStore } from '@/stores/chat'
import ChatPanel from './ChatPanel.vue'
import RobotAvatar from './RobotAvatar.vue'

const route = useRoute()
const router = useRouter()
const floatingStore = useFloatingChatStore()
const chatStore = useChatStore()

const fabRef = ref<HTMLElement | null>(null)
const windowRef = ref<HTMLElement | null>(null)

/** 从当前路由提取项目 id（仅项目工作区下显示 FAB） */
const projectId = computed<number | null>(() => {
  const id = route.params.id
  if (id && !isNaN(Number(id))) return Number(id)
  return null
})

/** 切换项目时重置 */
watch(projectId, (newId, oldId) => {
  if (newId !== oldId) {
    floatingStore.close()
    chatStore.reset()
  }
})

watch(
  () => chatStore.messages.length,
  () => floatingStore.notifyNew(),
)

function goFullPage() {
  if (!projectId.value) return
  router.push({
    name: 'FuncTestChat',
    params: { id: projectId.value },
  })
  floatingStore.close()
}

// ──────────────────────────────────────────────────────────
// FAB：拖拽 + 点击区分 + 吸边
// ──────────────────────────────────────────────────────────

const fabDragging = ref(false)
const nearEdge = ref(false)
let fabDragStartX = 0
let fabDragStartY = 0
let fabOrigX = 0
let fabOrigY = 0
let fabMoved = false

/** FAB 的位置（计算后，默认左下） */
const fabPos = computed(() => {
  const { x, y } = floatingStore.fabPosition
  if (x < 0 || y < 0) {
    return {
      x: 24,
      y: Math.max(FAB_EDGE, window.innerHeight - FAB_SIZE - 24),
    }
  }
  return { x, y }
})

const fabStyle = computed(() => ({
  left: `${fabPos.value.x}px`,
  top: `${fabPos.value.y}px`,
}))

function onFabMouseDown(ev: MouseEvent) {
  ev.preventDefault()
  fabDragging.value = false
  fabMoved = false
  fabDragStartX = ev.clientX
  fabDragStartY = ev.clientY
  fabOrigX = fabPos.value.x
  fabOrigY = fabPos.value.y
  document.addEventListener('mousemove', onFabMouseMove)
  document.addEventListener('mouseup', onFabMouseUp)
}

function onFabMouseMove(ev: MouseEvent) {
  const dx = ev.clientX - fabDragStartX
  const dy = ev.clientY - fabDragStartY
  // 鼠标移动超过 4px 才算拖拽
  if (!fabMoved && Math.hypot(dx, dy) < 4) return
  fabMoved = true
  fabDragging.value = true

  const newX = Math.min(
    Math.max(FAB_EDGE, fabOrigX + dx),
    window.innerWidth - FAB_SIZE - FAB_EDGE,
  )
  const newY = Math.min(
    Math.max(FAB_EDGE, fabOrigY + dy),
    window.innerHeight - FAB_SIZE - FAB_EDGE,
  )
  floatingStore.setFabPosition(newX, newY)

  // 判断是否靠近右/左边（用于"贴边"视觉提示）
  const distRight = window.innerWidth - (newX + FAB_SIZE)
  const distLeft = newX
  nearEdge.value = Math.min(distLeft, distRight) < 40
}

function onFabMouseUp(ev: MouseEvent) {
  document.removeEventListener('mousemove', onFabMouseMove)
  document.removeEventListener('mouseup', onFabMouseUp)

  if (fabMoved) {
    // 拖拽结束：贴边吸附
    snapFabToEdge()
  } else {
    // 点击：打开浮窗
    floatingStore.open()
    nextTick(() => ensureDefaultPosition())
  }

  fabDragging.value = false
  fabMoved = false
  // 兼容 ts 未使用警告
  void ev
}

/** 拖拽结束后吸到最近的左/右边 */
function snapFabToEdge() {
  const { x, y } = fabPos.value
  const center = x + FAB_SIZE / 2
  const targetX =
    center < window.innerWidth / 2
      ? FAB_EDGE
      : window.innerWidth - FAB_SIZE - FAB_EDGE
  // 平滑动画通过 CSS transition 实现
  floatingStore.setFabPosition(targetX, y)
  nearEdge.value = true
  // 短暂高亮后取消
  setTimeout(() => {
    nearEdge.value = false
  }, 600)
}

// ──────────────────────────────────────────────────────────
// 浮窗默认位置 & 窗口缩放保护
// ──────────────────────────────────────────────────────────

function ensureDefaultPosition() {
  const { x, y } = floatingStore.position
  const { width, height } = floatingStore.size
  if (x < 0 || y < 0 || x + width > window.innerWidth || y + height > window.innerHeight) {
    const dx = Math.max(WIN_EDGE, window.innerWidth - width - 28)
    const dy = Math.max(WIN_EDGE, window.innerHeight - height - 28)
    floatingStore.setPosition(dx, dy)
  }
}

onMounted(() => {
  if (floatingStore.isOpen) {
    ensureDefaultPosition()
  }
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  stopAllListeners()
})

function onWindowResize() {
  // FAB 位置约束
  if (floatingStore.fabPosition.x >= 0) {
    const { x, y } = floatingStore.fabPosition
    const newX = Math.min(
      Math.max(FAB_EDGE, x),
      window.innerWidth - FAB_SIZE - FAB_EDGE,
    )
    const newY = Math.min(
      Math.max(FAB_EDGE, y),
      window.innerHeight - FAB_SIZE - FAB_EDGE,
    )
    if (newX !== x || newY !== y) {
      floatingStore.setFabPosition(newX, newY)
    }
  }

  // 浮窗约束
  if (floatingStore.phase === 'maximized') return
  const { width, height } = floatingStore.size
  const { x, y } = floatingStore.position
  const newW = Math.min(width, window.innerWidth - WIN_EDGE * 2)
  const newH = Math.min(height, window.innerHeight - WIN_EDGE * 2)
  if (newW !== width || newH !== height) {
    floatingStore.setSize(Math.max(WIN_MIN_WIDTH, newW), Math.max(WIN_MIN_HEIGHT, newH))
  }
  const newX = Math.min(Math.max(WIN_EDGE, x), window.innerWidth - newW - WIN_EDGE)
  const newY = Math.min(Math.max(WIN_EDGE, y), window.innerHeight - newH - WIN_EDGE)
  if (newX !== x || newY !== y) {
    floatingStore.setPosition(newX, newY)
  }
}

// ──────────────────────────────────────────────────────────
// 浮窗拖拽（移动整个浮窗）
// ──────────────────────────────────────────────────────────

const dragging = ref(false)
let dragStartX = 0
let dragStartY = 0
let dragOrigX = 0
let dragOrigY = 0

function onDragStart(ev: MouseEvent) {
  if (floatingStore.phase === 'maximized') return
  dragging.value = true
  dragStartX = ev.clientX
  dragStartY = ev.clientY
  dragOrigX = floatingStore.position.x
  dragOrigY = floatingStore.position.y
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(ev: MouseEvent) {
  if (!dragging.value) return
  const dx = ev.clientX - dragStartX
  const dy = ev.clientY - dragStartY
  const { width, height } = floatingStore.size
  const newX = Math.min(
    Math.max(WIN_EDGE, dragOrigX + dx),
    window.innerWidth - width - WIN_EDGE,
  )
  const newY = Math.min(
    Math.max(WIN_EDGE, dragOrigY + dy),
    window.innerHeight - height - WIN_EDGE,
  )
  floatingStore.setPosition(newX, newY)
}

function onDragEnd() {
  dragging.value = false
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
}

// ──────────────────────────────────────────────────────────
// 浮窗 resize（8 个手柄）
// ──────────────────────────────────────────────────────────

type ResizeDir =
  | 'top'
  | 'bottom'
  | 'left'
  | 'right'
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'

const resizeActive = ref(false)
let resizeDir: ResizeDir | null = null
let resizeStartX = 0
let resizeStartY = 0
let resizeOrigX = 0
let resizeOrigY = 0
let resizeOrigW = 0
let resizeOrigH = 0

function onResizeStart(ev: MouseEvent, dir: ResizeDir) {
  if (floatingStore.phase === 'maximized') return
  ev.preventDefault()
  ev.stopPropagation()
  resizeActive.value = true
  resizeDir = dir
  resizeStartX = ev.clientX
  resizeStartY = ev.clientY
  resizeOrigX = floatingStore.position.x
  resizeOrigY = floatingStore.position.y
  resizeOrigW = floatingStore.size.width
  resizeOrigH = floatingStore.size.height
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(ev: MouseEvent) {
  if (!resizeActive.value || !resizeDir) return
  const dx = ev.clientX - resizeStartX
  const dy = ev.clientY - resizeStartY

  let newX = resizeOrigX
  let newY = resizeOrigY
  let newW = resizeOrigW
  let newH = resizeOrigH

  const includesLeft = resizeDir.includes('left')
  const includesRight = resizeDir.includes('right')
  const includesTop = resizeDir.includes('top')
  const includesBottom = resizeDir.includes('bottom')

  if (includesRight) {
    newW = resizeOrigW + dx
  } else if (includesLeft) {
    newW = resizeOrigW - dx
    newX = resizeOrigX + dx
    if (newW < WIN_MIN_WIDTH) {
      newX = resizeOrigX + (resizeOrigW - WIN_MIN_WIDTH)
      newW = WIN_MIN_WIDTH
    }
  }
  if (includesBottom) {
    newH = resizeOrigH + dy
  } else if (includesTop) {
    newH = resizeOrigH - dy
    newY = resizeOrigY + dy
    if (newH < WIN_MIN_HEIGHT) {
      newY = resizeOrigY + (resizeOrigH - WIN_MIN_HEIGHT)
      newH = WIN_MIN_HEIGHT
    }
  }

  newW = Math.max(WIN_MIN_WIDTH, newW)
  newH = Math.max(WIN_MIN_HEIGHT, newH)

  if (newX < WIN_EDGE) {
    if (includesLeft) {
      newW = resizeOrigX + resizeOrigW - WIN_EDGE
    }
    newX = WIN_EDGE
  }
  if (newY < WIN_EDGE) {
    if (includesTop) {
      newH = resizeOrigY + resizeOrigH - WIN_EDGE
    }
    newY = WIN_EDGE
  }
  if (newX + newW > window.innerWidth - WIN_EDGE) {
    newW = window.innerWidth - WIN_EDGE - newX
  }
  if (newY + newH > window.innerHeight - WIN_EDGE) {
    newH = window.innerHeight - WIN_EDGE - newY
  }

  newW = Math.max(WIN_MIN_WIDTH, newW)
  newH = Math.max(WIN_MIN_HEIGHT, newH)

  floatingStore.setSize(newW, newH)
  floatingStore.setPosition(newX, newY)
}

function onResizeEnd() {
  resizeActive.value = false
  resizeDir = null
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
}

function stopAllListeners() {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  document.removeEventListener('mousemove', onFabMouseMove)
  document.removeEventListener('mouseup', onFabMouseUp)
}

// ──────────────────────────────────────────────────────────
// 样式
// ──────────────────────────────────────────────────────────

const panelStyle = computed(() => {
  if (floatingStore.phase === 'maximized') {
    return {}
  }
  return {
    left: `${floatingStore.position.x}px`,
    top: `${floatingStore.position.y}px`,
    width: `${floatingStore.size.width}px`,
    height: `${floatingStore.size.height}px`,
  }
})
</script>

<style scoped>
/* ========== FAB ========== */
.fab {
  position: fixed;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  padding: 0;
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-600) 100%);
  color: #fff;
  cursor: grab;
  box-shadow:
    0 6px 20px color-mix(in srgb, var(--brand-500) 32%, transparent),
    0 2px 6px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  transition: transform 0.2s ease, box-shadow 0.25s ease, left 0.25s ease,
    top 0.25s ease;
  overflow: visible;
}

.fab.dragging {
  cursor: grabbing;
  transition: box-shadow 0.2s ease; /* 拖拽时不要 left/top 过渡 */
  transform: scale(1.05);
  box-shadow: 0 12px 30px color-mix(in srgb, var(--brand-500) 42%, transparent);
}

.fab:hover:not(.dragging) {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 10px 28px color-mix(in srgb, var(--brand-500) 38%, transparent);
}

.fab.near {
  box-shadow:
    0 8px 24px color-mix(in srgb, var(--brand-500) 46%, transparent),
    0 0 0 4px color-mix(in srgb, var(--brand-500) 16%, transparent);
}

.fab .robot {
  width: 44px;
  height: 44px;
  pointer-events: none;
}

/* 外圈光晕 */
.fab-ring {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.35);
  opacity: 0;
  animation: fab-ring 3s ease-out infinite;
  pointer-events: none;
}

@keyframes fab-ring {
  0% {
    transform: scale(1);
    opacity: 0.5;
  }
  100% {
    transform: scale(1.4);
    opacity: 0;
  }
}

.fab-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: var(--color-danger-500);
  color: #fff;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 0 0 2px #fff,
    0 2px 6px rgba(239, 68, 68, 0.4);
}

.fab-enter-active,
.fab-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.fab-enter-from,
.fab-leave-to {
  transform: scale(0.4);
  opacity: 0;
}

/* ========== 浮窗 ========== */
.float-panel {
  position: fixed;
  background: var(--bg-card);
  border-radius: 12px;
  /* 浅色 + 极轻投影（设计哲学：白卡 + 浅边框 + 微投影） */
  box-shadow:
    0 16px 48px rgba(0, 0, 0, 0.12),
    0 4px 16px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  z-index: 2000;
  overflow: hidden;
  transition: box-shadow 0.2s;
  border: 1px solid var(--border-light);
}

.float-panel.dragging,
.float-panel.resizing {
  user-select: none;
}

.float-panel.maximized {
  inset: 16px;
  left: 16px !important;
  top: 16px !important;
  width: auto !important;
  height: auto !important;
  border-radius: 16px;
}

/* 顶部 */
.float-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: linear-gradient(135deg, var(--brand-50) 0%, var(--bg-card) 100%);
  border-bottom: 1px solid var(--border-light);
  cursor: move;
  user-select: none;
  flex-shrink: 0;
}

.float-panel.maximized .float-header {
  cursor: default;
}

.float-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-600) 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px color-mix(in srgb, var(--brand-500) 28%, transparent);
}

.title-avatar :deep(.robot-avatar) {
  width: 28px;
  height: 28px;
}

.title-text {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.title-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.title-sub {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.2;
}

.float-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.header-btn {
  padding: 2px 6px;
}

.float-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* ========== Resize 手柄 ========== */
.resize-handle {
  position: absolute;
  z-index: 1;
  user-select: none;
}

.resize-handle.top {
  top: 0;
  left: 8px;
  right: 8px;
  height: 4px;
  cursor: ns-resize;
}
.resize-handle.bottom {
  bottom: 0;
  left: 8px;
  right: 8px;
  height: 4px;
  cursor: ns-resize;
}
.resize-handle.left {
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 4px;
  cursor: ew-resize;
}
.resize-handle.right {
  top: 8px;
  bottom: 8px;
  right: 0;
  width: 4px;
  cursor: ew-resize;
}

.resize-handle.corner {
  width: 12px;
  height: 12px;
  z-index: 2;
}
.resize-handle.top-left {
  top: 0;
  left: 0;
  cursor: nwse-resize;
}
.resize-handle.top-right {
  top: 0;
  right: 0;
  cursor: nesw-resize;
}
.resize-handle.bottom-left {
  bottom: 0;
  left: 0;
  cursor: nesw-resize;
}
.resize-handle.bottom-right {
  bottom: 0;
  right: 0;
  cursor: nwse-resize;
  background: linear-gradient(
    135deg,
    transparent 0%,
    transparent 50%,
    var(--text-placeholder) 50%,
    var(--text-placeholder) 60%,
    transparent 60%,
    transparent 70%,
    var(--text-placeholder) 70%,
    var(--text-placeholder) 80%,
    transparent 80%
  );
  opacity: 0.6;
}

.resize-handle.bottom-right:hover {
  opacity: 1;
}

/* 浮窗动画 */
.float-enter-active,
.float-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.float-enter-from,
.float-leave-to {
  transform: translateY(20px) scale(0.97);
  opacity: 0;
}

/* 移动端：自动全屏 */
@media (max-width: 768px) {
  .float-panel:not(.maximized) {
    left: 8px !important;
    top: 8px !important;
    width: calc(100vw - 16px) !important;
    height: calc(100vh - 16px) !important;
  }
  .resize-handle {
    display: none;
  }
}
</style>
