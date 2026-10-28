/**
 * 设备发现（契约 §10）—— 每 3s 轮询 `adb devices -l` 做 diff。
 *
 * 纯逻辑（parseAdbDevicesOutput / diffDevices）与副作用（DeviceWatcher 定时器 +
 * 子进程）分层：前者无 IO 可直接喂固定文本单测，后者只负责调度与告警节流。
 *
 * adb 不可用（未安装/不在 PATH/adb server 起不来）时按空列表出快照——上层心跳
 * 照发（devices=[]），本模块每分钟最多一条告警日志，不刷屏。
 * TODO(P2): 换 `adb track-devices` 长连接推送，去掉轮询。
 */

import { execFile } from 'node:child_process';

import type { DeviceConnection, DeviceEventKind, DeviceInfo, DeviceState } from './frames.js';
import { log } from './log.js';

export const POLL_INTERVAL_MS = 3_000;
/** adb 告警节流窗口：不可用期间每分钟一条（契约 §10） */
const ADB_WARN_INTERVAL_MS = 60_000;
/** 单次 adb 调用超时，须小于轮询间隔避免堆积 */
const ADB_EXEC_TIMEOUT_MS = 2_500;

const KNOWN_STATES: ReadonlySet<string> = new Set(['device', 'offline', 'unauthorized']);

/**
 * 解析 `adb devices -l` 输出。每行形如：
 *   `0A1B2C3D  device usb:1-4 product:raven model:Pixel_6 device:raven transport_id:5`
 * - serial 含 `:`（host:port）判 tcpip，否则 usb（emulator-5554 归 usb）；
 * - model 从 `model:` 键值取（adb 已把空格替换为下划线，原样保留）；
 * - brand/android_version/resolution 该命令拿不到，留空串（P1 契约允许）；
 * - 冷门态（no permissions / recovery / sideload…）折叠为 offline：不可控即不可用。
 */
export function parseAdbDevicesOutput(output: string): DeviceInfo[] {
  const devices: DeviceInfo[] = [];
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    // 跳过表头与 adb daemon 噪声行（"* daemon not running..."）
    if (!line || line.startsWith('List of devices') || line.startsWith('*')) continue;
    const tokens = line.split(/\s+/);
    const serial = tokens[0];
    const rawState = tokens[1];
    if (!serial || !rawState) continue;

    const props: Record<string, string> = {};
    for (const token of tokens.slice(2)) {
      const sep = token.indexOf(':');
      if (sep > 0) props[token.slice(0, sep)] = token.slice(sep + 1);
    }

    const state: DeviceState = KNOWN_STATES.has(rawState) ? (rawState as DeviceState) : 'offline';
    const connection: DeviceConnection = serial.includes(':') ? 'tcpip' : 'usb';
    devices.push({
      serial,
      state,
      model: props['model'] ?? '',
      brand: '',
      android_version: '',
      resolution: '',
      connection,
      platform: 'android',
    });
  }
  return devices;
}

/** 设备详情富化字段（brand/版本/分辨率，`adb devices -l` 拿不到，需单独 shell） */
export interface DeviceExtra {
  brand: string;
  android_version: string;
  resolution: string;
}

/**
 * 解析富化 shell 输出（单次调用三条命令）：
 *   getprop ro.product.brand; getprop ro.build.version.release; wm size
 * 输出形如：
 *   google
 *   15
 *   Physical size: 1080x2400
 *   [Override size: 720x1600]   ← 有 Override 时以它为准（当前生效分辨率）
 */
export function parseDeviceExtra(output: string): DeviceExtra {
  const lines = output
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  const brand = lines[0] && !lines[0].includes(':') ? lines[0] : '';
  const version = lines[1] && !lines[1].includes(':') ? lines[1] : '';
  let resolution = '';
  for (const line of lines) {
    const m = line.match(/^(Physical|Override) size:\s*(\d+x\d+)/);
    if (m && m[2]) {
      resolution = m[2];
      if (m[1] === 'Override') break; // Override 优先
    }
  }
  return { brand, android_version: version, resolution };
}

export interface DeviceEvent {
  event: DeviceEventKind;
  device: DeviceInfo;
}

function sameDevice(a: DeviceInfo, b: DeviceInfo): boolean {
  return (
    a.serial === b.serial &&
    a.state === b.state &&
    a.model === b.model &&
    a.brand === b.brand &&
    a.android_version === b.android_version &&
    a.resolution === b.resolution &&
    a.connection === b.connection &&
    a.platform === b.platform
  );
}

