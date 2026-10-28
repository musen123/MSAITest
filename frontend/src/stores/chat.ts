/**
 * 智能体对话 store
 *
 * 职责：
 *   - 会话列表
 *   - 当前会话 + 消息流
 *   - WebSocket 连接管理（断开/重连）
 *   - 协议帧 → UI 消息块的转换
 *
 * 浮窗和独立页面共享同一份 state。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import router from '@/router'
import { chatApi, connectChat, type ChatSocket } from '@/api/chat'
import type {
  Conversation,
  Message,
  UiBlock,
  UiMessage,
  WsServerFrame,
} from '@/types/chat'

/**
 * WebSocket 控制帧错误码 → 友好中文提示。
 *
 * 后端 chat/ws.py 发的是机器码（便于程序判断/未来分支处理），展示层在此做本地化；
 * 未命中的码（如运行时异常原文 str(exc)，往往本身已是中文）回退显示原文。
 * 最典型的就是未配置大模型时的 llm_not_configured——过去被原样弹成英文码。
 */
const WS_ERROR_MESSAGES: Record<string, string> = {
  llm_not_configured:
    '尚未配置大模型，请先到「用户中心 → 大模型配置」添加文本模型后再使用 AI 助手',
  invalid_token: '登录已失效，请重新登录后再试',
  conversation_not_found: '会话不存在或已被删除，请刷新后重试',
  user_inactive: '当前账号已被停用，请联系管理员',
  forbidden: '你没有该项目的访问权限，无法使用 AI 助手',
  conversation_busy: '当前会话正在响应中，请等待完成或中断后再发送',
  invalid_frame: '消息格式有误，请刷新页面后重试',
  empty_message: '消息内容不能为空',
  timeout: 'AI 响应超时，请稍后重试',
}

