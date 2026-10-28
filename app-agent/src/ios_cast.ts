/**
 * iOS 投屏会话（I3）—— 实现 ScrcpySessionLike，让 ScrcpyManager 的 gate/data-WS/
 * 生命周期编排原样复用（与 HarmonyCastSession 同构第三路），内部换成 WDA 数据面：
 *
 *   帧出:HTTP GET http://127.0.0.1:9100（WDA 内置 MJPEG server，iproxy 转发）
 *        → FFD8..FFD9 魔数扫描切帧（multipart 头懒得解析，S2 spike 同款）→ 转发
 *   控制入:{t:'down|move|up',x,y} 二进制 JSON（与鸿蒙同壳）。**坐标=逻辑 point**
 *        ——meta 帧发 point 尺寸（如 iPad 810×1080），前端按 meta 归一化后天然
 *        落 point 系；帧本体是 @2x 物理像素（1620×2160），两者由前端各自使用，
 *        互不换算（I0-S2 铁律:WDA actions 吃 point，帧是像素）。
 *
 * WDA 无流式触控（没有 touchDown 持住的 API）——手势整段缓冲，up 到达时编译成
 * 一次 W3C actions POST（pointerMove→Down→[moves/pause]→Up）。代价:手势在抬手后
 * ~0.3-1s 才在真机执行（S2 实测 tap 990ms），观战控制可接受，与鸿蒙"连续拖动
 * 降级为手势注入"同一档妥协。
 *
 * WDA 会话策略（与 Midscene 执行共存的关键）：actions 必须挂 session。
 * **绝不无脑新建**——WDA 单活跃会话，新建会顶掉 Midscene 执行中的会话。
 * 先 GET /status 读现存 sessionId 搭车；没有才 POST /session 自建；收到
 * invalid session（被 Midscene 顶掉后）刷新重试一次。stop 时**不 DELETE 会话**
 * （可能是搭车来的）。
 */

import { log } from './log.js';
import { parseControlMessage, type HarmonyControlMsg } from './harmony_cast.js';
import type { WdaLike } from './wda.js';

/** 元数据帧（二进制 JSON,首字节 0x7B 与 JPEG 0xFFD8 区分）；width/height=逻辑 point */
export function buildIosMetaFrame(width: number, height: number): Uint8Array {
  return Buffer.from(JSON.stringify({ type: 'ios_meta', width, height }), 'utf-8');
}

/** 从累积缓冲里切出完整 JPEG 帧（FFD8..FFD9），返回剩余缓冲（纯函数可单测） */
export function extractJpegFrames(buf: Buffer): { frames: Buffer[]; rest: Buffer } {
  const SOI = Buffer.from([0xff, 0xd8]);
  const EOI = Buffer.from([0xff, 0xd9]);
  const frames: Buffer[] = [];
  let rest = buf;
  for (;;) {
    const start = rest.indexOf(SOI);
    if (start === -1) {
      // 无帧头：全是 multipart 头/半截尾巴，只保尾部防无限涨
      return { frames, rest: rest.length > 4096 ? rest.subarray(rest.length - 4096) : rest };
    }
    const end = rest.indexOf(EOI, start + 2);
    if (end === -1) return { frames, rest: rest.subarray(start) };
    frames.push(rest.subarray(start, end + 2));
    rest = rest.subarray(end + 2);
  }
}

// ==================== 手势 → W3C actions 编译 ====================

export interface GesturePoint {
  t: HarmonyControlMsg['t'];
  x: number;
  y: number;
  /** 到达时刻（ms） */
  ts: number;
}

/** 滑动编译 move 步数：**1 = 首尾直线**。真机实测(iPad7)XCTest 每个 move 合成
 *  ~0.4-0.5s——6 步 3.15s / 2 步 1.6s / 1 步 1.3s(比 dragfromtoforduration 的
 *  2.0s 还快)。观战滚动几乎全是直线,路径保形不值 2s。 */
const SWIPE_MOVE_STEPS = 1;
/** 滑动**总**时长钳制：压缩成快速甩动。按真实时长慢放（旧实现）会变成无惯性的
 *  慢动作拖动——浏览器里 1s 的拖拽在设备上回放 1s+，滚动经常不生效;压到
 *  60~300ms 让系统识别为 swipe/fling（带惯性），执行也快。 */
