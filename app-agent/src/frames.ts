/**
 * 隧道控制帧协议 v1（契约 §2）—— Agent ↔ 网关的 JSON 文本帧。
 *
 * 判别联合以 `v` + `type` 双字段收窄：v 固定 1（协议大版本，破坏性变更才 +1），
 * type 区分帧种类。encode 只做序列化；decode 逐字段校验，收到脏帧抛
 * FrameDecodeError 由调用方决定丢弃/断连，绝不让半合法对象流入运行态。
 */

export const PROTOCOL_VERSION = 1;

// ---------------------------------------------------------------------------
// DeviceInfo（契约 §2）
// ---------------------------------------------------------------------------

/** adb 原始设备态；冷门态（no permissions/recovery 等）在采集层折叠为 offline */
export type DeviceState = 'device' | 'offline' | 'unauthorized';
export type DeviceConnection = 'usb' | 'tcpip';
/** 设备平台：android=adb 通道；harmony=鸿蒙 NEXT hdc 通道（H1）；ios=libimobiledevice 通道（I1） */
export type DevicePlatform = 'android' | 'harmony' | 'ios';

/** P1 能拿多少拿多少：model 之外的富信息 adb devices -l 给不了，拿不到留空串 */
export interface DeviceInfo {
  serial: string;
  state: DeviceState;
  model: string;
  brand: string;
  /** 系统版本号（android=Android 版本；harmony=HarmonyOS 版本），字段名历史遗留 */
  android_version: string;
  resolution: string;
  connection: DeviceConnection;
  platform: DevicePlatform;
}

// ---------------------------------------------------------------------------
// Agent → 网关
// ---------------------------------------------------------------------------

export interface RegisterFrame {
  v: 1;
  type: 'register';
  agent_version: string;
  capabilities: string[];
  protocol_version: number;
}

/** 每 heartbeat_interval_s 一发，devices 为全量快照（断连期间增量丢弃，靠它对账） */
export interface HeartbeatFrame {
  v: 1;
  type: 'heartbeat';
  ts: number;
  devices: DeviceInfo[];
}

export type DeviceEventKind = 'upsert' | 'remove';

export interface DeviceEventFrame {
  v: 1;
  type: 'device_event';
  event: DeviceEventKind;
  device: DeviceInfo;
}

/**
 * RPC 错误码。§2 基础集 `timeout|not_implemented|device_gone|internal`；
 * `busy` 为 §3.1 投屏"一次一台"gate 专用（已有活跃 scrcpy 会话时 start_scrcpy 回它）。
 */
export type RpcErrorCode = 'timeout' | 'not_implemented' | 'device_gone' | 'internal' | 'busy';

export interface RpcResponseOkFrame {
  v: 1;
  type: 'rpc_response';
  id: string;
  ok: true;
  result: Record<string, unknown>;
}

export interface RpcResponseErrFrame {
  v: 1;
  type: 'rpc_response';
  id: string;
  ok: false;
  error: { code: RpcErrorCode; message: string };
}

export type RpcResponseFrame = RpcResponseOkFrame | RpcResponseErrFrame;

/** 设备静态截图上报（列表缩略图用，非实时；契约 §2.1） */
export interface DeviceScreenshotFrame {
  v: 1;
  type: 'device_screenshot';
  serial: string;
  fmt: 'png';
  data_b64: string;
  captured_at: number;
}

export type AgentFrame =
  | RegisterFrame
  | HeartbeatFrame
  | DeviceEventFrame
  | RpcResponseFrame
  | DeviceScreenshotFrame;

// ---------------------------------------------------------------------------
// 网关 → Agent
// ---------------------------------------------------------------------------

export interface RegisteredFrame {
  v: 1;
  type: 'registered';
  agent_id: number;
  heartbeat_interval_s: number;
}

/** cmd 不做枚举收窄：未知 cmd 是合法帧，由 rpc 分发表回 not_implemented（契约 §10） */
export interface RpcRequestFrame {
  v: 1;
  type: 'rpc_request';
  id: string;
  cmd: string;
  params: Record<string, unknown>;
  timeout_ms: number;
}

export interface GatewayErrorFrame {
  v: 1;
  type: 'error';
  code: string;
  message: string;
}

export type GatewayFrame = RegisteredFrame | RpcRequestFrame | GatewayErrorFrame;

// ---------------------------------------------------------------------------
// 编解码
// ---------------------------------------------------------------------------

export class FrameDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'FrameDecodeError';
  }
}

export function encodeAgentFrame(frame: AgentFrame): string {
  return JSON.stringify(frame);
}

