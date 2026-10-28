/**
 * 功能测试模块类型定义
 *
 * 对应后端 backend/app/schemas/func_test/*
 */

// ─────────────────────────────────────────────────────────────
// 通用
// ─────────────────────────────────────────────────────────────

export interface FuncListResponse<T> {
  total: number
  items: T[]
}

export interface FuncPagedListResponse<T> extends FuncListResponse<T> {
  page: number
  page_size: number
}

// ─────────────────────────────────────────────────────────────
// 文档
// ─────────────────────────────────────────────────────────────

export type DocType = 'requirement' | 'prototype' | 'db_dict' | 'other'

export type DocParseStatus = 'pending' | 'parsing' | 'parsed' | 'failed'
export type DocKbStatus =
  | 'not_ingested'
  | 'ingesting'
  | 'ingested'
  | 'ingest_failed'

export interface FuncDocument {
  id: number
  project_id: number
  name: string
  doc_type: DocType
  file_name: string
  file_path: string
  file_size: number
  file_ext: string
  description?: string | null
  version?: string | null
  status: string
  uploaded_by: number
  created_at: string
  updated_at: string
  download_url?: string | null

  // AI 解析
  parse_status: DocParseStatus
  parsed_content?: string | null
  parsed_at?: string | null
  parse_error_message?: string | null

  // 知识库入库
  kb_status: DocKbStatus
  kb_ingested_at?: string | null
}

export interface FuncDocumentUpdate {
  name?: string
  doc_type?: DocType
  description?: string
  version?: string
}

export interface FuncDocumentParsePayload {
  custom_prompt?: string
}

export type DocPreviewType = 'url' | 'html' | 'markdown' | 'text' | 'unsupported'

export interface FuncDocumentPreview {
  preview_type: DocPreviewType
  file_ext: string
  file_name: string
  url?: string | null
  content?: string | null
  parsed_content?: string | null
}

// ─────────────────────────────────────────────────────────────
// 需求
// ─────────────────────────────────────────────────────────────

export type RequirementPriority = 'urgent' | 'high' | 'medium' | 'low'
export type RequirementStatus =
  | 'draft'
  | 'pending_review'
  | 'reviewed'
  | 'published'
  | 'deprecated'
export type RequirementSource = 'manual' | 'ai_generated'

export interface FuncRequirement {
  id: number
  project_id: number
  code?: string | null
  title: string
  module_id?: number | null
  priority: RequirementPriority
  status: RequirementStatus
  description?: string | null
  acceptance_criteria?: string | null
  understood_content?: string | null
  source: RequirementSource
  document_id?: number | null
  ai_task_id?: number | null
  attachments?: string[] | null
  review_comment?: string | null
  reviewed_by?: number | null
  reviewed_at?: string | null
  created_by: number
  created_at: string
  updated_at: string
  /** 关联用例数（列表接口聚合返回） */
  case_count?: number
}

export interface RequirementCreatePayload {
  title: string
  code?: string
  module_id?: number
  priority?: RequirementPriority
  description?: string
  acceptance_criteria?: string
  attachments?: string[]
}

export interface RequirementUpdatePayload
  extends Partial<RequirementCreatePayload> {
  status?: RequirementStatus
  understood_content?: string
}

export interface RequirementReviewPayload {
  action: 'approve' | 'reject'
  review_comment?: string
}

// ─────────────────────────────────────────────────────────────
// 用例
// ─────────────────────────────────────────────────────────────

export type CasePriority = 'urgent' | 'high' | 'medium' | 'low'
export type CaseType =
  | 'functional'
  | 'smoke'
  | 'regression'
  | 'exploratory'
export type ValidationLevel = 'system' | 'integration' | 'unit'
export type CaseStatus =
  | 'draft'
  | 'pending_review'
  | 'reviewed'
  | 'deprecated'
export type CaseSource = 'manual' | 'ai_generated'

export interface CaseStep {
  step_no: number
  action: string
  expected: string
}

export interface FuncTestCase {
  id: number
  project_id: number
  code?: string | null
  title: string
  requirement_id?: number | null
  module_id?: number | null
  priority: CasePriority
  case_type: CaseType
  validation_level: ValidationLevel
  status: CaseStatus
  preconditions?: string | null
  test_data?: Record<string, unknown> | null
  steps?: CaseStep[] | null
  expected_result?: string[] | null
  tags?: string[] | null
  /** 是否适合 Web UI 自动化：true=适合 / false=不适合（接口层）/ null=未评估 */
  ui_automatable?: boolean | null
  review_info?: {
    review_result?: string
    review_decs?: string
  } | null
  review_comment?: string | null
  reviewed_by?: number | null
  reviewed_at?: string | null
  source: CaseSource
  ai_task_id?: number | null
  created_by: number
  updated_by?: number | null
  created_at: string
  updated_at: string
}

export interface TestCaseCreatePayload {
  title: string
  code?: string
  requirement_id?: number
  module_id?: number
  priority?: CasePriority
  case_type?: CaseType
  validation_level?: ValidationLevel
  preconditions?: string
  test_data?: Record<string, unknown>
  steps?: CaseStep[]
  expected_result?: string[]
  tags?: string[]
}

export interface TestCaseUpdatePayload
  extends Partial<TestCaseCreatePayload> {
  status?: CaseStatus
}

// ─────────────────────────────────────────────────────────────
// 用例执行
// ─────────────────────────────────────────────────────────────

export type CaseExecuteResult = 'passed' | 'failed' | 'blocked' | 'skipped'

export interface FuncCaseExecution {
  id: number
  test_case_id: number
  project_id: number
  environment_id?: number | null
  execute_result: CaseExecuteResult
  executor_id: number
  notes?: string | null
  executed_at: string
  duration?: number | null
  created_at: string
}

export interface CaseExecutionCreatePayload {
  execute_result: CaseExecuteResult
  environment_id?: number
  notes?: string
  duration?: number
  executed_at?: string
}

