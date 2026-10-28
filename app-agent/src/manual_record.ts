/**
 * 手动操作录制 —— 投屏触控流 → VL 语义化 → 可回放步骤（操作台「手动录制」）。
 *
 * 数据源：浏览器经 data-WS 下发的控制裸字节（ScrcpyManager tee 出来，
 * **只旁观绝不阻塞/修改注入**）。一条控制消息 = 一个 WS 帧（浏览器逐条 send），
 * 逐帧解析即可。tee 在注入/合并之前，安卓 scrcpy 二进制与鸿蒙 {t,x,y} JSON
 * 都全量可见：
 *   - android：scrcpy 二进制（下方锁版本布局），坐标在**缩放流坐标系**须换算；
 *   - harmony：HarmonyCastSession 的二进制 JSON `{"t":"down|move|up","x","y"}`，
 *     坐标**已是设备物理像素**（浏览器按 meta 换算后下发），零换算。
 *     截图走 snapshot_display（JPEG，不碰 uitest 守护进程，与帧流并存安全），
 *     画圈前解码成位图再编回 PNG 给 VL。系统键/剪贴板注入鸿蒙投屏不支持，
 *     对应分支天然不触发。
 *
 * 语义化：手指按下瞬间异步 adb screencap（点击生效在抬起，DOWN 时抓的是
 * 动作前画面）→ 把截图+坐标交给用户 VISION 模型「描述该处元素」→ 录成
 * aiTap/aiLongPress: "<描述>"——与 AI 录制/探索生成**同一种语义 YAML**，
 * 跨设备可回放。滑动手势零 VL（起终点算 direction+distance → Swipe）；
 * Home/Back/最近任务键与剪贴板粘贴文本（aiInput，配对上一次点击的描述）
 * 直接解析，零 VL。识别经 promise 链按序落步骤，乱序不可能。
 *
 * 消息布局锁 @yume-chan/scrcpy 3.3.3（大端）：
 *   InjectTouch(type=2, 32B): u8 type, u8 action, u64 pointerId, u32 x, u32 y,
 *     u16 videoW, u16 videoH, u16 pressure, u32 actionButton, u32 buttons
 *   InjectKeyCode(type=0, 14B): u8 type, u8 action, u32 keyCode, u32 repeat, u32 meta
 *   SetClipboard(type=9, ≥14B): u8 type, u64 sequence, u8 paste, u32 len, utf8
 * 防御式解析：type/长度不匹配一律忽略（版本升级先跑单测再放行）。
 *
 * per-user modelConfig 内存态、stop 即清（G9 铁律，同 AutomationSession）。
 */

import { execFile } from 'node:child_process';

import * as jpeg from 'jpeg-js';
import { PNG } from 'pngjs';

import type { AppModelConfig } from './automation.js';
import { DeviceTouchSource, type DeviceTouchSourceOpts } from './device_touch.js';
import type { DevicePlatform } from './frames.js';
import { parseControlMessage as parseHarmonyControl } from './harmony_cast.js';
import { log } from './log.js';
import { stepsToYamlFlow, type RecoveredStep } from './recover.js';
import { hdcSnapshotJpeg } from './screenshot.js';

// ==================== 控制消息解析（纯函数，锁版本布局） ====================

export interface ParsedTouch {
  kind: 'touch';
  /** 0=down 1=up 2=move */
  action: number;
  x: number;
  y: number;
  /** 消息内嵌的视频流坐标系尺寸（scrcpy maxSize 缩放后，≠设备像素！） */
  videoW: number;
  videoH: number;
}
export interface ParsedKey {
  kind: 'key';
  /** 0=down 1=up */
  action: number;
  keyCode: number;
}
export interface ParsedClipboard {
  kind: 'clipboard';
  paste: boolean;
  text: string;
}
export type ParsedControl = ParsedTouch | ParsedKey | ParsedClipboard;

