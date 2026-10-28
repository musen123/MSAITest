/**
 * useScrcpyClient —— 浏览器侧 scrcpy 投屏客户端（S1 spike 蓝本产品化）
 *
 * 职责：
 *   1. 用一次性 ticket 作子协议连 control WS（`Sec-WebSocket-Protocol: ticket.<t>`）。
 *   2. 入站二进制帧 = 经中继的 scrcpy 裸视频流 → 喂 @yume-chan/stream-extra 的
 *      PushReadableStream → options.parseVideoStreamMetadata 解出 codec/尺寸 →
 *      createMediaStreamTransformer 切包 → WebCodecsVideoDecoder(WebGL renderer)
 *      上屏到 canvas。
 *   3. 出站 = ScrcpyControlMessageSerializer 序列化的裸控制字节（触控 / 按键 /
 *      剪贴板），直接 ws.send。
 *
 * S1 运维/实现铁律映射（前端侧相关项）：
 *   - handoff 丢字节：WS onmessage 一挂上就把字节推进 PushReadableStream，绝不懒执行。
 *   - video 首字节 dummy 0x00 strip：由 Agent 中继层负责（relay.mjs 已 strip），
 *     浏览器默认**不再** strip，避免双重剥字节（stripDummyByte 选项默认 false，留作
 *     真链路联调时的应急开关）。
 *   - 优雅退出：dispose() 关 decoder + close WS（正常关闭），让网关据此发 stop_scrcpy。
 *
 * 注意：WebCodecs 需要 secure context（生产 https / localhost 满足）。
 */

import {
  ScrcpyOptions3_3_3,
  ScrcpyControlMessageSerializer,
  ScrcpyVideoCodecNameMap,
  AndroidKeyEventAction,
  AndroidKeyCode,
  AndroidMotionEventAction,
  AndroidMotionEventButton,
  type AndroidMotionEventAction as MotionAction,
  type ScrcpyMediaStreamPacket,
} from '@yume-chan/scrcpy'
import {
  WebCodecsVideoDecoder,
  WebGLVideoFrameRenderer,
  BitmapVideoFrameRenderer,
} from '@yume-chan/scrcpy-decoder-webcodecs'
import { TinyH264Decoder } from '@yume-chan/scrcpy-decoder-tinyh264'
import {
  PushReadableStream,
  type PushReadableStreamController,
  type WritableStream,
} from '@yume-chan/stream-extra'

/** 客户端对外状态机 */
export type ScrcpyClientPhase =
  | 'idle'
  | 'connecting'
  | 'handshaking' // WS 已开，等首帧 + 解元数据
  | 'streaming' // 已上屏
  | 'reconnecting'
  | 'closed' // 正常关闭
  | 'expired' // 会话失效（ticket/锁失效、被接管、鉴权失败）
  | 'error' // 其它错误

export interface ScrcpyClientCallbacks {
  onPhase?: (phase: ScrcpyClientPhase, detail?: string) => void
  /** 解出视频元数据（设备名 / codec / 分辨率）后回调，供坐标映射与 UI 展示 */
  onMetadata?: (meta: {
    deviceName?: string
    codecName: string
    width: number
    height: number
  }) => void
  /** 分辨率变化（旋转 / 动态改尺寸）——坐标映射需据此更新 */
  onSizeChanged?: (width: number, height: number) => void
  /** 错误日志（面向调试） */
  onLog?: (msg: string) => void
}

export interface ScrcpyClientOptions {
  /** 完整 WS URL（wss://host/api/v1/app/devices/{udid}/control/ws） */
  wsUrl: string
  /** 一次性 ticket（作子协议 ticket.<t>） */
  ticket: string
  /** 上屏目标 canvas */
  canvas: HTMLCanvasElement
  /** 与后端 start_scrcpy 参数保持一致（库序列化的 server 参数要对齐才能正确解流） */
  serverOptions?: {
    maxSize?: number
    videoBitRate?: number
    maxFps?: number
  }
  /** 应急：浏览器侧再 strip 首字节 dummy 0x00（默认 false，由 Agent 中继负责） */
  stripDummyByte?: boolean
  callbacks?: ScrcpyClientCallbacks
}

/**
 * 关闭 code 语义（与网关约定，见契约 §2/§3/§3.1）：
 *   4401 鉴权失败 / 4403 session 不符（越权） / 4409 冲突 / 4410 被接管 /
 *   4423 观战被拒（同设备已有活跃观看会话，P4）
 * 这些都归入「会话失效（expired）」，UI 明确提示重新申请控制，不做自动重连。
 * ⚠ 4410 必须在此列：它意味着"别的连接接管了设备"，若当可重连错误会立刻
 * 反抢回来，两个标签页会陷入无限接管战争（联调实测踩过）。
 * ⚠ 4423 同理：自动重连会对正主的画面反复发起抢流探测。
 */
