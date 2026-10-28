/**
 * M-JPEG 投屏客户端（H3 鸿蒙 / I3 iOS 共用）—— 与 useScrcpyClient 的
 * createScrcpyClient **同接口形状**
 * （start/dispose/getPhase/touchDown|Move|Up/pressHome…/injectTextViaClipboard），
 * 让 useDeviceScreencast 的票据/锁/重连/坐标映射/observe 整套编排原样复用，只在
 * 工厂处按 platform 分派。iOS 帧协议与鸿蒙同壳（0x7B meta / FFD8 JPEG /
 * {t,x,y} 控制），meta 尺寸=iOS 逻辑 point（触控天然落 WDA point 坐标系）。
 *
 * 与 scrcpy 的差异（H.264 → M-JPEG）：
 *  - 收帧:同一 control/ws（子协议 ticket.<t>）收二进制帧,按首字节分流——
 *    0x7B '{' = 元数据 JSON（设备全分辨率,坐标映射用）；0xFF = 整帧 JPEG,
 *    createImageBitmap → drawImage 上屏。
 *  - 发控制:二进制 JSON `{t:'down|move|up',x,y}`（设备物理像素,取整）。Agent 侧
 *    经同一 hdckit 连接注入,并对 move 合并（S2:第二 uitest 客户端会打崩采集）。
 *  - 导航键/文本:hdckit 单连接无 keyEvent（走 uitest 会冲突）→ 鸿蒙 v1 一律 no-op。
 *
 * keepalive 与断连码语义同 scrcpy（网关平台无关）。
 */

export type HarmonyClientPhase =
  | 'idle'
  | 'connecting'
  | 'handshaking'
  | 'streaming'
  | 'closed'
  | 'expired'
  | 'error'

export interface HarmonyClientCallbacks {
  onPhase?: (phase: HarmonyClientPhase, detail?: string) => void
  onMetadata?: (meta: { deviceName?: string; codecName: string; width: number; height: number }) => void
  onSizeChanged?: (width: number, height: number) => void
  onLog?: (msg: string) => void
}

export interface HarmonyClientOptions {
  wsUrl: string
  ticket: string
  canvas: HTMLCanvasElement
  callbacks?: HarmonyClientCallbacks
}

/** 与 scrcpy 一致的失效码：4401 鉴权 / 4403 越权 / 4409 冲突 / 4410 被接管 / 4423 观战被拒 */
const EXPIRED_CLOSE_CODES = new Set([4401, 4403, 4409, 4410, 4423, 4426])
const KEEPALIVE_INTERVAL_MS = 10_000

/** 同 wsUrl 单例:重连/重开前 dispose 旧实例,避免两个 client 抢同一 canvas */
const activeClients = new Map<string, { dispose(): void }>()

