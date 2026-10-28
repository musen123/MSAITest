/**
 * App 自动化测试 API
 *
 * 用例/执行（项目域 /projects/{pid}/app/*）+ 录制操作台（设备域
 * /app/devices/{udid}/automation/*）。契约《APP自动化-P1接口契约.md》§3.2。
 *
 * 录制单步（step）是长请求：一句自然语言 = Agent 侧一次 aiAct（内部可多轮
 * 规划，S2 实测单句可 136s），axios 默认超时不够，须显式放宽。
 */

import axios from 'axios'
import { request } from './request'
import { useUserStore } from '@/stores/user'

// ==================== 类型 ====================

export type AppScriptStatus = 'draft' | 'active' | 'disabled'

/** 平台展示名（用例/设备通用） */
export const PLATFORM_LABEL: Record<string, string> = {
  android: '安卓',
  harmony: '鸿蒙',
  ios: 'iOS',
}

export interface AppScript {
  id: number
  project_id: number
  name: string
  platform: string
  target_app?: string | null
  description?: string | null
  yaml_content: string
  status: AppScriptStatus
  created_by?: number | null
  created_at?: string
  updated_at?: string
}

export interface AppScriptCreate {
  name: string
  yaml_content: string
  platform?: string
  target_app?: string | null
  description?: string | null
  status?: AppScriptStatus
}

export type AppExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'

export interface AppExecution {
  id: number
  script_id: number
  /** 用例名称（列表 JOIN） */
  script_name?: string | null
  /** 用例平台 android/harmony/ios（列表 JOIN） */
  script_platform?: string | null
  ai_task_id?: string | null
  device_udid: string
  /** 设备型号（左连设备表；设备已删则缺省） */
  device_name?: string | null
  /** 实际执行平台（左连设备表） */
  device_platform?: string | null
  status: AppExecutionStatus
  steps_summary?: Record<string, unknown> | null
  report_path?: string | null
  duration_ms?: number | null
  retry_index: number
  created_at?: string
  updated_at?: string
}

/** 录制单步回收的即时动作步骤（无定位动作 locate 缺省，参数在 params） */
export interface RecoveredStep {
  action: string
  locate?: string | null
  value?: string | null
  params?: Record<string, string | number> | null
}

/** 录制单步响应 */
export interface AutomationStepResult {
  session_id: string
  status: 'ok' | 'error'
  summary?: string | null
  steps: RecoveredStep[]
  yaml_flow: string
  error?: string | null
}

/** 执行进度行（单步 in-flight 直播：大模型规划原话/定位/动作） */
export interface StepProgressEntry {
  seq: number
  ts: number
  kind: 'plan' | 'locate' | 'action' | 'info' | 'error'
  text: string
}

/** 执行进度增量响应 */
export interface StepProgressResult {
  exists: boolean
  running: boolean
  seq: number
  entries: StepProgressEntry[]
}

/** 探索式生成请求（P3）：一句目标 → 自动探索 → 沉淀可回放用例 */
export interface ExploreRequest {
  device_udid: string
  goal: string
  script_name?: string
  app_hint?: string
  verify?: boolean
  suggest_asserts?: boolean
}

/** 探索任务最终结果（ai_task result_summary） */
export interface ExploreResultSummary {
  script_id?: number | null
  execution_id?: number | null
  steps_count?: number
  verify_status?: 'success' | 'failed' | 'skipped' | 'cancelled' | null
  asserts?: string[]
  error?: string | null
}

// ==================== 套件（P4） ====================

export interface AppSuiteCaseItem {
  id: number
  script_id: number
  script_name: string
  script_status: AppScriptStatus | string
  script_platform?: string
  sort_order: number
  enabled: boolean
}

export interface AppSuite {
  id: number
  project_id: number
  name: string
  description?: string | null
  device_udid?: string | null
  failure_strategy: 'continue' | 'stop'
  case_count: number
  created_by?: number | null
  created_at?: string
  updated_at?: string
  /** 详情接口才带编排 */
  cases?: AppSuiteCaseItem[]
}

export interface AppSuiteCreate {
  name: string
  description?: string | null
  device_udid?: string | null
  failure_strategy?: 'continue' | 'stop'
}

