/**
 * 鸿蒙 NEXT 设备发现（H1 多平台接入）—— 每 3s 轮询 `hdc list targets -v` 做 diff，
 * 与 DeviceWatcher（adb）同构：纯解析函数可单测,Watcher 只管调度/富化/告警节流。
 *
 * 事件出口与 adb 侧共用（DeviceEvent → tunnel.sendDeviceEvent），DeviceInfo 带
 * platform='harmony'。富化走 `param get`（brand/model/版本）+ hidumper（分辨率），
 * 真机实测(BLK-AL80/HarmonyOS 6.1)：
 *   const.product.brand=HUAWEI  const.product.model=BLK-AL80
 *   const.product.os.dist.version=6.1.0
 *   hidumper -s RenderService -a screen → "render resolution=1084x2412"
 *
 * hdc server 端口钉 7035（与 spikes/harmony-env.sh 一致）：若各进程各起默认端口
 * 的 server，会互抢 USB 设备（同 adb 多 server 之害）。
 */

import { execFile } from 'node:child_process';

import type { DeviceConnection, DeviceInfo, DeviceState } from './frames.js';
import type { DeviceEvent } from './devices.js';
import { diffDevices } from './devices.js';
import { log } from './log.js';

export const HDC_POLL_INTERVAL_MS = 3_000;
const HDC_WARN_INTERVAL_MS = 60_000;
const HDC_EXEC_TIMEOUT_MS = 2_500;
/** 富化 shell 较重（param get×3 + hidumper），超时放宽 */
const HDC_ENRICH_TIMEOUT_MS = 5_000;
const ENRICH_RETRY_COOLDOWN_MS = 30_000;

/**
 * hdc server 端口：统一钉 **8710**（hdc 官方默认）。实测教训:已有 server 时新
 * HDC_SERVER_PORT **不会接管**（CLI 静默 fallback 老 server,直连 server socket 的
 * hdckit 则 ECONNREFUSED）——全线用同一个默认端口才能保证 CLI 与 hdckit 打到同一
 * 个 server,避免多 server 抢 USB 设备。
 */
export const HDC_DEFAULT_SERVER_PORT = 8710;

export function hdcEnv(): NodeJS.ProcessEnv {
  return {
    ...process.env,
    HDC_SERVER_PORT: process.env.HDC_SERVER_PORT ?? String(HDC_DEFAULT_SERVER_PORT),
  };
}

/** 解析生效的 hdc server 端口（env 覆盖 > 默认 8710），hdckit 直连要用 */
export function hdcServerPort(): number {
  const fromEnv = Number(process.env.HDC_SERVER_PORT);
  return Number.isFinite(fromEnv) && fromEnv > 0 ? fromEnv : HDC_DEFAULT_SERVER_PORT;
}

/**
 * 解析 `hdc list targets -v` 输出。每行 tab/空白分隔：
 *   `4ACVB24929010894		USB	Connected	localhost`
 *   [serial, 连接类型(USB/TCP), 状态(Connected/Offline/...), host]
 * - 无设备时输出 `[Empty]`；
 * - Connected → device；其余状态（Offline/Unauthorized…实测口径不稳）折叠 offline；
 * - USB → usb，其余（TCP）→ tcpip。
 */
export function parseHdcTargetsOutput(output: string): DeviceInfo[] {
  const devices: DeviceInfo[] = [];
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line === '[Empty]') continue;
    const tokens = line.split(/\s+/);
    const serial = tokens[0];
    if (!serial) continue;
    const connToken = (tokens[1] ?? '').toUpperCase();
    const stateToken = (tokens[2] ?? '').toLowerCase();
    const state: DeviceState = stateToken === 'connected' ? 'device' : 'offline';
    const connection: DeviceConnection = connToken === 'USB' ? 'usb' : 'tcpip';
    devices.push({
      serial,
      state,
      model: '',
      brand: '',
      android_version: '',
      resolution: '',
      connection,
      platform: 'harmony',
    });
  }
  return devices;
}

export interface HdcDeviceExtra {
  brand: string;
  /** HarmonyOS 版本（走 DeviceInfo.android_version 字段下发） */
  os_version: string;
  model: string;
  resolution: string;
}

/**
 * 解析富化 shell 输出（一次调用四条命令，`;` 链）：
 *   param get const.product.brand; const.product.model; const.product.os.dist.version;
 *   hidumper -s RenderService -a screen
 * 前三行按序取值（param 失败会输出含 "fail!" 的错误行 → 置空）；
 * 分辨率从 `render resolution=1084x2412` 提取。
 */
