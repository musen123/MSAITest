/**
 * 智能体对话 API 封装
 *
 * REST 部分：会话 CRUD + 详情含消息
 * WebSocket 部分：connectChat() 工厂函数，返回带 send/interrupt/close 的会话对象
 */

import { request } from './request'
import { useUserStore } from '@/stores/user'
import type {
  Conversation,
  ConversationDetail,
  ConversationListResponse,
  WsClientFrame,
  WsServerFrame,
} from '@/types/chat'

// ─────────────────────────────────────────────────────────────
// REST
// ─────────────────────────────────────────────────────────────

export const chatApi = {
  /** 创建对话 */
  create(projectId: number, payload: { title?: string } = {}) {
    return request.post<Conversation>(
      `/projects/${projectId}/chat`,
      payload,
    )
  },

  /** 会话列表 */
  list(
    projectId: number,
    params: { status?: string; page?: number; page_size?: number } = {},
  ) {
    return request.get<ConversationListResponse>(
      `/projects/${projectId}/chat`,
      { params },
    )
  },

  /** 会话详情（含消息列表） */
  detail(projectId: number, convId: number) {
    return request.get<ConversationDetail>(
      `/projects/${projectId}/chat/${convId}`,
    )
  },

  /** 更新会话（改标题/状态） */
  update(
    projectId: number,
    convId: number,
    payload: { title?: string; status?: string },
  ) {
    return request.patch<Conversation>(
      `/projects/${projectId}/chat/${convId}`,
      payload,
    )
  },

  /** 删除会话 */
  remove(projectId: number, convId: number) {
    return request.delete(`/projects/${projectId}/chat/${convId}`)
  },
}

// ─────────────────────────────────────────────────────────────
// WebSocket
// ─────────────────────────────────────────────────────────────

export interface ChatSocketHandlers {
  onOpen?: () => void
  onClose?: (event: CloseEvent) => void
  onError?: (error: string) => void
  onMessage?: (frame: WsServerFrame) => void
}

export interface ChatSocket {
  send: (frame: WsClientFrame) => void
  interrupt: () => void
  close: () => void
  isOpen: () => boolean
}

/**
 * 建立 WebSocket 连接
 *
 * @param projectId  项目 ID
 * @param convId     会话 ID
 * @param handlers   事件回调
 * @returns          会话对象
 */
export function connectChat(
  projectId: number,
  convId: number,
  handlers: ChatSocketHandlers = {},
): ChatSocket {
  // 与 axios 拦截器一致：token 持久化在 Pinia user store
  const token = useUserStore().token || ''
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

  // 把 http/https 替换成 ws/wss，并保留相对路径处理
  let wsBase: string
  if (baseURL.startsWith('http://')) {
    wsBase = 'ws://' + baseURL.slice('http://'.length)
  } else if (baseURL.startsWith('https://')) {
    wsBase = 'wss://' + baseURL.slice('https://'.length)
  } else {
    // 相对路径：拼当前 origin
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsBase = `${protocol}//${location.host}${baseURL}`
  }

  const wsUrl = `${wsBase}/projects/${projectId}/chat/ws/${convId}?token=${encodeURIComponent(
    token,
  )}`

  const ws = new WebSocket(wsUrl)

  ws.addEventListener('open', () => {
    handlers.onOpen?.()
  })

  ws.addEventListener('close', (ev) => {
    handlers.onClose?.(ev)
  })

  ws.addEventListener('error', () => {
    handlers.onError?.('WebSocket connection error')
  })

  ws.addEventListener('message', (ev) => {
    try {
      const frame = JSON.parse(ev.data) as WsServerFrame
      handlers.onMessage?.(frame)
    } catch (err) {
      console.error('Failed to parse ws frame', err)
    }
  })

  return {
    send(frame: WsClientFrame) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(frame))
      } else {
        console.warn('WebSocket not open, dropping frame', frame)
      }
    },
    interrupt() {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'interrupt' }))
      }
    },
    close() {
      if (
        ws.readyState === WebSocket.OPEN ||
        ws.readyState === WebSocket.CONNECTING
      ) {
        ws.close()
      }
    },
    isOpen() {
      return ws.readyState === WebSocket.OPEN
    },
  }
}
