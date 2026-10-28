/**
 * useDeviceScreencast —— 设备投屏会话编排（票据 → control WS → scrcpy 客户端）。
 *
 * 把「申请 control-ticket → 连 WS → createScrcpyClient 上屏 canvas → 坐标映射 →
 * 断线重连 → 释放锁」这套编排从 DeviceControlDialog 抽出，供投屏弹框与智能操作台
 * 复用（方案 §2.2：录制会话中投屏与自动化单步同属一个锁 owner、一条隧道，共用
 * 同一 session_id）。底层解码/WS/keepalive 仍在 useScrcpyClient。
 *
 * 消费方提供 canvasRef / stageRef 与模板（手机外壳 + 遮罩），在自己的生命周期里
 * 调 start()/cleanup()（弹框 @open/@closed；页面 onMounted/onBeforeUnmount）。
 * cleanup 幂等（组件卸载兜底再调一次安全）。sessionId 暴露给操作台做录制单步。
 */

import { computed, onBeforeUnmount, reactive, ref, watch, nextTick, type Ref } from 'vue'
import { appDeviceApi } from '@/api/appDevice'
import { createScrcpyClient, type ScrcpyClient, type ScrcpyClientPhase } from './useScrcpyClient'
import { createHarmonyClient } from './useHarmonyScreencast'

/** 投屏客户端最小接口（scrcpy 与 harmony 两实现的公共形状）——编排层只依赖它 */
type CastClient = Pick<
  ScrcpyClient,
  | 'start'
  | 'dispose'
  | 'getPhase'
  | 'touchDown'
  | 'touchMove'
  | 'touchUp'
  | 'pressHome'
  | 'pressBack'
  | 'pressAppSwitch'
  | 'injectTextViaClipboard'
>

export type DeviceCastPlatform = 'android' | 'harmony' | 'ios'

export type ScreencastState =
  | 'init'
  | 'acquiring'
  | 'conflict'
  | 'connecting'
  | 'streaming'
  | 'reconnecting'
  | 'expired'
  | 'error'

export interface UseDeviceScreencastOptions {
  /** 设备 udid getter（可响应式变化） */
  udid: () => string
  canvasRef: Ref<HTMLCanvasElement | null>
  stageRef: Ref<HTMLDivElement | null>
  /** 设备平台 getter（H3/I3）：harmony/ios 走 M-JPEG 客户端，缺省 android(scrcpy) */
  platform?: () => DeviceCastPlatform
  /** 额外日志回调（消费方可自建日志面板） */
  onLog?: (msg: string) => void
}

const MAX_RECONNECT = 3

