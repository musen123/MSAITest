<template>
  <div class="query-view">
    <div class="query-layout">
      <!-- 左侧对话区 -->
      <AppSectionCard padless class="chat-panel">
        <div class="chat-area" ref="chatAreaRef">
          <div v-if="messages.length === 0 && !streaming" class="empty-state">
            <div class="empty-glow" />
            <img :src="aiKnowledgeIllustration" alt="知识库" class="empty-illustration" />
            <h3 class="empty-title">开始你的第一次提问</h3>
            <p class="empty-desc">输入问题，AI 将从项目知识库中检索相关片段并回答</p>
            <div class="quick-prompts">
              <button
                v-for="(prompt, pi) in quickPrompts"
                :key="pi"
                class="quick-prompt-btn"
                @click="handleQuickPrompt(prompt)"
              >
                <i :class="prompt.icon" class="quick-prompt-icon" />
                <span>{{ prompt.text }}</span>
              </button>
            </div>
          </div>

          <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
            <div class="msg-avatar">
              <div v-if="msg.role === 'user'" class="avatar user-avatar">
                <i class="i-solar-user-bold" />
              </div>
              <div v-else class="avatar ai-avatar">
                <i class="i-solar-cpu-bolt-bold" />
              </div>
            </div>
            <div class="msg-body">
              <!-- 引用来源（检索先于回答，卡片置顶） -->
              <div v-if="msg.references?.length" class="msg-refs">
                <div class="refs-title">
                  <i class="i-solar-document-text-bold" />
                  引用来源（{{ msg.references.length }}）
                  <span v-if="msg.degraded" class="degraded-tag" title="向量或全文其中一路检索降级，结果可能不完整">
                    检索降级
                  </span>
                </div>
                <div class="ref-cards">
                  <div
                    v-for="(refHit, ri) in msg.references"
                    :key="refHit.chunk_id"
                    class="ref-card"
                    @click="openHit(refHit)"
                  >
                    <div class="ref-card-head">
                      <span class="ref-index">{{ ri + 1 }}</span>
                      <span class="ref-doc" :title="refHit.doc_name">{{ refHit.doc_name }}</span>
                      <span class="ref-type">{{ docTypeLabel(refHit.doc_type) }}</span>
                      <span class="ref-score">{{ fmtScore(refHit.score) }}</span>
                    </div>
                    <div v-if="refHit.heading_path" class="ref-crumb">{{ refHit.heading_path }}</div>
                    <div class="ref-snippet">{{ refHit.content }}</div>
                  </div>
                </div>
              </div>
              <!-- 思考过程 -->
              <div v-if="msg.thinking" class="thinking-block">
                <div class="thinking-header" @click="toggleThinking(i)">
                  <div class="thinking-header-left">
                    <i class="i-solar-lamp-lightbulb-bold thinking-icon" />
                    <span class="thinking-label">思考过程</span>
                    <span v-if="msg.thinkingTime" class="thinking-duration">
                      思考了 {{ formatThinkingTime(msg.thinkingTime) }}
                    </span>
                  </div>
                  <span class="thinking-toggle">
                    {{ expandedThinking.has(i) ? '收起' : '展开' }}
                  </span>
                </div>
                <div v-show="expandedThinking.has(i)" class="thinking-content">
                  <div v-html="renderMarkdown(msg.thinking)"></div>
                </div>
              </div>
              <!-- 回复内容 -->
              <div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content)"></div>
              <!-- 反馈（有检索日志才有回写凭据） -->
              <div v-if="msg.role === 'assistant' && msg.logId" class="msg-feedback">
                <button
                  class="fb-btn"
                  :class="{ active: msg.feedback === 1 }"
                  title="有帮助"
                  type="button"
                  @click="sendFeedback(msg, 1)"
                >
                  <i :class="msg.feedback === 1 ? 'i-solar-like-bold' : 'i-solar-like-linear'" />
                </button>
                <button
                  class="fb-btn dislike"
                  :class="{ active: msg.feedback === -1 }"
                  title="没帮助"
                  type="button"
                  @click="sendFeedback(msg, -1)"
                >
                  <i :class="msg.feedback === -1 ? 'i-solar-dislike-bold' : 'i-solar-dislike-linear'" />
                </button>
              </div>
            </div>
          </div>

          <!-- 流式回复 -->
          <div v-if="streaming" class="message assistant">
            <div class="msg-avatar">
              <div class="avatar ai-avatar">
                <i class="i-solar-cpu-bolt-bold" />
              </div>
            </div>
            <div class="msg-body">
              <div
                v-if="!streamingRefs.length && !streamingContent && !isThinkingPhase"
                class="searching-note"
              >
                <i class="i-solar-magnifer-linear searching-icon" />
                正在检索知识库{{ params.deep ? '（深度模式）' : '' }}...
              </div>
              <div v-if="streamingRefs.length" class="msg-refs">
                <div class="refs-title">
                  <i class="i-solar-document-text-bold" />
                  引用来源（{{ streamingRefs.length }}）
                  <span v-if="streamingDegraded" class="degraded-tag">检索降级</span>
                </div>
                <div class="ref-cards">
                  <div
                    v-for="(refHit, ri) in streamingRefs"
                    :key="refHit.chunk_id"
                    class="ref-card"
                    @click="openHit(refHit)"
                  >
                    <div class="ref-card-head">
                      <span class="ref-index">{{ ri + 1 }}</span>
                      <span class="ref-doc" :title="refHit.doc_name">{{ refHit.doc_name }}</span>
                      <span class="ref-type">{{ docTypeLabel(refHit.doc_type) }}</span>
                      <span class="ref-score">{{ fmtScore(refHit.score) }}</span>
                    </div>
                    <div v-if="refHit.heading_path" class="ref-crumb">{{ refHit.heading_path }}</div>
                    <div class="ref-snippet">{{ refHit.content }}</div>
                  </div>
                </div>
              </div>
              <div v-if="isThinkingPhase" class="thinking-block thinking-active">
                <div class="thinking-header">
                  <div class="thinking-header-left">
                    <i class="i-solar-lamp-lightbulb-bold thinking-icon spinning" />
                    <span class="thinking-label">正在思考...</span>
                    <span class="thinking-duration">{{ formatThinkingTime(thinkingElapsed) }}</span>
                  </div>
                </div>
                <div v-if="streamingThinking" class="thinking-content thinking-preview">
                  <div v-html="renderMarkdown(streamingThinking)"></div>
                </div>
              </div>
              <div v-else-if="streamingThinking" class="thinking-block">
                <div
                  class="thinking-header"
                  @click="streamingThinkingExpanded = !streamingThinkingExpanded"
                >
                  <div class="thinking-header-left">
                    <i class="i-solar-lamp-lightbulb-bold thinking-icon" />
                    <span class="thinking-label">思考过程</span>
                    <span v-if="streamingThinkingTime" class="thinking-duration">
                      思考了 {{ formatThinkingTime(streamingThinkingTime) }}
                    </span>
                  </div>
                  <span class="thinking-toggle">
                    {{ streamingThinkingExpanded ? '收起' : '展开' }}
                  </span>
                </div>
                <div v-show="streamingThinkingExpanded" class="thinking-content">
                  <div v-html="renderMarkdown(streamingThinking)"></div>
                </div>
              </div>
              <div
                v-if="!isThinkingPhase && streamingResponse"
                class="msg-content"
                v-html="renderMarkdown(streamingResponse)"
              ></div>
              <span v-if="!isThinkingPhase && streamingContent" class="cursor-blink">▌</span>
            </div>
          </div>
        </div>

        <!-- 输入区 (ChatGPT 风格) -->
        <div class="input-area">
          <div class="input-container" :class="{ 'is-focus': inputFocused }">
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              placeholder="输入问题查询知识库... (Shift + Enter 换行)"
              @keydown.enter.exact.prevent="handleSend"
              @keydown.shift.enter.prevent
              @focus="inputFocused = true"
              @blur="inputFocused = false"
              :disabled="streaming"
              resize="none"
              class="chat-textarea"
            />
            <div class="input-toolbar">
              <div class="toolbar-left">
                <button
                  class="toolbar-btn"
                  title="清空对话"
                  type="button"
                  :disabled="!messages.length || streaming"
                  @click="handleClearMessages"
                >
                  <i class="i-solar-trash-bin-trash-linear" />
                </button>
              </div>
              <div class="toolbar-right">
                <el-button
                  type="primary"
                  :disabled="!streaming && !inputText.trim()"
                  @click="streaming ? handleStop() : handleSend()"
                  class="send-btn"
                  circle
                >
                  <i v-if="!streaming" class="i-solar-arrow-up-bold" />
                  <i v-else class="i-solar-stop-bold" />
                </el-button>
              </div>
            </div>
          </div>
          <div class="input-hint">
            按 Enter 发送 · Shift + Enter 换行 · 回答基于项目知识库，内容仅供参考
          </div>
        </div>
      </AppSectionCard>

      <!-- 右侧参数面板（自研检索：4 项） -->
      <AppSectionCard padless class="params-panel">
        <div class="params-header">
          <i class="i-solar-settings-bold" />
          <span>检索设置</span>
        </div>

        <div class="params-body">
          <div class="param-item">
            <div class="param-label">检索模式</div>
            <el-radio-group v-model="params.deep" class="mode-group">
              <el-radio-button :value="false">快速</el-radio-button>
              <el-radio-button :value="true">深度</el-radio-button>
            </el-radio-group>
            <div class="param-tip">深度模式启用查询改写与重排，更准但更慢、消耗 token</div>
          </div>

          <div class="param-item">
            <div class="param-label">输出方式</div>
            <el-radio-group v-model="params.withAnswer" class="mode-group">
              <el-radio-button :value="true">检索 + 回答</el-radio-button>
              <el-radio-button :value="false">仅检索</el-radio-button>
            </el-radio-group>
            <div class="param-tip">仅检索不调用大模型，直接返回引用片段</div>
          </div>

          <div class="param-item">
            <div class="param-label">召回条数（top_k）</div>
            <el-input-number
              v-model="params.top_k"
              :min="1"
              :max="30"
              size="default"
              class="full-input"
            />
          </div>

          <div class="param-item">
            <div class="param-label">文档类型过滤</div>
            <el-select
              v-model="params.doc_types"
              multiple
              clearable
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部类型"
              class="full-select"
            >
              <el-option
                v-for="t in docTypeOptions"
                :key="t.value"
                :label="t.label"
                :value="t.value"
              />
            </el-select>
          </div>

          <div class="params-note">
            <i class="i-solar-info-circle-linear" />
            <span>点击引用卡片可查看完整分块；👍👎 反馈会用于检索质量优化</span>
          </div>
        </div>
      </AppSectionCard>
    </div>

    <!-- 分块详情抽屉 -->
    <el-drawer v-model="drawerVisible" size="520px" append-to-body>
      <template #header>
        <div class="hit-drawer-title">
          <i class="i-solar-document-text-bold" />
          <span>{{ drawerHit?.doc_name || '分块详情' }}</span>
        </div>
      </template>
      <div v-if="drawerHit" class="hit-drawer-body">
        <div class="hit-meta">
          <span class="hit-meta-tag">{{ docTypeLabel(drawerHit.doc_type) }}</span>
          <span v-if="drawerHit.parse_mode === 'llm_normalized'" class="hit-meta-tag warn">
            LLM 规整产物
          </span>
          <span class="hit-meta-score">相关分 {{ fmtScore(drawerHit.score) }}</span>
        </div>
        <div v-if="drawerHit.heading_path" class="hit-crumb">
          <i class="i-solar-map-arrow-right-linear" />
          {{ drawerHit.heading_path }}
        </div>
        <div class="hit-content" v-html="renderMarkdown(drawerHit.content)"></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeQueryApi } from '@/api/knowledge'
