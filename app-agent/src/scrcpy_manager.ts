/**
 * 投屏会话编排（契约 §3.1）—— "一台设备一路" gate + data-WS 数据面 + 生命周期清理。
 *
 * 按 serial 分桶：一台设备同时最多 1 路投屏会话（同设备第二路 → busy，附
 * active_session_id 供网关停旧接管重试），不同设备并行互不影响。start 时：
 *   gate → 建 ScrcpySession → Agent 主动出站连网关 data-WS
 *   → video 字节经 WS 推出（bounded queue 超阈值丢帧）→ 从 WS 收控制字节写回设备。
 * stop 时优雅关会话 + 关 data-WS。Agent 退出 / 隧道断开 → stopAll 并行清所有活跃
 * 会话（绝不留僵尸烧编码器）。
 *
 * 依赖注入：ScrcpySession 与 data-WS 都经工厂传入，纯逻辑（gate/生命周期状态机/
 * 丢帧决策）可脱离真 scrcpy、真 WS 单测（见 test/scrcpy_manager.test.ts）。
 */

import WebSocket from 'ws';

import type { AgentConfig } from './config.js';
import type { DevicePlatform } from './frames.js';
import { HarmonyCastSession } from './harmony_cast.js';
import { IosCastSession } from './ios_cast.js';
import { log } from './log.js';
import type { WdaLike } from './wda.js';
import { ScrcpyError, ScrcpySession } from './scrcpy.js';
import type { ScrcpySessionOptions } from './scrcpy.js';
import {
  deriveDataWsUrl,
  emptyStats,
  shouldDropVideoFrame,
  VIDEO_BACKPRESSURE_BYTES,
} from './scrcpy_dataplane.js';
import type { DataPlaneStats } from './scrcpy_dataplane.js';

/** start_scrcpy 参数（契约 §3.1；session_id 为网关下发的会话标识） */
export interface StartScrcpyParams {
  serial: string;
  sessionId: string;
  maxFps?: number;
  bitRate?: number;
}

/** data-WS 抽象：只用到这几个成员，工厂在测试里注入 fake（不起真 WS） */
export interface DataWs {
  readonly bufferedAmount: number;
  readonly readyState: number;
  send(data: Uint8Array): void;
  close(code?: number, reason?: string): void;
  on(event: 'open', cb: () => void): void;
  on(event: 'message', cb: (data: Buffer, isBinary: boolean) => void): void;
  on(event: 'close', cb: (code: number, reason: Buffer) => void): void;
  on(event: 'error', cb: (err: Error) => void): void;
}

/** ScrcpySession 抽象：便于测试注入 fake（避免起真 adb/scrcpy） */
export interface ScrcpySessionLike {
  start(): Promise<void>;
  stop(): Promise<void>;
  onVideoBytes(cb: (bytes: Uint8Array) => void): void;
  writeControl(bytes: Uint8Array): void;
  /** 会话自死（video socket 断/server 退出）通知，编排层据此联动拆会话 */
  onClosed(cb: () => void): void;
}

/** 工厂入参 = scrcpy 选项 + 平台分派信息（harmony/ios 各走自家会话） */
export type SessionFactoryOpts = ScrcpySessionOptions & {
  platform: DevicePlatform;
  hdcPath?: string;
  /** WDA 存活管理（ios 会话数据面用；I3） */
  wda?: WdaLike;
};

export type SessionFactory = (opts: SessionFactoryOpts) => ScrcpySessionLike;
export type DataWsFactory = (url: string, token: string) => DataWs;

export interface ScrcpyManagerDeps {
  createSession?: SessionFactory;
  createDataWs?: DataWsFactory;
  /** 丢帧阈值（字节），测试可调小 */
  backpressureBytes?: number;
  /** serial → 平台（index 注入合并快照查询）；缺省恒 android（向后兼容） */
  resolvePlatform?: (serial: string) => DevicePlatform;
  /** WDA 存活管理（ios 投屏用；未配则 ios 设备 start 拒绝） */
  wda?: WdaLike;
}

/** 默认 session 工厂：android=ScrcpySession；harmony=HarmonyCastSession（H3）；
 *  ios=IosCastSession（I3；wda 必在——startScrcpy 前置闸已验） */
const defaultSessionFactory: SessionFactory = (opts) =>
  opts.platform === 'harmony'
    ? new HarmonyCastSession({ serial: opts.serial, hdcPath: opts.hdcPath ?? 'hdc' })
    : opts.platform === 'ios'
      ? new IosCastSession({ serial: opts.serial, wda: opts.wda as WdaLike })
      : new ScrcpySession(opts);

/** 默认 data-WS 工厂：ws 出站连网关，头带 X-Agent-Token（契约 §3.1） */
const defaultDataWsFactory: DataWsFactory = (url, token) =>
  new WebSocket(url, { headers: { 'X-Agent-Token': token } }) as unknown as DataWs;

