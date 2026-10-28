/**
 * 全局浮窗状态 store
 *
 * 负责：FAB 显示/隐藏、对话面板的展开/最小化/最大化状态、尺寸 + 位置、新消息提示等。
 *
 * 与 useChatStore 配合：浮窗只管"窗口状态"，对话数据走 useChatStore。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type FloatingPhase = 'closed' | 'open' | 'minimized' | 'maximized'

export interface FloatSize {
  width: number
  height: number
}

export interface FloatPosition {
  x: number
  y: number
}

export const WIN_MIN_WIDTH = 560
export const WIN_MIN_HEIGHT = 420
export const WIN_DEFAULT_WIDTH = 860
export const WIN_DEFAULT_HEIGHT = 680
export const WIN_EDGE = 8

export const FAB_SIZE = 56
export const FAB_EDGE = 16

const STORAGE_KEY = 'floating-chat-prefs'

interface PersistedPrefs {
  phase: FloatingPhase
  width: number
  height: number
  x: number
  y: number
  fabX: number
  fabY: number
}

function loadPrefs(): PersistedPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        // 最大化态不持久化（避免误触发后再打开就全屏）
        phase: parsed.phase === 'maximized' ? 'closed' : (parsed.phase || 'closed'),
        width: clampSize(parsed.width, WIN_DEFAULT_WIDTH, true),
        height: clampSize(parsed.height, WIN_DEFAULT_HEIGHT, false),
        x: typeof parsed.x === 'number' ? parsed.x : -1,
        y: typeof parsed.y === 'number' ? parsed.y : -1,
        fabX: typeof parsed.fabX === 'number' ? parsed.fabX : -1,
        fabY: typeof parsed.fabY === 'number' ? parsed.fabY : -1,
      }
    }
  } catch {
    // ignore
  }
  return {
    phase: 'closed',
    width: WIN_DEFAULT_WIDTH,
    height: WIN_DEFAULT_HEIGHT,
    x: -1,
    y: -1,
    fabX: -1,
    fabY: -1,
  }
}

function clampSize(v: unknown, fallback: number, isWidth: boolean): number {
  const n = typeof v === 'number' ? v : fallback
  const min = isWidth ? WIN_MIN_WIDTH : WIN_MIN_HEIGHT
  return Math.max(min, Math.min(n, isWidth ? 3000 : 2000))
}

export const useFloatingChatStore = defineStore('floatingChat', () => {
  const prefs = loadPrefs()

  /** 当前形态 */
  const phase = ref<FloatingPhase>(prefs.phase)
  /** 面板尺寸 */
  const size = ref<FloatSize>({ width: prefs.width, height: prefs.height })
  /** 面板位置（top-left 坐标，-1 代表使用默认右下） */
  const position = ref<FloatPosition>({ x: prefs.x, y: prefs.y })
  /** FAB 位置（top-left 坐标，-1 代表使用默认右下） */
  const fabPosition = ref<FloatPosition>({ x: prefs.fabX, y: prefs.fabY })
  /** 新消息红点（关闭/最小化时积累） */
  const unreadCount = ref(0)

  /** 最大化前的快照（用于还原） */
  let preMaxSnapshot: { size: FloatSize; position: FloatPosition } | null = null

  const isOpen = computed(
    () => phase.value === 'open' || phase.value === 'maximized',
  )
  const isFabVisible = computed(
    () => phase.value === 'closed' || phase.value === 'minimized',
  )

  function persist() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          phase: phase.value === 'maximized' ? 'open' : phase.value,
          width: size.value.width,
          height: size.value.height,
          x: position.value.x,
          y: position.value.y,
          fabX: fabPosition.value.x,
          fabY: fabPosition.value.y,
        }),
      )
    } catch {
      // ignore
    }
  }

  function open() {
    phase.value = 'open'
    unreadCount.value = 0
    persist()
  }

  function close() {
    phase.value = 'closed'
    persist()
  }

  function minimize() {
    phase.value = 'minimized'
    persist()
  }

  function toggleMaximize() {
    if (phase.value === 'maximized') {
      // 还原
      if (preMaxSnapshot) {
        size.value = { ...preMaxSnapshot.size }
        position.value = { ...preMaxSnapshot.position }
      }
      phase.value = 'open'
    } else {
      // 进入最大化
      preMaxSnapshot = {
        size: { ...size.value },
        position: { ...position.value },
      }
      phase.value = 'maximized'
    }
    persist()
  }

  function toggle() {
    if (isOpen.value) {
      close()
    } else {
      open()
    }
  }

  function notifyNew() {
    if (!isOpen.value) {
      unreadCount.value += 1
    }
  }

  function setSize(width: number, height: number) {
    size.value = {
      width: Math.max(WIN_MIN_WIDTH, width),
      height: Math.max(WIN_MIN_HEIGHT, height),
    }
    persist()
  }

  function setPosition(x: number, y: number) {
    position.value = { x, y }
    persist()
  }

  function setFabPosition(x: number, y: number) {
    fabPosition.value = { x, y }
    persist()
  }

  /** 重置到默认位置和尺寸（重新触发右下角逻辑） */
  function resetGeometry() {
    size.value = { width: WIN_DEFAULT_WIDTH, height: WIN_DEFAULT_HEIGHT }
    position.value = { x: -1, y: -1 }
    fabPosition.value = { x: -1, y: -1 }
    persist()
  }

  return {
    // state
    phase,
    size,
    position,
    fabPosition,
    unreadCount,
    // getters
    isOpen,
    isFabVisible,
    // actions
    open,
    close,
    minimize,
    toggleMaximize,
    toggle,
    notifyNew,
    setSize,
    setPosition,
    setFabPosition,
    resetGeometry,
  }
})
