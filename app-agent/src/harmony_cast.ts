/**
 * 鸿蒙 NEXT 投屏会话（H3）—— 实现与 ScrcpySessionLike 相同的接口形状，让
 * ScrcpyManager 的 gate/data-WS/生命周期整套编排原样复用，内部换成 hdckit
 * 单连接数据面（uitest 守护进程 8012,S2 spike 实证）：
 *
 *   帧出:startCaptureScreen → 每帧完整 JPEG（M-JPEG,画面变化才回帧,~10fps）
 *   控制入:同一连接的 touchDown/Move/Up（S2 铁律:开第二个 uitest 客户端会把
 *          采集流打崩——所以触控绝不走 `hdc shell uitest uiInput`）
 *
 * 数据面帧格式（Agent → 浏览器,经网关 VideoPump 二进制透传）：
 *   - 元数据帧:二进制 JSON `{"type":"harmony_meta","width":..,"height":..}`
 *     （首字节 0x7B='{',浏览器以此与 JPEG 的 0xFFD8 区分）
 *   - 视频帧:整帧 JPEG
 * 控制帧（浏览器 → Agent,二进制 JSON）:`{"t":"down|move|up","x":..,"y":..}`
 * 坐标=设备物理像素（浏览器按 meta 宽高归一化换算）。
 *
 * move 风暴防护:指针移动事件密度远超守护进程承受力（spike 实证连发 move 会打
 * 崩 daemon）——串行队列 + 「队尾 move 合并」,任意时刻在途 RPC ≤1,move 只保最新。
 *
 * DI createDriver 工厂便于单测（假 driver 验证队列/合并/生命周期,不碰真机）。
 */

import { Hdc } from 'hdckit';

import { hdcServerPort } from './hdc_devices.js';
import { log } from './log.js';

/** 浏览器 → Agent 的触控消息（二进制 JSON 解码后） */
export interface HarmonyControlMsg {
  t: 'down' | 'move' | 'up';
  x: number;
  y: number;
}

/** 解析控制帧：非 JSON / 结构不符返回 null（安卓 scrcpy 二进制误投时安静丢弃） */
export function parseControlMessage(data: Uint8Array): HarmonyControlMsg | null {
  // 快速否定：JSON 必以 '{' (0x7B) 开头，scrcpy 控制字节首字节是消息类型枚举
  if (data.length < 2 || data[0] !== 0x7b) return null;
  try {
    const parsed = JSON.parse(Buffer.from(data).toString('utf-8')) as Record<string, unknown>;
    const t = parsed['t'];
    const x = parsed['x'];
    const y = parsed['y'];
    if (t !== 'down' && t !== 'move' && t !== 'up') return null;
    if (typeof x !== 'number' || typeof y !== 'number') return null;
    return { t, x: Math.round(x), y: Math.round(y) };
  } catch {
    return null;
  }
}

// ==================== 手势缓冲 → 语义注入（滑动失灵的根治） ====================
//
// 逐事件 touchDown/Move/Up 流式注入的实证问题:每个 RPC ~100-300ms,down 与首个
// move 之间的静止期让设备把快速滑动认成「按住→点击」（真机实测:左滑翻页变成
// 打开了 down 点上的应用）。时序永远不像真手势——根治 = 整段手势缓冲,抬手时分类:
//   点按/长按 → touchDown→(按住时长)→touchUp 逐事件(两次 RPC,时序不敏感);
//   滑动     → uitest 原生 `Driver.swipe(x1,y1,x2,y2,speed)` 一发入魂(系统级
//              手势,必然滚动/翻页带惯性;经 hdckit 同一连接 callHypiumApi,与
//              帧流并存安全——inputText/aiAct 同路已实证)。
// 代价:慢速拖动不再实时跟手(抬手才注入)——RPC 延迟下本来也谈不上跟手,
// 与 iOS「抬手后整段注入」语义拉齐。

/** 手势缓冲点 */
export interface HmGesturePoint {
  t: HarmonyControlMsg['t'];
  x: number;
  y: number;
  ts: number;
}

/** 抬手后的注入操作 */
export type HarmonyOp =
  | { kind: 'tap'; x: number; y: number; heldMs: number }
  | { kind: 'swipe'; x1: number; y1: number; x2: number; y2: number; speed: number };

/** 位移 ≤ 此值(设备像素)视为点按（1084 宽屏上 ~24px 即指尖抖动量级） */
const TAP_MAX_DIST_PX = 24;
/** 点按按住时长上限（防呆滞;>该值仍保长按语义） */
const TAP_HELD_MAX_MS = 1_500;
/** swipe 速度钳制（px/s;hypium 合法域 200~40000,过快设备端易丢） */
const SWIPE_SPEED_MIN = 600;
const SWIPE_SPEED_MAX = 15_000;
/** 手势缓冲点上限（move 风暴防护:满了替换末位） */
const GESTURE_POINTS_MAX = 128;
/** 孤儿手势超龄丢弃（up 丢失后残留） */
const GESTURE_MAX_AGE_MS = 10_000;

