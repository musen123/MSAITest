/**
 * 功能测试模块 API 请求封装
 *
 * 对应后端路由：
 *   /projects/{project_id}/func-documents     文档管理
 *   /projects/{project_id}/func-requirements  需求管理（含附件 + VLM 需求理解 SSE）
 *   /projects/{project_id}/func-test-cases    用例管理 + 执行记录
 *
 * AI 任务（文档解析、用例生成等）已统一走 AI 任务中心，见 ./aiTask.ts
 */

import { request } from './request'
import type {
  CaseExecutionCreatePayload,
  FuncCaseExecution,
  FuncDocument,
  FuncDocumentUpdate,
  FuncDocumentParsePayload,
  FuncDocumentPreview,
  FuncListResponse,
  FuncPagedListResponse,
  FuncRequirement,
  FuncTestCase,
  RequirementCreatePayload,
  RequirementReviewPayload,
  RequirementUpdatePayload,
  TestCaseCreatePayload,
  TestCaseUpdatePayload,
} from '@/types/func-test'

/**
 * 文档管理 API
 */
export const funcDocumentApi = {
  /** 上传文档 */
  upload(projectId: number, file: File, payload: { name: string; doc_type?: string; description?: string; version?: string }) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', payload.name)
    if (payload.doc_type) formData.append('doc_type', payload.doc_type)
    if (payload.description) formData.append('description', payload.description)
    if (payload.version) formData.append('version', payload.version)
    return request.post<FuncDocument>(
      `/projects/${projectId}/func-documents`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },

  /** 文档列表 */
  list(
    projectId: number,
    params: {
      doc_type?: string
      keyword?: string
      page?: number
      page_size?: number
    } = {},
  ) {
    return request.get<FuncListResponse<FuncDocument>>(
      `/projects/${projectId}/func-documents`,
      { params },
    )
  },

  /** 文档详情 */
  detail(projectId: number, docId: number) {
    return request.get<FuncDocument>(
      `/projects/${projectId}/func-documents/${docId}`,
    )
  },

  /** 更新文档 */
  update(projectId: number, docId: number, payload: FuncDocumentUpdate) {
    return request.put<FuncDocument>(
      `/projects/${projectId}/func-documents/${docId}`,
      payload,
    )
  },

  /** 删除文档 */
  remove(projectId: number, docId: number) {
    return request.delete(`/projects/${projectId}/func-documents/${docId}`)
  },

  /** 在线预览 */
  preview(projectId: number, docId: number) {
    return request.get<FuncDocumentPreview>(
      `/projects/${projectId}/func-documents/${docId}/preview`,
    )
  },

  /** AI 解析为知识库 Markdown（同步执行，可能较慢） */
  parse(
    projectId: number,
    docId: number,
    payload: FuncDocumentParsePayload = {},
  ) {
    return request.post<FuncDocument>(
      `/projects/${projectId}/func-documents/${docId}/parse`,
      payload,
      { timeout: 180000 }, // LLM 调用可能耗时
    )
  },

  /** 导入到项目知识库（要求已 parsed） */
  toKnowledge(projectId: number, docId: number) {
    return request.post<FuncDocument>(
      `/projects/${projectId}/func-documents/${docId}/to-knowledge`,
    )
  },

  /** 从项目知识库移除（不删本地） */
  removeFromKnowledge(projectId: number, docId: number) {
    return request.post<FuncDocument>(
      `/projects/${projectId}/func-documents/${docId}/remove-from-knowledge`,
    )
  },
}

/**
 * 需求管理 API
 */
export const funcRequirementApi = {
  /** 上传需求附件图片 */
  uploadAttachment(projectId: number, file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<{ url: string }>(
      `/projects/${projectId}/func-requirements/attachments`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },

  /** 创建需求 */
  create(projectId: number, payload: RequirementCreatePayload) {
    return request.post<FuncRequirement>(
      `/projects/${projectId}/func-requirements`,
      payload,
    )
  },

  /** 需求列表 */
  list(
    projectId: number,
    params: {
      status?: string
      source?: string
      module_id?: number
      keyword?: string
      page?: number
      page_size?: number
    } = {},
  ) {
    return request.get<FuncListResponse<FuncRequirement>>(
      `/projects/${projectId}/func-requirements`,
      { params },
    )
  },

  /** 需求详情 */
  detail(projectId: number, reqId: number) {
    return request.get<FuncRequirement>(
      `/projects/${projectId}/func-requirements/${reqId}`,
    )
  },

  /** 更新需求 */
  update(projectId: number, reqId: number, payload: RequirementUpdatePayload) {
    return request.put<FuncRequirement>(
      `/projects/${projectId}/func-requirements/${reqId}`,
      payload,
    )
  },

  /** 删除需求 */
  remove(projectId: number, reqId: number) {
    return request.delete(`/projects/${projectId}/func-requirements/${reqId}`)
  },

  /** 审核需求 */
  review(projectId: number, reqId: number, payload: RequirementReviewPayload) {
    return request.post<FuncRequirement>(
      `/projects/${projectId}/func-requirements/${reqId}/review`,
      payload,
    )
  },
}

/**
 * 用例管理 API
 */
export const funcTestCaseApi = {
  /** 创建用例 */
  create(projectId: number, payload: TestCaseCreatePayload) {
    return request.post<FuncTestCase>(
      `/projects/${projectId}/func-test-cases`,
      payload,
    )
  },

  /** 用例列表 */
  list(
    projectId: number,
    params: {
      requirement_id?: number
      module_id?: number
      status?: string
      priority?: string
      source?: string
      keyword?: string
      page?: number
      page_size?: number
    } = {},
  ) {
    return request.get<FuncPagedListResponse<FuncTestCase>>(
      `/projects/${projectId}/func-test-cases`,
      { params },
    )
  },

  /** 用例详情 */
  detail(projectId: number, caseId: number) {
    return request.get<FuncTestCase>(
      `/projects/${projectId}/func-test-cases/${caseId}`,
    )
  },

  /** 更新用例 */
  update(projectId: number, caseId: number, payload: TestCaseUpdatePayload) {
    return request.put<FuncTestCase>(
      `/projects/${projectId}/func-test-cases/${caseId}`,
      payload,
    )
  },

  /** 删除用例 */
  remove(projectId: number, caseId: number) {
    return request.delete(`/projects/${projectId}/func-test-cases/${caseId}`)
  },

  /** 评审用例 */
  review(projectId: number, caseId: number, payload: RequirementReviewPayload) {
    return request.post<FuncTestCase>(
      `/projects/${projectId}/func-test-cases/${caseId}/review`,
      payload,
    )
  },

  /** 批量评审用例 */
  batchReview(
    projectId: number,
    payload: RequirementReviewPayload & { case_ids: number[] },
  ) {
    return request.post<{ reviewed: number }>(
      `/projects/${projectId}/func-test-cases/batch-review`,
      payload,
    )
  },

  /** 提交执行记录 */
  submitExecution(
    projectId: number,
    caseId: number,
    payload: CaseExecutionCreatePayload,
  ) {
    return request.post<FuncCaseExecution>(
      `/projects/${projectId}/func-test-cases/${caseId}/executions`,
      payload,
    )
  },

  /** 执行记录列表 */
  listExecutions(
    projectId: number,
    caseId: number,
    params: { page?: number; page_size?: number } = {},
  ) {
    return request.get<FuncListResponse<FuncCaseExecution>>(
      `/projects/${projectId}/func-test-cases/${caseId}/executions`,
      { params },
    )
  },
}
