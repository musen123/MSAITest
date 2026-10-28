/**
 * 统一 AI 任务 API
 *
 * 对应后端前缀 /projects/{project_id}/ai-tasks
 */

import { request } from './request'
import { useUserStore } from '@/stores/user'
import type {
  AiTask,
  AiTaskCreatePayload,
  AiTaskDetail,
  AiTaskListResult,
  AiTaskStats,
  AiTaskStreamEvent,
} from '@/types/ai-task'

const base = (projectId: number) => `/projects/${projectId}/ai-tasks`

export const aiTaskApi = {
  /** 提交任务 */
  submit(projectId: number, payload: AiTaskCreatePayload) {
    return request.post<AiTask>(base(projectId), payload)
  },

  /** 任务列表 */
  list(
    projectId: number,
    params: { task_type?: string; status?: string; page?: number; page_size?: number } = {},
  ) {
    return request.get<AiTaskListResult>(base(projectId), { params })
  },

  /** 状态统计（任务中心统计卡，全项目维度；kind 区分 AI/执行两页） */
  stats(projectId: number, params: { task_type?: string; kind?: 'ai' | 'exec' } = {}) {
    return request.get<AiTaskStats>(`${base(projectId)}/stats`, { params })
  },

  /** 任务详情（主表 + 已落库事件） */
  detail(projectId: number, taskId: number) {
    return request.get<AiTaskDetail>(`${base(projectId)}/${taskId}`)
  },

  /** 取消 */
  cancel(projectId: number, taskId: number) {
    return request.post<AiTask>(`${base(projectId)}/${taskId}/cancel`)
  },

  /** 重试（用原参数新建） */
  retry(projectId: number, taskId: number) {
    return request.post<AiTask>(`${base(projectId)}/${taskId}/retry`)
  },

  /** 删除（仅限终态任务，事件流级联删除） */
  remove(projectId: number, taskId: number) {
    return request.delete<null>(`${base(projectId)}/${taskId}`)
  },
}

/**
 * 提交统一 AI 任务并等待其完成（适用于无需展示进度、只要「等结果」的场景，
 * 如参数依赖解析）。内部走异步任务，不阻塞后端事件循环。
 *
 * @returns 成功时 resolve 任务最终 result_summary；失败/取消时 reject。
 * @param onStage 可选：阶段变化回调（用于按钮上显示「解析中…」之类）。
 */
export function runAiTaskToCompletion(
  projectId: number,
  payload: AiTaskCreatePayload,
  onStage?: (name: string) => void,
): Promise<Record<string, unknown> | null> {
  return new Promise(async (resolve, reject) => {
    let taskId: number
    try {
      const res = await aiTaskApi.submit(projectId, payload)
      taskId = res.data.id
    } catch (err) {
      reject(err)
      return
    }

    let summary: Record<string, unknown> | null = null
    let errMsg = ''
    let stop: (() => void) | null = null
    stop = streamAiTask(
      projectId,
      taskId,
      {
        onEvent: (ev) => {
          const p = ev.payload || {}
          if (ev.type === 'stage') {
            onStage?.(String(p.name || ''))
          } else if (ev.type === 'result') {
            summary = (p.summary as Record<string, unknown>) || null
          } else if (ev.type === 'error') {
            errMsg = String(p.message || '任务执行失败')
          } else if (ev.type === 'task_end') {
            stop?.()
            const st = String(p.status || '')
            if (st === 'succeeded') resolve(summary)
            else reject(new Error(errMsg || (st === 'canceled' ? '任务已取消' : '任务执行失败')))
          }
        },
        onError: (err) => {
          stop?.()
          reject(err instanceof Error ? err : new Error('事件流连接失败'))
        },
      },
    )
  })
}

/**
 * 订阅任务实时事件（SSE）。
 *
 * 用 fetch + ReadableStream 读取（EventSource 不支持自定义鉴权头）。
 * 返回一个 stop() 函数用于中止订阅。
 *
 * @param afterSeq 从该 seq 之后开始（断线重连传已收到的最大 seq）
 */
export function streamAiTask(
  projectId: number,
  taskId: number,
  handlers: {
    onEvent: (ev: AiTaskStreamEvent) => void
    onError?: (err: unknown) => void
    onClose?: () => void
  },
  afterSeq = 0,
): () => void {
  const controller = new AbortController()
  const userStore = useUserStore()
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const url = `${baseURL}${base(projectId)}/${taskId}/stream?after_seq=${afterSeq}`

  ;(async () => {
    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: userStore.token ? `Bearer ${userStore.token}` : '',
          Accept: 'text/event-stream',
        },
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) {
        handlers.onError?.(new Error(`SSE 连接失败：${resp.status}`))
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE 以空行分隔事件块
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''
        for (const block of blocks) {
          const dataLine = block
            .split('\n')
            .find((l) => l.startsWith('data:'))
          if (!dataLine) continue
          const jsonStr = dataLine.slice(5).trim()
          if (!jsonStr) continue
          try {
            const ev = JSON.parse(jsonStr) as AiTaskStreamEvent
            handlers.onEvent(ev)
          } catch {
            /* 跳过非 JSON */
          }
        }
      }
      handlers.onClose?.()
    } catch (err) {
      if ((err as Error)?.name !== 'AbortError') {
        handlers.onError?.(err)
      }
    }
  })()

  return () => controller.abort()
}