/** 单路活跃会话的内部持有 */
interface ActiveSession {
  sessionId: string;
  serial: string;
  session: ScrcpySessionLike;
  ws: DataWs;
  stats: DataPlaneStats;
  /** stop 幂等门闩：防 WS close 与显式 stop 双触发 */
  stopping: boolean;
}

export class ScrcpyManager {
  /** serial → 该设备的活跃投屏会话（一台设备一路；不同设备并行） */
  private readonly sessions = new Map<string, ActiveSession>();
  private readonly createSession: SessionFactory;
  private readonly createDataWs: DataWsFactory;
  private readonly backpressureBytes: number;
  private readonly resolvePlatform: (serial: string) => DevicePlatform;
  private readonly wda?: WdaLike;
  /** 控制字节旁观者（手动录制 tee）：注入后调用，绝不阻塞/修改注入 */
  private controlObserver: ((sessionId: string, data: Buffer) => void) | undefined;

  constructor(
    private readonly cfg: AgentConfig,
    deps: ScrcpyManagerDeps = {},
  ) {
    this.createSession = deps.createSession ?? defaultSessionFactory;
    this.createDataWs = deps.createDataWs ?? defaultDataWsFactory;
    this.backpressureBytes = deps.backpressureBytes ?? VIDEO_BACKPRESSURE_BYTES;
    this.resolvePlatform = deps.resolvePlatform ?? (() => 'android');
    this.wda = deps.wda;
  }

  hasActiveSession(): boolean {
    return this.sessions.size > 0;
  }

  /** 指定投屏会话是否活跃（手动录制 start 校验用） */
  isSessionActive(sessionId: string): boolean {
    return this.findBySessionId(sessionId) !== undefined;
  }

  /** 某设备是否有活跃投屏会话（WDA 单 iOS 守卫探针用） */
  hasSessionForSerial(serial: string): boolean {
    return this.sessions.has(serial);
  }

  /** 注册/摘除控制字节旁观者（手动录制 tee） */
  setControlObserver(cb?: (sessionId: string, data: Buffer) => void): void {
    this.controlObserver = cb;
  }

  /** 观测：指定会话的数据面计数（无会话返回 undefined） */
  statsOf(sessionId: string): DataPlaneStats | undefined {
    const entry = this.findBySessionId(sessionId);
    return entry ? { ...entry.stats } : undefined;
  }

  /** 按 sessionId 找条目（sessionId 全局唯一，首个匹配即唯一） */
  private findBySessionId(sessionId: string): ActiveSession | undefined {
    for (const entry of this.sessions.values()) {
      if (entry.sessionId === sessionId) return entry;
    }
    return undefined;
  }

  /**
   * start_scrcpy（契约 §3.1）：一台设备一路 gate → 建会话 → 连 data-WS → 接通数据面。
   * 同设备已有活跃会话时抛 ScrcpyError('busy')（附 active_session_id，网关据此
   * 停旧接管重试——收窄后停的必然是同设备旧会话）；不同设备并行直接放行。
   * 启动任一步失败清理并向上抛。
   */
  async startScrcpy(params: StartScrcpyParams): Promise<{ started: true }> {
    // ── 一台设备一路 gate ──
    const existing = this.sessions.get(params.serial);
    if (existing) {
      // 带上活跃会话 id：网关据此可做接管编排（停旧 → 重试新）
      throw new ScrcpyError('busy', { active_session_id: existing.sessionId });
    }
    // 立即占位，防同一 tick 内同设备第 2 个 start 穿透 gate（await 前先落骨架）
    const entry: ActiveSession = {
      sessionId: params.sessionId,
      serial: params.serial,
      session: undefined as unknown as ScrcpySessionLike,
      ws: undefined as unknown as DataWs,
      stats: emptyStats(),
      stopping: false,
    };
    this.sessions.set(params.serial, entry);

    // 平台分派：harmony=HarmonyCastSession（H3）/ ios=IosCastSession（I3）
    const platform = this.resolvePlatform(params.serial);
    if (platform === 'harmony' && !this.cfg.hdcPath) {
      this.releaseSlot(entry); // 释放占位
      throw new ScrcpyError('鸿蒙设备投屏需要配置 HDC_PATH');
    }
    if (platform === 'ios' && !this.wda) {
      this.releaseSlot(entry); // 释放占位
      throw new ScrcpyError('iOS 设备投屏需要 idevice 工具链（IDEVICE_PATH/libimobiledevice）');
    }

    try {
      const session = this.createSession({
        serial: params.serial,
        adbPath: this.cfg.adbPath,
        maxFps: params.maxFps,
        bitRate: params.bitRate,
        platform,
        hdcPath: this.cfg.hdcPath,
        wda: this.wda,
      });
      entry.session = session;
      // 会话自死（server 退出/设备断开）→ 联动拆：关 data-WS + 释放 gate
      session.onClosed(() => {
        void this.teardown(entry, 'session_closed');
      });

      const wsUrl = deriveDataWsUrl(this.cfg.platformWsUrl, params.sessionId);
      const ws = this.createDataWs(wsUrl, this.cfg.agentToken);
      entry.ws = ws;
      this.wireDataWs(entry);

      // 先起 scrcpy（失败则不必建 WS 数据面）
      await session.start();

      // video 出站：bounded queue 超阈值丢帧（S1 backpressure 结论）
      session.onVideoBytes((bytes) => this.forwardVideo(entry, bytes));

      log('info', '投屏数据面接通', {
        sessionId: params.sessionId,
        serial: params.serial,
        platform,
        dataWs: wsUrl,
      });
      return { started: true };
    } catch (err) {
      await this.teardown(entry, 'start_failed');
      throw err;
    }
  }