export const useChatStore = defineStore('chat', () => {
  // ─────────────────────────────────────────────────────────
  // State
  // ─────────────────────────────────────────────────────────

  /** 当前活跃的 project_id（每次切换都要重连 WS） */
  const activeProjectId = ref<number | null>(null)

  /** 会话列表（按 updated_at 倒序） */
  const conversations = ref<Conversation[]>([])

  /** 当前选中的会话 ID */
  const activeConvId = ref<number | null>(null)

  /** 当前会话的消息列表（UI 维度） */
  const messages = ref<UiMessage[]>([])

  /** 是否正在加载会话详情/列表 */
  const loadingDetail = ref(false)
  const loadingList = ref(false)

  /** 是否正在 streaming（assistant 正在响应） */
  const streaming = ref(false)

  /** WebSocket 实例 */
  let socket: ChatSocket | null = null

  /** 当前正在流式接收的 assistant 消息 id（UI 维度） */
  let streamingMessageId: string | null = null

  /** connect 调用序号：守卫并发 connect 交错（快速切换/双击会话） */
  let connectSeq = 0

  /** 心跳定时器：防止后端 5 分钟空闲超时断连 */
  let pingTimer: number | null = null

  function stopPing() {
    if (pingTimer !== null) {
      clearInterval(pingTimer)
      pingTimer = null
    }
  }

  function startPing() {
    stopPing()
    pingTimer = window.setInterval(() => {
      if (socket?.isOpen()) {
        socket.send({ type: 'ping' })
      } else {
        stopPing()
      }
    }, 60_000)
  }

  // ─────────────────────────────────────────────────────────
  // Getters
  // ─────────────────────────────────────────────────────────

  const activeConversation = computed(() =>
    conversations.value.find((c) => c.id === activeConvId.value) || null,
  )

  const hasMessages = computed(() => messages.value.length > 0)

  // ─────────────────────────────────────────────────────────
  // Actions: REST 数据
  // ─────────────────────────────────────────────────────────

  async function loadConversations(projectId: number) {
    loadingList.value = true
    try {
      const res = await chatApi.list(projectId, { page: 1, page_size: 100 })
      conversations.value = res.data.items
    } catch (err) {
      console.error(err)
    } finally {
      loadingList.value = false
    }
  }

  async function createConversation(projectId: number, title?: string) {
    const res = await chatApi.create(projectId, { title })
    conversations.value.unshift(res.data)
    return res.data
  }

  async function renameConversation(
    projectId: number,
    convId: number,
    title: string,
  ) {
    const res = await chatApi.update(projectId, convId, { title })
    const idx = conversations.value.findIndex((c) => c.id === convId)
    if (idx !== -1) conversations.value[idx] = res.data
    return res.data
  }

  async function deleteConversation(projectId: number, convId: number) {
    await chatApi.remove(projectId, convId)
    conversations.value = conversations.value.filter((c) => c.id !== convId)
    if (activeConvId.value === convId) {
      disconnect()
      activeConvId.value = null
      messages.value = []
    }
  }

  /** 加载会话详情 + 把历史消息转成 UI 块 */
  async function loadConversation(projectId: number, convId: number) {
    loadingDetail.value = true
    try {
      const res = await chatApi.detail(projectId, convId)
      messages.value = res.data.messages.map(historyMessageToUi)
      // 同步到会话列表
      const idx = conversations.value.findIndex((c) => c.id === convId)
      if (idx !== -1) {
        // 仅更新元信息（不覆盖整个对象）
        Object.assign(conversations.value[idx], {
          title: res.data.title,
          status: res.data.status,
          updated_at: res.data.updated_at,
        })
      }
    } catch (err) {
      console.error(err)
    } finally {
      loadingDetail.value = false
    }
  }

  function historyMessageToUi(m: Message): UiMessage {
    if (m.role === 'assistant') {
      const blocks: UiBlock[] = []
      // 重建工具调用块
      for (const tc of m.tool_calls || []) {
        blocks.push({
          id: `tool_history_${tc.runId}`,
          type: 'tool',
          content: tc.toolOutput || '',
          status: mapToolStatus(tc.status),
          runId: tc.runId,
          toolName: tc.toolName,
          toolInput: tc.toolInput,
          toolOutput: tc.toolOutput || undefined,
          errorMessage: tc.error,
          action: tc.action || undefined,
          startedAt: tc.startedAt,
          endedAt: tc.endedAt || undefined,
        })
      }
      // 文本块
      if (m.content) {
        blocks.push({
          id: `text_history_${m.id}`,
          type: 'text',
          content: m.content,
          status: 'success',
          startedAt: Date.parse(m.created_at),
          endedAt: Date.parse(m.created_at),
        })
      }
      return {
        id: `msg_db_${m.id}`,
        dbId: m.id,
        role: 'assistant',
        content: m.content,
        blocks,
        toolCalls: m.tool_calls || [],
        createdAt: m.created_at,
      }
    }
    // user / system 消息
    return {
      id: `msg_db_${m.id}`,
      dbId: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.created_at,
    }
  }

  function mapToolStatus(s: string): UiBlock['status'] {
    if (s === 'success') return 'success'
    if (s === 'error') return 'error'
    if (s === 'interrupted') return 'interrupted'
    return 'streaming'
  }

  // ─────────────────────────────────────────────────────────
  // Actions: WebSocket
  // ─────────────────────────────────────────────────────────

  /**
   * 连接到指定会话的 WebSocket
   *
   * 不重复连接同一会话；切换会话时自动断开旧连接。
   */
  async function connect(projectId: number, convId: number) {
    if (
      socket &&
      socket.isOpen() &&
      activeProjectId.value === projectId &&
      activeConvId.value === convId
    ) {
      return
    }

    const seq = ++connectSeq

    disconnect()
    activeProjectId.value = projectId
    activeConvId.value = convId

    // 先加载历史
    await loadConversation(projectId, convId)

    // 守卫：await 期间又发起了新的 connect（快速切换/双击会话），
    // 本次调用作废，不创建会泄漏的连接
    if (seq !== connectSeq) return

    socket = connectChat(projectId, convId, {
      onOpen: () => {
        startPing()
      },
      onClose: (ev) => {
        stopPing()
        if (ev.code === 4001) {
          ElMessage.warning('会话被占用，请稍后再试')
        } else if (ev.code === 4401) {
          ElMessage.error('登录已过期，请重新登录')
        }
        streaming.value = false
      },
      onError: (msg) => {
        console.error('WebSocket error:', msg)
      },
      onMessage: (frame) => handleServerFrame(frame),
    })
  }

  function disconnect() {
    stopPing()
    if (socket) {
      socket.close()
      socket = null
    }
    streaming.value = false
    streamingMessageId = null
  }

  /** 发送用户消息 */
  async function sendMessage(content: string) {
    if (!socket || !socket.isOpen()) {
      // 断线自愈：会话仍有效则自动重连一次再发送
      if (activeProjectId.value && activeConvId.value) {
        await connect(activeProjectId.value, activeConvId.value)
        // 等待握手完成（最多 3s）
        const deadline = Date.now() + 3000
        while (
          socket &&
          !(socket as ChatSocket).isOpen() &&
          Date.now() < deadline
        ) {
          await new Promise((r) => setTimeout(r, 100))
        }
      }
      if (!socket || !(socket as ChatSocket).isOpen()) {
        ElMessage.error('对话未连接，请刷新重试')
        return
      }
    }
    if (streaming.value) {
      ElMessage.warning('AI 正在响应，请先中断或等待完成')
      return
    }

    // 1. 先把 user 消息插到列表
    const userMsg: UiMessage = {
      id: `msg_user_${Date.now()}`,
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 2. 预先插入一个空的 assistant 消息占位
    const assistantId = `msg_asst_${Date.now()}`
    const assistantMsg: UiMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      blocks: [],
      createdAt: new Date().toISOString(),
      streaming: true,
    }
    messages.value.push(assistantMsg)
    streamingMessageId = assistantId
    streaming.value = true

    // 3. 发送
    socket.send({ type: 'user_message', content })
  }

  function interrupt() {
    if (!socket || !socket.isOpen()) return
    socket.interrupt()
  }

  // ─────────────────────────────────────────────────────────
  // 协议帧处理
  // ─────────────────────────────────────────────────────────

  function handleServerFrame(frame: WsServerFrame) {
    switch (frame.type) {
      case 'init':
        // 握手帧，目前不做特殊处理
        break
      case 'thinking_start':
        // 标志一段 LLM 推理开始（实际块在 block_start 时创建）
        break
      case 'block_start':
        handleBlockStart(frame)
        break
      case 'block_delta':
        handleBlockDelta(frame)
        break
      case 'block_end':
        handleBlockEnd(frame)
        break
      case 'done':
        finalizeAssistantMessage(false, !!frame.interrupted)
        break
      case 'interrupted':
        finalizeAssistantMessage(true, true)
        break
      case 'pong':
        break
      case 'error': {
        const code = frame.error || ''
        if (code === 'llm_not_configured') {
          // 未配置大模型是需要用户「去操作」的场景，一闪而过的 toast 不够；
          // 给可点击跳转的确认框，直接引导到「用户中心 → 大模型配置」。
          ElMessageBox.confirm(
            '检测到你还没有配置大模型，AI 助手暂时无法使用。是否现在前往「用户中心 → 大模型配置」添加一个文本模型？',
            '尚未配置大模型',
            {
              confirmButtonText: '去配置',
              cancelButtonText: '暂不',
              type: 'warning',
            },
          )
            .then(() => {
              router.push({ name: 'LlmConfig' })
            })
            .catch(() => {
              /* 用户选择「暂不」，忽略即可 */
            })
        } else {
          ElMessage.error(
            WS_ERROR_MESSAGES[code] || code || 'AI 助手出错，请稍后重试',
          )
        }
        finalizeAssistantMessage(false, false)
        break
      }
    }
  }

  function currentAssistantMessage(): UiMessage | null {
    if (!streamingMessageId) return null
    const msg = messages.value.find((m) => m.id === streamingMessageId)
    return msg || null
  }

  function handleBlockStart(frame: Extract<WsServerFrame, { type: 'block_start' }>) {
    const msg = currentAssistantMessage()
    if (!msg) return
    if (!msg.blocks) msg.blocks = []
    msg.blocks.push({
      id: frame.block_id,
      type: frame.block_type,
      content: '',
      status: 'streaming',
      runId: frame.run_id,
      toolName: frame.tool_name,
      toolInput: frame.tool_input,
      startedAt: Date.now(),
    })
  }

  function handleBlockDelta(frame: Extract<WsServerFrame, { type: 'block_delta' }>) {
    const msg = currentAssistantMessage()
    if (!msg || !msg.blocks) return
    const block = msg.blocks.find((b) => b.id === frame.block_id)
    if (!block) return
    block.content += frame.delta
    if (block.type === 'text') {
      msg.content = msg.blocks
        .filter((b) => b.type === 'text')
        .map((b) => b.content)
        .join('')
    }
  }

  function handleBlockEnd(frame: Extract<WsServerFrame, { type: 'block_end' }>) {
    const msg = currentAssistantMessage()
    if (!msg || !msg.blocks) return
    const block = msg.blocks.find((b) => b.id === frame.block_id)
    if (!block) return
    block.status = frame.status
    block.endedAt = Date.now()
    if (frame.tool_output !== undefined) {
      block.toolOutput = frame.tool_output
      block.content = frame.tool_output
    }
    if (frame.action) {
      block.action = frame.action
    }
    if (frame.error) {
      block.errorMessage = frame.error
    }
  }

  function finalizeAssistantMessage(interrupted: boolean, _done: boolean) {
    const msg = currentAssistantMessage()
    if (msg) {
      msg.streaming = false
      msg.interrupted = interrupted
      // 同步最终 content（取所有 text 块拼接）
      if (msg.blocks) {
        msg.content = msg.blocks
          .filter((b) => b.type === 'text')
          .map((b) => b.content)
          .join('')
      }
    }
    streaming.value = false
    streamingMessageId = null
  }

  // ─────────────────────────────────────────────────────────
  // 切换 / 重置
  // ─────────────────────────────────────────────────────────

  function reset() {
    disconnect()
    activeProjectId.value = null
    activeConvId.value = null
    messages.value = []
    conversations.value = []
  }

  return {
    // state
    activeProjectId,
    activeConvId,
    conversations,
    messages,
    loadingList,
    loadingDetail,
    streaming,
    // getters
    activeConversation,
    hasMessages,
    // actions
    loadConversations,
    createConversation,
    renameConversation,
    deleteConversation,
    loadConversation,
    connect,
    disconnect,
    sendMessage,
    interrupt,
    reset,
  }
})