import type { KbSearchHit, KbSearchPayload } from '@/api/knowledge'
import type { KbDocType } from '@/types/knowledge'
import { useMarkdown } from '@/composables/useMarkdown'
import aiKnowledgeIllustration from '@/assets/illustrations/ai-knowledge.svg'
import { AppSectionCard } from '@/components/common'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const { render: renderMarkdown } = useMarkdown()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  thinkingTime?: number
  references?: KbSearchHit[]
  logId?: number | null
  feedback?: 1 | -1
  degraded?: boolean
}

const STORAGE_KEY_PREFIX = 'knowledge_query_messages_'
const storageKey = computed(() => STORAGE_KEY_PREFIX + projectId.value)

const loadMessages = (): ChatMessage[] => {
  try {
    const raw = localStorage.getItem(storageKey.value)
    const parsed = raw ? (JSON.parse(raw) as ChatMessage[]) : []
    // 旧版（LightRAG）会话的 references 是 {file_path} 形态，过滤掉避免渲染空卡片
    return parsed.map((m) => ({
      ...m,
      references: Array.isArray(m.references)
        ? (m.references as unknown[]).filter(
            (r): r is KbSearchHit => typeof (r as KbSearchHit)?.chunk_id === 'number',
          )
        : undefined,
    }))
  } catch {
    return []
  }
}

