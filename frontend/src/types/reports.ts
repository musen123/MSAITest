/**
 * 测试报告模块 TypeScript 类型定义
 */
export type ExecType = 'functional';
export interface ReportSummary {
    total_executions: number;
    functional_executions: number;
app_executions: number;
    overall_pass_rate: number;
    functional_pass_rate: number;
app_pass_rate: number;
}
export interface ReportExecutionItem {
    id: number;
    exec_type: ExecType;
    name: string;
    status: string;
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
    duration_ms: number;
    executor_name?: string;
    executed_at: string;
}
export interface ReportExecutionListResponse {
    total: number;
    page: number;
    page_size: number;
    items: ReportExecutionItem[];
}
export interface ReportQuery {
    exec_type?: ExecType;
    start_date?: string;
    end_date?: string;
    page?: number;
    page_size?: number;
}
