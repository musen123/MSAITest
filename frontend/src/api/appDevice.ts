/**
 * App 设备管理 API
 *
 * 对应后端「设备域」REST 端点（契约《APP自动化-P1接口契约.md》§5/§6）。
 * 注意：设备域端点**不带** /projects 前缀，直接挂在 /app/* 下。
 *
 * 占用冲突约定（重要）：
 *   POST /app/devices/{udid}/control-ticket 在设备被他人占用时返回
 *   **HTTP 200 + body.code === 409**（而非 HTTP 409）。因此该接口必须
 *   绕过全局响应拦截器（拦截器会把 code!==200 直接 reject 成裸 Error、
 *   丢掉 body），改用「返回原始 {code,message,data}」的裸客户端，由调用方
 *   按 body.code 分支处理占用者信息。其余接口走标准 request 封装即可。
 */

import axios from 'axios'
import { request } from './request'
import { useUserStore } from '@/stores/user'

// ==================== 类型定义 ====================

/** 执行机（Agent）在线判定态：service 内按心跳现算下发 */
export type AgentOnlineState = 'online' | 'stale' | 'offline'

/** 执行机信息（GET /app/agents 列表项） */
export interface AppAgent {
  id: number
  name: string
  host_label?: string | null
  agent_version?: string | null
  capabilities?: string[] | null
  protocol_version?: number
  last_heartbeat_at?: string | null
  /** 在线态：后端按心跳现算（≤30s online / ≤60s stale / else offline） */
  online_state: AgentOnlineState
  created_at?: string
  updated_at?: string
}

/** 设备来源 */
export type DeviceSource = 'local_adb' | 'remote_adb'
/** 连接方式 */
export type DeviceConnection = 'usb' | 'tcpip'

/** 当前锁占用信息（后端实时读 Redis 锁下发；未占用时为 null） */
export interface DeviceLockHolder {
  owner_user_id: number
  /** 占用者展示名（后端可选下发，缺省时前端回退显示 user_id） */
  owner_name?: string | null
  session_id: string
  kind: 'control' | 'record' | 'replay'
}

/** 设备信息（GET /app/devices 列表项） */
export interface AppDevice {
  id: number
  agent_id: number
  /** 执行机名（后端 join 下发，便于列表展示；缺省时前端按 agent_id 兜底） */
  agent_name?: string | null
  serial: string
  /** 全局唯一设备标识 = `{agent_id}:{serial}` */
  udid: string
  model?: string | null
  brand?: string | null
  /** 系统版本（android=Android 版本；harmony=HarmonyOS 版本；ios=iOS 版本，字段名历史遗留） */
  android_version?: string | null
  /** 设备平台：android（adb）/ harmony（鸿蒙 NEXT hdc）/ ios（libimobiledevice）；旧数据缺省 android */
  platform?: 'android' | 'harmony' | 'ios'
  resolution?: string | null
  source: DeviceSource
  connection: DeviceConnection
  /** adb 原始态（device / offline / unauthorized …） */
  state: string
  project_id?: number | null
  last_seen_at?: string | null
  /** 所属 agent 是否在线（后端现算下发；用于 online 派生） */
  agent_online?: boolean
  /** device online = 所属 agent online 且 state=='device'（后端现算下发） */
  online: boolean
  /** 当前锁占用；未占用为 null */
  lock?: DeviceLockHolder | null
  created_at?: string
  updated_at?: string
}

/** control-ticket 成功签发返回体 */
export interface ControlTicket {
  ticket: string
  session_id: string
  /** WS 路径（相对，如 /api/v1/app/devices/{udid}/control/ws） */
  ws_path: string
  /** 会话模式：control=占锁可注入；observe=不占锁只读观战（P4） */
  mode?: 'control' | 'observe'
}

/** control-ticket 占用冲突返回体（body.code === 409 时） */
export interface ControlTicketConflict {
  /** 当前占用者 user_id */
  owner_user_id: number
  owner_name?: string | null
  kind?: string
}

/** control-ticket 接口的判别联合返回 */
export type ControlTicketResult =
  | { ok: true; data: ControlTicket }
  | { ok: false; code: number; message: string; conflict?: ControlTicketConflict }

// ==================== 裸客户端（用于 control-ticket 的 body.code 判别） ====================

