/**
 * iOS 设备发现（I1 多平台接入）—— 每 3s 轮询 `idevice_id -l` 做 diff，与
 * DeviceWatcher(adb)/HdcWatcher(hdc) 同构：纯解析函数可单测，Watcher 只管
 * 调度/富化/告警节流。
 *
 * 事件出口与 adb/hdc 侧共用（DeviceEvent → tunnel.sendDeviceEvent），DeviceInfo
 * 带 platform='ios'。富化走 `ideviceinfo -u <udid>` 全量 dump 一次解析三键，
 * 真机实测(iPad7,11 / iPadOS 18.7.9)：
 *   DeviceName: iPad   ProductVersion: 18.7.9   ProductType: iPad7,11
 *
 * 信任语义：idevice_id -l 列出所有 USB 连接的设备（含未信任），ideviceinfo
 * 对未配对设备报 pairing 类错误 → 状态折叠为 unauthorized（对齐 adb 口径，
 * 设备页能提示用户去 iPad 上点信任）。
 */

import { execFile } from 'node:child_process';
import path from 'node:path';

import type { DeviceInfo } from './frames.js';
import type { DeviceEvent } from './devices.js';
import { diffDevices } from './devices.js';
import { log } from './log.js';

export const IOS_POLL_INTERVAL_MS = 3_000;
const IOS_WARN_INTERVAL_MS = 60_000;
const IOS_EXEC_TIMEOUT_MS = 2_500;
const IOS_ENRICH_TIMEOUT_MS = 5_000;
const ENRICH_RETRY_COOLDOWN_MS = 30_000;

/**
 * 解析 `idevice_id -l` 输出：每行一个 UDID（USB 连接的设备，含未信任）。
 * 新老格式并存：40 位 hex（≤iPhoneX 代）/ 8-4-16 连字符（新设备），
 * 按「行内容像标识符且无空格」宽松接收；错误行（ERROR:/Unable…）忽略。
 */
export function parseIdeviceIdOutput(output: string): string[] {
  const udids: string[] = [];
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (!/^[0-9a-fA-F][0-9a-fA-F-]{15,}$/.test(line)) continue;
    udids.push(line);
  }
  return udids;
}

export interface IosDeviceExtra {
  /** 用户设备名（DeviceName，如「iPad」）→ model 展示位 */
  device_name: string;
  /** iOS/iPadOS 版本（ProductVersion）→ 走 android_version 字段下发 */
  os_version: string;
  /** 产品代号（ProductType，如 iPad7,11）——展示价值低，留档不下发 */
  product_type: string;
}

/**
 * 解析 `ideviceinfo -u <udid>` 全量 dump（`Key: value` 行式），取三键。
 * 一次调用零 shell 链，避免逐键三连的时延。
 */
export function parseIdeviceInfoOutput(output: string): IosDeviceExtra {
  const kv = new Map<string, string>();
  for (const rawLine of output.split(/\r?\n/)) {
    const idx = rawLine.indexOf(': ');
    if (idx <= 0) continue;
    kv.set(rawLine.slice(0, idx).trim(), rawLine.slice(idx + 2).trim());
  }
  return {
    device_name: kv.get('DeviceName') ?? '',
    os_version: kv.get('ProductVersion') ?? '',
    product_type: kv.get('ProductType') ?? '',
  };
}

/** ideviceinfo 报错是否为「未配对/未信任」类（→ 状态折叠 unauthorized） */
export function isPairingError(message: string): boolean {
  return /pair|trust|password protected|Invalid HostID|user denied/i.test(message);
}

/** 与 DeviceWatcher/HdcWatcher 同构的 iOS 轮询 watcher（复用 diffDevices/DeviceEvent） */
export class IosWatcher {
  private devices = new Map<string, DeviceInfo>();
  private timer: NodeJS.Timeout | undefined;
  private polling = false;
  private lastWarnAt = 0;
  private extras = new Map<string, IosDeviceExtra>();
  private enriching = new Set<string>();
  private enrichFailedAt = new Map<string, number>();
  /** 富化报 pairing 错的设备 → unauthorized（设备页提示去 iPad 点信任） */
  private unauthorized = new Set<string>();
  private readonly ideviceInfoPath: string;