export function parseControlMessage(buf: Buffer): ParsedControl | null {
  if (buf.length < 1) return null;
  const type = buf[0];
  if (type === 2 && buf.length === 32) {
    // InjectTouch —— 坐标在**视频流坐标系**（真机实证 488×1080，为 scrcpy
    // maxSize 缩放流；≠设备像素 1080×2400）。设备系换算交给调用方。
    return {
      kind: 'touch',
      action: buf[1]!,
      x: buf.readUInt32BE(10),
      y: buf.readUInt32BE(14),
      videoW: buf.readUInt16BE(18),
      videoH: buf.readUInt16BE(20),
    };
  }
  if (type === 0 && buf.length === 14) {
    return { kind: 'key', action: buf[1]!, keyCode: buf.readUInt32BE(2) };
  }
  if (type === 9 && buf.length >= 14) {
    const len = buf.readUInt32BE(10);
    if (buf.length === 14 + len) {
      return {
        kind: 'clipboard',
        paste: buf[9] === 1,
        text: buf.subarray(14, 14 + len).toString('utf8'),
      };
    }
  }
  return null;
}

// ==================== 手势分类（纯函数） ====================

export interface GestureEvent {
  action: number;
  x: number;
  y: number;
  t: number;
}
export type Gesture =
  | { kind: 'tap'; x: number; y: number }
  | { kind: 'longPress'; x: number; y: number }
  | {
      kind: 'swipe';
      direction: 'up' | 'down' | 'left' | 'right';
      distance: number;
    };

export const LONG_PRESS_MIN_MS = 550;
export const SWIPE_MIN_PX = 40;

/** down..up 事件序列 → 手势。位移主轴 ≥40px=滑动；≥550ms=长按；否则点击。 */
export function classifyGesture(events: GestureEvent[]): Gesture | null {
  const down = events.find((e) => e.action === 0);
  const up = [...events].reverse().find((e) => e.action === 1);
  if (!down || !up) return null;
  const dx = up.x - down.x;
  const dy = up.y - down.y;
  const dist = Math.max(Math.abs(dx), Math.abs(dy));
  if (dist >= SWIPE_MIN_PX) {
    // direction=手指滑动方向（与 Midscene Swipe.direction 语义一致）
    const direction =
      Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : dy > 0 ? 'down' : 'up';
    return { kind: 'swipe', direction, distance: Math.round(dist) };
  }
  if (up.t - down.t >= LONG_PRESS_MIN_MS) return { kind: 'longPress', x: down.x, y: down.y };
  return { kind: 'tap', x: down.x, y: down.y };
}

/** 系统键 keycode → 回收动作（Android 标准键值） */
export const KEYCODE_STEP: Record<number, RecoveredStep['action']> = {
  3: 'AndroidHomeButton',
  4: 'AndroidBackButton',
  187: 'AndroidRecentAppsButton',
};

// ==================== VL 语义化（默认实现，DI 可换假） ====================

/** PNG/JPEG → pngjs 位图（鸿蒙 snapshot_display 出 JPEG，画圈前先统一解码） */
export function decodeToBitmap(image: Buffer): PNG {
  if (image.length >= 2 && image[0] === 0xff && image[1] === 0xd8) {
    const raw = jpeg.decode(image, { maxMemoryUsageInMB: 512 });
    const img = new PNG({ width: raw.width, height: raw.height });
    img.data = raw.data; // jpeg-js 默认出 RGBA Buffer，与 pngjs 布局一致
    return img;
  }
  return PNG.sync.read(image);
}

/**
 * 在截图上以 (x,y) 为中心画红色圆环标记（set-of-marks 标准做法）。
 *
 * 真机实证：只给"像素坐标数字"VL 空间定位不准会幻觉元素细节（把 Google
 * 搜索栏描述成"放大镜+Search文字按钮"→ 回放定位必失败）；画醒目红圈让
 * 模型"看图找圈"，描述才锚定在真实元素上。纯 pngjs/jpeg-js 像素操作，
 * 零原生依赖。入 PNG 或 JPEG，出恒为 PNG。
 */
