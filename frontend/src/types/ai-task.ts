/**
 * 统一 AI 任务类型
 *
 * 对应后端 app/schemas/ai/ai_task.py + 事件协议 app/ai_core/runtime/events.py
 */

export type AiTaskStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'canceled'

export type AiTaskEventType =
  | 'task_start'
  | 'stage'
  | 'progress'
  | 'log'
  | 'message_delta'
  | 'node_update'
  | 'result'
  | 'error'
  | 'task_end'
  /** 业务自定义事件：payload.kind 标识业务类型（如 web_agent 的 command/screenshot） */
  | 'biz'

/** AI 任务（列表/主体） */
export interface AiTask {
  id: number
  project_id: number
  created_by: number
  task_type: string
  title: string
  biz_ref_type: string | null
  biz_ref_id: number | null
  status: AiTaskStatus
  progress: number
  current_stage: string | null
  stage_index: number | null
  total_stages: number | null
  ai_model: string | null
  result_summary: Record<string, unknown> | null
  result_ref: Record<string, unknown> | null
  error_message: string | null
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
  updated_at: string | null
}

/** AI 任务事件 */
export interface AiTaskEvent {
  seq: number
  event_type: AiTaskEventType
  payload: Record<string, any> | null
  created_at?: string | null
}

/** AI 任务详情（含输入参数与已落库事件） */
export interface AiTaskDetail extends AiTask {
  input_params: Record<string, unknown> | null
  events: AiTaskEvent[]
}

/** 列表响应 */
export interface AiTaskListResult {
  total: number
  items: AiTask[]
}

/** 状态统计（任务中心统计卡） */
export interface AiTaskStats {
  total: number
  pending: number
  running: number
  succeeded: number
  failed: number
  canceled: number
}

/** 提交任务入参 */
export interface AiTaskCreatePayload {
  task_type: string
  params?: Record<string, unknown>
  biz_ref_type?: string
  biz_ref_id?: number
  title?: string
}

/** SSE 实时事件信封（与 AiTaskEvent 同构，seq 必有） */
export interface AiTaskStreamEvent {
  seq: number
  type: AiTaskEventType
  payload: Record<string, any>
}