  /** stop_scrcpy（契约 §3.1）：优雅停对应会话 + 关 data-WS，回 {stopped:true} */
  async stopScrcpy(sessionId: string): Promise<{ stopped: true }> {
    const entry = this.findBySessionId(sessionId);
    if (!entry) {
      // 幂等：目标会话不存在（已停/从未起）也回 stopped，不报错
      return { stopped: true };
    }
    await this.teardown(entry, 'stop_scrcpy');
    return { stopped: true };
  }

  /** Agent 退出 / 隧道断开：并行清所有活跃会话（不留僵尸烧编码器，契约 §3.1） */
  async stopAll(reason: string): Promise<void> {
    const entries = [...this.sessions.values()];
    if (entries.length === 0) return;
    await Promise.allSettled(entries.map((entry) => this.teardown(entry, reason)));
  }

  /** 释放某条目的 gate 占位（比对同一性防误删同设备后续新会话） */
  private releaseSlot(entry: ActiveSession): void {
    if (this.sessions.get(entry.serial) === entry) this.sessions.delete(entry.serial);
  }

  private wireDataWs(entry: ActiveSession): void {
    const { ws, session, sessionId } = entry;
    ws.on('open', () => {
      log('info', 'data-WS 已连通', { sessionId });
    });
    // 控制字节：WS → 设备（控制绝不丢）
    ws.on('message', (data, isBinary) => {
      if (!isBinary) return; // 数据面只走二进制帧
      entry.stats.controlBytesReceived += data.length;
      session.writeControl(new Uint8Array(data));
      // 旁观 tee（手动录制）：注入之后调用，异常吞掉，绝不影响控制通路
      try {
        this.controlObserver?.(entry.sessionId, data as Buffer);
      } catch {
        /* observer 异常不外溢 */
      }
    });
    ws.on('error', (err) => {
      log('warn', 'data-WS 错误', { sessionId, error: err.message });
    });
    ws.on('close', (code, reason) => {
      log('info', 'data-WS 关闭，联动停会话', {
        sessionId,
        code,
        reason: reason.toString('utf-8'),
      });
      void this.teardown(entry, 'data_ws_closed');
    });
  }

  /** video 出站：bounded queue 超阈值丢帧计数，否则经 WS 推出 */
  private forwardVideo(entry: ActiveSession, bytes: Uint8Array): void {
    const ws = entry.ws;
    if (ws.readyState !== WebSocket.OPEN) {
      // WS 未就绪（握手中/已关）→ 丢帧，不缓存（视频可丢，S1 结论）
      entry.stats.videoFramesDropped += 1;
      return;
    }
    if (shouldDropVideoFrame(ws.bufferedAmount, this.backpressureBytes)) {
      entry.stats.videoFramesDropped += 1;
      return;
    }
    try {
      ws.send(bytes);
      entry.stats.videoBytesForwarded += bytes.length;
      entry.stats.videoFramesForwarded += 1;
    } catch {
      entry.stats.videoFramesDropped += 1;
    }
  }

  /** 拆一路会话（幂等）：停 scrcpy（优雅）+ 关 data-WS + 释放 gate */
  private async teardown(entry: ActiveSession, reason: string): Promise<void> {
    if (entry.stopping) return;
    entry.stopping = true;
    // 先释放 gate，让同设备后续 start 不被已死会话卡住（stop 本身仍在跑收尾）
    this.releaseSlot(entry);

    try {
      entry.ws?.close(1000, reason);
    } catch {
      /* ignore */
    }
    try {
      await entry.session?.stop();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      log('warn', 'scrcpy 会话停止异常', { sessionId: entry.sessionId, error: message });
    }
    log('info', 'scrcpy 会话已拆除', {
      sessionId: entry.sessionId,
      reason,
      framesDropped: entry.stats.videoFramesDropped,
      framesForwarded: entry.stats.videoFramesForwarded,
    });
  }
}