export function markTapPoint(png: Buffer, x: number, y: number): Buffer {
  const img = decodeToBitmap(png);
  const setRed = (px: number, py: number) => {
    if (px < 0 || py < 0 || px >= img.width || py >= img.height) return;
    const idx = (img.width * py + px) << 2;
    img.data[idx] = 255;
    img.data[idx + 1] = 0;
    img.data[idx + 2] = 0;
    img.data[idx + 3] = 255;
  };
  // 大圈"圈住"元素而非盖住（R=42 时圆环贴着小图标边缘，VL 会把红环当元素
  // 描述进去——真机实证「蓝色云形图标右侧的红色环形图标」）
  const R = 90;
  const THICK = 8;
  for (let dy = -R - THICK; dy <= R + THICK; dy++) {
    for (let dx = -R - THICK; dx <= R + THICK; dx++) {
      const d = Math.sqrt(dx * dx + dy * dy);
      // 圆环（R±THICK/2）+ 中心小点（r≤5）
      if (Math.abs(d - R) <= THICK / 2 || d <= 5) setRed(x + dx, y + dy);
    }
  }
  return PNG.sync.write(img);
}

/** 截图+坐标 → 元素定位描述（OpenAI 兼容 chat + image，Agent 直连不过平台） */
export async function describeElementByVl(
  png: Buffer,
  x: number,
  y: number,
  model: AppModelConfig,
  osName = 'Android',
): Promise<string> {
  let marked = png;
  try {
    marked = markTapPoint(png, x, y); // 标记失败退回原图（描述质量降级但不失败）
  } catch (err) {
    log('warn', '截图标记失败，用原图描述', {
      error: err instanceof Error ? err.message : String(err),
    });
  }
  // 标记成功恒为 PNG；标记失败退回的原图可能是 JPEG（鸿蒙），按魔数给对 mime
  const mime = marked[0] === 0xff && marked[1] === 0xd8 ? 'image/jpeg' : 'image/png';
  const base = model.baseUrl.replace(/\/+$/, '');
  const resp = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${model.apiKey}`,
    },
    body: JSON.stringify({
      model: model.name,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image_url',
              image_url: { url: `data:${mime};base64,${marked.toString('base64')}` },
            },
            {
              type: 'text',
              text:
                `这是一张 ${osName} 手机屏幕截图。图上的红色大圆环是我们后期叠加的` +
                '**标注**（不是界面的一部分），圆环中心的红色小点标记了用户的点击' +
                '位置。请用一句简洁中文描述被圆环圈住、位于中心点处的那个 UI 元素：' +
                '只描述界面上真实存在的内容（元素类型、可见文字/图标特征），同类元素' +
                '多时补相对位置（如「列表第三行的」）。绝对不要提及红圈/红点/标注本身' +
                '——该描述将用于在没有任何标注的新截图上重新定位此元素。' +
                '只输出描述，不要任何其他文字。',
            },
          ],
        },
      ],
      temperature: 0.1,
      max_tokens: 120,
    }),
    signal: AbortSignal.timeout(30_000),
  });
  if (!resp.ok) throw new Error(`VL 描述请求失败：HTTP ${resp.status}`);
  const data = (await resp.json()) as {
    choices?: Array<{ message?: { content?: unknown } }>;
  };
  const raw = data.choices?.[0]?.message?.content;
  const text = Array.isArray(raw) ? raw.map((b) => String((b as any)?.text ?? '')).join('') : String(raw ?? '');
  return text.trim().split('\n')[0]!.trim().slice(0, 200);
}

// ==================== iOS：WDA 截图 + point 尺寸（I4） ====================

/**
 * WDA GET /screenshot（8100，**免会话**）→ PNG（@2x/@3x 物理像素）。
 * 与投屏 MJPEG(9100) 分端口互不干扰；iOS17+ 截图只有这条通道。
 */
export async function wdaScreenshotPng(port: number): Promise<Buffer> {
  const resp = await fetch(`http://127.0.0.1:${port}/screenshot`, {
    signal: AbortSignal.timeout(8_000),
  });
  if (!resp.ok) throw new Error(`WDA screenshot HTTP ${resp.status}`);
  const data = (await resp.json()) as { value?: unknown };
  const buf = Buffer.from(String(data.value ?? ''), 'base64');
  if (buf.length < 24 || buf[0] !== 0x89 || buf[1] !== 0x50) {
    throw new Error('WDA screenshot 输出非 PNG');
  }
  return buf;
}

