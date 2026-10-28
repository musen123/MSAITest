/**
 * 数据报表中心 API
 *
 * 对应后端 /projects/{id}/report/* 三个维度聚合接口
 */
import { request } from './request';
// ── 测试资产 ──
export interface AssetsReportData {
  days: number
  cards: {
    case_total: { value: number; by_type: { functional: number; app: number } }
    requirements: { value: number; reviewed: number }
    suites: { value: number }
    kb_documents: { value: number; processed: number }
    ai_cases: { value: number; pct: number | null }
  }
  coverage: {
    requirement: { rate: number | null; covered: number; total: number }
    review: { rate: number | null; reviewed: number; total: number }
  }
  growth_trend: { date: string; functional: number; app: number }[]
  review_status: Record<string, Record<string, number>>
  priority_dist: Record<string, number>
  source_dist: { ai_generated: number; manual: number }
}
// ── 缺陷质量 ──
export interface QualityReportData {
    days: number;
    cards: {
        open: {
            value: number;
            urgent: number;
        };
        created: {
            value: number;
            trend: number | null;
        };
        closed: {
            value: number;
            converging: boolean;
        };
        avg_resolve_days: number | null;
        resolve_rate: number | null;
        reopened: number;
        ai_coverage: number | null;
        stale: number;
    };
    trend: {
        date: string;
        created: number;
        closed: number;
        open: number;
    }[];
    severity_dist: Record<string, number>;
    status_dist: Record<string, number>;
    assignee_load: {
        user_id: number | null;
        name: string;
        count: number;
    }[];
    source_dist: Record<string, number>;
    stale_list: {
        id: number;
        title: string;
        days: number;
    }[];
}
// ── AI 提效 ──
export interface AiReportData {
    days: number;
    cards: {
        total: {
            value: number;
            trend: number | null;
        };
        success_rate: number | null;
        ai_cases: {
            value: number;
            pct: number | null;
        };
        ai_review_pass: number | null;
        avg_duration_min: number | null;
        saved_hours: number;
    };
    type_dist: {
        type: string;
        count: number;
        succeeded: number;
        success_rate: number | null;
    }[];
    trend: {
        date: string;
        count: number;
        succeeded: number;
    }[];
    ai_vs_manual: {
        week: string;
        ai: number;
        manual: number;
    }[];
    type_avg_duration: Record<string, number>;
    saved_breakdown: {
        key: string;
        label: string;
        unit: string;
        unit_minutes: number;
        count: number;
        minutes: number;
    }[];
    saved_rule: string;
}
// ── 执行汇总 ──
export interface ExecutionModuleStat {
    key: 'functional' | 'app';
    executions: number;
    exec_trend: number | null;
    passed: number;
    failed: number;
    pass_rate: number | null;
    cases: number;
    avg_duration_s: number | null;
}
export interface ExecutionReportData {
    days: number;
    cards: {
        executions: {
            value: number;
            trend: number | null;
        };
        pass_rate: {
            value: number | null;
            trend: number | null;
        };
        failed: {
            value: number;
            trend: number | null;
        };
        executed_cases: {
            value: number;
            total_cases: number;
            coverage: number | null;
        };
        today: {
            value: number;
            pass_rate: number | null;
        };
    };
    trend: {
        date: string;
        functional: number;
        app: number;
        total: number;
        pass_rate: number | null;
    }[];
    modules: ExecutionModuleStat[];
    result_dist: {
        passed: number;
        failed: number;
        skipped: number;
        running: number;
    };
    executor_rank: {
        user_id: number;
        name: string;
        count: number;
        passed: number;
        pass_rate: number | null;
    }[];
    top_failures: {
        module: string;
        case_id: number;
        name: string;
        fail_count: number;
        exec_count: number;
        fail_rate: number | null;
    }[];
}
export const reportCenterApi = {
    assets(projectId: number, days = 30) {
        return request.get<AssetsReportData>(`/projects/${projectId}/report/assets`, { params: { days } });
    },
    execution(projectId: number, days = 30) {
        return request.get<ExecutionReportData>(`/projects/${projectId}/report/execution`, { params: { days } });
    },
    quality(projectId: number, days = 30) {
        return request.get<QualityReportData>(`/projects/${projectId}/report/quality`, { params: { days } });
    },
    aiEfficiency(projectId: number, days = 30) {
        return request.get<AiReportData>(`/projects/${projectId}/report/ai-efficiency`, { params: { days } });
    },
};
/** AI 任务类型中文名映射 */
export const AI_TASK_TYPE_LABELS: Record<string, string> = {
    generate_case: '功能用例生成',
    understand_requirement: '需求理解',
    parse_document: '文档解析',
    demo: '演示任务'
};
export function aiTaskTypeLabel(t: string): string {
    return AI_TASK_TYPE_LABELS[t] || t;
}