const saveMessages = (msgs: ChatMessage[]) => {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify(msgs))
  } catch {
    /* ignore */
  }
}

const messages = ref<ChatMessage[]>(loadMessages())
watch(messages, (val) => saveMessages(val), { deep: true })

const inputText = ref('')
const streaming = ref(false)
const inputFocused = ref(false)

// 快捷提问
const quickPrompts = [
  { icon: 'i-solar-document-text-linear', text: '项目有哪些核心功能模块？' },
  { icon: 'i-solar-code-linear', text: '登录接口的参数与错误码有哪些？' },
  { icon: 'i-solar-lightbulb-linear', text: '支付模块的验收标准是什么？' },
  { icon: 'i-solar-graph-new-linear', text: '有哪些历史缺陷复盘值得注意？' },
]

const handleQuickPrompt = (prompt: { text: string }) => {
  inputText.value = prompt.text
  handleSend()
}

const chatAreaRef = ref<HTMLElement>()

// 流式状态
const streamingContent = ref('')
const streamingRefs = ref<KbSearchHit[]>([])
const streamingLogId = ref<number | null>(null)
const streamingDegraded = ref(false)

// thinking 状态
const streamingThinking = ref('')
const streamingResponse = ref('')
const isThinkingPhase = ref(false)
const thinkingStartTime = ref(0)
const streamingThinkingTime = ref(0)
const thinkingElapsed = ref(0)
let thinkingTimer: ReturnType<typeof setInterval> | null = null
const expandedThinking = ref(new Set<number>())
const streamingThinkingExpanded = ref(false)