const DEVICE_STATES: ReadonlySet<string> = new Set(['device', 'offline', 'unauthorized']);
const DEVICE_CONNECTIONS: ReadonlySet<string> = new Set(['usb', 'tcpip']);
const RPC_ERROR_CODES: ReadonlySet<string> = new Set([
  'timeout',
  'not_implemented',
  'device_gone',
  'internal',
  'busy',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function fail(where: string, detail: string): never {
  throw new FrameDecodeError(`${where}: ${detail}`);
}

function requireString(obj: Record<string, unknown>, key: string, where: string): string {
  const value = obj[key];
  if (typeof value !== 'string') fail(where, `字段 ${key} 应为 string`);
  return value;
}

function requireNumber(obj: Record<string, unknown>, key: string, where: string): number {
  const value = obj[key];
  if (typeof value !== 'number' || !Number.isFinite(value)) fail(where, `字段 ${key} 应为 number`);
  return value;
}

export function validateDeviceInfo(value: unknown, where = 'DeviceInfo'): DeviceInfo {
  if (!isRecord(value)) fail(where, '应为对象');
  const state = requireString(value, 'state', where);
  if (!DEVICE_STATES.has(state)) fail(where, `state 非法: ${state}`);
  const connection = requireString(value, 'connection', where);
  if (!DEVICE_CONNECTIONS.has(connection)) fail(where, `connection 非法: ${connection}`);
  // platform 缺省 android（向后兼容旧 Agent/旧帧）
  const platform = value['platform'];
  if (
    platform !== undefined &&
    platform !== 'android' &&
    platform !== 'harmony' &&
    platform !== 'ios'
  ) {
    fail(where, `platform 非法: ${String(platform)}`);
  }
  return {
    serial: requireString(value, 'serial', where),
    state: state as DeviceState,
    model: requireString(value, 'model', where),
    brand: requireString(value, 'brand', where),
    android_version: requireString(value, 'android_version', where),
    resolution: requireString(value, 'resolution', where),
    connection: connection as DeviceConnection,
    platform: (platform as DevicePlatform | undefined) ?? 'android',
  };
}

function parseEnvelope(raw: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new FrameDecodeError('非法 JSON');
  }
  if (!isRecord(parsed)) throw new FrameDecodeError('帧应为 JSON 对象');
  if (parsed['v'] !== PROTOCOL_VERSION) throw new FrameDecodeError(`不支持的协议版本 v=${String(parsed['v'])}`);
  if (typeof parsed['type'] !== 'string') throw new FrameDecodeError('缺少 type 字段');
  return parsed;
}

/** 网关 → Agent 方向解码（Agent 收帧入口） */
export function decodeGatewayFrame(raw: string): GatewayFrame {
  const obj = parseEnvelope(raw);
  const type = obj['type'] as string;
  switch (type) {
    case 'registered':
      return {
        v: 1,
        type,
        agent_id: requireNumber(obj, 'agent_id', type),
        heartbeat_interval_s: requireNumber(obj, 'heartbeat_interval_s', type),
      };
    case 'rpc_request': {
      const params = obj['params'];
      if (!isRecord(params)) fail(type, '字段 params 应为对象');
      return {
        v: 1,
        type,
        id: requireString(obj, 'id', type),
        cmd: requireString(obj, 'cmd', type),
        params,
        timeout_ms: requireNumber(obj, 'timeout_ms', type),
      };
    }
    case 'error':
      return {
        v: 1,
        type,
        code: requireString(obj, 'code', type),
        message: requireString(obj, 'message', type),
      };
    default:
      throw new FrameDecodeError(`未知网关帧 type: ${type}`);
  }
}

/** Agent → 网关方向解码（网关侧对称使用；本工程内主要供编解码单测回环校验） */
export function decodeAgentFrame(raw: string): AgentFrame {
  const obj = parseEnvelope(raw);
  const type = obj['type'] as string;
  switch (type) {
    case 'register': {
      const capabilities = obj['capabilities'];
      if (!Array.isArray(capabilities) || capabilities.some((c) => typeof c !== 'string')) {
        fail(type, '字段 capabilities 应为 string[]');
      }
      return {
        v: 1,
        type,
        agent_version: requireString(obj, 'agent_version', type),
        capabilities: capabilities as string[],
        protocol_version: requireNumber(obj, 'protocol_version', type),
      };
    }
    case 'heartbeat': {
      const devices = obj['devices'];
      if (!Array.isArray(devices)) fail(type, '字段 devices 应为数组');
      return {
        v: 1,
        type,
        ts: requireNumber(obj, 'ts', type),
        devices: devices.map((d) => validateDeviceInfo(d, `${type}.devices[]`)),
      };
    }
    case 'device_event': {
      const event = requireString(obj, 'event', type);
      if (event !== 'upsert' && event !== 'remove') fail(type, `event 非法: ${event}`);
      return { v: 1, type, event, device: validateDeviceInfo(obj['device'], `${type}.device`) };
    }
    case 'rpc_response': {
      const id = requireString(obj, 'id', type);
      if (obj['ok'] === true) {
        const result = obj['result'];
        if (!isRecord(result)) fail(type, '字段 result 应为对象');
        return { v: 1, type, id, ok: true, result };
      }
      if (obj['ok'] === false) {
        const error = obj['error'];
        if (!isRecord(error)) fail(type, '字段 error 应为对象');
        const code = requireString(error, 'code', `${type}.error`);
        if (!RPC_ERROR_CODES.has(code)) fail(type, `error.code 非法: ${code}`);
        return {
          v: 1,
          type,
          id,
          ok: false,
          error: { code: code as RpcErrorCode, message: requireString(error, 'message', `${type}.error`) },
        };
      }
      fail(type, '字段 ok 应为 boolean');
      break;
    }
    default:
      throw new FrameDecodeError(`未知 Agent 帧 type: ${type}`);
  }
}
