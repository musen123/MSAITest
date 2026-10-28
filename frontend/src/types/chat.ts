/**
 * 智能体对话类型定义
 *
 * 对应后端：
 *   - REST: backend/app/api/v1/endpoints/chat/conversations.py
 *   - WS:   backend/app/api/v1/endpoints/chat/ws.py
 */

// ─────────────────────────────────────────────────────────────
// 实体类型
// ─────────────────────────────────────────────────────────────

export type ConversationStatus = 'active' | 'completed' | 'archived'
export type MessageRole = 'user' | 'assistant' | 'system'

export interface Conversation {
  id: number
  project_id: number
  title: string
  status: ConversationStatus
  created_by: number
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  conversation_id: number
  role: MessageRole
  content: string
  tool_calls?: PersistedToolCall[] | null
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface ConversationListResponse {
  total: number
  items: Conversation[]
}

// ─────────────────────────────────────────────────────────────
// 持久化的工具调用记录（数据库里 chat_message.tool_calls）
// ─────────────────────────────────────────────────────────────

export type ToolCallStatus = 'running' | 'success' | 'error' | 'interrupted'

/**
 * 工具返回的动作卡片（后端工具输出 _action → orchestrator 透传）。
 * kind=navigate：用户点击后 router.push 到命名路由（params 自动补项目 id）
 */
export interface BlockAction {
  kind: 'navigate'
  route_name: string
  params?: Record<string, string | number>
  label: string
}

export interface PersistedToolCall {
  runId: string
  toolName: string
  toolInput: string
  toolOutput: string | null
  status: ToolCallStatus
  startedAt: number
  endedAt: number | null
  error?: string
  action?: BlockAction
}

// ─────────────────────────────────────────────────────────────
// WebSocket 帧（C→S）
// ─────────────────────────────────────────────────────────────

export interface WsUserMessageFrame {
  type: 'user_message'
  content: string
}

export interface WsInterruptFrame {
  type: 'interrupt'
}

export interface WsPingFrame {
  type: 'ping'
}

export type WsClientFrame = WsUserMessageFrame | WsInterruptFrame | WsPingFrame

// ─────────────────────────────────────────────────────────────
// WebSocket 帧（S→C）
// ─────────────────────────────────────────────────────────────

export interface WsInitFrame {
  type: 'init'
  conversation_id: number
  resumed: boolean
  message_count: number
}

export interface WsThinkingStartFrame {
  type: 'thinking_start'
}

export type BlockType = 'text' | 'tool' | 'thinking'
export type BlockStatus = 'success' | 'error' | 'interrupted'

export interface WsBlockStartFrame {
  type: 'block_start'
  block_id: string
  block_type: BlockType
  // tool 块独有
  run_id?: string
  tool_name?: string
  tool_input?: string
}

export interface WsBlockDeltaFrame {
  type: 'block_delta'
  block_id: string
  delta: string
}

export interface WsBlockEndFrame {
  type: 'block_end'
  block_id: string
  status: BlockStatus
  // tool 块独有
  block_type?: BlockType
  run_id?: string
  tool_name?: string
  tool_output?: string
  error?: string
  /** 工具附带的动作卡片（跳转按钮） */
  action?: BlockAction
}

export interface WsDoneFrame {
  type: 'done'
  interrupted?: boolean
}

export interface WsInterruptedFrame {
  type: 'interrupted'
  conversation_id?: number
}

export interface WsPongFrame {
  type: 'pong'
}

export interface WsErrorFrame {
  type: 'error'
  error: string
}

export type WsServerFrame =
  | WsInitFrame
  | WsThinkingStartFrame
  | WsBlockStartFrame
  | WsBlockDeltaFrame
  | WsBlockEndFrame
  | WsDoneFrame
  | WsInterruptedFrame
  | WsPongFrame
  | WsErrorFrame

// ─────────────────────────────────────────────────────────────
// UI 消息块（store 用）
// ─────────────────────────────────────────────────────────────

/**
 * 一条 assistant 消息由多个 block 构成。
 * 每个 block 对应 LangGraph 工作流里 LLM 推理 / 工具调用的一个阶段。
 */
export interface UiBlock {
  id: string
  type: BlockType
  /** 累积的文本内容（text / thinking 块）或工具输出（tool 块） */
  content: string
  status: BlockStatus | 'streaming'
  // tool 块专属
  runId?: string
  toolName?: string
  toolInput?: string
  toolOutput?: string
  errorMessage?: string
  /** 工具附带的动作卡片（跳转按钮） */
  action?: BlockAction
  startedAt: number
  endedAt?: number
}

/**
 * 一条消息（user / assistant / system）。
 * - user 消息：content 即用户输入
 * - assistant 消息：由 blocks 构成；旧消息（从历史加载）会被还原成 blocks
 * - system 消息：暂未使用
 */
export interface UiMessage {
  id: string // UI 维度的 id（不是数据库 id），便于流式过程中合并
  dbId?: number // 数据库 id（来自 GET /chat/{id} 的 messages）
  role: MessageRole
  content: string // user 消息直接用；assistant 消息可缓存最终文本
  blocks?: UiBlock[]
  toolCalls?: PersistedToolCall[]
  createdAt: string
  /** 当前消息是否正在流式接收（assistant 流式中） */
  streaming?: boolean
  /** 是否被中断 */
  interrupted?: boolean
}
