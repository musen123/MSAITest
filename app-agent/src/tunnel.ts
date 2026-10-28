/**
 * 控制隧道（契约 §2/§10）—— Agent 出站 ws 长连接到平台网关。
 *
 * 生命周期：connect → 发 register → 收 registered 进入运行态（开心跳定时器）
 * → 断连清态并指数退避重连（1s→2s→…→30s 封顶，注册成功即归零）。
 * 断连期间设备增量事件直接丢弃（sendDeviceEvent 静默 no-op），重连后靠
 * heartbeat 全量快照对账，Agent 侧不做事件缓存。
 *
 * 握手拒绝 close code（4401 token 无效 / 4403 指纹不符 / 4426 协议过低）属于
 * 配置级错误，重试大概率无效，但 Agent 作为常驻进程不自杀——按封顶间隔慢速
 * 重试并每次高声告警，等运维改配置（token 轮转后无需重启进程即可恢复不成立，
 * token 变更需重启，README 有说明）。
 */

import WebSocket from 'ws';

import type { AgentConfig } from './config.js';
import { AGENT_VERSION, CAPABILITIES } from './config.js';
import type {
  AgentFrame,
  DeviceEventKind,
  DeviceInfo,
  RpcRequestFrame,
} from './frames.js';
import { FrameDecodeError, PROTOCOL_VERSION, decodeGatewayFrame, encodeAgentFrame } from './frames.js';
import { log } from './log.js';
import type { RpcOutcome } from './rpc.js';

/** 网关未下发 heartbeat_interval_s 时的兜底（契约值 10s） */
const DEFAULT_HEARTBEAT_INTERVAL_S = 10;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const HANDSHAKE_TIMEOUT_MS = 10_000;

/** 握手拒绝码 → 人话（契约 §2） */
const REJECT_CLOSE_REASONS: Record<number, string> = {
  4401: 'token 无效',
  4403: '宿主机指纹不符',
  4409: '同 agent 已有活跃连接',
  4426: 'protocol_version 过低',
};

export interface TunnelHooks {
  /** heartbeat 全量快照来源 */
  getSnapshot(): DeviceInfo[];
  /** rpc_request 执行（含超时兜底），任何 cmd 都必须给出 outcome */
  dispatchRpc(cmd: string, params: Record<string, unknown>, timeoutMs: number): Promise<RpcOutcome>;
  /**
   * 控制隧道断开回调（可选）。契约 §3.1：隧道断开须清理活跃 scrcpy 会话，
   * 不留僵尸烧编码器。每次 close 都触发（含握手拒绝）。
   */
  onDisconnect?(reason: string): void;
}

export class Tunnel {
  private ws: WebSocket | undefined;
  private registered = false;
  private retries = 0;
  private heartbeatTimer: NodeJS.Timeout | undefined;
  private reconnectTimer: NodeJS.Timeout | undefined;
  private stopped = false;

