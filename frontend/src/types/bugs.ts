/**
 * 缺陷管理模块 TypeScript 类型定义
 */

export type BugSeverity = 'critical' | 'major' | 'moderate' | 'minor' | 'trivial'
export type BugPriority = 'urgent' | 'high' | 'medium' | 'low'
export type BugStatus =
  | 'new'
  | 'assigned'
  | 'in_progress'
  | 'resolved'
  | 'verified'
  | 'reopened'
  | 'closed'
  | 'postponed'
  | 'wontfix'

// ── Bug 列表项（简略） ─────────────────────────────────────

export interface BugListItem {
  id: number
  bug_key: string
  title: string
  severity: BugSeverity
  priority: BugPriority
  status: BugStatus
  module_id?: number
  module_name?: string
  assigned_to?: number
  assignee_name?: string
  created_by: number
  creator_name?: string
  is_archived: boolean
  created_at: string
  updated_at: string
}

// ── Bug 完整详情 ──────────────────────────────────────────

export interface Bug extends BugListItem {
  project_id: number
  description: string
  test_case_id?: number
  test_case_type?: string
  environment?: string
  reproduction_steps?: string
  expected_result?: string
  actual_result?: string
  tags?: string[]
  external_bug_key?: string
  has_ai_analysis: boolean
}

export interface BugListResponse {
  total: number
  page: number
  page_size: number
  items: BugListItem[]
}

// ── 创建 / 更新 ───────────────────────────────────────────

export interface BugCreate {
  title: string
  description: string
  severity: BugSeverity
  priority: BugPriority
  module_id?: number
  test_case_id?: number
  test_case_type?: string
  assigned_to?: number
  environment?: string
  reproduction_steps?: string
  expected_result?: string
  actual_result?: string
  tags?: string[]
  external_bug_key?: string
}

export interface BugUpdate {
  title?: string
  description?: string
  severity?: BugSeverity
  priority?: BugPriority
  module_id?: number
  test_case_id?: number
  test_case_type?: string
  environment?: string
  reproduction_steps?: string
  expected_result?: string
  actual_result?: string
  tags?: string[]
  external_bug_key?: string
}

// ── 状态流转 ──────────────────────────────────────────────

export interface BugStatusChange {
  status: BugStatus
  comment?: string
}

export interface BugAssign {
  assigned_to: number
  comment?: string
}

export interface BugResolve {
  action: 'resolve' | 'close' | 'reopen'
  comment?: string
}

// ── 操作历史 ──────────────────────────────────────────────

export interface BugHistory {
  id: number
  action: string
  from_value?: string
  to_value?: string
  comment?: string
  operated_by: number
  operator_name?: string
  operated_at: string
}

// ── AI 分析 ───────────────────────────────────────────────

export interface AiAnalysisStatus {
  analysis_id: string
  analysis_status: string
  error_message?: string
  created_at: string
  completed_at?: string
}

export interface SimilarBug {
  bug_id: number
  bug_key: string
  title: string
  similarity_score: number
  status: string
}

export interface AiAnalysisResult {
  analysis_id: string
  analysis_status: string
  root_cause_analysis?: Record<string, unknown>
  solution_recommendation?: Record<string, unknown>
  similar_bugs?: SimilarBug[]
  severity_assessment?: Record<string, unknown>
  error_message?: string
  created_at: string
  completed_at?: string
}

// ── 统计 ──────────────────────────────────────────────────

export interface BugStatistics {
  total: number
  by_status: Record<string, number>
  by_severity: Record<string, number>
  by_priority: Record<string, number>
  resolution_rate: number
  avg_resolution_hours?: number
}

export interface BugTrends {
  dates: string[]
  created: number[]
  resolved: number[]
  closed: number[]
}

// ── 查询参数 ──────────────────────────────────────────────

export interface BugListQuery {
  status?: string
  severity?: string
  priority?: string
  assigned_to?: number
  module_id?: number
  created_by?: number
  keyword?: string
  is_archived?: boolean
  page?: number
  page_size?: number
}