export interface AppSuiteExecution {
  id: number
  suite_id: number
  project_id: number
  suite_name?: string | null
  ai_task_id?: string | null
  device_udid: string
  /** 设备型号（左连设备表；设备已删则缺省） */
  device_name?: string | null
  /** 设备平台 android/harmony/ios（左连设备表） */
  device_platform?: string | null
  trigger_type: 'manual' | 'scheduled'
  status: AppExecutionStatus
  total_cases: number
  passed_count: number
  failed_count: number
  skipped_count: number
  error?: string | null
  duration_ms?: number | null
  created_at?: string
  updated_at?: string
}

export interface AppSuiteExecutionDetail extends AppSuiteExecution {
  /** 用例级明细（app_execution 行 + 用例名），报告仍走 fetchReport(execution.id) */
  cases: Array<AppExecution & { script_name: string }>
}

/** 执行概览聚合（报表页图表 tab，与 web_test 报表 stats 同构） */
export interface AppExecStats {
  summary: {
    total: number
    passed: number
    failed: number
    running: number
    pass_rate: number | null
    prev_pass_rate: number | null
    avg_duration_ms: number | null
  }
  daily: Array<{ date: string; passed: number; failed: number }>
  top_failures: Array<{ id: number; name: string; failures: number; runs: number }>
  /** case 维度 = {standalone, suite} 来源分布；suite 维度 = {manual, scheduled} 触发分布 */
  dist: Record<string, number>
}

// ==================== 项目域：用例 / 执行 ====================

function base(projectId: number) {
  return `/projects/${projectId}/app`
}

