/**
 * 安卓设备端触控源（DT）—— 手动录制的第二事件源：用户直接在手机屏幕上操作。
 *
 * 通道：`adb shell getevent` 读内核 evdev 事件（免 root，adbd 有 input 组权限）。
 * 与浏览器投屏 tee 互补——tee 只看得见浏览器画布下发的控制流，手指直接落在
 * 真机屏幕上的触控只存在于内核 /dev/input，从这里旁听。
 *
 * 三段式：
 *  1. 探测：`getevent -p` 全设备能力清单 → 挑触摸屏（含 ABS_MT_POSITION_X/Y，
 *     0035/0036）+ 读原始量程（触摸板 raw 量程 ≠ 屏幕像素！模拟器 0..32767，
 *     真机常见 0..1079 或 0..4095，必须标定）。
 *  2. 流解析：`getevent -lt <dev>` 长进程，MT 协议 type B：TRACKING_ID 落/抬指、
 *     POSITION_X/Y 坐标、SYN_REPORT 出帧。**v1 只跟 slot 0 单指**（与浏览器录制
 *     能力对齐；多指手势本就不在回收动作集）。值全是无前缀十六进制。
 *  3. 标定：raw → 屏幕像素（线性缩放）。屏幕尺寸优先用后端下发 resolution，
 *     缺省 `wm size` 兜底。v1 按竖屏（rot 0）直通映射——录制中途横屏会错位，
 *     属已知局限（内核触控坐标不随显示旋转，屏幕坐标随）。
 *
 * 注入侧事实（e2e 设计依据）：`input tap`/monkey 走 InputManager 用户态注入，
 * **不经过 /dev/input，getevent 看不见**；只有物理触屏或 root 下 sendevent
 * 可见——所以闭环验证用模拟器（adbd 可 root，/dev/input 可写）。
 */

import { execFile, spawn, type ChildProcess } from 'node:child_process';

import { log } from './log.js';

// ==================== 探测（纯函数） ====================

export interface TouchPanelInfo {
  path: string;
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  /** 是否带 TRACKING_ID(0039)——type B 面板；缺失则退 BTN_TOUCH 判落抬 */
  hasTrackingId: boolean;
}

/** getevent -p 输出 → 触摸屏设备（多候选取 X 量程最大的 MT 设备；无 MT 设备回 null） */
export function parseGeteventDevices(text: string): TouchPanelInfo | null {
  const blocks = text.split(/^add device \d+: /m).slice(1);
  const found: TouchPanelInfo[] = [];
  for (const block of blocks) {
    const path = block.match(/^(\/dev\/input\/event\d+)/)?.[1];
    if (!path) continue;
    // "0035  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0"
    const axis = (code: string) => {
      const m = block.match(new RegExp(`^\\s*${code}\\s*:\\s*value -?\\d+, min (-?\\d+), max (-?\\d+)`, 'm'));
      return m ? { min: parseInt(m[1]!, 10), max: parseInt(m[2]!, 10) } : null;
    };
    const x = axis('0035');
    const y = axis('0036');
    if (!x || !y || x.max <= x.min || y.max <= y.min) continue;
    found.push({
      path,
      xMin: x.min,
      xMax: x.max,
      yMin: y.min,
      yMax: y.max,
      hasTrackingId: /^\s*0039\s*:/m.test(block),
    });
  }
  if (!found.length) return null;
  found.sort((a, b) => b.xMax - b.xMin - (a.xMax - a.xMin));
  return found[0]!;
}

/** `wm size` 输出 → {w,h}（"Physical size: 1080x2400"；Override 行优先） */
export function parseWmSize(text: string): { w: number; h: number } | null {
  const m =
    text.match(/Override size:\s*(\d+)x(\d+)/) ?? text.match(/Physical size:\s*(\d+)x(\d+)/);
  return m ? { w: parseInt(m[1]!, 10), h: parseInt(m[2]!, 10) } : null;
}

// ==================== 流解析（纯状态机，喂行出事件） ====================

/** 设备触控事件（屏幕像素系，action 与手势状态机对齐：0=down 1=up 2=move） */
export interface DeviceTouchEvent {
  action: 0 | 1 | 2;
  x: number;
  y: number;
  t: number;
}

export class GeteventParser {
  private buf = '';
  private touching = false;
  /** raw 坐标（16 进制解出）；up 帧无坐标沿用最后值 */
  private rawX = 0;
  private rawY = 0;
  private sawDown = false;
  private sawUp = false;
  private moved = false;
  /** MT type B 多指：非 0 slot 期间的事件全部忽略（v1 单指） */
  private activeSlot = 0;

  constructor(
    private readonly panel: Pick<TouchPanelInfo, 'xMin' | 'xMax' | 'yMin' | 'yMax'>,
    private readonly screen: { w: number; h: number },
  ) {}

  private toScreen(): { x: number; y: number } {
    const { xMin, xMax, yMin, yMax } = this.panel;
    const x = Math.round(((this.rawX - xMin) * (this.screen.w - 1)) / Math.max(1, xMax - xMin));
    const y = Math.round(((this.rawY - yMin) * (this.screen.h - 1)) / Math.max(1, yMax - yMin));
    return {
      x: Math.min(Math.max(0, x), this.screen.w - 1),
      y: Math.min(Math.max(0, y), this.screen.h - 1),
    };
  }

  /** 喂原始 stdout 块（跨行/半行安全），SYN_REPORT 边界产出事件 */
  feed(chunk: string): DeviceTouchEvent[] {
    this.buf += chunk;
    const lines = this.buf.split('\n');
    this.buf = lines.pop() ?? '';
    const out: DeviceTouchEvent[] = [];
    for (const line of lines) this.feedLine(line, out);
    return out;
  }