/** 前后两次快照 diff：新增/字段变化 → upsert，消失 → remove（携带旧信息） */
export function diffDevices(
  prev: ReadonlyMap<string, DeviceInfo>,
  next: readonly DeviceInfo[],
): DeviceEvent[] {
  const events: DeviceEvent[] = [];
  const seen = new Set<string>();
  for (const device of next) {
    seen.add(device.serial);
    const old = prev.get(device.serial);
    if (!old || !sameDevice(old, device)) events.push({ event: 'upsert', device });
  }
  for (const [serial, old] of prev) {
    if (!seen.has(serial)) events.push({ event: 'remove', device: old });
  }
  return events;
}

/** 富化失败冷却：避免对坏设备每个 tick 重试 shell */
const ENRICH_RETRY_COOLDOWN_MS = 30_000;

export class DeviceWatcher {
  private devices = new Map<string, DeviceInfo>();
  private timer: NodeJS.Timeout | undefined;
  private polling = false;
  private lastAdbWarnAt = 0;
  private extras = new Map<string, DeviceExtra>();
  private enriching = new Set<string>();
  private enrichFailedAt = new Map<string, number>();

  constructor(
    private readonly adbPath: string,
    private readonly onEvent: (event: DeviceEvent) => void,
    private readonly pollIntervalMs: number = POLL_INTERVAL_MS,
  ) {}

  start(): void {
    if (this.timer) return;
    void this.poll(); // 启动立即采一次，不等首个 tick
    this.timer = setInterval(() => void this.poll(), this.pollIntervalMs);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }

  /** 当前全量快照（heartbeat 用），返回拷贝防外部改动内部状态 */
  snapshot(): DeviceInfo[] {
    return [...this.devices.values()].map((d) => ({ ...d }));
  }

  private async poll(): Promise<void> {
    if (this.polling) return; // adb 偶发卡顿时防重入堆积
    this.polling = true;
    try {
      const next = await this.listDevices();
      for (const device of next) {
        const extra = this.extras.get(device.serial);
        if (extra) {
          device.brand = extra.brand;
          device.android_version = extra.android_version;
          device.resolution = extra.resolution;
        } else if (device.state === 'device') {
          void this.enrich(device.serial);
        }
      }
      for (const event of diffDevices(this.devices, next)) this.onEvent(event);
      this.devices = new Map(next.map((d) => [d.serial, d]));
      // 拔线即弃富化缓存：重插重采（OTA 升级/改分辨率后不会拿到陈旧值）
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

  /** 单次 shell 采 brand/版本/分辨率；成功即时 upsert，失败 30s 冷却后随 tick 重试 */
  private async enrich(serial: string): Promise<void> {
    if (this.enriching.has(serial)) return;
    const failedAt = this.enrichFailedAt.get(serial);
    if (failedAt && Date.now() - failedAt < ENRICH_RETRY_COOLDOWN_MS) return;
    this.enriching.add(serial);
    try {
      const stdout = await new Promise<string>((resolve, reject) => {
        execFile(
          this.adbPath,
          [
            '-s',
            serial,
            'shell',
            'getprop ro.product.brand; getprop ro.build.version.release; wm size',
          ],
          { timeout: ADB_EXEC_TIMEOUT_MS, encoding: 'utf-8' },
          (err, out) => (err ? reject(err) : resolve(out)),
        );
      });
      const extra = parseDeviceExtra(stdout);
      this.extras.set(serial, extra);
      this.enrichFailedAt.delete(serial);
      const current = this.devices.get(serial);
      if (current) {
        const merged: DeviceInfo = { ...current, ...extra };
        this.devices.set(serial, merged);
        this.onEvent({ event: 'upsert', device: { ...merged } });
      }
    } catch (err) {
      this.enrichFailedAt.set(serial, Date.now());
      log('warn', '设备详情采集失败，30s 后重试', {
        serial,
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      this.enriching.delete(serial);
    }
  }

  private listDevices(): Promise<DeviceInfo[]> {
    return new Promise((resolve) => {
      execFile(
        this.adbPath,
        ['devices', '-l'],
        { timeout: ADB_EXEC_TIMEOUT_MS, encoding: 'utf-8' },
        (err, stdout) => {
          if (err) {
            this.warnAdbUnavailable(err);
            resolve([]); // 空列表：已插设备会 diff 出 remove，心跳照发空数组
            return;
          }
          resolve(parseAdbDevicesOutput(stdout));
        },
      );
    });
  }

  private warnAdbUnavailable(err: Error): void {
    const now = Date.now();
    if (now - this.lastAdbWarnAt < ADB_WARN_INTERVAL_MS) return;
    this.lastAdbWarnAt = now;
    log('warn', 'adb 不可用，按空设备列表上报', { adbPath: this.adbPath, error: err.message });
  }
}
