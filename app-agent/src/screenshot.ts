/**
 * 设备静态截图采集（契约 §2.1）—— 定时对每台在线设备截屏上报做列表缩略图（非实时）。
 * 按平台分流：android=`adb exec-out screencap -p`(PNG)；harmony=`hdc shell
 * snapshot_display` 落设备端再 `file recv` 拉回(JPEG)。
 *
 * 约束：
 *  - 单进程内串行采集（一次只截一台），避免多设备同时 screencap 抖动低配宿主机；
 *  - 每台设备各自限频（默认 5min），且上线后尽快补一张（首轮不等满周期）；
 *  - 只截 state==='device' 的设备；拔线即弃其节流记录，重插重采；
 *  - 采集失败静默节流重试，不刷屏。
 */

import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import type { DeviceInfo } from './frames.js';
import { hdcEnv } from './hdc_devices.js';
import { log } from './log.js';

/** 每台设备两次截图最小间隔 */
export const SCREENSHOT_INTERVAL_MS = 5 * 60_000;
/** 采集调度轮询间隔（找到期设备） */
const TICK_MS = 15_000;
/** 单次 screencap 超时（大屏 PNG 可能偏大） */
const CAPTURE_TIMEOUT_MS = 8_000;
/** PNG 上限（防异常大图撑爆帧）：约 4MB */
const MAX_PNG_BYTES = 4 * 1024 * 1024;

/**
 * 鸿蒙单帧截图（JPEG）：snapshot_display 落设备端 → file recv 拉回 → 读取删除。
 * 缩略图采集与手动录制共用；remote 路径按调用唯一（并发两路不互相覆盖），
 * 设备端文件 recv 后尽力 rm（失败留几百 KB 垃圾可接受）。
 * 注意 snapshot_display 走 RenderService，不碰 uitest 守护进程——与投屏帧流并存安全。
 */
export async function hdcSnapshotJpeg(
  hdcPath: string,
  serial: string,
  timeoutMs = CAPTURE_TIMEOUT_MS,
): Promise<Buffer> {
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const remote = `/data/local/tmp/agent_snap_${stamp}.jpeg`;
  const local = path.join(os.tmpdir(), `agent-snap-${serial}-${stamp}.jpeg`);
  const run = (args: string[]): Promise<void> =>
    new Promise((resolve, reject) => {
      execFile(hdcPath, args, { timeout: timeoutMs, env: hdcEnv() }, (err) =>
        err ? reject(err) : resolve(),
      );
    });
  try {
    await run(['-t', serial, 'shell', `snapshot_display -f ${remote}`]);
    await run(['-t', serial, 'file', 'recv', remote, local]);
    const buf = await fs.readFile(local);
    // JPEG 魔数校验（FFD8；snapshot 偶发失败会落错误文本）
    if (buf.length < 4 || buf[0] !== 0xff || buf[1] !== 0xd8) {
      throw new Error('snapshot_display 输出非 JPEG');
    }
    return buf;
  } finally {
    void fs.unlink(local).catch(() => {});
    void run(['-t', serial, 'shell', `rm -f ${remote}`]).catch(() => {});
  }
}

export interface ScreenshotDeps {
  adbPath: string;
  /** 鸿蒙 hdc 路径；未配置时 harmony 设备跳过截图 */
  hdcPath?: string;
  /** iOS idevice_id 路径（idevicescreenshot 取同目录兄弟）；未配置时 ios 设备跳过截图 */
  ideviceIdPath?: string;
  /** 当前在线设备快照（adb + hdc 两个 watcher 合并） */
  getSnapshot: () => DeviceInfo[];
  /** 隧道是否就绪（未注册不采，省得白截） */
  isReady: () => boolean;
  /** 上报一张截图 */
  onShot: (serial: string, dataB64: string, capturedAt: number) => void;
}

export class ScreenshotCapturer {
  private timer: NodeJS.Timeout | undefined;
  private capturing = false;
  /** serial → 上次成功/尝试采集时刻（ms） */
  private lastAt = new Map<string, number>();

