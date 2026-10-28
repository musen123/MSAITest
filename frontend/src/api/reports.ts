/**
 * 测试报告模块 API 请求封装
 */

import { request } from './request'
import type {
  ReportExecutionListResponse,
  ReportQuery,
  ReportSummary,
} from '@/types/reports'

const BASE = (projectId: number) => `/projects/${projectId}/reports`

export const reportApi = {
  getSummary(projectId: number, params: { start_date?: string; end_date?: string } = {}) {
    return request.get<ReportSummary>(`${BASE(projectId)}/summary`, { params })
  },

  getExecutions(projectId: number, params: ReportQuery = {}) {
    return request.get<ReportExecutionListResponse>(`${BASE(projectId)}/executions`, {
      params,
    })
  },
}