export function useDeviceScreencast(opts: UseDeviceScreencastOptions) {
  const { canvasRef, stageRef } = opts

  const viewState = ref<ScreencastState>('init')
  const errorMsg = ref('')
  const conflict = reactive<{ owner_user_id: number; owner_name?: string | null }>({
    owner_user_id: 0,
    owner_name: null,
  })
  const sessionId = ref('')
  /** 会话模式（P4 观战锁）：control=占锁可注入；observe=不占锁只读观看。
   *  重连沿用当前模式；switch 用 startObserve()/manualReconnect()。 */
  const mode = ref<'control' | 'observe'>('control')
  const meta = reactive<{ deviceName: string; codecName: string; width: number; height: number }>({
    deviceName: '',
    codecName: '',
    width: 0,
    height: 0,
  })
  const canvasRect = reactive({ left: 0, top: 0, width: 0, height: 0 })
  const logs = ref<string[]>([])
  const secureOk = window.isSecureContext

  let tearingDown = false
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let client: CastClient | null = null
  let resizeObserver: ResizeObserver | null = null
  let pointerDown = false
  let started = false

  // ── 派生 ──
  const canInteract = computed(
    () => viewState.value === 'streaming' && meta.width > 0 && mode.value === 'control',
  )
  const screenAspect = computed(() =>
    meta.width && meta.height ? `${meta.width} / ${meta.height}` : '9 / 20',
  )
  const stateLabel = computed(() => {
    switch (viewState.value) {
      case 'init':
        return '准备就绪'
      case 'acquiring':
        return mode.value === 'observe' ? '申请观战…' : '申请控制权…'
      case 'conflict':
        return '设备被占用'
      case 'connecting':
        return '连接中…'
      case 'streaming':
        return mode.value === 'observe' ? '观战中（只读）' : '投屏中'
      case 'reconnecting':
        return `重连中（${reconnectAttempts}/${MAX_RECONNECT}）`
      case 'expired':
        return '会话已失效'
      case 'error':
        return '连接异常'
      default:
        return ''
    }
  })
  const stateType = computed(() => {
    switch (viewState.value) {
      case 'streaming':
        return 'success'
      case 'reconnecting':
      case 'connecting':
      case 'acquiring':
        return 'warning'
      case 'conflict':
      case 'expired':
      case 'error':
        return 'danger'
      default:
        return 'info'
    }
  })

  function pushLog(m: string) {
    const ts = new Date().toLocaleTimeString()
    logs.value.push(`[${ts}] ${m}`)
    if (logs.value.length > 200) logs.value.shift()
    opts.onLog?.(m)
  }

  // ── 票据 + 连接编排 ──
  function buildWsUrl(wsPath: string): string {
    if (wsPath.startsWith('ws://') || wsPath.startsWith('wss://')) return wsPath
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const path = wsPath.startsWith('/') ? wsPath : `/${wsPath}`
    return `${proto}//${location.host}${path}`
  }

  async function acquireAndConnect() {
    const udid = opts.udid()
    if (!udid) {
      viewState.value = 'error'
      errorMsg.value = '缺少设备标识'
      return
    }
    clearReconnect()
    disposeClient()
    viewState.value = 'acquiring'
    errorMsg.value = ''

    let result
    try {
      result = await appDeviceApi.requestControlTicket(udid, mode.value)
    } catch (e) {
      viewState.value = 'error'
      errorMsg.value = `申请控制票据失败：${(e as Error)?.message ?? e}`
      pushLog(errorMsg.value)
      return
    }

    if (!result.ok) {
      if (result.code === 409 && result.conflict) {
        conflict.owner_user_id = result.conflict.owner_user_id
        conflict.owner_name = result.conflict.owner_name
        viewState.value = 'conflict'
        pushLog(`设备被占用：${result.conflict.owner_name || '#' + result.conflict.owner_user_id}`)
      } else {
        viewState.value = 'error'
        errorMsg.value = result.message
        pushLog(errorMsg.value)
      }
      return
    }

    sessionId.value = result.data.session_id
    const wsUrl = buildWsUrl(result.data.ws_path)
    pushLog(`票据签发成功 session=${result.data.session_id}`)

    await nextTick()
    const canvas = canvasRef.value
    if (!canvas) {
      viewState.value = 'error'
      errorMsg.value = 'canvas 未就绪'
      return
    }

    viewState.value = 'connecting'
    // 平台分派（H3/I3）：harmony/ios=M-JPEG 客户端（鸿蒙 uitest 帧流 / iOS WDA
    // MJPEG，帧协议同壳:0x7B meta + FFD8 JPEG + {t,x,y} 控制）/ android=scrcpy
    // H.264 客户端。同接口形状（start/dispose/touch*/press*），编排层完全共用。
    const platform = opts.platform?.() ?? 'android'
    const isMjpeg = platform === 'harmony' || platform === 'ios'
    const cbs = {
      onPhase: handleClientPhase,
      onMetadata: (m: { deviceName?: string; codecName: string; width: number; height: number }) => {
        meta.deviceName = m.deviceName ?? ''
        meta.codecName = m.codecName
        meta.width = m.width
        meta.height = m.height
        pushLog(`元数据 ${m.codecName} ${m.width}x${m.height}`)
        nextTick(updateCanvasRect)
      },
      onSizeChanged: (w: number, h: number) => {
        meta.width = w
        meta.height = h
        nextTick(updateCanvasRect)
      },
      onLog: pushLog,
    }
    client = isMjpeg
      ? createHarmonyClient({ wsUrl, ticket: result.data.ticket, canvas, callbacks: cbs })
      : createScrcpyClient({ wsUrl, ticket: result.data.ticket, canvas, callbacks: cbs })
    client.start()
  }

  function handleClientPhase(phase: ScrcpyClientPhase, detail?: string) {
    pushLog(`client phase=${phase}${detail ? ' · ' + detail : ''}`)
    if (tearingDown && (phase === 'closed' || phase === 'error')) return
    switch (phase) {
      case 'streaming':
        viewState.value = 'streaming'
        reconnectAttempts = 0
        break
      case 'expired':
        viewState.value = 'expired'
        errorMsg.value = detail || '会话已失效，请重新申请控制'
        disposeClient()
        break
      case 'error':
        handleUnexpectedDrop(detail)
        break
      case 'closed':
        if (viewState.value === 'streaming') handleUnexpectedDrop(detail)
        break
    }
  }

  function handleUnexpectedDrop(detail?: string) {
    disposeClient()
    if (reconnectAttempts >= MAX_RECONNECT) {
      viewState.value = 'error'
      errorMsg.value = detail || '连接已断开，自动重连失败'
      pushLog('达到最大重连次数，停止重连')
      return
    }
    reconnectAttempts += 1
    viewState.value = 'reconnecting'
    const delay = Math.min(1000 * 2 ** (reconnectAttempts - 1), 8000)
    pushLog(`${delay}ms 后第 ${reconnectAttempts} 次重连`)
    reconnectTimer = setTimeout(() => acquireAndConnect(), delay)
  }

  function clearReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function disposeClient() {
    if (client) {
      tearingDown = true
      client.dispose()
      client = null
      tearingDown = false
    }
  }

  async function manualReconnect() {
    reconnectAttempts = 0
    await acquireAndConnect()
  }

  /** 申请接管（同用户在别处占用时，后端 control-ticket 走 takeover 语义） */
  async function requestTakeover() {
    mode.value = 'control'
    await acquireAndConnect()
  }

  /** 转观战（P4）：不占锁只读观看——自动化执行/他人占用时的观看入口。
   *  冷启动（从未 start）也可直接调：内部补挂监听。 */
  async function startObserve() {
    mode.value = 'observe'
    reconnectAttempts = 0
    pushLog('切换观战模式（只读，不占锁）')
    if (!started) {
      await start()
    } else {
      await acquireAndConnect()
    }
  }

  // ── 坐标映射 ──
  function updateCanvasRect() {
    const canvas = canvasRef.value
    if (!canvas) return
    const r = canvas.getBoundingClientRect()
    canvasRect.left = r.left
    canvasRect.top = r.top
    canvasRect.width = r.width
    canvasRect.height = r.height
  }

  function toDevicePoint(clientX: number, clientY: number): { x: number; y: number } | null {
    if (!meta.width || !meta.height || !canvasRect.width || !canvasRect.height) return null
    const nx = (clientX - canvasRect.left) / canvasRect.width
    const ny = (clientY - canvasRect.top) / canvasRect.height
    return {
      x: Math.min(Math.max(nx, 0), 1) * meta.width,
      y: Math.min(Math.max(ny, 0), 1) * meta.height,
    }
  }

  function onPointerDown(e: PointerEvent) {
    if (!canInteract.value || !client) return
    const p = toDevicePoint(e.clientX, e.clientY)
    if (!p) return
    pointerDown = true
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
    client.touchDown(p.x, p.y)
  }

  function onPointerMove(e: PointerEvent) {
    if (!pointerDown || !canInteract.value || !client) return
    const p = toDevicePoint(e.clientX, e.clientY)
    if (!p) return
    client.touchMove(p.x, p.y)
  }

  function onPointerUp(e: PointerEvent) {
    if (!pointerDown || !client) return
    const p = toDevicePoint(e.clientX, e.clientY)
    pointerDown = false
    if (p) client.touchUp(p.x, p.y)
  }

  // ── 控制注入（供导航键 / 中文文本；观战模式一律拒发——网关侧也会丢弃） ──
  const pressHome = () => {
    if (mode.value === 'control') client?.pressHome()
  }
  const pressBack = () => {
    if (mode.value === 'control') client?.pressBack()
  }
  const pressAppSwitch = () => {
    if (mode.value === 'control') client?.pressAppSwitch()
  }
  function injectText(text: string): boolean {
    if (!client || !text || mode.value !== 'control') return false
    client.injectTextViaClipboard(text)
    pushLog(`剪贴板注入 ${text.length} 字符`)
    return true
  }

  // ── 生命周期（消费方在自己的开合/挂载时机调用）──
  async function start() {
    if (started) return
    started = true
    reconnectAttempts = 0
    if (!secureOk) pushLog('非安全上下文（HTTP）：安卓走 TinyH264 软解兜底，鸿蒙/iOS 走 M-JPEG，均可上屏')
    await acquireAndConnect()
    window.addEventListener('resize', updateCanvasRect)
    if (stageRef.value) {
      resizeObserver = new ResizeObserver(() => updateCanvasRect())
      resizeObserver.observe(stageRef.value)
    }
  }

  /** 幂等清理：dispose 客户端 + 尽力释放锁 + 拆监听，并复位为可再次 start */
  function cleanup() {
    if (!started) return
    started = false
    clearReconnect()
    disposeClient()
    const udid = opts.udid()
    // 观战不占锁无从释放；控制会话带自己的 session_id 做 CAS 释放——被 exec
    // 接管后 holder 已易主，后端静默 no-op，绝不误放自动化任务的锁
    if (udid && mode.value === 'control' && sessionId.value) {
      appDeviceApi.releaseDevice(udid, sessionId.value).catch(() => {})
    }
    window.removeEventListener('resize', updateCanvasRect)
    resizeObserver?.disconnect()
    resizeObserver = null
    // 复位供下次 start（弹框 destroy-on-close 语义）
    viewState.value = 'init'
    errorMsg.value = ''
    sessionId.value = ''
    mode.value = 'control'
    meta.deviceName = ''
    meta.codecName = ''
    meta.width = 0
    meta.height = 0
  }

  watch(
    () => [meta.width, meta.height],
    () => nextTick(updateCanvasRect),
  )

  // 组件卸载兜底（消费方通常已显式 cleanup；幂等，安全再调）
  onBeforeUnmount(cleanup)

  return {
    // 状态
    viewState,
    errorMsg,
    conflict,
    sessionId,
    mode,
    meta,
    logs,
    secureOk,
    // 派生
    canInteract,
    screenAspect,
    stateLabel,
    stateType,
    // 生命周期
    start,
    cleanup,
    manualReconnect,
    requestTakeover,
    startObserve,
    // 指针 + 坐标
    onPointerDown,
    onPointerMove,
    onPointerUp,
    updateCanvasRect,
    // 控制
    pressHome,
    pressBack,
    pressAppSwitch,
    injectText,
  }
}