export function createHarmonyClient(opts: HarmonyClientOptions) {
  const { wsUrl, ticket, canvas, callbacks = {} } = opts
  let ws: WebSocket | null = null
  let keepaliveTimer: ReturnType<typeof setInterval> | null = null
  let phase: HarmonyClientPhase = 'idle'
  let disposed = false
  let deviceWidth = 0
  let deviceHeight = 0
  let ctx: CanvasRenderingContext2D | null = null
  // 帧渲染串行化:createImageBitmap 是异步的,慢帧堆积会乱序 → 只保最新待渲染帧
  let rendering = false
  let pendingFrame: ArrayBuffer | null = null

  const setPhase = (p: HarmonyClientPhase, detail?: string) => {
    if (phase === p) return
    phase = p
    callbacks.onPhase?.(p, detail)
  }
  const log = (m: string) => callbacks.onLog?.(m)

  function handleMeta(bytes: Uint8Array) {
    try {
      const m = JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>
      if (m.type !== 'harmony_meta' && m.type !== 'ios_meta') return
      const w = Number(m.width) || 0
      const h = Number(m.height) || 0
      const changed = w !== deviceWidth || h !== deviceHeight
      deviceWidth = w
      deviceHeight = h
      if (phase === 'handshaking' || phase === 'connecting') {
        callbacks.onMetadata?.({ deviceName: '', codecName: 'MJPEG', width: w, height: h })
        setPhase('streaming')
      } else if (changed) {
        callbacks.onSizeChanged?.(w, h)
      }
      log(`元数据 MJPEG ${w}x${h}`)
    } catch {
      /* 坏 meta 帧忽略 */
    }
  }

  async function renderFrame(buf: ArrayBuffer) {
    if (disposed) return
    try {
      const bmp = await createImageBitmap(new Blob([buf], { type: 'image/jpeg' }))
      if (disposed) {
        bmp.close()
        return
      }
      // canvas 背景尺寸对齐 JPEG 实际像素（缩放采集,如 542x1206）；显示由 CSS 拉伸
      if (canvas.width !== bmp.width || canvas.height !== bmp.height) {
        canvas.width = bmp.width
        canvas.height = bmp.height
        ctx = canvas.getContext('2d')
      }
      ctx?.drawImage(bmp, 0, 0)
      bmp.close()
      if (phase === 'handshaking') setPhase('streaming') // 无 meta 兜底:首帧即上屏
    } catch (e) {
      log(`JPEG 解码失败：${(e as Error)?.message ?? e}`)
    }
  }

  function scheduleRender(buf: ArrayBuffer) {
    pendingFrame = buf // 只留最新帧,慢渲染时丢旧（M-JPEG 无帧间依赖,丢帧无害）
    if (rendering) return
    rendering = true
    const pump = async () => {
      while (pendingFrame && !disposed) {
        const next = pendingFrame
        pendingFrame = null
        await renderFrame(next)
      }
      rendering = false
    }
    void pump()
  }

  function connect() {
    setPhase('connecting')
    ws = new WebSocket(wsUrl, [`ticket.${ticket}`])
    ws.binaryType = 'arraybuffer'
    ctx = canvas.getContext('2d')

    ws.addEventListener('open', () => {
      log('鸿蒙 control WS 已连接')
      startKeepalive()
      setPhase('handshaking')
    })
    ws.addEventListener('message', (ev) => {
      if (disposed) return
      if (typeof ev.data === 'string') {
        handleTextFrame(ev.data)
        return
      }
      const buf = ev.data as ArrayBuffer
      const head = new Uint8Array(buf, 0, 1)[0]
      if (head === 0x7b) handleMeta(new Uint8Array(buf)) // '{' 元数据
      else scheduleRender(buf) // 0xFF JPEG
    })
    ws.addEventListener('close', (ev) => {
      if (disposed) return
      stopKeepalive()
      log(`鸿蒙 control WS 关闭 code=${ev.code} reason=${ev.reason || '-'}`)
      if (EXPIRED_CLOSE_CODES.has(ev.code)) setPhase('expired', ev.reason || '会话已失效，请重新申请控制')
      else if (ev.code === 1000) setPhase('closed', '连接已关闭')
      else setPhase('error', ev.reason || `连接断开 (code ${ev.code})`)
    })
    ws.addEventListener('error', () => {
      if (!disposed) log('鸿蒙 control WS 出错')
    })
  }

  function handleTextFrame(raw: string) {
    try {
      const frame = JSON.parse(raw)
      if (frame?.type === 'session_expired') setPhase('expired', frame.message || '会话已失效')
    } catch {
      /* 忽略非 JSON 文本帧 */
    }
  }

  function startKeepalive() {
    stopKeepalive()
    keepaliveTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('{"type":"keepalive"}')
    }, KEEPALIVE_INTERVAL_MS)
  }
  function stopKeepalive() {
    if (keepaliveTimer) {
      clearInterval(keepaliveTimer)
      keepaliveTimer = null
    }
  }

  /** 发二进制 JSON 触控（设备物理像素,取整）；未连通静默丢 */
  function sendTouch(t: 'down' | 'move' | 'up', x: number, y: number) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(new TextEncoder().encode(JSON.stringify({ t, x: Math.round(x), y: Math.round(y) })))
  }

  const start = () => {
    disposed = false
    const prev = activeClients.get(wsUrl)
    activeClients.set(wsUrl, api)
    if (prev && prev !== api) prev.dispose()
    connect()
  }
  function dispose() {
    if (disposed) return
    disposed = true
    stopKeepalive()
    pendingFrame = null
    if (activeClients.get(wsUrl) === api) activeClients.delete(wsUrl)
    if (ws) {
      try {
        ws.close(1000, 'client_dispose')
      } catch {
        /* ignore */
      }
      ws = null
    }
    setPhase('closed')
  }

  const api = {
    start,
    dispose,
    deviceSize: () => ({ width: deviceWidth, height: deviceHeight }),
    getPhase: () => phase,
    touchDown: (x: number, y: number) => sendTouch('down', x, y),
    touchMove: (x: number, y: number) => sendTouch('move', x, y),
    touchUp: (x: number, y: number) => sendTouch('up', x, y),
    // 鸿蒙 v1 无导航键/文本注入（hdckit 单连接无 keyEvent，走 uitest 会冲突）→ no-op
    pressHome: () => {},
    pressBack: () => {},
    pressAppSwitch: () => {},
    injectTextViaClipboard: (_text: string) => {},
  }
  return api
}

export type HarmonyClient = ReturnType<typeof createHarmonyClient>