export const appTestApi = {
  /** 用例列表 */
  async listScripts(
    projectId: number,
    params: { keyword?: string; status?: string; platform?: string; page?: number; page_size?: number } = {},
  ): Promise<{ items: AppScript[]; total: number }> {
    const res = (await request.get(`${base(projectId)}/scripts`, { params })) as any
    return { items: res?.data?.items ?? [], total: res?.data?.total ?? 0 }
  },

  createScript(projectId: number, body: AppScriptCreate) {
    return request.post(`${base(projectId)}/scripts`, body)
  },

  async getScript(projectId: number, scriptId: number): Promise<AppScript> {
    const res = (await request.get(`${base(projectId)}/scripts/${scriptId}`)) as any
    return res?.data
  },

  updateScript(projectId: number, scriptId: number, body: Partial<AppScriptCreate>) {
    return request.put(`${base(projectId)}/scripts/${scriptId}`, body)
  },

  deleteScript(projectId: number, scriptId: number) {
    return request.delete(`${base(projectId)}/scripts/${scriptId}`)
  },

  /** 提交探索式生成任务 → {task_id}（进度经统一任务 SSE streamAiTask） */
  async explore(projectId: number, body: ExploreRequest): Promise<{ task_id: number }> {
    const res = (await request.post(`${base(projectId)}/automation/explore`, body)) as any
    return res?.data
  },

  /** 提交回放 → {execution_id, task_id}（force：跳过平台不匹配软拦截） */
  async runScript(
    projectId: number,
    scriptId: number,
    deviceUdid: string,
    force = false,
  ): Promise<{ execution_id: number; task_id: number }> {
    const res = (await request.post(`${base(projectId)}/scripts/${scriptId}/run`, {
      device_udid: deviceUdid,
      force: force || undefined,
    })) as any
    return res?.data
  },

  /** 执行记录列表（项目内，可按用例过滤） */
  async listExecutions(
    projectId: number,
    params: { script_id?: number; status?: string; page?: number; page_size?: number } = {},
  ): Promise<{ items: AppExecution[]; total: number }> {
    const res = (await request.get(`${base(projectId)}/executions`, { params })) as any
    return { items: res?.data?.items ?? [], total: res?.data?.total ?? 0 }
  },

  async getExecution(projectId: number, executionId: number): Promise<AppExecution> {
    const res = (await request.get(`${base(projectId)}/executions/${executionId}`)) as any
    return res?.data
  },

  /**
   * 签发报告独立源 URL（P4-D）：报告经网关（跨源）展示，JS 全量水合且
   * 摸不到平台 JWT；短时效 HMAC 签名解决 iframe 带不了鉴权头的问题。
   * 无报告/失败返回 null（弹窗展示错误文案）。
   */
  async getReportUrl(projectId: number, executionId: number): Promise<string | null> {
    try {
      const res = (await request.get(
        `${base(projectId)}/executions/${executionId}/report-url`,
      )) as any
      return res?.data?.url ?? null
    } catch {
      return null
    }
  },

  /**
   * 拉取执行报告 HTML → objectURL（严格 sandbox iframe 的旧展示路径；
   * 现仅作下载兜底）。用完须 URL.revokeObjectURL。404（无报告）返回 null。
   */
  async fetchReport(projectId: number, executionId: number): Promise<string | null> {
    const userStore = useUserStore()
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    try {
      const resp = await fetch(`${baseURL}${base(projectId)}/executions/${executionId}/report`, {
        headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
      })
      if (!resp.ok) return null
      const blob = await resp.blob()
      return URL.createObjectURL(blob)
    } catch {
      return null
    }
  },

  // ==================== 套件（P4） ====================

  /** 套件列表（含编排用例数） */
  async listSuites(
    projectId: number,
    params: { keyword?: string; page?: number; page_size?: number } = {},
  ): Promise<{ items: AppSuite[]; total: number }> {
    const res = (await request.get(`${base(projectId)}/suites`, { params })) as any
    return { items: res?.data?.items ?? [], total: res?.data?.total ?? 0 }
  },

  createSuite(projectId: number, body: AppSuiteCreate) {
    return request.post(`${base(projectId)}/suites`, body)
  },

  /** 套件详情（含编排 cases） */
  async getSuite(projectId: number, suiteId: number): Promise<AppSuite> {
    const res = (await request.get(`${base(projectId)}/suites/${suiteId}`)) as any
    return res?.data
  },

  updateSuite(projectId: number, suiteId: number, body: Partial<AppSuiteCreate>) {
    return request.put(`${base(projectId)}/suites/${suiteId}`, body)
  },

  deleteSuite(projectId: number, suiteId: number) {
    return request.delete(`${base(projectId)}/suites/${suiteId}`)
  },

  /** 全量替换编排：数组顺序即执行顺序 */
  async replaceSuiteCases(
    projectId: number,
    suiteId: number,
    items: Array<{ script_id: number; enabled?: boolean }>,
  ): Promise<AppSuite> {
    const res = (await request.put(`${base(projectId)}/suites/${suiteId}/cases`, {
      items,
    })) as any
    return res?.data
  },

  /** 提交套件批量执行 → {suite_execution_id, task_id}（device 缺省用套件默认设备；force 跳过平台软拦截） */
  async runSuite(
    projectId: number,
    suiteId: number,
    deviceUdid?: string,
    force = false,
  ): Promise<{ suite_execution_id: number; task_id: number }> {
    const res = (await request.post(`${base(projectId)}/suites/${suiteId}/run`, {
      device_udid: deviceUdid || undefined,
      force: force || undefined,
    })) as any
    return res?.data
  },

  /** 套件执行汇总列表 */
  async listSuiteExecutions(
    projectId: number,
    params: { suite_id?: number; status?: string; page?: number; page_size?: number } = {},
  ): Promise<{ items: AppSuiteExecution[]; total: number }> {
    const res = (await request.get(`${base(projectId)}/suite-executions`, { params })) as any
    return { items: res?.data?.items ?? [], total: res?.data?.total ?? 0 }
  },

  /** 套件执行详情（含用例级明细下钻） */
  async getSuiteExecution(
    projectId: number,
    executionId: number,
  ): Promise<AppSuiteExecutionDetail> {
    const res = (await request.get(
      `${base(projectId)}/suite-executions/${executionId}`,
    )) as any
    return res?.data
  },

  /** 执行概览聚合（报表页图表 tab） */
  async getReportStats(
    projectId: number,
    params: { dimension: 'case' | 'suite'; days: number },
  ): Promise<AppExecStats | null> {
    try {
      const res = (await request.get(`${base(projectId)}/report/stats`, { params })) as any
      return res?.data ?? null
    } catch {
      return null
    }
  },

  // ==================== 设备域：录制操作台 ====================

  /**
   * 录制单步：一句自然语言 → Agent aiAct → 回收步骤。
   * 长请求（后端 240s 宽超时），axios 超时放到 250s；错误体走业务 code 判别，
   * 绕开全局拦截器的 toast（操作台自己展示错误）。
   */
  async runStep(
    udid: string,
    body: { session_id: string; instruction: string; act_context?: string },
  ): Promise<
    | { ok: true; data: AutomationStepResult }
    | { ok: false; code: number; message: string; activeSessionId?: string }
  > {
    const userStore = useUserStore()
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    try {
      const resp = await axios.post(
        `${baseURL}/app/devices/${encodeURIComponent(udid)}/automation/step`,
        body,
        {
          headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
          timeout: 250_000,
          validateStatus: (s) => s < 500 || s === 502 || s === 504,
        },
      )
      const payload = resp.data as { code: number; message: string; data: any }
      if (resp.status === 200 && payload.code === 200) {
        return { ok: true, data: payload.data as AutomationStepResult }
      }
      return {
        ok: false,
        code: payload.code ?? resp.status,
        message: payload.message || (payload as any).detail || '执行失败',
        activeSessionId: payload.data?.active_session_id,
      }
    } catch (e) {
      return { ok: false, code: 0, message: (e as Error)?.message || '请求失败' }
    }
  },

  /**
   * 执行进度增量读（单步 in-flight 期间 1.5s 轮询）。
   * 裸 axios 绕开全局拦截器（轮询失败会 toast 刷屏）；任何失败静默回 null——
   * 直播是增益项，不打扰执行主流程。
   */
  async stepProgress(
    udid: string,
    sessionId: string,
    afterSeq: number,
  ): Promise<StepProgressResult | null> {
    const userStore = useUserStore()
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    try {
      const resp = await axios.get(
        `${baseURL}/app/devices/${encodeURIComponent(udid)}/automation/progress`,
        {
          params: { session_id: sessionId, after_seq: afterSeq },
          headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
          timeout: 12_000,
          validateStatus: (s) => s < 500,
        },
      )
      const payload = resp.data as { code: number; data: StepProgressResult }
      if (resp.status === 200 && payload.code === 200) return payload.data ?? null
      return null
    } catch {
      return null
    }
  },

  // ==================== 手动操作录制 ====================

  /** 开始手动录制（投屏触控流 → VL 语义化步骤） */
  manualStart(udid: string, sessionId: string) {
    return request.post(`/app/devices/${encodeURIComponent(udid)}/automation/manual/start`, {
      session_id: sessionId,
    })
  },

  /**
   * 手动录制步骤增量读（1.5s 轮询）。裸 axios 静默失败（同 stepProgress，
   * 轮询失败不 toast 刷屏）。
   */
  async manualSteps(
    udid: string,
    sessionId: string,
    afterSeq: number,
  ): Promise<{ recording: boolean; pending: number; seq: number; entries: Array<{ seq: number; step: RecoveredStep }> } | null> {
    const userStore = useUserStore()
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    try {
      const resp = await axios.get(
        `${baseURL}/app/devices/${encodeURIComponent(udid)}/automation/manual/steps`,
        {
          params: { session_id: sessionId, after_seq: afterSeq },
          headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
          timeout: 12_000,
          validateStatus: (s) => s < 500,
        },
      )
      const payload = resp.data as { code: number; data: any }
      if (resp.status === 200 && payload.code === 200) return payload.data
      return null
    } catch {
      return null
    }
  },

  /** 结束手动录制 → {steps, yaml_flow}（等在途 VL 识别落定，后端 60s 富余） */
  async manualStop(
    udid: string,
    sessionId: string,
  ): Promise<{ steps: RecoveredStep[]; yaml_flow: string } | null> {
    const res = (await request.post(
      `/app/devices/${encodeURIComponent(udid)}/automation/manual/stop`,
      { session_id: sessionId },
      { timeout: 65_000 } as any,
    )) as any
    return res?.data ?? null
  },

  /** 取消当前在跑的步骤 */
  abortStep(udid: string, sessionId: string) {
    return request.post(`/app/devices/${encodeURIComponent(udid)}/automation/abort`, {
      session_id: sessionId,
    })
  },

  /** 结束录制会话（dispose Agent 侧 AndroidAgent） */
  endSession(udid: string, sessionId: string) {
    return request.post(`/app/devices/${encodeURIComponent(udid)}/automation/end`, {
      session_id: sessionId,
    })
  },
}

export default appTestApi
