/**
 * 项目知识库 API 封装（全自研，LightRAG 代理已随 P1b 下线）
 *
 * 全部走 axios {code,message,data} 壳，唯一例外是 /answer 流式问答
 * （SSE，原生 fetch 读 event-stream）。
 */

import { request } from './request'
import { useUserStore } from '@/stores/user'
import type {
  KbDocType,
  KbDocumentListResponse,
  KbEntityDetail,
  KbExtractBatchResult,
  KbGraphNode,
  KbGraphStats,
  KbInsertTextPayload,
  KbSubgraphData,
  KbUploadResult,
} from '@/types/knowledge'

// ─────────────────────────────────────────────────────────────
// 文档管理（自研业务接口：本地单一数据源 + 任务式入库）
// ─────────────────────────────────────────────────────────────

export const knowledgeDocApi = {
  /** 文档列表（本地 kb_document 单一数据源，含各状态计数） */
  list(
    projectId: number,
    params: {
      status?: string
      doc_type?: string
      keyword?: string
      page?: number
      page_size?: number
    } = {},
  ) {
    return request.get<KbDocumentListResponse>(
      `/projects/${projectId}/knowledge/documents`,
      { params },
    )
  },

  /** 上传文档（原件落 storage → 提交 kb_ingest 任务，进度走 AI 任务 SSE） */
  upload(projectId: number, file: File, docType?: KbDocType) {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) formData.append('doc_type', docType)
    return request.post<KbUploadResult>(
      `/projects/${projectId}/knowledge/documents/upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      },
    )
  },

  /** 插入文本入库（同上，任务式） */
  insertText(projectId: number, payload: KbInsertTextPayload) {
    return request.post<KbUploadResult>(
      `/projects/${projectId}/knowledge/documents/text`,
      payload,
    )
  },

  /** 删除单文档（取消在途任务 + 物理删分块 + 计数回收） */
  remove(projectId: number, kbDocId: number) {
    return request.delete(
      `/projects/${projectId}/knowledge/documents/${kbDocId}`,
    )
  },

  /** 清空当前项目所有知识库文档 */
  clearAll(projectId: number) {
    return request.delete<{ deleted: number; chunks: number }>(
      `/projects/${projectId}/knowledge/documents`,
    )
  },

  /** 手动提取图谱（任务式，不受 graph_doc_types 白名单限制） */
  extract(projectId: number, kbDocId: number) {
    return request.post<{ ai_task_id: number }>(
      `/projects/${projectId}/knowledge/documents/${kbDocId}/extract`,
    )
  },

  /** 批量提取（未抽取/失败的就绪文档，单次上限 100） */
  extractBatch(projectId: number) {
    return request.post<KbExtractBatchResult>(
      `/projects/${projectId}/knowledge/graph/extract-batch`,
    )
  },
}

// ─────────────────────────────────────────────────────────────
// 检索（自研：/search 同步、/answer SSE、/feedback）
// ─────────────────────────────────────────────────────────────

export interface KbSearchHit {
  chunk_id: number
  document_id: number
  doc_name: string
  doc_type: string
  heading_path: string
  seq: number
  content: string
  score: number
  source_type: string
  source_id?: number | null
  parse_mode?: string | null
}

export interface KbSearchData {
  hits: KbSearchHit[]
  degraded: { vector: boolean; fulltext: boolean }
  index_version: number
  log_id?: number | null
  reranked: boolean
  /** 图增强第三路是否实际参与（库级开关 settings.graph_channel，默认关） */
  graph_boosted?: boolean
}

export interface KbSearchPayload {
  query: string
  top_k?: number
  doc_types?: string[]
  deep?: boolean
  consumer?: 'search' | 'requirement'
}

export const knowledgeQueryApi = {
  /** 同步混合检索：返回 chunk 引用列表（需求页/纯检索用） */
  search(projectId: number, payload: KbSearchPayload) {
    return request.post<KbSearchData>(
      `/projects/${projectId}/knowledge/search`,
      payload,
    )
  },

  /**
   * 流式问答（SSE）——原生 fetch 读 event-stream。
   * 返回 Response，调用方用 ReadableStream 解析 `event:`/`data:` 帧。
   * 错误体是平台 {code,message}（400 未配 TEXT 模型等）。
   */
  answerStream(
    projectId: number,
    payload: KbSearchPayload,
    signal?: AbortSignal,
  ): Promise<Response> {
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const token = useUserStore().token || ''
    return fetch(`${baseURL}/projects/${projectId}/knowledge/answer`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    })
  },

  /** 检索反馈回写（采纳 chunk / 赞踩） */
  feedback(
    projectId: number,
    payload: { log_id: number; adopted_chunk_ids?: number[]; feedback?: 1 | -1 },
  ) {
    return request.post(
      `/projects/${projectId}/knowledge/search/feedback`,
      payload,
    )
  },
}

// 兼容 knowledgeApi 名称（需求创建/详情页用 knowledgeApi.search）
export const knowledgeApi = knowledgeQueryApi

// ─────────────────────────────────────────────────────────────
// 图谱（自研四表：数字 id 契约）
// ─────────────────────────────────────────────────────────────

export const knowledgeGraphApi = {
  /** 子图查询（label 起点 BFS；label 空/'*' = 热门种子；预算截断 is_truncated） */
  getGraph(
    projectId: number,
    params: { label?: string; max_depth?: number; max_nodes?: number },
  ) {
    return request.get<KbSubgraphData>(
      `/projects/${projectId}/knowledge/graph`,
      { params },
    )
  },

  /** 热门实体标签（ref_count 降序） */
  popularLabels(projectId: number, limit: number = 100) {
    return request.get<{ labels: string[] }>(
      `/projects/${projectId}/knowledge/graph/labels/popular`,
      { params: { limit } },
    )
  },

  /** 标签搜索 */
  searchLabels(projectId: number, q: string, limit: number = 50) {
    return request.get<{ labels: string[] }>(
      `/projects/${projectId}/knowledge/graph/labels/search`,
      { params: { q, limit } },
    )
  },

  /** 实体搜索（返回 id+name，合并目标选择器用） */
  searchEntities(projectId: number, q: string, limit: number = 20) {
    return request.get<KbGraphNode[]>(
      `/projects/${projectId}/knowledge/graph/entities`,
      { params: { q, limit } },
    )
  },

  /** 实体详情（mentions 溯源 + 邻接关系） */
  entityDetail(projectId: number, entityId: number) {
    return request.get<KbEntityDetail>(
      `/projects/${projectId}/knowledge/graph/entity/${entityId}`,
    )
  },

  /** 手工创建实体 */
  createEntity(
    projectId: number,
    payload: { name: string; entity_type?: string; description?: string },
  ) {
    return request.post<KbGraphNode>(
      `/projects/${projectId}/knowledge/graph/entity`,
      payload,
    )
  },

  /** 编辑实体（置 human_edited 保护位；改名自动留旧名重定向） */
  updateEntity(
    projectId: number,
    entityId: number,
    payload: { name?: string; entity_type?: string; description?: string },
  ) {
    return request.patch<KbGraphNode>(
      `/projects/${projectId}/knowledge/graph/entity/${entityId}`,
      payload,
    )
  },

  /** 删除实体（软删墓碑，防自动抽取复活） */
  deleteEntity(projectId: number, entityId: number) {
    return request.delete(
      `/projects/${projectId}/knowledge/graph/entity/${entityId}`,
    )
  },

  /** 合并实体（source 并入 target，留重定向指针） */
  mergeEntities(projectId: number, payload: { source_id: number; target_id: number }) {
    return request.post<KbGraphNode>(
      `/projects/${projectId}/knowledge/graph/entity/merge`,
      payload,
    )
  },

  /** 编辑关系 */
  updateRelation(
    projectId: number,
    relationId: number,
    payload: { keywords?: string; description?: string },
  ) {
    return request.patch(
      `/projects/${projectId}/knowledge/graph/relation/${relationId}`,
      payload,
    )
  },

  /** 删除关系（软删墓碑） */
  deleteRelation(projectId: number, relationId: number) {
    return request.delete(
      `/projects/${projectId}/knowledge/graph/relation/${relationId}`,
    )
  },

  /** 图谱统计 */
  stats(projectId: number) {
    return request.get<KbGraphStats>(
      `/projects/${projectId}/knowledge/graph/stats`,
    )
  },
}
