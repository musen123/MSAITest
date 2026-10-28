import { request } from './request'
import type { ApiResponse } from '@/types'

export type ModelType = 'text' | 'embed' | 'vision' | 'rerank'

export interface LlmConfigData {
  id: number
  user_id: number
  model_type: ModelType
  name: string | null
  provider: string
  model: string
  api_key: string
  base_url: string | null
  /** Midscene 模型家族（vision 用，如 doubao-seed/qwen3-vl） */
  model_family?: string | null
  is_active: boolean
  is_default: boolean
}

/** 新建配置请求体 */
export interface LlmConfigForm {
  model_type: ModelType
  name?: string | null
  provider: string
  model: string
  api_key: string
  base_url?: string
  model_family?: string
  make_default?: boolean
}

/** 修改配置请求体（字段全可选，按 id） */
export interface LlmConfigUpdateForm {
  name?: string | null
  provider?: string
  model?: string
  api_key?: string
  base_url?: string
  model_family?: string | null
}

/** 连接测试请求体（不落库） */
export interface TestConnectionForm {
  model_type: ModelType
  provider: string
  model: string
  api_key: string
  base_url?: string
}

export interface TestConnectionResult {
  success: boolean
  message: string
  latency_ms: number
}

export const llmConfigApi = {
  /** 列出当前用户的配置，可按类型过滤 */
  list(model_type?: ModelType): Promise<ApiResponse<LlmConfigData[]>> {
    return request.get('/users/me/llm-configs', {
      params: model_type ? { model_type } : {},
    })
  },

  /** 取单条完整配置（含完整 API Key，仅用于编辑回填） */
  getFull(id: number): Promise<ApiResponse<LlmConfigData>> {
    return request.get(`/users/me/llm-config/${id}/full`)
  },

  /** 新建一条配置 */
  create(data: LlmConfigForm): Promise<ApiResponse<LlmConfigData>> {
    return request.post('/users/me/llm-config', data)
  },

  /** 修改一条配置 */
  update(id: number, data: LlmConfigUpdateForm): Promise<ApiResponse<LlmConfigData>> {
    return request.put(`/users/me/llm-config/${id}`, data)
  },

  /** 设为该类型默认（运行时使用） */
  setDefault(id: number): Promise<ApiResponse<LlmConfigData>> {
    return request.post(`/users/me/llm-config/${id}/set-default`)
  },

  /** 删除一条配置（删默认会自动顺位提升） */
  remove(id: number): Promise<ApiResponse<null>> {
    return request.delete(`/users/me/llm-config/${id}`)
  },

  /** 验证连接 */
  testConnection(data: TestConnectionForm): Promise<ApiResponse<TestConnectionResult>> {
    return request.post('/users/me/llm-config/test-connection', data)
  },
}