// 参数 —— 自研混合检索（/search /answer 共用）
const params = reactive({
  deep: false,
  withAnswer: true,
  top_k: 10,
  doc_types: [] as KbDocType[],
})

const docTypeOptions: { value: KbDocType; label: string }[] = [
  { value: 'requirement', label: '需求文档' },
  { value: 'api_doc', label: '接口文档' },
  { value: 'design', label: '设计文档' },
  { value: 'test_case', label: '测试用例' },
  { value: 'bug_review', label: '缺陷复盘' },
  { value: 'meeting', label: '会议纪要' },
  { value: 'other', label: '其他' },
]

const docTypeLabel = (t: string): string =>
  docTypeOptions.find((o) => o.value === t)?.label || '其他'

const fmtScore = (s: number): string => s.toFixed(3)

const buildPayload = (query: string): KbSearchPayload => ({
  query,
  top_k: params.top_k,
  doc_types: params.doc_types.length ? [...params.doc_types] : undefined,
  deep: params.deep,
})

// ────────────────── 分块详情抽屉 ──────────────────
const drawerVisible = ref(false)
const drawerHit = ref<KbSearchHit | null>(null)

const openHit = (h: KbSearchHit) => {
  drawerHit.value = h
  drawerVisible.value = true
}

// ────────────────── 反馈回写 ──────────────────
const feedbackBusy = ref(false)

const sendFeedback = async (msg: ChatMessage, val: 1 | -1) => {
  if (!msg.logId || feedbackBusy.value || msg.feedback === val) return
  feedbackBusy.value = true
  try {
    await knowledgeQueryApi.feedback(projectId.value, {
      log_id: msg.logId,
      feedback: val,
    })
    msg.feedback = val
  } catch (err) {
    console.error(err)
  } finally {
    feedbackBusy.value = false
  }
}

// ────────────────── <think> 解析（与 Chat 页一致） ──────────────────
function parseThinkingContent(raw: string): {
  thinking: string
  response: string
  isThinking: boolean
} {
  const startMatch = raw.match(/<think\s*>/)
  if (!startMatch) {
    return { thinking: '', response: raw, isThinking: false }
  }
  const startIdx = startMatch.index!
  const afterStart = startIdx + startMatch[0].length
  const endMatch = raw.substring(afterStart).match(/<\/think\s*>/)
  if (!endMatch) {
    return {
      thinking: raw.substring(afterStart).trim(),
      response: raw.substring(0, startIdx).trim(),
      isThinking: true,
    }
  }
  const endIdx = afterStart + endMatch.index!
  return {
    thinking: raw.substring(afterStart, endIdx).trim(),
    response: (raw.substring(0, startIdx) + raw.substring(endIdx + endMatch[0].length)).trim(),
    isThinking: false,
  }
}

const formatThinkingTime = (seconds: number): string => {
  if (!seconds) return ''
  if (seconds < 60) return `${seconds.toFixed(1)}秒`
  const min = Math.floor(seconds / 60)
  const sec = Math.round(seconds % 60)
  return `${min}分${sec}秒`
}

const toggleThinking = (index: number) => {
  const s = new Set(expandedThinking.value)
  if (s.has(index)) s.delete(index)
  else s.add(index)
  expandedThinking.value = s
}

