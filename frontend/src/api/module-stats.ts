/**
 * 列表页全量统计 API
 *
 * 对应后端 GET /projects/{id}/module-stats?module=xxx
 * 列表页顶部统计卡片的统一数据源（替代此前用当前分页数据假算）。
 */
import { request } from './request';
export interface FuncCasesStats {
    total: number;
    by_status: Record<string, number>;
    ai_generated: number;
}
export interface RequirementsStats {
    total: number;
    by_status: Record<string, number>;
    ai_generated: number;
}
export interface InterfacesStats {
    total: number;
    by_status: Record<string, number>;
    categories: number;
}
export interface ApiCasesStats {
    total: number;
    active: number;
    automated: number;
    flows: number;
    /** 业务流用例数（挂普通业务流） */
    flow_cases: number;
    /** 单接口用例数（挂单接口容器流） */
    interface_cases: number;
}
export interface WebScriptsStats {
    total: number;
    by_status: Record<string, number>;
}
export interface BugsStats {
    total: number;
    by_status: Record<string, number>;
}
export type ModuleStatsMap = {
    func_cases: FuncCasesStats;
    requirements: RequirementsStats;
    bugs: BugsStats;
};
export const moduleStatsApi = {
    get<M extends keyof ModuleStatsMap>(projectId: number, module: M) {
        return request.get<ModuleStatsMap[M]>(`/projects/${projectId}/module-stats`, { params: { module } });
    },
};
