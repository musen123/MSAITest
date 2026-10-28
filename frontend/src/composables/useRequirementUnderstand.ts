/**
 * 需求理解 composable（统一 AI 任务驱动）
 *
 * 提交 task_type=understand_requirement 的统一任务，订阅其 SSE 事件流：
 *   - stage「图片理解 i/N」 → 切换 token 写入目标到第 i 张图片卡片
 *   - stage「整理需求」     → 切换 token 写入目标到总结区
 *   - message_delta         → 追加到当前目标（打字机）
 *   - progress              → 任务进度条
 *   - error / task_end      → 终态
 *
 * 任务同时出现在「AI 任务中心」，支持取消 / 回放 / 断线续传。
 */

import { ref } from 'vue'
import { aiTaskApi, streamAiTask } from '@/api/aiTask'
import type { AiTaskStreamEvent } from '@/types/ai-task'

export type ImageItemStatus = 'pending' | 'streaming' | 'done' | 'error'

export interface ImageItem {
  index: number
  url: string
  status: ImageItemStatus
  content: string
}

export type SummaryStatus = 'idle' | 'streaming' | 'done' | 'error'

export function useRequirementUnderstand(
  projectId: () => number,
  reqId: () => number,
  attachments: () => string[] = () => [],
  requirementTitle: () => string = () => '',
) {
  /** 流式运行状态：idle / running / done / error / aborted */
  const phase = ref<'idle' | 'running' | 'done' | 'error' | 'aborted'>('idle')

  /** 错误信息 */
  const errorMessage = ref('')

  /** 图片总数 */
  const totalImages = ref(0)

  /** 已完成的图片数 */
  const doneImages = ref(0)

  /** 图片列表 */
  const images = ref<ImageItem[]>([])

  /** LLM 总结状态 */
  const summaryStatus = ref<SummaryStatus>('idle')

  /** LLM 总结累积内容 */
  const summaryContent = ref('')

  /** 任务进度（后端 progress 事件，0-100） */
  const progress = ref(0)

  /** 统一任务 id（用于跳转任务中心详情） */
  const taskId = ref<number | null>(null)

  /** 当前 token 写入目标：图片索引（0 起）或总结区 */
  let target: { kind: 'image'; index: number } | { kind: 'summary' } | null = null

  let stopStream: (() => void) | null = null

  /** 重置状态 */
  function reset() {
    phase.value = 'idle'
    errorMessage.value = ''
    totalImages.value = 0
    doneImages.value = 0
    images.value = []
    summaryStatus.value = 'idle'
    summaryContent.value = ''
    progress.value = 0
    taskId.value = null
    target = null
  }

  /** 中止：取消统一任务并断开订阅 */
  async function abort() {
    if (stopStream) {
      stopStream()
      stopStream = null
    }
    if (taskId.value != null) {
      try {
        await aiTaskApi.cancel(projectId(), taskId.value)
      } catch {
        /* 任务可能已终态 */
      }
    }
    phase.value = 'aborted'
  }

  /**
   * 启动需求理解（提交统一 AI 任务 + 订阅事件流）
   *
   * @param payload.extra_attachments  临时附件 URL
   * @param payload.custom_prompt      自定义提示词
   */
  async function start(
    payload: { extra_attachments?: string[]; custom_prompt?: string } = {},
  ) {
    reset()
    phase.value = 'running'

    try {
      const res = await aiTaskApi.submit(projectId(), {
        task_type: 'understand_requirement',
        params: {
          requirement_id: reqId(),
          requirement_title: requirementTitle() || undefined,
          extra_attachments: payload.extra_attachments,
          custom_prompt: payload.custom_prompt,
        },
        biz_ref_type: 'requirement',
        biz_ref_id: reqId(),
      })
      taskId.value = res.data.id
    } catch (err) {
      phase.value = 'error'
      errorMessage.value = (err as Error).message || '任务提交失败'
      return
    }

    stopStream = streamAiTask(projectId(), taskId.value, {
      onEvent: dispatchEvent,
      onError: (err) => {
        if (phase.value === 'running') {
          phase.value = 'error'
          errorMessage.value = (err as Error)?.message || '事件流连接失败'
        }
      },
      onClose: () => {
        // 后端正常关闭但没收到 task_end（异常兜底）
        if (phase.value === 'running') phase.value = 'done'
      },
    })
  }

  /** 处理一个统一任务 SSE 事件 */
  function dispatchEvent(ev: AiTaskStreamEvent) {
    const p = ev.payload || {}
    switch (ev.type) {
      case 'stage':
        handleStage(String(p.name || ''), p.index, p.total)
        break
      case 'message_delta':
        appendToTarget(String(p.text || ''))
        break
      case 'progress':
        progress.value = Number(p.percent) || 0
        break
      case 'log':
        // 图片理解失败 → 标红对应卡片
        if (p.level === 'warning' && target?.kind === 'image') {
          const item = images.value.find((i) => i.index === target!.index)
          if (item && String(p.message || '').includes('理解失败')) {
            item.status = 'error'
          }
        }
        break
      case 'error':
        phase.value = 'error'
        errorMessage.value = String(p.message || '任务执行失败')
        break
      case 'task_end': {
        finishCurrentTarget()
        const st = String(p.status || '')
        if (st === 'succeeded') {
          phase.value = 'done'
          progress.value = 100
          summaryStatus.value = summaryContent.value ? 'done' : summaryStatus.value
        } else if (st === 'canceled') {
          phase.value = 'aborted'
        } else if (st === 'failed') {
          phase.value = 'error'
          if (!errorMessage.value) errorMessage.value = '任务执行失败'
        }
        stopStream?.()
        stopStream = null
        break
      }
    }
  }

  /** stage 切换：路由后续 token 的写入目标 */
  function handleStage(name: string, index?: number, total?: number) {
    finishCurrentTarget()
    if (name.startsWith('图片理解') && typeof index === 'number') {
      const imgIdx = index - 1 // stage index 1 起
      if (typeof total === 'number') totalImages.value = Math.max(total - 1, 0)
      upsertImage(imgIdx, {
        url: attachments()[imgIdx] || '',
        status: 'streaming',
        content: '',
      })
      target = { kind: 'image', index: imgIdx }
    } else if (name.startsWith('整理需求')) {
      summaryStatus.value = 'streaming'
      summaryContent.value = ''
      target = { kind: 'summary' }
    } else {
      target = null
    }
  }

  /** 当前目标收尾（图片标完成 / 总结标完成） */
  function finishCurrentTarget() {
    if (!target) return
    if (target.kind === 'image') {
      const item = images.value.find((i) => i.index === (target as { index: number }).index)
      if (item && item.status === 'streaming') {
        item.status = 'done'
        doneImages.value += 1
      }
    } else if (target.kind === 'summary' && summaryStatus.value === 'streaming') {
      summaryStatus.value = 'done'
    }
    target = null
  }

  function appendToTarget(text: string) {
    if (!text || !target) return
    if (target.kind === 'image') {
      const item = images.value.find((i) => i.index === (target as { index: number }).index)
      if (item) item.content += text
    } else {
      summaryContent.value += text
    }
  }

  function upsertImage(index: number, partial: Partial<ImageItem>) {
    const existing = images.value.find((i) => i.index === index)
    if (existing) {
      Object.assign(existing, partial)
    } else {
      images.value.push({
        index,
        url: partial.url || '',
        status: partial.status || 'pending',
        content: partial.content || '',
      })
      images.value.sort((a, b) => a.index - b.index)
    }
  }

  return {
    // state
    phase,
    errorMessage,
    totalImages,
    doneImages,
    images,
    summaryStatus,
    summaryContent,
    progress,
    taskId,
    // actions
    start,
    abort,
    reset,
  }
}