/**
 * 手势点序列 → 注入操作（纯函数）。残缺（无 down/无 up）回 null。
 * 位移小=点按（保真实按住时长）；位移大=swipe，speed 按真实手速换算钳制。
 */
export function classifyGesture(points: HmGesturePoint[]): HarmonyOp | null {
  if (points.length < 2) return null;
  const down = points[0]!;
  const up = points[points.length - 1]!;
  if (down.t !== 'down' || up.t !== 'up') return null;
  const dx = up.x - down.x;
  const dy = up.y - down.y;
  const dist = Math.hypot(dx, dy);
  if (dist <= TAP_MAX_DIST_PX) {
    return {
      kind: 'tap',
      x: down.x,
      y: down.y,
      heldMs: Math.min(Math.max(up.ts - down.ts, 0), TAP_HELD_MAX_MS),
    };
  }
  const durS = Math.max((up.ts - down.ts) / 1_000, 0.05);
  const speed = Math.min(Math.max(Math.round(dist / durS), SWIPE_SPEED_MIN), SWIPE_SPEED_MAX);
  return { kind: 'swipe', x1: down.x, y1: down.y, x2: up.x, y2: up.y, speed };
}

/** 元数据帧（二进制 JSON,首字节 0x7B 与 JPEG 0xFFD8 区分） */
export function buildMetaFrame(width: number, height: number): Uint8Array {
  return Buffer.from(JSON.stringify({ type: 'harmony_meta', width, height }), 'utf-8');
}

/** hdckit UiDriver 最小契约（单测替身用）。swipe = uitest 原生系统级滑动手势
 *  （hdckit 未公开,缺省工厂借其私有 send 走 callHypiumApi Driver.swipe 挂上;
 *  与 inputText/aiAct 同路,单连接并存已实证安全）。 */
export interface HarmonyDriverLike {
  start(): Promise<void>;
  stop(): Promise<void>;
  getDisplaySize(): Promise<{ width?: number; height?: number } | undefined>;
  startCaptureScreen(cb: (frame: Buffer) => void, options?: { scale: number }): Promise<void>;
  stopCaptureScreen(): Promise<void>;
  touchDown(x: number, y: number): Promise<void>;
  touchMove(x: number, y: number): Promise<void>;
  touchUp(x: number, y: number): Promise<void>;
  swipe(x1: number, y1: number, x2: number, y2: number, speed: number): Promise<void>;
  /** 短点按（单 RPC;down+up 双 RPC 延迟减半） */
  click(x: number, y: number): Promise<void>;
}

export interface HarmonyCastOptions {
  serial: string;
  hdcPath: string;
  /** 帧缩放（0~1）；缺省 0.5——1084 宽半分辨率下单帧 ~60-115KB,观战够清晰 */
  scale?: number;
  /** DI:driver 工厂（单测替身）；缺省 hdckit 真连接 */
  createDriver?: () => Promise<HarmonyDriverLike>;
}

/** 早到帧缓冲上限（start 返回到 onVideoBytes 注册之间的窗口） */
const EARLY_FRAME_MAX = 4;

export class HarmonyCastSession {
  private driver: HarmonyDriverLike | undefined;
  private videoCb: ((bytes: Uint8Array) => void) | undefined;
  private closedCb: (() => void) | undefined;
  private earlyFrames: Uint8Array[] = [];
  private ops: HarmonyOp[] = [];
  private gesture: HmGesturePoint[] = [];
  private draining = false;
  private disposed = false;
  private state: 'idle' | 'starting' | 'running' | 'stopped' = 'idle';

  constructor(private readonly opts: HarmonyCastOptions) {}

  /** 建 hdckit 连接 → 起守护进程 → 查尺寸 → 开帧流（meta 帧先行入缓冲） */
  async start(): Promise<void> {
    if (this.state !== 'idle') throw new Error(`HarmonyCast 非法状态: ${this.state}`);
    this.state = 'starting';
    try {
      const create =
        this.opts.createDriver ??
        (async () => {
          const client = Hdc.createClient({ bin: this.opts.hdcPath, port: hdcServerPort() });
          const raw = await client.getTarget(this.opts.serial).createUiDriver();
          await raw.start();
          const anyRaw = raw as unknown as Record<string, unknown> & {
            send(method: string, api: string, args?: unknown): Promise<unknown>;
          };
          // swipe 借 hdckit 私有 send:callHypiumApi 自动加 Driver. 前缀,args=位置参数
          // （与 hdckit 自家 inputText 同构;钉版 0.12.1,升级时须复核 send 形状）
          const driver = raw as unknown as HarmonyDriverLike;
          driver.swipe = async (x1, y1, x2, y2, speed) => {
            await anyRaw.send('callHypiumApi', 'swipe', [x1, y1, x2, y2, speed]);
          };
          driver.click = async (x, y) => {
            await anyRaw.send('callHypiumApi', 'click', [x, y]);
          };
          return driver;
        });
      const driver = await create();
      this.driver = driver;

      const size = await driver.getDisplaySize();
      const width = size?.width ?? 0;
      const height = size?.height ?? 0;
      this.pushFrame(buildMetaFrame(width, height));

      await driver.startCaptureScreen(
        (frame) => this.pushFrame(new Uint8Array(frame)),
        { scale: this.opts.scale ?? 0.5 },
      );
      this.state = 'running';
      log('info', '鸿蒙投屏帧流已开', {
        serial: this.opts.serial,
        size: `${width}x${height}`,
      });
    } catch (err) {
      this.state = 'stopped';
      await this.disposeDriver();
      throw err;
    }
  }