  constructor(private readonly deps: ScreenshotDeps) {}

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => void this.tick(), TICK_MS);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }

  /** 立即补采某台（如投屏结束后由外部触发） */
  captureNow(serial: string): void {
    void this.capture(serial);
  }

  private async tick(): Promise<void> {
    if (this.capturing || !this.deps.isReady()) return;
    const online = this.deps.getSnapshot().filter((d) => d.state === 'device');
    const onlineSerials = new Set(online.map((d) => d.serial));
    // 拔线设备弃节流记录（重插重采）
    for (const s of this.lastAt.keys()) if (!onlineSerials.has(s)) this.lastAt.delete(s);

    const now = Date.now();
    // 取最久未采的一台到期设备，一次只截一台（串行）
    const due = online
      .filter((d) => now - (this.lastAt.get(d.serial) ?? 0) >= SCREENSHOT_INTERVAL_MS)
      .sort((a, b) => (this.lastAt.get(a.serial) ?? 0) - (this.lastAt.get(b.serial) ?? 0))[0];
    if (due) await this.capture(due.serial);
  }

  private async capture(serial: string): Promise<void> {
    if (this.capturing) return;
    this.capturing = true;
    this.lastAt.set(serial, Date.now()); // 先占位，失败也进入下个节流窗口
    try {
      const device = this.deps.getSnapshot().find((d) => d.serial === serial);
      const platform = device?.platform ?? 'android';
      if (platform === 'harmony' && !this.deps.hdcPath) return; // hdc 未配置：静默跳过
      if (platform === 'ios' && !this.deps.ideviceIdPath) return; // 同上
      const img =
        platform === 'harmony'
          ? await this.hdcSnapshot(serial)
          : platform === 'ios'
            ? await this.iosScreenshot(serial)
            : await this.screencap(serial);
      if (img.length > MAX_PNG_BYTES) {
        log('warn', '设备截图过大，丢弃', { serial, bytes: img.length });
        return;
      }
      this.deps.onShot(serial, img.toString('base64'), Date.now());
    } catch (err) {
      log('warn', '设备截图失败', {
        serial,
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      this.capturing = false;
    }
  }

  /** 鸿蒙截图：委托共用 hdcSnapshotJpeg（与手动录制同一实现） */
  private hdcSnapshot(serial: string): Promise<Buffer> {
    return hdcSnapshotJpeg(this.deps.hdcPath as string, serial);
  }

  /**
   * iOS 截图：走 WDA `/screenshot`（HTTP，base64 PNG）。
   * 真机实证(iPadOS 18.7.9)：libimobiledevice 的 screenshotr 服务在 iOS 17+
   * 需要挂载个性化开发者磁盘镜像，idevicescreenshot 直接不可用——WDA 通道
   * 是唯一稳路（S1 实证 494ms/306KB PNG）。依赖 iproxy 转发 8100（I2 收编
   * 进 WDA 存活管理）；WDA 不可达 → 抛错走上层「采集失败静默节流重试」。
   */
  private async iosScreenshot(_serial: string): Promise<Buffer> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), CAPTURE_TIMEOUT_MS);
    try {
      const resp = await fetch('http://127.0.0.1:8100/screenshot', { signal: ctrl.signal });
      if (!resp.ok) throw new Error(`WDA /screenshot HTTP ${resp.status}`);
      const data = (await resp.json()) as { value?: string };
      const buf = Buffer.from(data.value ?? '', 'base64');
      if (buf.length < 8 || buf[0] !== 0x89 || buf[1] !== 0x50) {
        throw new Error('WDA /screenshot 输出非 PNG');
      }
      return buf;
    } finally {
      clearTimeout(timer);
    }
  }

  private screencap(serial: string): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      execFile(
        this.deps.adbPath,
        ['-s', serial, 'exec-out', 'screencap', '-p'],
        { timeout: CAPTURE_TIMEOUT_MS, encoding: 'buffer', maxBuffer: MAX_PNG_BYTES + 1 },
        (err, stdout) => {
          if (err) return reject(err);
          const buf = stdout as unknown as Buffer;
          // PNG 魔数校验（截屏偶发返回空/错误文本）
          if (buf.length < 8 || buf[0] !== 0x89 || buf[1] !== 0x50) {
            return reject(new Error('screencap 输出非 PNG'));
          }
          resolve(buf);
        },
      );
    });
  }
}