  constructor(
    /** idevice_id 可执行路径；ideviceinfo 取同目录兄弟 */
    private readonly ideviceIdPath: string,
    private readonly onEvent: (event: DeviceEvent) => void,
    private readonly pollIntervalMs: number = IOS_POLL_INTERVAL_MS,
  ) {
    this.ideviceInfoPath = path.join(path.dirname(ideviceIdPath), 'ideviceinfo');
  }

  start(): void {
    if (this.timer) return;
    void this.poll();
    this.timer = setInterval(() => void this.poll(), this.pollIntervalMs);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }

  snapshot(): DeviceInfo[] {
    return [...this.devices.values()].map((d) => ({ ...d }));
  }

  private toInfo(udid: string): DeviceInfo {
    const extra = this.extras.get(udid);
    return {
      serial: udid,
      state: this.unauthorized.has(udid) ? 'unauthorized' : 'device',
      model: extra?.device_name ?? '',
      brand: 'Apple',
      android_version: extra?.os_version ?? '',
      resolution: '',
      connection: 'usb',
      platform: 'ios',
    };
  }

  private async poll(): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    try {
      const udids = await this.listUdids();
      const next: DeviceInfo[] = [];
      for (const udid of udids) {
        // 未信任设备也持续按冷却重试：用户在 iPad 上点完信任后自动转好
        if (!this.extras.has(udid)) void this.enrich(udid);
        next.push(this.toInfo(udid));
      }
      for (const event of diffDevices(this.devices, next)) this.onEvent(event);
      this.devices = new Map(next.map((d) => [d.serial, d]));
      for (const udid of this.extras.keys()) {
        if (!this.devices.has(udid)) {
          this.extras.delete(udid);
          this.enrichFailedAt.delete(udid);
          this.unauthorized.delete(udid);
        }
      }
    } finally {
      this.polling = false;
    }
  }

  private async enrich(udid: string): Promise<void> {
    if (this.enriching.has(udid)) return;
    const failedAt = this.enrichFailedAt.get(udid);
    if (failedAt && Date.now() - failedAt < ENRICH_RETRY_COOLDOWN_MS) return;
    this.enriching.add(udid);
    try {
      const stdout = await new Promise<string>((resolve, reject) => {
        execFile(
          this.ideviceInfoPath,
          ['-u', udid],
          { timeout: IOS_ENRICH_TIMEOUT_MS, encoding: 'utf-8' },
          (err, out, stderr) =>
            err ? reject(new Error(`${err.message} ${stderr ?? ''}`)) : resolve(out),
        );
      });
      const extra = parseIdeviceInfoOutput(stdout);
      this.extras.set(udid, extra);
      this.unauthorized.delete(udid);
      this.enrichFailedAt.delete(udid);
      if (this.devices.has(udid)) {
        const merged = this.toInfo(udid);
        this.devices.set(udid, merged);
        this.onEvent({ event: 'upsert', device: { ...merged } });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.enrichFailedAt.set(udid, Date.now());
      if (isPairingError(message)) {
        // 未信任：状态翻 unauthorized 并立即上报（设备页提示去 iPad 点信任）
        if (!this.unauthorized.has(udid)) {
          this.unauthorized.add(udid);
          if (this.devices.has(udid)) {
            const merged = this.toInfo(udid);
            this.devices.set(udid, merged);
            this.onEvent({ event: 'upsert', device: { ...merged } });
          }
          log('warn', 'iOS 设备未信任本机（去 iPad 上点「信任此电脑」）', { udid });
        }
      } else {
        log('warn', 'iOS 设备详情采集失败，30s 后重试', { udid, error: message });
      }
    } finally {
      this.enriching.delete(udid);
    }
  }

  private listUdids(): Promise<string[]> {
    return new Promise((resolve) => {
      execFile(
        this.ideviceIdPath,
        ['-l'],
        { timeout: IOS_EXEC_TIMEOUT_MS, encoding: 'utf-8' },
        (err, stdout) => {
          if (err) {
            this.warnUnavailable(err);
            resolve([]);
            return;
          }
          resolve(parseIdeviceIdOutput(stdout));
        },
      );
    });
  }

  private warnUnavailable(err: Error): void {
    const now = Date.now();
    if (now - this.lastWarnAt < IOS_WARN_INTERVAL_MS) return;
    this.lastWarnAt = now;
    log('warn', 'idevice_id 不可用，按空 iOS 设备列表上报', {
      ideviceIdPath: this.ideviceIdPath,
      error: err.message,
    });
  }
}