/**
 * 复用 axios baseURL / Authorization 头，但**不挂全局拦截器**——直接拿到
 * 原始 {code,message,data} 响应体，由调用方按 code 分支。
 */
async function postRaw<T = unknown>(
  url: string,
  data?: unknown,
): Promise<{ code: number; message: string; data: T }> {
  const userStore = useUserStore()
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const resp = await axios.post(baseURL + url, data ?? {}, {
    headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
    // 只要 HTTP 层不抛（2xx），就把响应体交回调用方自行判别
    validateStatus: (s) => s >= 200 && s < 300,
  })
  return resp.data as { code: number; message: string; data: T }
}

/**
 * 拉取设备静态截图（契约 §2.1）。`<img src>` 不能带 Authorization 头，故用
 * fetch 带 token 取 PNG blob 转 objectURL。无缓存(404)/失败返回 null（前端回落壁纸）。
 * ⚠ 调用方拿到的 objectURL 用完须 URL.revokeObjectURL 释放。
 */
async function fetchScreenshot(udid: string): Promise<string | null> {
  const userStore = useUserStore()
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const url = `${baseURL}/app/devices/${encodeURIComponent(udid)}/screenshot`
  try {
    const resp = await fetch(url, {
      headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
    })
    if (!resp.ok) return null
    const blob = await resp.blob()
    return URL.createObjectURL(blob)
  } catch {
    return null
  }
}

// ==================== API ====================

export const appDeviceApi = {
  /** 执行机列表（online/stale/offline 后端按心跳现算） */
  async listAgents(): Promise<AppAgent[]> {
    // 后端返回分页体 {code,message,data:{items,total,...}}；拦截器透传整个响应。
    // 兼容多种形状；agent 在线态后端字段名为 status，归一到前端 online_state。
    const res = (await request.get('/app/agents')) as any
    const items: any[] = res?.data?.items ?? res?.items ?? (Array.isArray(res?.data) ? res.data : [])
    return items.map((a) => ({ ...a, online_state: a.online_state ?? a.status ?? 'offline' }))
  },

  /** 设备列表（含 online 现算 + 当前锁占用） */
  async listDevices(): Promise<AppDevice[]> {
    const res = (await request.get('/app/devices')) as any
    return res?.data?.items ?? res?.items ?? (Array.isArray(res?.data) ? res.data : [])
  },

  /**
   * 申请控制票据（抢锁 + 发 ticket）。
   *
   * 返回判别联合：
   *   - { ok: true, data }  —— 成功签发，拿 {ticket, session_id, ws_path} 去连 control WS
   *   - { ok: false, code: 409, conflict } —— 设备被他人占用（HTTP 200 + body.code 409）
   *   - { ok: false, code, message } —— 其它业务错误
   *
   * 说明：本接口刻意绕过全局拦截器，故不会自动弹 toast，错误提示由页面自行处理。
   */
  async requestControlTicket(
    udid: string,
    mode: 'control' | 'observe' = 'control',
  ): Promise<ControlTicketResult> {
    const body = await postRaw<ControlTicket | ControlTicketConflict>(
      `/app/devices/${encodeURIComponent(udid)}/control-ticket`,
      { mode },
    )
    if (body.code === 200) {
      return { ok: true, data: body.data as ControlTicket }
    }
    if (body.code === 409) {
      return {
        ok: false,
        code: 409,
        message: body.message || '设备已被占用',
        conflict: body.data as ControlTicketConflict,
      }
    }
    return { ok: false, code: body.code, message: body.message || '申请控制票据失败' }
  },

  /**
   * 释放设备锁（仅锁 owner 或 manage 权限可释放）。
   * sessionId（CAS）：只释放自己那把会话锁——被 exec 接管后 holder 已易主时
   * 后端静默 no-op，绝不误放自动化任务正持有的锁。投屏 cleanup 必须带。
   */
  releaseDevice(udid: string, sessionId?: string) {
    return request.post(
      `/app/devices/${encodeURIComponent(udid)}/release`,
      sessionId ? { session_id: sessionId } : {},
    )
  },

  /** 设备静态截图 → objectURL（无则 null；用完须 revokeObjectURL） */
  fetchScreenshot,
}

export default appDeviceApi
