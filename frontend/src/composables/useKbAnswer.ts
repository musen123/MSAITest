/**
 * 知识库 AI 综合问答流（POST /knowledge/answer SSE）的可复用状态机。
 *
 * 需求创建/详情页在 chunk 检索之上叠加「AI 综合结果」卡片用：
 *   references 帧 → 引用命中（取文档名去重作来源脚注）
 *   delta 帧     → 增量正文（实时剥 <think>…</think>）
 *   done / error → 收尾
 *
 * 失败口径：综合是增强能力，任何失败（未配 TEXT 模型 400 / 网络错 / error 帧）
 * 一律静默降级——无正文则卡片不占位，chunk 检索主链路不受影响，不弹全局报错。
 */
import { computed, ref } from 'vue'

import type { KbSearchHit, KbSearchPayload } from '@/api/knowledge'
import { knowledgeQueryApi } from '@/api/knowledge'

function parseSseFrame(frame: string): { event: string; data: string } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}

/** 剥 <think>…</think>：未闭合视为「思考中」，已产出的正文先行展示 */
function stripThink(raw: string): { response: string; isThinking: boolean } {
  const startMatch = raw.match(/<think\s*>/)
  if (!startMatch) return { response: raw.trim(), isThinking: false }
  const afterStart = startMatch.index! + startMatch[0].length
  const endMatch = raw.substring(afterStart).match(/<\/think\s*>/)
  if (!endMatch) {
    return { response: raw.substring(0, startMatch.index!).trim(), isThinking: true }
  }
  const endIdx = afterStart + endMatch.index!
  return {
    response: (
      raw.substring(0, startMatch.index!) + raw.substring(endIdx + endMatch[0].length)
    ).trim(),
    isThinking: false,
  }
}

export function useKbAnswer() {
  const streaming = ref(false)
  const thinking = ref(false)
  const text = ref('')
  const references = ref<KbSearchHit[]>([])
  const logId = ref<number | null>(null)
  const interrupted = ref(false)

  /** 引用文档名（按命中序去重） */
  const refDocs = computed(() => [...new Set(references.value.map((h) => h.doc_name))])
  /** 卡片是否展示：生成中或已有正文；静默失败/空命中都不占位 */
  const visible = computed(() => streaming.value || Boolean(text.value))

  let abortCtrl: AbortController | null = null

  function abort() {
    abortCtrl?.abort()
  }

  function reset() {
    abort()
    abortCtrl = null
    streaming.value = false
    thinking.value = false
    text.value = ''
    references.value = []
    logId.value = null
    interrupted.value = false
  }

  async function run(projectId: number, payload: KbSearchPayload) {
    reset()
    const ctrl = new AbortController()
    abortCtrl = ctrl
    streaming.value = true
    let raw = ''
    let sseError = false

    const handleFrame = (rawFrame: string) => {
      if (abortCtrl !== ctrl) return // 已被新一轮检索接管，旧流残帧丢弃
      const f = parseSseFrame(rawFrame)
      if (!f) return
      let data: Record<string, unknown> = {}
      try {
        data = JSON.parse(f.data)
      } catch {
        return
      }
      if (f.event === 'references') {
        references.value = (data.hits as KbSearchHit[]) || []
        if (data.log_id != null) logId.value = data.log_id as number
      } else if (f.event === 'delta') {
        raw += (data.text as string) || ''
        const parsed = stripThink(raw)
        thinking.value = parsed.isThinking
        text.value = parsed.response
      } else if (f.event === 'done') {
        if (data.log_id != null) logId.value = data.log_id as number
      } else if (f.event === 'error') {
        sseError = true
      }
    }

    try {
      const resp = await knowledgeQueryApi.answerStream(projectId, payload, ctrl.signal)
      if (!resp.ok || !resp.body) return // 未配 TEXT 模型等 → 静默降级为纯片段列表
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() || ''
        for (const frame of frames) handleFrame(frame)
      }
      if (buffer.trim()) handleFrame(buffer)
    } catch {
      // AbortError / 网络错：静默，已产出的正文保留可采纳
    } finally {
      if (abortCtrl === ctrl) {
        streaming.value = false
        thinking.value = false
        interrupted.value = (ctrl.signal.aborted || sseError) && Boolean(text.value)
      }
    }
  }

  return {
    streaming,
    thinking,
    text,
    refDocs,
    logId,
    visible,
    interrupted,
    run,
    abort,
    reset,
  }
}