  onVideoBytes(cb: (bytes: Uint8Array) => void): void {
    this.videoCb = cb;
    // 补发 start→注册窗口内的早到帧（meta 帧总在最前）
    for (const frame of this.earlyFrames) cb(frame);
    this.earlyFrames = [];
  }

  onClosed(cb: () => void): void {
    this.closedCb = cb;
  }

  /**
   * 控制入：手势缓冲（down 起新/move 追加/up 分类入队），抬手才注入。
   * down 重入（up 丢失）= 弃旧起新;孤儿 move/up、超龄手势丢弃。
   */
  writeControl(bytes: Uint8Array): void {
    if (this.disposed) return;
    const msg = parseControlMessage(bytes);
    if (!msg) return;
    const point: HmGesturePoint = { ...msg, ts: Date.now() };
    if (msg.t === 'down') {
      this.gesture = [point];
      return;
    }
    if (this.gesture.length === 0) return; // 无 down 的孤儿
    if (msg.t === 'move') {
      if (this.gesture.length >= GESTURE_POINTS_MAX) this.gesture[this.gesture.length - 1] = point;
      else this.gesture.push(point);
      return;
    }
    // up:分类入队
    this.gesture.push(point);
    const points = this.gesture;
    this.gesture = [];
    if (point.ts - points[0]!.ts > GESTURE_MAX_AGE_MS) return;
    const op = classifyGesture(points);
    if (!op) return;
    this.ops.push(op);
    void this.drain();
  }

  private async drain(): Promise<void> {
    if (this.draining || this.disposed || !this.driver) return;
    this.draining = true;
    try {
      while (this.ops.length && !this.disposed) {
        const op = this.ops.shift() as HarmonyOp;
        try {
          if (op.kind === 'swipe') {
            // 系统级滑动手势:必然滚动/翻页带惯性(逐事件注入时序不像真手势,
            // 会被认成点击——真机实证的翻车点)
            await this.driver.swipe(op.x1, op.y1, op.x2, op.y2, op.speed);
          } else if (op.heldMs < 600) {
            // 短点按:Driver.click 单 RPC(down+up 双 RPC 延迟减半)
            await this.driver.click(op.x, op.y);
          } else {
            // 长按:down/up 逐事件保真实按住时长
            await this.driver.touchDown(op.x, op.y);
            await new Promise((r) => setTimeout(r, op.heldMs));
            await this.driver.touchUp(op.x, op.y);
          }
        } catch (err) {
          // 单手势失败：丢弃继续（守护进程偶发 hypium 异常,不因此拆会话）
          log('warn', '鸿蒙触控注入失败', {
            serial: this.opts.serial,
            op: op.kind,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
    } finally {
      this.draining = false;
    }
  }

  private pushFrame(frame: Uint8Array): void {
    if (this.disposed) return;
    if (this.videoCb) {
      this.videoCb(frame);
      return;
    }
    if (this.earlyFrames.length < EARLY_FRAME_MAX) this.earlyFrames.push(frame);
    // 超上限丢旧视频帧,但 meta 帧(下标0)永不丢
    else if (this.earlyFrames.length >= EARLY_FRAME_MAX) {
      this.earlyFrames.splice(1, 1);
      this.earlyFrames.push(frame);
    }
  }

  /** 优雅停：停帧流 + 断连接（幂等；异常吞掉——守护进程可能已死） */
  async stop(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    this.state = 'stopped';
    this.ops = [];
    this.gesture = [];
    await this.disposeDriver();
    log('info', '鸿蒙投屏会话已停', { serial: this.opts.serial });
    this.closedCb?.();
  }

  private async disposeDriver(): Promise<void> {
    const driver = this.driver;
    this.driver = undefined;
    if (!driver) return;
    try {
      await driver.stopCaptureScreen();
    } catch {
      /* 已死/未开帧流 */
    }
    try {
      await driver.stop();
    } catch {
      /* 连接已断 */
    }
  }
}