  private feedLine(line: string, out: DeviceTouchEvent[]): void {
    // "[   123.456] /dev/input/event4: EV_ABS ABS_MT_POSITION_X 000002a4"
    // 指定单设备时无路径段："[   123.456] EV_ABS ABS_MT_POSITION_X 000002a4"
    const m = line.match(/(EV_\w+)\s+(\w+)\s+(\S+)\s*$/);
    if (!m) return;
    const [, type, code, valueRaw] = m;
    if (type === 'EV_ABS' && code === 'ABS_MT_SLOT') {
      this.activeSlot = parseInt(valueRaw!, 16) || 0;
      return;
    }
    if (this.activeSlot !== 0 && type !== 'EV_SYN') return; // 非主指忽略
    if (type === 'EV_ABS') {
      if (code === 'ABS_MT_POSITION_X') {
        this.rawX = parseInt(valueRaw!, 16);
        if (this.touching) this.moved = true;
      } else if (code === 'ABS_MT_POSITION_Y') {
        this.rawY = parseInt(valueRaw!, 16);
        if (this.touching) this.moved = true;
      } else if (code === 'ABS_MT_TRACKING_ID') {
        if (/^f{8}$/i.test(valueRaw!) || valueRaw === '-1') this.sawUp = true;
        else this.sawDown = true;
      }
    } else if (type === 'EV_KEY' && code === 'BTN_TOUCH') {
      // 兜底通道（无 TRACKING_ID 的面板 / type A）：DOWN/UP 文本值
      if (valueRaw === 'DOWN' || valueRaw === '00000001') this.sawDown = true;
      else if (valueRaw === 'UP' || valueRaw === '00000000') this.sawUp = true;
    } else if (type === 'EV_SYN' && code === 'SYN_REPORT') {
      const t = Date.now();
      if (this.sawDown && !this.touching) {
        this.touching = true;
        out.push({ action: 0, ...this.toScreen(), t });
      } else if (this.sawUp && this.touching) {
        this.touching = false;
        out.push({ action: 1, ...this.toScreen(), t });
      } else if (this.touching && this.moved) {
        out.push({ action: 2, ...this.toScreen(), t });
      }
      this.sawDown = false;
      this.sawUp = false;
      this.moved = false;
    }
  }
}

// ==================== 进程编排 ====================

export interface DeviceTouchSourceOpts {
  adbPath: string;
  serial: string;
  /** 设备分辨率 "1080x2400"（后端下发）；缺省 wm size 兜底 */
  resolution?: string;
  onEvent: (ev: DeviceTouchEvent) => void;
  /** DI：探测命令执行（测试注入假输出） */
  probeImpl?: (adbPath: string, serial: string, args: string[]) => Promise<string>;
  /** DI：长进程 spawn（测试注入假流） */
  spawnImpl?: typeof spawn;
}

function adbExec(adbPath: string, serial: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      adbPath,
      ['-s', serial, ...args],
      { timeout: 8_000, maxBuffer: 4 * 1024 * 1024 },
      (err, stdout) => (err ? reject(err) : resolve(String(stdout))),
    );
  });
}

/**
 * 设备端触控长流：start 探测+拉流（失败上抛，调用方降级纯浏览器录制），
 * stop 杀进程幂等。进程意外退出只告警不自拉——录制会话本就短命，
 * 下次 start 重建。
 */
export class DeviceTouchSource {
  private child: ChildProcess | null = null;
  private stopped = false;

  constructor(private readonly opts: DeviceTouchSourceOpts) {}

  async start(): Promise<void> {
    const { adbPath, serial } = this.opts;
    const probe = this.opts.probeImpl ?? adbExec;
    const panel = parseGeteventDevices(await probe(adbPath, serial, ['shell', 'getevent', '-p']));
    if (!panel) throw new Error('未找到多点触控输入设备（getevent -p 无 ABS_MT 轴）');
    let screen: { w: number; h: number } | null = null;
    const res = (this.opts.resolution ?? '').match(/^(\d+)x(\d+)$/);
    if (res) screen = { w: parseInt(res[1]!, 10), h: parseInt(res[2]!, 10) };
    if (!screen) screen = parseWmSize(await probe(adbPath, serial, ['shell', 'wm', 'size']));
    if (!screen) throw new Error('无法确定屏幕分辨率（resolution 缺失且 wm size 不可解析）');
    if (this.stopped) return;

    const parser = new GeteventParser(panel, screen);
    const sp = this.opts.spawnImpl ?? spawn;
    const child = sp(adbPath, ['-s', serial, 'shell', 'getevent', '-lt', panel.path], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    this.child = child;
    child.stdout?.setEncoding('utf-8');
    child.stdout?.on('data', (chunk: string) => {
      for (const ev of parser.feed(chunk)) this.opts.onEvent(ev);
    });
    child.on('error', (err) => {
      // spawn 失败走 error 事件;不挂监听会炸整个进程
      if (!this.stopped) {
        log('warn', '设备触控流进程启动失败（本次录制仅浏览器事件源）', {
          serial,
          error: err.message,
        });
      }
      this.child = null;
    });
    child.on('exit', (code) => {
      if (!this.stopped) {
        log('warn', '设备触控流意外退出（本次录制仅剩浏览器事件源）', {
          serial,
          code,
        });
      }
      this.child = null;
    });
    log('info', '设备端触控源已开启', {
      serial,
      dev: panel.path,
      raw: `${panel.xMax - panel.xMin + 1}x${panel.yMax - panel.yMin + 1}`,
      screen: `${screen.w}x${screen.h}`,
    });
  }

  stop(): void {
    this.stopped = true;
    if (this.child) {
      try {
        this.child.kill();
      } catch {
        /* 已退出 */
      }
      this.child = null;
    }
  }
}