export function parseHdcDeviceExtra(output: string): HdcDeviceExtra {
  const lines = output
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  const val = (i: number): string => {
    const v = lines[i] ?? '';
    // param get 失败输出形如 `Get parameter "x" fail! errNum is:1002!`
    return v.includes('fail!') || v.includes('errNum') ? '' : v;
  };
  const resolution = output.match(/render resolution=(\d+x\d+)/)?.[1] ?? '';
  return { brand: val(0), model: val(1), os_version: val(2), resolution };
}

/** 与 DeviceWatcher 同构的 hdc 轮询 watcher（复用 diffDevices/DeviceEvent） */
export class HdcWatcher {
  private devices = new Map<string, DeviceInfo>();
  private timer: NodeJS.Timeout | undefined;
  private polling = false;
  private lastWarnAt = 0;
  private extras = new Map<string, HdcDeviceExtra>();
  private enriching = new Set<string>();
  private enrichFailedAt = new Map<string, number>();

  constructor(
    private readonly hdcPath: string,
    private readonly onEvent: (event: DeviceEvent) => void,
    private readonly pollIntervalMs: number = HDC_POLL_INTERVAL_MS,
  ) {}

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

  private async poll(): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    try {
      const next = await this.listTargets();
      for (const device of next) {
        const extra = this.extras.get(device.serial);
        if (extra) {
          device.brand = extra.brand;
          device.model = extra.model;
          device.android_version = extra.os_version;
          device.resolution = extra.resolution;
        } else if (device.state === 'device') {
          void this.enrich(device.serial);
        }
      }
      for (const event of diffDevices(this.devices, next)) this.onEvent(event);
      this.devices = new Map(next.map((d) => [d.serial, d]));
      for (const serial of this.extras.keys()) {
        if (!this.devices.has(serial)) {
          this.extras.delete(serial);
          this.enrichFailedAt.delete(serial);
        }
      }
    } finally {
      this.polling = false;
    }
  }

  private async enrich(serial: string): Promise<void> {
    if (this.enriching.has(serial)) return;
    const failedAt = this.enrichFailedAt.get(serial);
    if (failedAt && Date.now() - failedAt < ENRICH_RETRY_COOLDOWN_MS) return;
    this.enriching.add(serial);
    try {
      const stdout = await new Promise<string>((resolve, reject) => {
        execFile(
          this.hdcPath,
          [
            '-t',
            serial,
            'shell',
            'param get const.product.brand; param get const.product.model; ' +
              'param get const.product.os.dist.version; hidumper -s RenderService -a screen',
          ],
          { timeout: HDC_ENRICH_TIMEOUT_MS, encoding: 'utf-8', env: hdcEnv() },
          (err, out) => (err ? reject(err) : resolve(out)),
        );
      });
      const extra = parseHdcDeviceExtra(stdout);
      this.extras.set(serial, extra);
      this.enrichFailedAt.delete(serial);
      const current = this.devices.get(serial);
      if (current) {
        const merged: DeviceInfo = {
          ...current,
          brand: extra.brand,
          model: extra.model,
          android_version: extra.os_version,
          resolution: extra.resolution,
        };
        this.devices.set(serial, merged);
        this.onEvent({ event: 'upsert', device: { ...merged } });
      }
    } catch (err) {
      this.enrichFailedAt.set(serial, Date.now());
      log('warn', '鸿蒙设备详情采集失败，30s 后重试', {
        serial,
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      this.enriching.delete(serial);
    }
  }

  private listTargets(): Promise<DeviceInfo[]> {
    return new Promise((resolve) => {
      execFile(
        this.hdcPath,
        ['list', 'targets', '-v'],
        { timeout: HDC_EXEC_TIMEOUT_MS, encoding: 'utf-8', env: hdcEnv() },
        (err, stdout) => {
          if (err) {
            this.warnUnavailable(err);
            resolve([]);
            return;
          }
          resolve(parseHdcTargetsOutput(stdout));
        },
      );
    });
  }

  private warnUnavailable(err: Error): void {
    const now = Date.now();
    if (now - this.lastWarnAt < HDC_WARN_INTERVAL_MS) return;
    this.lastWarnAt = now;
    log('warn', 'hdc 不可用，按空鸿蒙设备列表上报', { hdcPath: this.hdcPath, error: err.message });
  }
}
