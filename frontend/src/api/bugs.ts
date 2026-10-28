/**
 * 缺陷管理模块 API 请求封装
 */

import { request } from './request'
import type {
  Bug,
  BugListResponse,
  BugListQuery,
  BugCreate,
  BugUpdate,
  BugStatusChange,
  BugAssign,
  BugResolve,
  BugHistory,
  AiAnalysisStatus,
  AiAnalysisResult,
  BugStatistics,
  BugTrends,
} from '@/types/bugs'

const BASE = (projectId: number) => `/projects/${projectId}/bugs`

export const bugApi = {
  list(projectId: number, query: BugListQuery = {}) {
    return request.get<BugListResponse>(BASE(projectId), { params: query })
  },

  get(projectId: number, bugId: number) {
    return request.get<Bug>(`${BASE(projectId)}/${bugId}`)
  },

  create(projectId: number, data: BugCreate) {
    return request.post<Bug>(BASE(projectId), data)
  },

  update(projectId: number, bugId: number, data: BugUpdate) {
    return request.put<Bug>(`${BASE(projectId)}/${bugId}`, data)
  },

  delete(projectId: number, bugId: number) {
    return request.delete<null>(`${BASE(projectId)}/${bugId}`)
  },

  archive(projectId: number, bugId: number, isArchived: boolean) {
    return request.post<null>(`${BASE(projectId)}/${bugId}/archive`, {
      is_archived: isArchived,
    })
  },

  changeStatus(projectId: number, bugId: number, data: BugStatusChange) {
    return request.post<{ id: number; status: string; updated_at: string }>(
      `${BASE(projectId)}/${bugId}/status`,
      data,
    )
  },

  assign(
    projectId: number,
    bugId: number,
    data: BugAssign,
  ) {
    return request.post<{
      id: number
      assigned_to?: number
      assignee_name?: string
      status: string
      updated_at: string
    }>(`${BASE(projectId)}/${bugId}/assign`, data)
  },

  resolve(projectId: number, bugId: number, data: BugResolve) {
    return request.post<{ id: number; status: string; updated_at: string }>(
      `${BASE(projectId)}/${bugId}/resolve`,
      data,
    )
  },

  getHistories(projectId: number, bugId: number) {
    return request.get<BugHistory[]>(`${BASE(projectId)}/${bugId}/histories`)
  },

  triggerAiAnalysis(projectId: number, bugId: number, customPrompt?: string) {
    return request.post<{ analysis_id: string; status: string }>(
      `${BASE(projectId)}/${bugId}/ai-analysis`,
      customPrompt ? { custom_prompt: customPrompt } : {},
    )
  },

  getAiAnalysisStatus(projectId: number, bugId: number) {
    return request.get<AiAnalysisStatus>(`${BASE(projectId)}/${bugId}/ai-analysis/status`)
  },

  getAiAnalysis(projectId: number, bugId: number) {
    return request.get<AiAnalysisResult>(`${BASE(projectId)}/${bugId}/ai-analysis`)
  },

  getStatistics(
    projectId: number,
    params: { start_date?: string; end_date?: string } = {},
  ) {
    return request.get<BugStatistics>(`${BASE(projectId)}/statistics`, { params })
  },

  getTrends(projectId: number, days: 7 | 14 | 30 | 90 = 30) {
    return request.get<BugTrends>(`${BASE(projectId)}/trends`, { params: { days } })
  },
}