const SWIPE_TOTAL_MIN_MS = 60;
const SWIPE_TOTAL_MAX_MS = 300;
/** 单步 pointerMove 时长下限（过短 WDA 忽略） */
const MOVE_DURATION_MIN_MS = 10;
/** 纯点按的按住时长钳制（长按语义天然保留,上限防呆滞） */
const PRESS_MIN_MS = 50;
const PRESS_MAX_MS = 3_000;

/**
 * 手势点序列 → W3C actions 载荷（纯函数）。
 * 单指:pointerMove(0,起点)→pointerDown→[逐段 pointerMove / 无移动则 pause]→pointerUp。
 * 点按/长按保留真实按住时长；滑动**不还原节奏**——抽样 ≤SWIPE_MOVE_STEPS 个点、
 * 总时长压缩到 SWIPE_TOTAL_MIN/MAX 区间（快速甩动，路径保形）。
 */
export function compileGestureToActions(points: GesturePoint[]): Record<string, unknown> | null {
  if (points.length < 2) return null;
  const down = points[0]!;
  const up = points[points.length - 1]!;
  if (down.t !== 'down' || up.t !== 'up') return null;

  let moves = points.slice(1, -1).filter((p) => p.t === 'move');
  if (moves.length > SWIPE_MOVE_STEPS) {
    if (SWIPE_MOVE_STEPS === 1) {
      moves = [moves[moves.length - 1]!]; // 直线:只保尾点（首点在 pointerDown 处）
    } else {
      const sampled: GesturePoint[] = [];
      const step = (moves.length - 1) / (SWIPE_MOVE_STEPS - 1);
      for (let i = 0; i < SWIPE_MOVE_STEPS; i++) sampled.push(moves[Math.round(i * step)]!);
      moves = sampled;
    }
  }

  const seq: Record<string, unknown>[] = [
    { type: 'pointerMove', duration: 0, x: down.x, y: down.y },
    { type: 'pointerDown', button: 0 },
  ];
  if (moves.length === 0) {
    const held = Math.min(Math.max(up.ts - down.ts, PRESS_MIN_MS), PRESS_MAX_MS);
    seq.push({ type: 'pause', duration: held });
  } else {
    // 甩动压缩：真实拖动时长 → 钳到 [60,300]ms 均摊到各步
    const realMs = moves[moves.length - 1]!.ts - down.ts;
    const totalMs = Math.min(Math.max(realMs, SWIPE_TOTAL_MIN_MS), SWIPE_TOTAL_MAX_MS);
    const perMove = Math.max(Math.round(totalMs / moves.length), MOVE_DURATION_MIN_MS);
    for (const m of moves) {
      seq.push({ type: 'pointerMove', duration: perMove, x: m.x, y: m.y });
    }
  }
  seq.push({ type: 'pointerUp', button: 0 });

  return {
    actions: [
      { type: 'pointer', id: 'finger1', parameters: { pointerType: 'touch' }, actions: seq },
    ],
  };
}

// ==================== 会话实现 ====================