/**
 * 设备 point 尺寸（window/rect）：控制流坐标在 point 系（浏览器按 ios_meta
 * 换算），截图在 @2x/@3x 像素系——红圈标注前必须放大。搭车 /status 现存
 * 会话（绝不顶掉别人）；没有才自建。失败由调用方按 @2x 兜底。
 */
export async function wdaPointSize(port: number): Promise<{ width: number; height: number }> {
  const base = `http://127.0.0.1:${port}`;
  const t = (ms: number) => ({ signal: AbortSignal.timeout(ms) });
  const status = (await (await fetch(`${base}/status`, t(4_000))).json()) as Record<string, unknown>;
  let sid = typeof status['sessionId'] === 'string' && status['sessionId'] ? String(status['sessionId']) : '';
  if (!sid) {
    const created = (await (
      await fetch(`${base}/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capabilities: { alwaysMatch: {} } }),
        ...t(10_000),
      })
    ).json()) as { sessionId?: string; value?: { sessionId?: string } };
    sid = String(created.sessionId ?? created.value?.sessionId ?? '');
  }
  if (!sid) throw new Error('WDA 无可用会话（point 尺寸不可得）');
  const rect = (await (await fetch(`${base}/session/${sid}/window/rect`, t(5_000))).json()) as {
    value?: { width?: number; height?: number };
  };
  const width = Number(rect.value?.width ?? 0);
  const height = Number(rect.value?.height ?? 0);
  if (!width || !height) throw new Error('WDA window/rect 无有效尺寸');
  return { width, height };
}

/** PNG IHDR 快读宽高（不解码全图；WDA 截图恒 PNG） */
export function pngDims(png: Buffer): { width: number; height: number } | null {
  if (png.length < 24 || png[0] !== 0x89 || png[1] !== 0x50) return null;
  return { width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
}

/** adb screencap（同 ScreenshotCapturer 套路，超时/非 PNG 报错） */
export function screencapPng(adbPath: string, serial: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    execFile(
      adbPath,
      ['-s', serial, 'exec-out', 'screencap', '-p'],
      { timeout: 8_000, encoding: 'buffer', maxBuffer: 8 * 1024 * 1024 },
      (err, stdout) => {
        if (err) return reject(err);
        const buf = stdout as unknown as Buffer;
        if (buf.length < 8 || buf[0] !== 0x89 || buf[1] !== 0x50) {
          return reject(new Error('screencap 输出非 PNG'));
        }
        resolve(buf);
      },
    );
  });
}

// ==================== 录制器 ====================

export interface ManualStepEntry {
  seq: number;
  step: RecoveredStep;
}

export interface ManualRecorderDeps {
  adbPath: string;
  /** 鸿蒙 hdc 路径；未配置时 harmony 设备无法手动录制（start 报错） */
  hdcPath?: string;
  /** iOS：WDA 存活链（探活/iproxy 自拉起）；未配置时 ios 设备无法手动录制 */
  wda?: { port: number; ensureAlive(udid: string): Promise<void> };
  /** DI：VL 描述（测试注入假实现） */
  describe?: typeof describeElementByVl;
  /** DI：截图（测试注入假实现） */
  screencap?: typeof screencapPng;
  /** DI：鸿蒙截图（测试注入假实现） */
  snapshotHdc?: typeof hdcSnapshotJpeg;
  /** DI：iOS WDA 截图（测试注入假实现） */
  wdaShot?: typeof wdaScreenshotPng;
  /** DI：iOS point 尺寸（测试注入假实现） */
  wdaPointSizeFn?: typeof wdaPointSize;
}

const MAX_MANUAL_STEPS = 300;

export class ManualRecorder {
  private model: AppModelConfig | null;
  private readonly describe: typeof describeElementByVl;
  private readonly screencap: typeof screencapPng;
  private entries: ManualStepEntry[] = [];
  private seq = 0;
  /** 进行中的触控手势事件（down..up） */
  private gesture: GestureEvent[] | null = null;
  /** DOWN 时刻发起的异步截图（动作生效前的画面） */
  private shotAtDown: Promise<Buffer | null> | null = null;
  /** 语义化按序队列：VL 识别并发也保证步骤顺序 */
  private chain: Promise<void> = Promise.resolve();
  /** 识别中的数量（前端显示「识别中 N」） */
  private pendingCount = 0;
  /** 上一次点击的元素描述（配对后续文本输入的 locate） */
  private lastTapDesc: string | null = null;
  /** iOS：point 尺寸（构造时异步预取；失败 null → 红圈按 @2x 兜底） */
  private iosPointSize: Promise<{ width: number; height: number } | null> = Promise.resolve(null);
  private stopped = false;

  constructor(
    readonly serial: string,
    readonly sessionId: string,
    model: AppModelConfig,
    private readonly deps: ManualRecorderDeps,
    /** 设备物理分辨率 "1080x2400"（后端设备表下发；安卓触控消息坐标在缩放流坐标系，须换算） */
    private readonly resolution?: string,
    /** 平台：决定控制消息解析（scrcpy 二进制 vs harmony JSON）与截图通道 */
    readonly platform: DevicePlatform = 'android',
  ) {
    this.model = model;
    this.describe = deps.describe ?? describeElementByVl;
    this.screencap = deps.screencap ?? screencapPng;
    if (platform === 'ios' && deps.wda) {
      // 存活链先行（探活/iproxy 自拉起）→ point 尺寸;失败不阻断录制,红圈按 @2x 兜底。
      // 注意保持方法绑定:WdaManager.ensureAlive 内部依赖 this（in-flight 去重表）,
      // 解构裸调会炸 "Cannot read properties of undefined (reading 'pending')"
      const wda = deps.wda;
      const fetchSize = deps.wdaPointSizeFn ?? wdaPointSize;
      this.iosPointSize = wda
        .ensureAlive(serial)
        .then(() => fetchSize(wda.port))
        .catch((err) => {
          log('warn', 'iOS point 尺寸预取失败（红圈坐标按 @2x 兜底）', {
            serial,
            error: err instanceof Error ? err.message : String(err),
          });
          return null;
        });
    }
  }

  /** 流坐标 → 设备坐标（真机实证：触控消息 videoW/H=488×1080 缩放流，截图/回放
   * 都在设备像素系——不换算则红圈画错位、Swipe distance 偏小一半） */
  private toDevice(v: number, videoDim: number, axis: 'w' | 'h'): number {
    const [w, h] = (this.resolution ?? '').split('x').map((s) => parseInt(s, 10));
    const dev = axis === 'w' ? w : h;
    if (!dev || !Number.isFinite(dev) || !videoDim) return v; // 无分辨率信息原样（兼容）
    return Math.round((v * dev) / videoDim);
  }

  /** 控制字节旁观入口（ScrcpyManager tee 调用；解析失败静默忽略） */
  onControl(buf: Buffer): void {
    if (this.stopped) return;
    if (this.platform === 'harmony' || this.platform === 'ios') {
      // 鸿蒙/iOS：{t,x,y} 二进制 JSON 同壳。坐标系不同——harmony=设备物理像素
      // （浏览器按 harmony_meta 换算），ios=**point 系**（浏览器按 ios_meta 换算；
      // WDA 注入/回放同在 point 系,手势/Swipe 零换算,仅截图红圈标注时放大）
      const hm = parseHarmonyControl(buf);
      if (!hm) return;
      this.onTouchEvent({
        action: hm.t === 'down' ? 0 : hm.t === 'up' ? 1 : 2,
        x: hm.x,
        y: hm.y,
        t: Date.now(),
      });
      return;
    }
    const msg = parseControlMessage(buf);
    if (!msg) return;
    if (msg.kind === 'touch') {
      this.onTouchEvent({
        action: msg.action,
        x: this.toDevice(msg.x, msg.videoW, 'w'),
        y: this.toDevice(msg.y, msg.videoH, 'h'),
        t: Date.now(),
      });
    } else if (msg.kind === 'key' && msg.action === 1) {
      // down+up 成对下发，按 UP 记一次
      const action = KEYCODE_STEP[msg.keyCode];
      if (action) {
        this.pushStep({ action });
        this.lastTapDesc = null;
      }
    } else if (msg.kind === 'clipboard' && msg.paste && msg.text) {
      // 操作台文本注入走剪贴板 paste：录成 aiInput，locate 配对上一次点击的元素
      this.pushStep({
        action: 'aiInput',
        locate: this.lastTapDesc ?? '当前获得焦点的输入框',
        value: msg.text,
      });
    }
  }

  /** 设备端触控源入口（DT:getevent 旁听,坐标已是屏幕像素）——与浏览器 tee
   *  汇入同一手势状态机,截图/VL/步骤沉淀全复用,天然支持混合录制 */
  feedTouch(ev: GestureEvent): void {
    if (!this.stopped) this.onTouchEvent(ev);
  }

  /** 触控事件统一入口（安卓/鸿蒙/iOS 解析归一后走同一手势状态机） */
  private onTouchEvent(ev: GestureEvent): void {
    if (ev.action === 0) {
      this.gesture = [ev];
      // DOWN 即异步截图：点击生效在 UP，抓到的是动作前画面；绝不阻塞注入
      this.shotAtDown = this.captureShot().catch((err) => {
        log('warn', '手动录制截图失败（该步将用坐标兜底描述）', {
          serial: this.serial,
          error: err instanceof Error ? err.message : String(err),
        });
        return null;
      });
    } else if (this.gesture) {
      this.gesture.push(ev);
      if (ev.action === 1) this.finishGesture();
    }
  }

  /** 平台分流截图：android=screencap(PNG)，harmony=snapshot_display(JPEG)，
   *  ios=WDA /screenshot(PNG，@2x/@3x 像素，免会话与投屏 MJPEG 并存) */
  private captureShot(): Promise<Buffer> {
    if (this.platform === 'harmony') {
      if (!this.deps.hdcPath) return Promise.reject(new Error('HDC_PATH 未配置'));
      const snapshot = this.deps.snapshotHdc ?? hdcSnapshotJpeg;
      return snapshot(this.deps.hdcPath, this.serial);
    }
    if (this.platform === 'ios') {
      if (!this.deps.wda) return Promise.reject(new Error('WDA 未配置'));
      const shot = this.deps.wdaShot ?? wdaScreenshotPng;
      return shot(this.deps.wda.port);
    }
    return this.screencap(this.deps.adbPath, this.serial);
  }

  /** iOS：point 坐标 → 截图像素坐标（scale=截图宽/point宽,旋转时用高兜底;全失败按 @2x） */
  private async iosShotCoords(png: Buffer, x: number, y: number): Promise<{ x: number; y: number }> {
    let scale = 2;
    const dims = pngDims(png);
    const pt = await this.iosPointSize;
    if (dims && pt) {
      const byW = dims.width / pt.width;
      const byH = pt.height ? dims.width / pt.height : 0;
      if (byW >= 0.9 && byW <= 3.6) scale = byW;
      else if (byH >= 0.9 && byH <= 3.6) scale = byH; // 录制中途旋转:宽高互换
    }
    return { x: Math.round(x * scale), y: Math.round(y * scale) };
  }

  private finishGesture(): void {
    const gestureEvents = this.gesture;
    const shot = this.shotAtDown;
    this.gesture = null;
    this.shotAtDown = null;
    if (!gestureEvents) return;
    const g = classifyGesture(gestureEvents);
    if (!g) return;
    if (g.kind === 'swipe') {
      // 零 VL：方向+距离直接可回放（页面中心起滑，与探索回收同语义）
      this.pushStep({ action: 'Swipe', params: { direction: g.direction, distance: g.distance } });
      this.lastTapDesc = null;
      return;
    }
    // tap / longPress → VL 语义化（按序链；失败用坐标兜底描述，诚实保留）
    const model = this.model;
    if (!model) return;
    this.pendingCount += 1;
    this.chain = this.chain
      .then(async () => {
        let locate = `屏幕坐标(${g.x}, ${g.y})处的元素`;
        try {
          const png = await shot;
          if (png) {
            const osName =
              this.platform === 'harmony'
                ? 'HarmonyOS（鸿蒙）'
                : this.platform === 'ios'
                  ? 'iOS/iPadOS'
                  : 'Android';
            // iOS 控制坐标在 point 系,截图在 @2x/@3x 像素系:红圈标注前放大
            const mark =
              this.platform === 'ios' ? await this.iosShotCoords(png, g.x, g.y) : { x: g.x, y: g.y };
            const desc = await this.describe(png, mark.x, mark.y, model, osName);
            if (desc) locate = desc;
          }
        } catch (err) {
          log('warn', '手动录制 VL 描述失败（用坐标兜底）', {
            serial: this.serial,
            error: err instanceof Error ? err.message : String(err),
          });
        }
        // 注意不检查 stopped：stop() 等待本链落定，在途识别应入步骤而非丢弃
        this.lastTapDesc = locate;
        this.pushStep({ action: g.kind === 'tap' ? 'aiTap' : 'aiLongPress', locate });
      })
      .finally(() => {
        this.pendingCount -= 1;
      });
  }

  private pushStep(step: RecoveredStep): void {
    if (this.entries.length >= MAX_MANUAL_STEPS) return;
    this.seq += 1;
    this.entries.push({ seq: this.seq, step });
  }

  /** 增量拉步骤（操作台轮询） */
  pull(afterSeq: number): { seq: number; pending: number; entries: ManualStepEntry[] } {
    return {
      seq: this.seq,
      pending: this.pendingCount,
      entries: this.entries.filter((e) => e.seq > afterSeq),
    };
  }

  /** 停止：等在途 VL 识别落定 → 回步骤+YAML → 清 modelConfig（不漏 key） */
  async stop(): Promise<{ steps: RecoveredStep[]; yamlFlow: string }> {
    this.stopped = true;
    await this.chain; // 在途识别收尾（stopped 置位后不再落新步骤，但等干净）
    this.model = null;
    const steps = this.entries.map((e) => e.step);
    return { steps, yamlFlow: stepsToYamlFlow(steps) };
  }
}

// ==================== 编排（一台设备一路，同构 AutomationManager） ====================

export interface ManualRecordManagerDeps extends ManualRecorderDeps {
  /** serial → 平台（adb+hdc 合并快照查询；缺省一律按 android） */
  resolvePlatform?: (serial: string) => DevicePlatform;
  /** DI：设备端触控源工厂（DT；测试注入假源）。缺省用 DeviceTouchSource */
  deviceTouchFactory?: (opts: DeviceTouchSourceOpts) => Pick<DeviceTouchSource, 'start' | 'stop'>;
}

/** 一路录制的内部持有：recorder + 它专属的设备端触控源（android 才有） */
interface RecordEntry {
  recorder: ManualRecorder;
  source?: Pick<DeviceTouchSource, 'start' | 'stop'>;
}

export class ManualRecordManager {
  /** sessionId → 录制条目（sessionId 全局唯一；不同设备并行录制互不可见） */
  private readonly sessions = new Map<string, RecordEntry>();

  constructor(private readonly deps: ManualRecordManagerDeps) {}

  /** android 开设备端旁听:失败只降级纯浏览器录制,绝不拖垮开录 */
  private startDeviceSource(entry: RecordEntry, resolution?: string): void {
    const { recorder } = entry;
    if (recorder.platform !== 'android') return;
    const make = this.deps.deviceTouchFactory ?? ((o: DeviceTouchSourceOpts) => new DeviceTouchSource(o));
    const source = make({
      adbPath: this.deps.adbPath,
      serial: recorder.serial,
      resolution,
      onEvent: (ev) => recorder.feedTouch(ev),
    });
    entry.source = source;
    source.start().catch((err) => {
      log('warn', '设备端触控旁听不可用（本次录制仅浏览器事件源）', {
        serial: recorder.serial,
        error: err instanceof Error ? err.message : String(err),
      });
      // 只清仍属于本条目的源（防换会话后误清新源）
      if (entry.source === source) entry.source = undefined;
    });
  }

  /** 收掉一条录制（停设备源 + fire-and-forget 停 recorder），幂等 */
  private evict(sessionId: string, reason: string): void {
    const entry = this.sessions.get(sessionId);
    if (!entry) return;
    this.sessions.delete(sessionId);
    entry.source?.stop();
    entry.source = undefined;
    log('info', '手动录制会话替换/收掉', { session: sessionId, reason });
    void entry.recorder.stop().catch(() => {});
  }

  /**
   * 开始录制（同 session 重复 start 幂等复用）。同一**设备**的旧录制会话被替换
   * （录制无长任务，多因投屏重连换了 session_id）；其它设备的录制并行不受影响。
   */
  start(
    serial: string,
    sessionId: string,
    model: AppModelConfig,
    resolution?: string,
  ): { recording: true } {
    const platform = this.deps.resolvePlatform?.(serial) ?? 'android';
    if (platform === 'harmony' && !this.deps.hdcPath) {
      throw new Error('鸿蒙手动录制需要 Agent 配置 HDC_PATH（截图走 snapshot_display）');
    }
    if (platform === 'ios' && !this.deps.wda) {
      throw new Error('iOS 手动录制需要 idevice 工具链（WDA 截图语义化通道）');
    }
    if (this.sessions.has(sessionId)) return { recording: true }; // 同 session 幂等
    // 只替换同 serial 的旧会话——跨设备替换是旧单槽实现的副作用，并行下会误杀
    for (const [sid, entry] of this.sessions) {
      if (entry.recorder.serial === serial) this.evict(sid, `同设备新会话 ${sessionId}`);
    }
    const entry: RecordEntry = {
      recorder: new ManualRecorder(serial, sessionId, model, this.deps, resolution, platform),
    };
    this.sessions.set(sessionId, entry);
    // DT:安卓同时旁听设备端物理触控（用户直接在手机上操作也入录）
    this.startDeviceSource(entry, resolution);
    log('info', '手动录制开始', { serial, session: sessionId, resolution, platform });
    return { recording: true };
  }

  /** 控制字节 tee 入口（挂到 ScrcpyManager 的观察者上；按 sessionId 直路由） */
  onControl(sessionId: string, buf: Buffer): void {
    this.sessions.get(sessionId)?.recorder.onControl(buf);
  }

  pull(sessionId: string, afterSeq: number) {
    const entry = this.sessions.get(sessionId);
    if (!entry) {
      return { recording: false, seq: afterSeq, pending: 0, entries: [] as ManualStepEntry[] };
    }
    return { recording: true, ...entry.recorder.pull(afterSeq) };
  }

  async stop(sessionId: string): Promise<{ steps: RecoveredStep[]; yaml_flow: string } | null> {
    const entry = this.sessions.get(sessionId);
    if (!entry) return null;
    this.sessions.delete(sessionId);
    entry.source?.stop();
    entry.source = undefined;
    const { steps, yamlFlow } = await entry.recorder.stop();
    log('info', '手动录制结束', { session: sessionId, steps: steps.length });
    return { steps, yaml_flow: yamlFlow };
  }

  /** 某设备是否有活跃录制会话（WDA 单 iOS 守卫探针用） */
  hasSessionForSerial(serial: string): boolean {
    for (const entry of this.sessions.values()) {
      if (entry.recorder.serial === serial) return true;
    }
    return false;
  }

  async stopAll(reason: string): Promise<void> {
    const entries = [...this.sessions.entries()];
    if (entries.length === 0) return;
    this.sessions.clear();
    await Promise.allSettled(
      entries.map(async ([sessionId, entry]) => {
        entry.source?.stop();
        entry.source = undefined;
        log('info', 'ManualRecordManager.stopAll', { session: sessionId, reason });
        await entry.recorder.stop().catch(() => {});
      }),
    );
  }
}