const updateStreamingParse = () => {
  const raw = streamingContent.value
  const parsed = parseThinkingContent(raw)

  if (parsed.isThinking && !isThinkingPhase.value) {
    thinkingStartTime.value = Date.now()
    thinkingTimer = setInterval(() => {
      thinkingElapsed.value = Math.round((Date.now() - thinkingStartTime.value) / 100) / 10
    }, 100)
  }

  if (isThinkingPhase.value && !parsed.isThinking) {
    if (thinkingTimer) {
      clearInterval(thinkingTimer)
      thinkingTimer = null
    }
    streamingThinkingTime.value = Math.round((Date.now() - thinkingStartTime.value) / 100) / 10
    streamingThinkingExpanded.value = false
  }

  isThinkingPhase.value = parsed.isThinking
  streamingThinking.value = parsed.thinking
  streamingResponse.value = parsed.response
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatAreaRef.value) {
      chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
    }
  })
}

// ────────────────── SSE 帧解析 ──────────────────
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

// ────────────────── 发送 ──────────────────
let abortCtrl: AbortController | null = null

const handleStop = () => {
  abortCtrl?.abort()
}

/** 仅检索模式：同步 /search，引用卡片直出 */
const runSearch = async (query: string) => {
  const res = await knowledgeQueryApi.search(projectId.value, {
    ...buildPayload(query),
    consumer: 'search',
  })
  const data = res.data
  const degraded = Boolean(data.degraded?.vector || data.degraded?.fulltext)
  messages.value.push({
    role: 'assistant',
    content: data.hits.length
      ? `以上为检索到的 ${data.hits.length} 条相关片段，点击卡片可查看完整内容。`
      : '未在知识库中检索到相关内容，请尝试调整关键词或文档类型过滤。',
    references: data.hits.length ? data.hits : undefined,
    logId: data.log_id ?? null,
    degraded: degraded || undefined,
  })
}

/** 检索+回答模式：/answer SSE（references → delta 流 → done/error） */
const runAnswer = async (query: string) => {
  abortCtrl = new AbortController()
  let resp: Response
  try {
    resp = await knowledgeQueryApi.answerStream(
      projectId.value,
      buildPayload(query),
      abortCtrl.signal,
    )
  } catch (err) {
    if ((err as Error)?.name !== 'AbortError') {
      console.error(err)
      ElMessage.error('网络请求失败，请稍后重试')
    }
    return
  }

  if (!resp.ok) {
    // 平台错误壳 {code,message}（如 400 未配 TEXT 模型）或 FastAPI {detail}
    let msg = `请求失败（HTTP ${resp.status}）`
    try {
      const err = await resp.json()
      const d = err?.message ?? err?.detail
      if (typeof d === 'string' && d) msg = d
    } catch {
      /* 非 JSON 响应体，保留默认提示 */
    }
    ElMessage.error(msg)
    return
  }

  const reader = resp.body?.getReader()
  if (!reader) {
    ElMessage.error('无法读取响应流')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let doneEmpty = false
  let sseError = ''

  const handleFrame = (rawFrame: string) => {
    const f = parseSseFrame(rawFrame)
    if (!f) return
    let payload: Record<string, unknown> = {}
    try {
      payload = JSON.parse(f.data)
    } catch {
      return
    }
    if (f.event === 'references') {
      streamingRefs.value = (payload.hits as KbSearchHit[]) || []
      streamingLogId.value = (payload.log_id as number | null) ?? null
      const dg = payload.degraded as { vector?: boolean; fulltext?: boolean } | undefined
      streamingDegraded.value = Boolean(dg?.vector || dg?.fulltext)
      scrollToBottom()
    } else if (f.event === 'delta') {
      streamingContent.value += (payload.text as string) || ''
      updateStreamingParse()
      scrollToBottom()
    } else if (f.event === 'done') {
      doneEmpty = Boolean(payload.empty)
      if (payload.log_id != null) streamingLogId.value = payload.log_id as number
    } else if (f.event === 'error') {
      sseError = (payload.message as string) || '答案生成失败'
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() || ''
      for (const frame of frames) handleFrame(frame)
    }
    if (buffer.trim()) handleFrame(buffer)
  } catch (err) {
    if ((err as Error)?.name !== 'AbortError') throw err
  }

  if (sseError) ElMessage.error(sseError)

  // 收尾：把流式内容固化为一条消息（中断/空命中都有明确文案，不留悬空气泡）
  const parsed = parseThinkingContent(streamingContent.value)
  const aborted = abortCtrl?.signal.aborted ?? false
  let content = parsed.response
  if (!content) {
    if (doneEmpty) {
      content = '未在知识库中检索到与该问题相关的内容，请尝试调整提问或先上传文档。'
    } else if (aborted) {
      content = '（已停止生成）'
    } else if (sseError) {
      content = '（答案生成中断）'
    }
  } else if (aborted) {
    content = `${content}\n\n（已停止生成）`
  }

  if (content || parsed.thinking || streamingRefs.value.length) {
    messages.value.push({
      role: 'assistant',
      content,
      thinking: parsed.thinking || undefined,
      thinkingTime: streamingThinkingTime.value || undefined,
      references: streamingRefs.value.length ? [...streamingRefs.value] : undefined,
      logId: streamingLogId.value,
      degraded: streamingDegraded.value || undefined,
    })
  }
}

const handleSend = async () => {
  const query = inputText.value.trim()
  if (!query || streaming.value) return

  messages.value.push({ role: 'user', content: query })
  inputText.value = ''
  streaming.value = true
  streamingContent.value = ''
  streamingRefs.value = []
  streamingLogId.value = null
  streamingDegraded.value = false
  scrollToBottom()

  try {
    if (params.withAnswer) {
      await runAnswer(query)
    } else {
      await runSearch(query)
    }
  } catch (err) {
    // axios 拦截器已对业务错误弹过提示，这里只兜底记录
    console.error(err)
  } finally {
    if (thinkingTimer) {
      clearInterval(thinkingTimer)
      thinkingTimer = null
    }
    streaming.value = false
    streamingContent.value = ''
    streamingRefs.value = []
    streamingLogId.value = null
    streamingDegraded.value = false
    streamingThinking.value = ''
    streamingResponse.value = ''
    isThinkingPhase.value = false
    streamingThinkingTime.value = 0
    thinkingElapsed.value = 0
    thinkingStartTime.value = 0
    streamingThinkingExpanded.value = false
    abortCtrl = null
    scrollToBottom()
  }
}

const clearMessages = () => {
  messages.value = []
  expandedThinking.value = new Set()
  localStorage.removeItem(storageKey.value)
}

const handleClearMessages = async () => {
  try {
    await ElMessageBox.confirm('确定清空当前对话记录吗？', '清空对话', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  clearMessages()
  ElMessage.success('对话已清空')
}
</script>

<style scoped lang="scss">
.query-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.query-layout {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 0;
}

/* ====== 左侧对话区 ====== */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;

  /* 覆盖 AppSectionCard 内部 section-body，让它撑满 */
  :deep(.section-body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  display: flex;
  flex-direction: column;

  /* 自定义滚动条 */
  &::-webkit-scrollbar {
    width: 5px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: var(--radius-full);
    &:hover {
      background: var(--gray-400);
    }
  }
}

/* ====== 空状态 ====== */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-placeholder);
  text-align: center;
  padding: var(--space-10) var(--space-5);
  position: relative;
}

.empty-glow {
  position: absolute;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    var(--brand-glow-soft) 0%,
    var(--brand-glow-faint) 40%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 0;
}

.empty-illustration {
  width: 320px;
  max-width: 60%;
  height: auto;
  margin-bottom: var(--space-4);
  filter: drop-shadow(0 12px 28px var(--brand-glow-soft));
  position: relative;
  z-index: 1;
}

.empty-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  position: relative;
  z-index: 1;
}