/** 最小 HTTP 形状（会话/actions 用；DI 便于单测） */
type HttpLike = (
  url: string,
  init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>;

/** MJPEG 流打开器（DI:测试直接灌 chunk，不起真 HTTP） */
export type MjpegOpener = (handlers: {
  onChunk(chunk: Buffer): void;
  onEnd(): void;
  onError(err: Error): void;
}) => { abort(): void };

export interface IosCastOptions {
  serial: string;
  wda: WdaLike;
  mjpegPort?: number;
  httpImpl?: HttpLike;
  openMjpeg?: MjpegOpener;
  /** actions POST 超时（缺省 ACTIONS_TIMEOUT_MS；单测注入毫秒级） */
  actionsTimeoutMs?: number;
}

/** 早到帧缓冲上限（start 返回到 onVideoBytes 注册之间的窗口，与鸿蒙一致） */
const EARLY_FRAME_MAX = 4;
/** MJPEG 累积缓冲上限（半截帧防涨爆；超限保尾部,偶发花一帧可接受,spike 同款） */
const MJPEG_BUF_MAX = 4 * 1024 * 1024;
const MJPEG_BUF_KEEP = 2 * 1024 * 1024;
/** 手势原始点缓冲上限（move 风暴防护:满了合并到队尾） */
const GESTURE_POINTS_MAX = 256;
/** 手势最长时长（超时视为脏数据丢弃,如 up 丢失后的孤儿手势） */
const GESTURE_MAX_AGE_MS = 10_000;
/** actions POST 超时：正常 tap/swipe ~1-1.5s（S2 实证 tap 990ms），留足余量。
 *  超时多因搭车了失效残留 session（失效 session GET 能用但 POST actions 卡死）
 *  → 触发一次「清缓存强制新建重试」，故不必设太长空等。 */
const ACTIONS_TIMEOUT_MS = 5_000;

/**
 * WDA MJPEG 降载设置（防前端卡顿）。WDA 默认 mjpegScalingFactor=100 即**全分辨率**
 * ——iPad 单帧 1620×2160，前端 createImageBitmap 解码 + 2160 高画布 drawImage 吃力
 * 卡顿。降到 50 = 半分辨率(810×1080，恰等于逻辑 point 尺寸)，帧字节≈1/4，观战够清。
 * framerate 12 略提流畅感，quality 30 平衡清晰度/带宽。经 appium/settings 下发。
 */
const MJPEG_SETTINGS: Record<string, number> = {
  mjpegScalingFactor: 50,
  mjpegServerFramerate: 12,
  mjpegServerScreenshotQuality: 30,
};

export class IosCastSession {
  private readonly mjpegPort: number;
  private readonly http: HttpLike;
  private readonly actionsTimeoutMs: number;
  private videoCb: ((bytes: Uint8Array) => void) | undefined;
  private closedCb: (() => void) | undefined;
  private earlyFrames: Uint8Array[] = [];
  private mjpeg: { abort(): void } | undefined;
  private wdaSessionId: string | null = null;
  private gesture: GesturePoint[] = [];
  /** actions 串行链（在途 ≤1；手势级粒度,天然稀疏） */
  private dispatching: Promise<void> = Promise.resolve();
  private disposed = false;
  private state: 'idle' | 'starting' | 'running' | 'stopped' = 'idle';

  constructor(private readonly opts: IosCastOptions) {
    this.mjpegPort = opts.mjpegPort ?? 9100;
    this.http = opts.httpImpl ?? (fetch as unknown as HttpLike);
    this.actionsTimeoutMs = opts.actionsTimeoutMs ?? ACTIONS_TIMEOUT_MS;
  }

  /** WDA 自愈 → 取 point 尺寸发 meta → 开 MJPEG 拉流 */
  async start(): Promise<void> {
    if (this.state !== 'idle') throw new Error(`IosCast 非法状态: ${this.state}`);
    this.state = 'starting';
    try {
      await this.opts.wda.ensureAlive(this.opts.serial);
      const sid = await this.ensureWdaSession();
      const rect = await this.windowRect(sid);
      await this.configureMjpeg(sid); // 降载：半分辨率/限帧/降质，防前端卡顿
      this.pushFrame(buildIosMetaFrame(rect.width, rect.height));

      const open = this.opts.openMjpeg ?? this.defaultMjpegOpener();
      this.mjpeg = open({
        onChunk: (c) => this.onMjpegChunk(c),
        onEnd: () => this.onStreamGone('MJPEG 流结束'),
        onError: (err) => this.onStreamGone(`MJPEG 流错误: ${err.message}`),
      });
      this.state = 'running';
      log('info', 'iOS 投屏帧流已开', {
        serial: this.opts.serial,
        pointSize: `${rect.width}x${rect.height}`,
      });
    } catch (err) {
      this.state = 'stopped';
      throw err;
    }
  }

  onVideoBytes(cb: (bytes: Uint8Array) => void): void {
    this.videoCb = cb;
    for (const frame of this.earlyFrames) cb(frame);
    this.earlyFrames = [];
  }

  onClosed(cb: () => void): void {
    this.closedCb = cb;
  }

  /**
   * 控制入：{t,x,y}（point 坐标）→ 手势缓冲；up 完成时编译 W3C actions 串行下发。
   * down 重入（up 丢失）= 弃旧起新;超龄手势直接丢。
   */
  writeControl(bytes: Uint8Array): void {
    if (this.disposed) return;
    const msg = parseControlMessage(bytes);
    if (!msg) return;
    const point: GesturePoint = { ...msg, ts: Date.now() };
    if (msg.t === 'down') {
      this.gesture = [point];
      return;
    }
    if (this.gesture.length === 0) return; // 无 down 的孤儿 move/up:丢
    if (msg.t === 'move') {
      if (this.gesture.length >= GESTURE_POINTS_MAX) this.gesture[this.gesture.length - 1] = point;
      else this.gesture.push(point);
      return;
    }
    // up:手势完成
    this.gesture.push(point);
    const points = this.gesture;
    this.gesture = [];
    if (point.ts - points[0]!.ts > GESTURE_MAX_AGE_MS) return; // 孤儿/呆滞手势
    const payload = compileGestureToActions(points);
    if (!payload) return;
    this.dispatching = this.dispatching
      .then(() => this.postActions(payload))
      .catch(() => {
        /* postActions 内部已 log,链不断 */
      });
  }

  /** 优雅停：断拉流即可——WDA/设备侧无需清理（server 常驻）;不 DELETE 会话（可能是搭车的） */
  async stop(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    this.state = 'stopped';
    this.gesture = [];
    try {
      this.mjpeg?.abort();
    } catch {
      /* 已断 */
    }
    this.mjpeg = undefined;
    log('info', 'iOS 投屏会话已停', { serial: this.opts.serial });
    this.closedCb?.();
  }

  // ==================== 内部 ====================

  private mjpegBuf: Buffer = Buffer.alloc(0);

  private onMjpegChunk(chunk: Buffer): void {
    if (this.disposed) return;
    this.mjpegBuf = this.mjpegBuf.length ? Buffer.concat([this.mjpegBuf, chunk]) : chunk;
    const { frames, rest } = extractJpegFrames(this.mjpegBuf);
    this.mjpegBuf = rest;
    for (const f of frames) this.pushFrame(new Uint8Array(f));
    if (this.mjpegBuf.length > MJPEG_BUF_MAX) {
      this.mjpegBuf = this.mjpegBuf.subarray(this.mjpegBuf.length - MJPEG_BUF_KEEP);
    }
  }

  private onStreamGone(reason: string): void {
    if (this.disposed) return;
    log('warn', 'iOS 投屏流中断', { serial: this.opts.serial, reason });
    // 联动拆会话（ScrcpyManager onClosed → teardown），与鸿蒙会话自死语义一致
    void this.stop();
  }

  private pushFrame(frame: Uint8Array): void {
    if (this.disposed) return;
    if (this.videoCb) {
      this.videoCb(frame);
      return;
    }
    if (this.earlyFrames.length < EARLY_FRAME_MAX) this.earlyFrames.push(frame);
    else {
      // 超上限丢旧视频帧,但 meta 帧(下标0)永不丢
      this.earlyFrames.splice(1, 1);
      this.earlyFrames.push(frame);
    }
  }

  /**
   * 取 WDA 会话。默认搭车 /status.sessionId（别顶掉正在执行的 Midscene 会话——
   * observe 回放并发场景），没有才自建。
   *
   * ⚠ forceNew：搭车来的 sessionId 可能是**上一次 Midscene 执行残留的失效
   * session**——真机实证:失效 session `GET window/rect` 仍能应付（所以 start 不
   * 报错），但 `POST actions` 会**卡死**（不像不存在的 id 快速 404）。postActions
   * 超时后带 forceNew=true 重来,跳过搭车直接新建一个干净 session。
   */
  private async ensureWdaSession(forceNew = false): Promise<string> {
    if (this.wdaSessionId) return this.wdaSessionId;
    const base = `http://127.0.0.1:${this.opts.wda.port}`;
    if (!forceNew) {
      const status = (await (await this.http(`${base}/status`)).json()) as Record<string, unknown>;
      const existing = status['sessionId'];
      if (typeof existing === 'string' && existing) {
        this.wdaSessionId = existing;
        log('info', 'WDA 会话搭车（复用现存活跃会话）', { serial: this.opts.serial });
        return existing;
      }
    }
    const resp = await this.http(`${base}/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ capabilities: { alwaysMatch: {} } }),
    });
    const created = (await resp.json()) as {
      value?: { sessionId?: string };
      sessionId?: string;
    };
    const sid = created.value?.sessionId ?? created.sessionId;
    if (!sid) throw new Error('WDA 建会话失败（无 sessionId）');
    this.wdaSessionId = sid;
    log('info', 'WDA 会话新建', { serial: this.opts.serial });
    // 只对**自建**会话关静默等待（每动作省 ~50ms,免费）；搭车的（可能是
    // Midscene 执行会话）不动——它的定位截图可能依赖 quiescence 等待
    void this.http(`${base}/session/${sid}/appium/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        settings: { waitForIdleTimeout: 0, animationCoolOffTimeout: 0 },
      }),
    }).catch(() => {});
    return sid;
  }

  /** 下发 MJPEG 降载设置（best-effort：失败只是不优化，不影响投屏） */
  private async configureMjpeg(sid: string): Promise<void> {
    try {
      await this.http(`http://127.0.0.1:${this.opts.wda.port}/session/${sid}/appium/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: MJPEG_SETTINGS }),
      });
    } catch (err) {
      log('warn', 'MJPEG 降载设置下发失败（画面可能偏大偏卡）', {
        serial: this.opts.serial,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  /** 窗口 point 尺寸（meta 帧用；W3C actions 也吃这个坐标系） */
  private async windowRect(sid: string): Promise<{ width: number; height: number }> {
    const base = `http://127.0.0.1:${this.opts.wda.port}`;
    const resp = await this.http(`${base}/session/${sid}/window/rect`);
    const data = (await resp.json()) as { value?: { width?: number; height?: number } };
    const width = Number(data.value?.width) || 0;
    const height = Number(data.value?.height) || 0;
    if (!width || !height) throw new Error('WDA window/rect 无有效尺寸');
    return { width, height };
  }

  /**
   * actions 下发。失效会话自愈：invalid-session 响应 **或** 超时（失效 session
   * POST 卡死）→ 清缓存 + forceNew 重建 + 重试一次。单手势失败丢弃继续，不拆会话
   * （与鸿蒙单条注入失败同语义）。
   */
  private async postActions(payload: Record<string, unknown>, retried = false): Promise<void> {
    if (this.disposed) return;
    const base = `http://127.0.0.1:${this.opts.wda.port}`;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), this.actionsTimeoutMs);
    try {
      // 重试路径 forceNew：搭车的可能是上次执行残留的失效 session（POST 卡死）
      const sid = await this.ensureWdaSession(retried);
      const resp = await this.http(`${base}/session/${sid}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      if (!resp.ok) {
        const body = JSON.stringify(await resp.json().catch(() => ({})));
        if (!retried && /invalid session|session does not exist/i.test(body)) {
          this.wdaSessionId = null;
          return await this.postActions(payload, true);
        }
        throw new Error(`actions HTTP ${resp.status}: ${body.slice(0, 200)}`);
      }
    } catch (err) {
      // 超时（多为失效 session POST 卡死）→ 强制新建会话重试一次
      if (!retried && ctrl.signal.aborted && !this.disposed) {
        this.wdaSessionId = null;
        log('warn', 'iOS 触控注入超时，疑似 WDA 会话失效，重建重试', {
          serial: this.opts.serial,
        });
        return await this.postActions(payload, true);
      }
      log('warn', 'iOS 触控注入失败', {
        serial: this.opts.serial,
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      clearTimeout(timer);
    }
  }

  /** 默认 MJPEG 打开器：HTTP GET 流式读（WDA MJPEG server 是 HTTP multipart） */
  private defaultMjpegOpener(): MjpegOpener {
    const url = `http://127.0.0.1:${this.mjpegPort}`;
    return (handlers) => {
      const ctrl = new AbortController();
      void (async () => {
        try {
          const resp = await fetch(url, { signal: ctrl.signal });
          if (!resp.ok || !resp.body) throw new Error(`MJPEG HTTP ${resp.status}`);
          const reader = resp.body.getReader();
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            if (value) handlers.onChunk(Buffer.from(value));
          }
          handlers.onEnd();
        } catch (err) {
          if (ctrl.signal.aborted) return; // 主动 stop:不是错误
          handlers.onError(err instanceof Error ? err : new Error(String(err)));
        }
      })();
      return { abort: () => ctrl.abort() };
    };
  }
}