const EXPIRED_CLOSE_CODES = new Set([4401, 4403, 4409, 4410, 4423, 4426])

/**
 * 空闲 keepalive 间隔。网关对浏览器 control WS 有 30s「无入站帧即踢断」的
 * 心跳窗口（BROWSER_IDLE_TIMEOUT_S，契约 §3.1「不看即停」）。纯观看时
 * 浏览器→网关方向没有任何帧（视频是反向的），必须周期性发文本 keepalive：
 * 既刷新心跳窗口、也驱动网关侧锁续期（锁 TTL 也是 30s）。否则每 30s 被踢
 * 一次、画面闪断重连。间隔取窗口的 1/3，容忍个别丢失。
 */
const KEEPALIVE_INTERVAL_MS = 10_000

/**
 * 模块级单例守卫：同一 wsUrl（即同一 udid）同时只允许一个活客户端。
 * HMR 双挂载 / 快速重进会开出第二个 control WS，撞 Agent 一次一台 gate
 * 回 busy——新建前强制 dispose 旧实例（网关另有服务端接管编排兜底）。
 */
const activeClients = new Map<string, { dispose(): void }>()

export function createScrcpyClient(opts: ScrcpyClientOptions) {
  const { wsUrl, ticket, canvas, callbacks = {} } = opts
  const serverOptions = {
    maxSize: 800,
    videoBitRate: 2_000_000,
    maxFps: 15,
    ...(opts.serverOptions ?? {}),
  }

  let ws: WebSocket | null = null
  let keepaliveTimer: ReturnType<typeof setInterval> | null = null
  // WebCodecs（硬解，需 https 安全上下文）或 TinyH264（纯 WASM 软解，http 也能上屏）
  let decoder: WebCodecsVideoDecoder | TinyH264Decoder | null = null
  let serializer: ScrcpyControlMessageSerializer | null = null
  let options: ScrcpyOptions3_3_3 | null = null

  // 视频流生产端：WS 帧一到就 enqueue，绝不懒执行（S1 handoff 丢字节铁律）
  let videoController: PushReadableStreamController<Uint8Array> | null = null
  let firstByteStripped = false

  let phase: ScrcpyClientPhase = 'idle'
  let disposed = false

  // 设备侧视频尺寸（坐标映射用）
  let deviceWidth = 0
  let deviceHeight = 0

  const setPhase = (p: ScrcpyClientPhase, detail?: string) => {
    if (phase === p) return
    phase = p
    callbacks.onPhase?.(p, detail)
  }
  const log = (m: string) => callbacks.onLog?.(m)

  /** 选 WebGL 渲染器，失败回退 Bitmap（二者都在 canvas 上屏） */
  function makeRenderer() {
    try {
      return new WebGLVideoFrameRenderer(canvas)
    } catch (e) {
      log(`WebGL 渲染器创建失败，回退 Bitmap：${(e as Error)?.message ?? e}`)
      return new BitmapVideoFrameRenderer(canvas)
    }
  }

  /** 建立视频解码管线：PushReadableStream → 解元数据 → 切包 → decoder.writable */
  async function startVideoPipeline() {
    options = new ScrcpyOptions3_3_3({
      audio: false,
      control: true,
      maxSize: serverOptions.maxSize,
      videoBitRate: serverOptions.videoBitRate,
      maxFps: serverOptions.maxFps,
    })
    serializer = new ScrcpyControlMessageSerializer(options)

    // 生产端：WS 帧推进来（enqueue 在 ws.onmessage 里做）
    const videoStream = new PushReadableStream<Uint8Array>((controller) => {
      videoController = controller
      // 不做任何懒 pull——source 回调仅用于抓住 controller。
    })

    setPhase('handshaking')
    // 解元数据（会消费流的头部）
    const { metadata, stream } = await options.parseVideoStreamMetadata(videoStream)
    if (disposed) return

    deviceWidth = metadata.width ?? 0
    deviceHeight = metadata.height ?? 0
    const codecName =
      ScrcpyVideoCodecNameMap.get(metadata.codec) ?? `0x${metadata.codec.toString(16)}`
    callbacks.onMetadata?.({
      deviceName: metadata.deviceName,
      codecName,
      width: deviceWidth,
      height: deviceHeight,
    })
    log(`视频元数据：${codecName} ${deviceWidth}x${deviceHeight} (${metadata.deviceName ?? '?'})`)

    const onDecoderSize = ({ width, height }: { width: number; height: number }) => {
      deviceWidth = width
      deviceHeight = height
      callbacks.onSizeChanged?.(width, height)
    }

    if (WebCodecsVideoDecoder.isSupported) {
      // 硬解（https / localhost 安全上下文）
      const wc = new WebCodecsVideoDecoder({ codec: metadata.codec, renderer: makeRenderer() })
      wc.sizeChanged(onDecoderSize)
      decoder = wc
    } else {
      // WebCodecs 在非安全上下文（内网 http 访问）不可用 → TinyH264 纯 WASM 软解
      // 兜底：http 也能上屏。仅支持 H264（安卓 scrcpy 默认即 H264）；帧率略低于
      // 硬解。鸿蒙/iOS 走 M-JPEG 播放器不经此路，本就 http 可显示。
      log('WebCodecs 不可用（非安全上下文），已回退 TinyH264 软解（H264，帧率略低）')
      const tiny = new TinyH264Decoder({ canvas })
      tiny.sizeChanged(onDecoderSize)
      decoder = tiny
    }

    setPhase('streaming')
    // 切包 → 灌进 decoder.writable。这个 pipe 一直跑到流关闭/出错。
    stream
      .pipeThrough(options.createMediaStreamTransformer())
      .pipeTo(decoder.writable as WritableStream<ScrcpyMediaStreamPacket>)
      .catch((e: unknown) => {
        if (disposed) return
        log(`视频管线结束：${(e as Error)?.message ?? e}`)
      })
  }

  /** 建立 WS 并接线 */
  function connect() {
    setPhase('connecting')
    // 子协议 ticket.<t>：网关须原样回选该子协议完成握手
    ws = new WebSocket(wsUrl, [`ticket.${ticket}`])
    ws.binaryType = 'arraybuffer'
    firstByteStripped = false

    ws.addEventListener('open', () => {
      log('control WS 已连接')
      startKeepalive()
      // 视频管线在 WS open 之后再拉起，确保 controller 就绪即有帧可推
      startVideoPipeline().catch((e) => {
        if (disposed) return
        setPhase('error', `视频初始化失败：${(e as Error)?.message ?? e}`)
      })
    })

    ws.addEventListener('message', (ev) => {
      if (disposed) return
      // 只处理二进制视频帧；服务端如发文本控制帧（如会话事件）可在此扩展
      if (typeof ev.data === 'string') {
        handleTextFrame(ev.data)
        return
      }
      let bytes = new Uint8Array(ev.data as ArrayBuffer)
      if (opts.stripDummyByte && !firstByteStripped) {
        firstByteStripped = true
        bytes = bytes.subarray(1)
        if (bytes.length === 0) return
      }
      // enqueue 可能返回 Promise（背压），但我们不 await——WS 帧不可阻塞事件循环；
      // 慢消费者由 PushReadableStream 内部缓冲，界与丢帧策略在网关侧（S1 结论）。
      // 流已被消费端取消/生产端关闭时 enqueue 会 reject，吞掉以免未处理拒绝。
      void videoController?.enqueue(bytes).catch(() => {})
    })

    ws.addEventListener('close', (ev) => {
      if (disposed) return
      stopKeepalive()
      log(`control WS 关闭 code=${ev.code} reason=${ev.reason || '-'}`)
      teardownStream()
      if (EXPIRED_CLOSE_CODES.has(ev.code)) {
        setPhase('expired', ev.reason || '会话已失效，请重新申请控制')
      } else if (ev.code === 1000) {
        setPhase('closed', '连接已关闭')
      } else {
        // 非正常关闭 → 交给上层决定是否重连
        setPhase('error', ev.reason || `连接断开 (code ${ev.code})`)
      }
    })

    ws.addEventListener('error', () => {
      if (disposed) return
      log('control WS 出错')
      // error 之后通常紧跟 close，phase 交由 close 事件决定
    })
  }

  /** 服务端文本帧（会话事件等）——P1 骨架，按需扩展 */
  function handleTextFrame(raw: string) {
    try {
      const frame = JSON.parse(raw)
      if (frame?.type === 'session_expired') {
        setPhase('expired', frame.message || '会话已失效')
      }
      log(`收到文本帧：${raw.slice(0, 200)}`)
    } catch {
      log(`收到非 JSON 文本帧：${raw.slice(0, 120)}`)
    }
  }

  /** 空闲 keepalive：WS 开着就每 KEEPALIVE_INTERVAL_MS 发一个文本帧，
   *  防网关 30s 无入站帧踢断（契约 §3.1）并驱动锁续期。 */
  function startKeepalive() {
    stopKeepalive()
    keepaliveTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send('{"type":"keepalive"}')
        } catch {
          /* ignore */
        }
      }
    }, KEEPALIVE_INTERVAL_MS)
  }

  function stopKeepalive() {
    if (keepaliveTimer) {
      clearInterval(keepaliveTimer)
      keepaliveTimer = null
    }
  }

  function teardownStream() {
    try {
      videoController?.close()
    } catch {
      /* ignore */
    }
    videoController = null
    if (decoder) {
      try {
        decoder.dispose()
      } catch {
        /* ignore */
      }
      decoder = null
    }
  }

  // ==================== 控制注入 ====================

  /** 发送序列化后的控制裸字节 */
  function send(bytes: Uint8Array) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(bytes)
    }
  }

  /** 设备当前尺寸（坐标映射用） */
  function deviceSize() {
    return { width: deviceWidth, height: deviceHeight }
  }

  /**
   * 注入触控。x/y 为**设备像素坐标**（调用方已完成 canvas→设备的映射）。
   * pointerId 默认 0；pressure：按下 1、抬起 0。
   */
  function injectTouch(
    action: MotionAction,
    x: number,
    y: number,
    opts2: { pointerId?: bigint; pressure?: number; buttons?: number } = {},
  ) {
    if (!serializer || !deviceWidth || !deviceHeight) return
    const isUp = action === AndroidMotionEventAction.Up
    // 触控：按下/移动时 buttons=Primary、pressure=1；抬起时清零（对齐 ya-webadb 官方示例）
    const bytes = serializer.injectTouch({
      action,
      pointerId: opts2.pointerId ?? 0n,
      pointerX: Math.round(x),
      pointerY: Math.round(y),
      videoWidth: deviceWidth,
      videoHeight: deviceHeight,
      pressure: opts2.pressure ?? (isUp ? 0 : 1),
      actionButton: 0,
      buttons: opts2.buttons ?? (isUp ? 0 : AndroidMotionEventButton.Primary),
    })
    send(bytes)
  }

  /** 便捷触控三态（供 canvas 事件调用） */
  const touchDown = (x: number, y: number) => injectTouch(AndroidMotionEventAction.Down, x, y)
  const touchMove = (x: number, y: number) => injectTouch(AndroidMotionEventAction.Move, x, y)
  const touchUp = (x: number, y: number) => injectTouch(AndroidMotionEventAction.Up, x, y)

  /** 注入单个按键（down+up） */
  function pressKey(keyCode: number) {
    if (!serializer) return
    send(
      serializer.injectKeyCode({
        action: AndroidKeyEventAction.Down,
        keyCode,
        repeat: 0,
        metaState: 0,
      }),
    )
    send(
      serializer.injectKeyCode({
        action: AndroidKeyEventAction.Up,
        keyCode,
        repeat: 0,
        metaState: 0,
      }),
    )
  }

  const pressHome = () => pressKey(AndroidKeyCode.AndroidHome)
  const pressBack = () => pressKey(AndroidKeyCode.AndroidBack)
  const pressAppSwitch = () => pressKey(AndroidKeyCode.AndroidAppSwitch)

  /**
   * 中文/任意文本注入：走 SET_CLIPBOARD(paste=true)。
   * scrcpy 的 injectText 只支持 ASCII，中文必须经剪贴板 paste。
   */
  function injectTextViaClipboard(text: string) {
    if (!serializer || !text) return
    const result = serializer.setClipboard({
      sequence: 0n, // 0 = 不要求 ack
      paste: true,
      content: text,
    })
    // setClipboard 可能返回 [bytes, ackPromise] 或 bytes
    const bytes = Array.isArray(result) ? result[0] : result
    send(bytes)
  }

  // ==================== 生命周期 ====================

  function start() {
    disposed = false
    // 单例守卫：拆掉同 wsUrl 的旧实例（HMR 双挂载/快速重进）再注册自己
    const prev = activeClients.get(wsUrl)
    if (prev && prev !== api) prev.dispose()
    activeClients.set(wsUrl, api)
    connect()
  }

  function dispose() {
    if (disposed) return
    disposed = true
    stopKeepalive()
    if (activeClients.get(wsUrl) === api) activeClients.delete(wsUrl)
    teardownStream()
    if (ws) {
      try {
        // 正常关闭（1000）：网关据此发 stop_scrcpy，Agent 优雅 release 编码器
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close(1000, 'client_dispose')
        }
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
    deviceSize,
    getPhase: () => phase,
    // 控制
    injectTouch,
    touchDown,
    touchMove,
    touchUp,
    pressHome,
    pressBack,
    pressAppSwitch,
    injectTextViaClipboard,
  }
  return api
}

export type ScrcpyClient = ReturnType<typeof createScrcpyClient>