.empty-desc {
  font-size: var(--font-size-sm);
  margin: 0;
  color: var(--text-secondary);
  position: relative;
  z-index: 1;
}

/* 快捷提问 */
.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-5);
  position: relative;
  z-index: 1;
}

.quick-prompt-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  white-space: nowrap;

  &:hover {
    border-color: var(--brand-300);
    color: var(--brand-600);
    background: var(--brand-50);
    box-shadow: var(--shadow-sm);
  }
}

.quick-prompt-icon {
  font-size: 14px;
  flex-shrink: 0;
}

/* ====== 消息 ====== */
.message {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  animation: msg-fade-in 0.3s var(--ease-out);
}

@keyframes msg-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.msg-avatar {
  flex-shrink: 0;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;

  > i { font-size: 16px; }
}

.user-avatar {
  background: var(--brand-500);
  color: var(--text-inverse);
  box-shadow: 0 2px 8px var(--brand-glow-strong);
}

.ai-avatar {
  background: linear-gradient(135deg, var(--brand-50), var(--brand-100));
  color: var(--brand-600);
}

.msg-body {
  flex: 1;
  min-width: 0;
}

.msg-content {
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
  color: var(--text-primary);

  :deep(code) {
    background: var(--gray-100);
    padding: 2px 6px;
    border-radius: var(--radius-xs);
    font-size: var(--font-size-sm);
    color: var(--brand-700);
    font-family: var(--font-mono);
  }

  :deep(pre.hljs) {
    background: var(--gray-50);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    overflow-x: auto;
    font-size: var(--font-size-sm);
    line-height: 1.6;

    code {
      background: transparent;
      padding: 0;
      color: inherit;
    }
  }

  :deep(p) {
    margin: 0 0 var(--space-2);
    &:last-child { margin-bottom: 0; }
  }

  :deep(ul),
  :deep(ol) {
    margin: 0 0 var(--space-2);
    padding-left: var(--space-5);
  }

  :deep(table) {
    border-collapse: collapse;
    margin: var(--space-2) 0;
    font-size: var(--font-size-sm);

    th,
    td {
      border: 1px solid var(--border-base);
      padding: 4px 10px;
    }
    th {
      background: var(--gray-50);
    }
  }

  :deep(blockquote) {
    margin: var(--space-2) 0;
    padding: 4px 12px;
    border-left: 3px solid var(--brand-300);
    color: var(--text-secondary);
    background: var(--gray-50);
  }
}

