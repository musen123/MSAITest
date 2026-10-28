/**
 * 定时任务调度 API
 *
 * 对应后端 /projects/{id}/scheduled-jobs：
 * 数据库即调度配置，beat 每 30s 巡检派发，增删改即时生效。
 */
import { request } from './request';
export type ScheduledJobType = 'app_suite';
export type ScheduleType = 'cron' | 'interval';
export type JobLastStatus = 'dispatched' | 'skipped_overlap' | 'failed';
export interface ScheduledJob {
    id: number;
    project_id: number;
    name: string;
    description?: string | null;
    job_type: ScheduledJobType;
    target_id: number;
    target_name?: string | null;
    params?: {
        environment_id?: number | null;
        run_mode?: string | null;
        device_udid?: string | null;
    } | null;
    schedule_type: ScheduleType;
    cron_expr?: string | null;
    interval_seconds?: number | null;
    enabled: boolean;
    allow_overlap: boolean;
    next_run_at?: string | null;
    last_run_at?: string | null;
    last_status?: JobLastStatus | null;
    last_task_id?: number | null;
    total_runs: number;
    created_by: number;
    created_at: string;
    updated_at: string;
}
export interface ScheduledJobPayload {
    name: string;
    description?: string;
    job_type: ScheduledJobType;
    target_id: number;
    params?: {
        environment_id?: number | null;
        run_mode?: string | null;
        device_udid?: string | null;
    };
    schedule_type: ScheduleType;
    cron_expr?: string | null;
    interval_seconds?: number | null;
    enabled?: boolean;
    allow_overlap?: boolean;
}
export interface ScheduledJobRun {
    id: number;
    job_id: number;
    ai_task_id?: number | null;
    fired_at: string;
    status: JobLastStatus;
    note?: string | null;
    task_status?: string | null;
}
export const scheduledJobApi = {
    list(projectId: number, params: {
        enabled?: boolean;
        job_type?: string;
        keyword?: string;
        page?: number;
        page_size?: number;
    } = {}) {
        return request.get<{
            total: number;
            items: ScheduledJob[];
        }>(`/projects/${projectId}/scheduled-jobs`, { params });
    },
    create(projectId: number, payload: ScheduledJobPayload) {
        return request.post<ScheduledJob>(`/projects/${projectId}/scheduled-jobs`, payload);
    },
    update(projectId: number, jobId: number, payload: Partial<ScheduledJobPayload>) {
        return request.put<ScheduledJob>(`/projects/${projectId}/scheduled-jobs/${jobId}`, payload);
    },
    toggle(projectId: number, jobId: number) {
        return request.post<ScheduledJob>(`/projects/${projectId}/scheduled-jobs/${jobId}/toggle`);
    },
    runNow(projectId: number, jobId: number) {
        return request.post<{
            status: string;
            ai_task_id?: number;
        }>(`/projects/${projectId}/scheduled-jobs/${jobId}/run-now`);
    },
    listRuns(projectId: number, jobId: number, params: {
        page?: number;
        page_size?: number;
    } = {}) {
        return request.get<{
            total: number;
            items: ScheduledJobRun[];
        }>(`/projects/${projectId}/scheduled-jobs/${jobId}/runs`, { params });
    },
    remove(projectId: number, jobId: number) {
        return request.delete(`/projects/${projectId}/scheduled-jobs/${jobId}`);
    },
    validateCron(projectId: number, cronExpr: string) {
        return request.post<{
            valid: boolean;
            next_runs: string[];
        }>(`/projects/${projectId}/scheduled-jobs/validate-cron`, { cron_expr: cronExpr });
    },
};
/** job_type 展示元数据 */
export const JOB_TYPE_META: Record<ScheduledJobType, {
    label: string;
    color: string;
    icon: string;
}> = {
    app_suite: {
        label: 'App 套件',
        color: 'primary',
        icon: 'i-app-mobile',
    }
};
/** 常用 cron 预设 */
export const CRON_PRESETS = [
    { label: '每天 02:00', value: '0 2 * * *' },
    { label: '每天 09:00', value: '0 9 * * *' },
    { label: '工作日 09:00', value: '0 9 * * 1-5' },
    { label: '每周一 09:00', value: '0 9 * * 1' },
    { label: '每小时整点', value: '0 * * * *' },
    { label: '每 30 分钟', value: '*/30 * * * *' },
];