  constructor(
    private readonly cfg: AgentConfig,
    private readonly hooks: TunnelHooks,
  ) {}

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = undefined;
    this.stopHeartbeat();
    this.registered = false;
    this.ws?.close(1000, 'agent shutdown');
    this.ws = undefined;
  }

  /** 设备增量事件；未注册/断连期间丢弃（契约：重连后靠 heartbeat 对账） */
  sendDeviceEvent(event: DeviceEventKind, device: DeviceInfo): void {
    if (!this.registered) return;
    this.send({ v: 1, type: 'device_event', event, device });
  }

  /** 设备静态截图（列表缩略图，契约 §2.1）；未注册期间丢弃，下次周期重采 */
  sendScreenshot(serial: string, dataB64: string, capturedAt: number): void {
    if (!this.registered) return;
    this.send({ v: 1, type: 'device_screenshot', serial, fmt: 'png', data_b64: dataB64, captured_at: capturedAt });
  }

  /** 当前是否已注册（截图采集器据此决定是否值得采） */
  isReady(): boolean {
    return this.registered;
  }

  private connect(): void {
    if (this.stopped) return;
    log('info', '连接平台网关', { url: this.cfg.platformWsUrl });
    const ws = new WebSocket(this.cfg.platformWsUrl, {
      headers: {
        'X-Agent-Token': this.cfg.agentToken,
        'X-Host-Fingerprint': this.cfg.hostFingerprint,
      },
      handshakeTimeout: HANDSHAKE_TIMEOUT_MS,
    });
    this.ws = ws;

    ws.on('open', () => {
      this.send({
        v: 1,
        type: 'register',
        agent_version: AGENT_VERSION,
        capabilities: CAPABILITIES,
        protocol_version: PROTOCOL_VERSION,
      });
    });

    ws.on('message', (data, isBinary) => {
      if (isBinary) return; // 控制隧道只有文本帧，二进制走独立 data-ws（契约 §3）
      this.onMessage(data.toString('utf-8'));
    });

    ws.on('error', (err) => {
      log('warn', '隧道连接错误', { error: err.message });
    });

    ws.on('close', (code, reasonBuf) => {
      const rejectReason = REJECT_CLOSE_REASONS[code];
      if (rejectReason) {
        log('error', `网关拒绝连接: ${rejectReason}，请检查 AGENT_TOKEN/HOST_FINGERPRINT 配置`, { code });
        this.retries = Math.max(this.retries, 10); // 配置级错误直接按封顶间隔慢速重试
      } else {
        log('warn', '隧道断开', { code, reason: reasonBuf.toString('utf-8') });
      }
      this.stopHeartbeat();
      this.registered = false;
      this.ws = undefined;
      // 契约 §3.1：隧道断开清理活跃 scrcpy 会话（数据面 data-WS 独立于控制隧道，
      // 控制隧道一断，网关侧无法再下发 stop_scrcpy，须 Agent 主动兜底停会话）
      this.hooks.onDisconnect?.(`tunnel_close_${code}`);
      this.scheduleReconnect();
    });
  }

  private onMessage(raw: string): void {
    let frame;
    try {
      frame = decodeGatewayFrame(raw);
    } catch (err) {
      if (err instanceof FrameDecodeError) {
        log('warn', '收到非法网关帧，已丢弃', { error: err.message });
        return;
      }
      throw err;
    }
    switch (frame.type) {
      case 'registered':
        this.registered = true;
        this.retries = 0;
        log('info', '注册成功，进入运行态', {
          agentId: frame.agent_id,
          heartbeatIntervalS: frame.heartbeat_interval_s,
        });
        this.startHeartbeat(frame.heartbeat_interval_s || DEFAULT_HEARTBEAT_INTERVAL_S);
        break;
      case 'rpc_request':
        void this.handleRpcRequest(frame);
        break;
      case 'error':
        log('warn', '网关错误帧', { code: frame.code, message: frame.message });
        break;
    }
  }

  private async handleRpcRequest(frame: RpcRequestFrame): Promise<void> {
    const outcome = await this.hooks.dispatchRpc(frame.cmd, frame.params, frame.timeout_ms);
    const response: AgentFrame = outcome.ok
      ? { v: 1, type: 'rpc_response', id: frame.id, ok: true, result: outcome.result }
      : { v: 1, type: 'rpc_response', id: frame.id, ok: false, error: outcome.error };
    this.send(response);
  }

  private startHeartbeat(intervalS: number): void {
    this.stopHeartbeat();
    this.sendHeartbeat(); // 注册后立即发一次，让网关尽快拿到设备快照
    this.heartbeatTimer = setInterval(() => this.sendHeartbeat(), intervalS * 1_000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = undefined;
  }

  private sendHeartbeat(): void {
    this.send({
      v: 1,
      type: 'heartbeat',
      ts: Math.floor(Date.now() / 1_000),
      devices: this.hooks.getSnapshot(),
    });
  }

  private send(frame: AgentFrame): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(encodeAgentFrame(frame));
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.reconnectTimer) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** this.retries, RECONNECT_MAX_MS);
    this.retries += 1;
    log('info', `${delay}ms 后重连`, { attempt: this.retries });
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connect();
    }, delay);
  }
}