.message.user .msg-content {
  background: var(--brand-50);
  padding: 10px 16px;
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px;
  display: inline-block;
  color: var(--text-primary);
  border: 1px solid color-mix(in srgb, var(--brand-200) 50%, transparent);
}

/* ====== 引用来源（chunk 卡片） ====== */
.msg-refs {
  margin-bottom: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
}

.refs-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  background: var(--gray-50);
  border-bottom: 1px solid var(--border-light);

  > i { color: var(--brand-500); font-size: 14px; }
}

.degraded-tag {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--warning-500, #f59e0b) 12%, transparent);
  color: var(--warning-600, #d97706);
  font-size: 11px;
  font-weight: var(--font-weight-medium);
}

.ref-cards {
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.ref-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  cursor: pointer;
  background: var(--bg-card);
  transition: var(--transition-fast);

  &:hover {
    border-color: var(--brand-300);
    box-shadow: var(--shadow-sm);
    background: var(--brand-50);
  }
}

.ref-card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.ref-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
}

.ref-doc {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.ref-type {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: var(--radius-xs);
  background: var(--gray-100);
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 18px;
}

.ref-score {
  flex-shrink: 0;
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-placeholder);
}

.ref-crumb {
  margin-top: 4px;
  font-size: 11px;
  color: var(--brand-600);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-snippet {
  margin-top: 4px;
  font-size: var(--font-size-xs);
  line-height: 1.6;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

/* ====== 反馈 ====== */
.msg-feedback {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: var(--space-2);
}

.fb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--text-placeholder);
  cursor: pointer;
  transition: var(--transition-fast);

  > i { font-size: 14px; }

  &:hover {
    background: var(--gray-100);
    color: var(--brand-600);
  }

  &.active {
    color: var(--brand-600);
    background: var(--brand-50);
  }

  &.dislike:hover,
  &.dislike.active {
    color: var(--danger-600, #dc2626);
    background: color-mix(in srgb, var(--danger-500, #ef4444) 8%, transparent);
  }
}

/* ====== 检索中提示 ====== */
.searching-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding: 6px 0;
}

.searching-icon {
  font-size: 14px;
  color: var(--brand-500);
  animation: searching-pulse 1.2s ease-in-out infinite;
}

@keyframes searching-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.9); }
}

.cursor-blink {
  animation: blink 1s infinite;
  color: var(--brand-500);
  font-weight: var(--font-weight-bold);
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* ====== 输入区 (ChatGPT 风格) ====== */
.input-area {
  padding: var(--space-3) var(--space-5) var(--space-4);
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.input-container {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xl);
  transition: var(--transition-fast);
  box-shadow: var(--shadow-xs);

  &:hover {
    border-color: var(--gray-300);
  }

  &.is-focus {
    border-color: var(--brand-400);
    box-shadow: 0 0 0 3px var(--brand-glow-soft), var(--shadow-sm);
  }
}

.chat-textarea {
  :deep(.el-textarea__inner) {
    border: none !important;
    box-shadow: none !important;
    padding: 12px 16px 8px;
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
    color: var(--text-primary);
    background: transparent;
    resize: none;
    font-family: var(--font-sans);

    &::placeholder {
      color: var(--text-placeholder);
    }
  }
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px 8px 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 2px;
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);

  > i {
    font-size: 16px;
  }

  &:hover {
    background: var(--gray-100);
    color: var(--brand-600);
  }

  &:disabled {
    color: var(--text-disabled);
    cursor: not-allowed;

    &:hover {
      background: transparent;
      color: var(--text-disabled);
    }
  }
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.send-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: var(--radius-md) !important;
  background: var(--brand-500) !important;
  border: none !important;
  transition: var(--transition-fast);

  > i {
    font-size: 16px;
  }

  &:hover:not(.is-disabled) {
    background: var(--brand-600) !important;
    transform: scale(1.05);
  }

  &.is-disabled {
    background: var(--gray-200) !important;
    color: var(--text-placeholder) !important;
  }
}

.input-hint {
  margin-top: var(--space-2);
  text-align: center;
  font-size: 11px;
  color: var(--text-placeholder);
  letter-spacing: 0.02em;
}

/* ====== 右侧参数面板 ====== */
.params-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.params-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
  background: var(--gray-50);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);

  > i { color: var(--brand-500); font-size: 16px; }
}

.params-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--gray-200);
    border-radius: var(--radius-full);
  }
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  letter-spacing: 0.02em;
}

.full-select { width: 100%; }
.full-input { width: 100%; }

.mode-group {
  display: flex;
  width: 100%;

  :deep(.el-radio-button) {
    flex: 1;
  }
  :deep(.el-radio-button__inner) {
    width: 100%;
  }
}

.param-tip {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-placeholder);
}

.params-note {
  display: flex;
  gap: 6px;
  padding: var(--space-3);
  margin-top: auto;
  border-radius: var(--radius-md);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-placeholder);

  > i {
    flex-shrink: 0;
    font-size: 13px;
    margin-top: 1px;
    color: var(--brand-500);
  }
}

/* ====== 分块详情抽屉 ====== */
.hit-drawer-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  min-width: 0;

  > i { color: var(--brand-500); font-size: 16px; flex-shrink: 0; }
  > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.hit-drawer-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.hit-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.hit-meta-tag {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);

  &.warn {
    background: color-mix(in srgb, var(--warning-500, #f59e0b) 12%, transparent);
    color: var(--warning-600, #d97706);
  }
}

.hit-meta-score {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
}

.hit-crumb {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: var(--gray-50);
  font-size: var(--font-size-xs);
  color: var(--brand-600);
  word-break: break-all;

  > i { flex-shrink: 0; font-size: 13px; }
}

.hit-content {
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--text-primary);
  word-break: break-word;

  :deep(code) {
    background: var(--gray-100);
    padding: 2px 6px;
    border-radius: var(--radius-xs);
    font-size: var(--font-size-xs);
    color: var(--brand-700);
    font-family: var(--font-mono);
  }

  :deep(pre.hljs) {
    background: var(--gray-50);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    overflow-x: auto;
    font-size: var(--font-size-xs);

    code {
      background: transparent;
      padding: 0;
      color: inherit;
    }
  }

  :deep(table) {
    border-collapse: collapse;
    margin: var(--space-2) 0;
    font-size: var(--font-size-xs);
    display: block;
    overflow-x: auto;

    th,
    td {
      border: 1px solid var(--border-base);
      padding: 4px 10px;
    }
    th {
      background: var(--gray-50);
    }
  }
}

/* ====== 思考块 ====== */
.thinking-block {
  margin-bottom: var(--space-3);
  border: 1px solid color-mix(in srgb, var(--brand-500) 20%, transparent);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--brand-50);
  transition: var(--transition-fast);
}

.thinking-block.thinking-active {
  border-color: color-mix(in srgb, var(--brand-500) 40%, transparent);
  background: linear-gradient(
    135deg,
    var(--brand-50) 0%,
    color-mix(in srgb, var(--brand-500) 6%, transparent) 100%
  );
  box-shadow: 0 0 20px var(--brand-glow-faint);
}

.thinking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  transition: var(--transition-fast);
}

.thinking-header:hover {
  background: color-mix(in srgb, var(--brand-500) 6%, transparent);
}

.thinking-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.thinking-icon {
  font-size: 14px;
  line-height: 1;
  color: var(--brand-600);
}

.thinking-icon.spinning {
  display: inline-block;
  animation: think-spin 1.5s linear infinite;
}

@keyframes think-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.thinking-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--brand-700);
}

.thinking-duration {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.thinking-toggle {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  transition: var(--transition-fast);

  &:hover {
    color: var(--brand-600);
    background: color-mix(in srgb, var(--brand-500) 8%, transparent);
  }
}

.thinking-content {
  padding: 10px 12px 12px;
  border-top: 1px solid color-mix(in srgb, var(--brand-500) 12%, transparent);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
  color: var(--text-secondary);
  max-height: 300px;
  overflow-y: auto;
}

.thinking-content.thinking-preview {
  max-height: 120px;
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
}

.thinking-content :deep(strong) {
  color: var(--text-primary);
}

.thinking-content :deep(code) {
  background: var(--bg-card);
  padding: 1px 4px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  color: var(--brand-700);
}

/* ====== 响应式 ====== */
@media (max-width: 900px) {
  .query-layout {
    flex-direction: column;
  }
  .params-panel {
    width: 100%;
  }
  .quick-prompts {
    flex-direction: column;
    align-items: stretch;
  }
  .quick-prompt-btn {
    justify-content: center;
  }
}
</style>
