/**
 * 项目管理模块 API
 *
 * AI 智能测试平台 - 项目管理模块
 * 对应需求文档：02-项目管理模块.md
 * 对应 API 文档：02-项目管理模块API.md
 */
import service from './request';
import type { ApiResponse } from './request';
// ==================== 类型定义 ====================
/**
 * 项目状态
 */
export type ProjectStatus = 'active' | 'archived' | 'deleted';
/**
 * 项目角色
 */
export type ProjectRole = 'owner' | 'test_lead' | 'tester' | 'viewer';
/**
 * Bug 严重程度
 */
export type BugSeverity = 'critical' | 'high' | 'medium' | 'low';
/**
 * 测试用例优先级
 */
export type TestCasePriority = 'critical' | 'high' | 'medium' | 'low';
/**
 * 项目基本信息
 */
export interface Project {
    id: number;
    name: string;
    code: string;
    description?: string;
    avatar?: string;
    status: ProjectStatus;
    is_public: boolean;
    start_date?: string;
    end_date?: string;
    member_count: number;
    module_count: number;
    case_count: number;
    bug_count: number;
    created_by: {
        id: number;
        username: string;
        real_name: string;
    };
    owner?: {
        id: number;
        username: string;
        real_name: string;
        avatar?: string;
    };
    created_at: string;
    updated_at: string;
}
/**
 * 项目详情
 */
export interface ProjectDetail extends Project {
    owner: {
        id: number;
        username: string;
        real_name: string;
        avatar?: string;
    };
    statistics: ProjectStatistics;
    config: ProjectConfig;
}
/**
 * 项目统计
 */
export interface ProjectStatistics {
    module_count: number;
    case_count: {
        total: number;
        functional: number;
    };
    bug_count: number;
    member_count: number;
}
/**
 * 单项指标（数值 + 环比）
 */
export interface OverviewMetric {
    /** 当前值 */
    value: number;
    /** 较上周/上月变化百分比（正数=上升，负数=下降；0=无变化） */
    trend: number;
    /** 比较窗口：week | month */
    compare_window: 'week' | 'month';
}
/**
 * 工作台项目总览（跨项目聚合）
 *
 * 用于 /workspace/projects 顶部 5 个统计卡
 */
export interface ProjectsOverview {
    /** 项目总数（仅活跃项目） */
    project_count: OverviewMetric;
    /** 团队成员总数（按 user_id 去重） */
    member_count: OverviewMetric;
    /** 模块总数 */
    module_count: OverviewMetric;
    /** 用例总数 */
    case_count: OverviewMetric;
    /** 缺陷总数（未关闭） */
    bug_count: OverviewMetric;
    /** 数据快照时间 */
    generated_at: string;
}
/**
 * 项目概览仪表盘聚合统计
 *
 * 对应 GET /projects/{id}/dashboard
 */
export interface DashboardRecentExecution {
    module: 'app';
    kind: 'suite' | 'task' | 'run';
    execution_id: number;
    ref_id: number;
    name: string;
    status: string;
    total: number;
    passed: number;
    failed: number;
    started_at: string | null;
}
export interface ProjectDashboardData {
    days: number;
    stat_cards: {
        case_total: {
            value: number;
            by_type: {
                functional: number;
                app: number;
            };
            ai_generated: number;
        };
        executions: {
            value: number;
            trend: number | null;
        };
        pass_rate: {
            value: number | null;
            trend: number | null;
        };
        open_bugs: {
            value: number;
            by_severity: Record<string, number>;
        };
        ai_tasks: {
            value: number;
            success_rate: number | null;
        };
        new_cases: {
            value: number;
            trend: number | null;
        };
    };
    today: {
        executions: number;
        passed: number;
        pass_rate: number | null;
    };
    execution_trend: {
        date: string;
        passed: number;
        failed: number;
    }[];
    recent_executions: DashboardRecentExecution[];
    bug_status_dist: Record<string, number>;
    kb: {
        status: string;
        documents: number;
        chunks: number;
        nodes: number;
        edges: number;
        last_built_at: string | null;
    };
}
/**
 * 项目配置
 */
export interface ProjectConfig {
    default_env_id?: number;
    bug_auto_assign: boolean;
    bug_severity_default: BugSeverity;
    test_case_priority_default: TestCasePriority;
    allow_public_report: boolean;
    retention_days: number;
}
/**
 * 创建项目请求
 */
export interface CreateProjectRequest {
    name: string;
    code: string;
    description?: string;
    avatar?: string;
    start_date?: string;
    end_date?: string;
    is_public?: boolean;
}
/**
 * 更新项目请求
 */
export interface UpdateProjectRequest {
    name?: string;
    description?: string;
    avatar?: string;
    start_date?: string;
    end_date?: string;
    is_public?: boolean;
}
/**
 * 项目列表查询参数
 */
export interface ProjectListQuery {
    page?: number;
    page_size?: number;
    keyword?: string;
    status?: ProjectStatus;
    is_public?: boolean;
    member_id?: number;
    owner_id?: number;
    start_date?: string;
    end_date?: string;
    order_by?: 'created_at' | 'updated_at' | 'name';
    order?: 'asc' | 'desc';
}
/**
 * 项目列表响应
 */
export interface ProjectListResponse {
    total: number;
    page: number;
    page_size: number;
    items: Project[];
}
// ==================== 项目模块类型定义 ====================
/**
 * 项目模块
 */
export interface ProjectModule {
    id: number;
    name: string;
    parent_id?: number | null;
    sort_order: number;
    description?: string;
    path: string;
    case_count: number;
    children?: ProjectModule[];
    created_at?: string;
    updated_at?: string;
    children_count?: number;
}
/**
 * 创建模块请求
 */
export interface CreateModuleRequest {
    name: string;
    parent_id?: number | null;
    sort_order?: number;
    description?: string;
}
/**
 * 更新模块请求
 */
export interface UpdateModuleRequest {
    name?: string;
    sort_order?: number;
    description?: string;
}
/**
 * 移动模块请求
 */
export interface MoveModuleRequest {
    parent_id?: number | null;
    sort_order?: number;
}
// ==================== 项目成员类型定义 ====================
/**
 * 项目中的用户信息
 */
export interface UserInProject {
    id: number;
    username: string;
    real_name: string;
    email?: string;
    avatar?: string;
    /** 用户的系统角色（决定实际操作权限；项目角色仅作组织标签） */
    roles?: {
        code: string;
        name: string;
    }[];
}
/**
 * 项目成员
 */
export interface ProjectMember {
    id: number;
    user: UserInProject;
    project_role: ProjectRole;
    joined_at: string;
    last_active_at?: string;
}
/**
 * 添加成员请求
 */
export interface AddMemberRequest {
    user_ids: number[];
    project_role: ProjectRole;
}
/**
 * 修改成员角色请求
 */
export interface UpdateMemberRoleRequest {
    project_role: ProjectRole;
}
/**
 * 转让项目请求
 */
export interface TransferProjectRequest {
    to_user_id: number;
}
/**
 * 成员权限响应
 */
export interface MemberPermissionsResponse {
    project_role: ProjectRole | null;
    permissions: string[];
    can_edit_project: boolean;
    can_manage_members: boolean;
    can_delete_project: boolean;
}
// ==================== API 请求 ====================
/**
 * 项目管理 API 类
 */
class ProjectApi {
    /**
     * 获取项目列表
     */
    async getProjectList(params?: ProjectListQuery): Promise<ApiResponse<ProjectListResponse>> {
        try {
            return await service.get(`/projects/`, { params });
        }
        catch (error) {
            console.error('获取项目列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取项目详情
     */
    async getProjectDetail(projectId: number): Promise<ApiResponse<ProjectDetail>> {
        try {
            return await service.get(`/projects/${projectId}`);
        }
        catch (error) {
            console.error('获取项目详情失败:', error);
            throw error;
        }
    }
    /**
     * 创建项目
     */
    async createProject(data: CreateProjectRequest): Promise<ApiResponse<{
        id: number;
        name: string;
        code: string;
    }>> {
        try {
            return await service.post(`/projects`, data);
        }
        catch (error) {
            console.error('创建项目失败:', error);
            throw error;
        }
    }
    /**
     * 更新项目信息
     */
    async updateProject(projectId: number, data: UpdateProjectRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.put(`/projects/${projectId}`, data);
        }
        catch (error) {
            console.error('更新项目失败:', error);
            throw error;
        }
    }
    /**
     * 归档项目
     */
    async archiveProject(projectId: number): Promise<ApiResponse<{
        id: number;
        status: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/archive`);
        }
        catch (error) {
            console.error('归档项目失败:', error);
            throw error;
        }
    }
    /**
     * 恢复项目
     */
    async restoreProject(projectId: number): Promise<ApiResponse<{
        id: number;
        status: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/restore`);
        }
        catch (error) {
            console.error('恢复项目失败:', error);
            throw error;
        }
    }
    /**
     * 删除项目
     */
    async deleteProject(projectId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/projects/${projectId}`);
        }
        catch (error) {
            console.error('删除项目失败:', error);
            throw error;
        }
    }
    /**
     * 获取项目统计
     */
    async getProjectStatistics(projectId: number, params?: {
        start_date?: string;
        end_date?: string;
    }): Promise<ApiResponse<any>> {
        try {
            return await service.get(`/projects/${projectId}/statistics`, { params });
        }
        catch (error) {
            console.error('获取项目统计失败:', error);
            throw error;
        }
    }
    /**
     * 获取工作台项目总览（跨项目聚合）
     *
     * 一次性返回「我的项目」页面顶部 5 张统计卡的真实数据与环比趋势。
     * ⚠️ 注意：路径故意不使用 `/projects/overview`，
     *    因为后端有 `GET /projects/{project_id}` 路由要求 int，
     *    走 `/projects/overview` 会被解析为 project_id=overview 触发 422。
     *    使用 `/projects-overview` 独立前缀绝对不冲突。
     *
     * 后端约定：GET /projects-overview
     */
    async getProjectsOverview(params?: {
        compare_window?: 'week' | 'month';
    }): Promise<ApiResponse<ProjectsOverview>> {
        try {
            return await service.get(`/projects-overview`, { params });
        }
        catch (error) {
            console.error('获取项目总览失败:', error);
            throw error;
        }
    }
    /**
     * 更新项目配置
     */
    async updateProjectConfig(projectId: number, config: Partial<ProjectConfig>): Promise<ApiResponse<ProjectConfig>> {
        try {
            return await service.put(`/projects/${projectId}/config`, config);
        }
        catch (error) {
            console.error('更新项目配置失败:', error);
            throw error;
        }
    }
    // ==================== 项目模块管理 ====================
    // 注意：后端使用 /project-modules 路径，project_id 作为查询参数传递
    /**
     * 获取模块树
     * GET /project-modules/tree?project_id={projectId}
     */
    async getModuleTree(projectId: number): Promise<ApiResponse<ProjectModule[]>> {
        try {
            return await service.get(`/project-modules/tree`, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('获取模块树失败:', error);
            throw error;
        }
    }
    /**
     * 获取模块详情
     * GET /project-modules/{moduleId}?project_id={projectId}
     */
    async getModuleDetail(projectId: number, moduleId: number): Promise<ApiResponse<ProjectModule>> {
        try {
            return await service.get(`/project-modules/${moduleId}`, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('获取模块详情失败:', error);
            throw error;
        }
    }
    /**
     * 创建模块
     * POST /project-modules?project_id={projectId}
     */
    async createModule(projectId: number, data: CreateModuleRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.post(`/project-modules`, data, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('创建模块失败:', error);
            throw error;
        }
    }
    /**
     * 更新模块
     * PUT /project-modules/{moduleId}?project_id={projectId}
     */
    async updateModule(projectId: number, moduleId: number, data: UpdateModuleRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.put(`/project-modules/${moduleId}`, data, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('更新模块失败:', error);
            throw error;
        }
    }
    /**
     * 移动模块
     * POST /project-modules/{moduleId}/move?project_id={projectId}
     */
    async moveModule(projectId: number, moduleId: number, data: MoveModuleRequest): Promise<ApiResponse<{
        id: number;
        parent_id?: number | null;
        sort_order?: number;
    }>> {
        try {
            return await service.post(`/project-modules/${moduleId}/move`, data, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('移动模块失败:', error);
            throw error;
        }
    }
    /**
     * 删除模块
     * DELETE /project-modules/{moduleId}?project_id={projectId}
     */
    async deleteModule(projectId: number, moduleId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/project-modules/${moduleId}`, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('删除模块失败:', error);
            throw error;
        }
    }
    // ==================== 项目成员管理 ====================
    // 注意：后端使用 /project-members 路径，project_id 作为查询参数传递
    /**
     * 获取项目成员列表
     * GET /project-members?project_id={projectId}
     */
    async getProjectMembers(projectId: number, params?: {
        role?: ProjectRole | null;
        keyword?: string | null;
    }): Promise<ApiResponse<ProjectMember[]>> {
        try {
            return await service.get(`/project-members`, { params: { project_id: projectId, ...params } });
        }
        catch (error) {
            console.error('获取项目成员列表失败:', error);
            throw error;
        }
    }
    /**
     * 添加项目成员
     * POST /project-members?project_id={projectId}
     */
    async addProjectMembers(projectId: number, data: AddMemberRequest): Promise<ApiResponse<{
        added_count: number;
        members: Array<{
            id: number;
            user_id: number;
            project_role: ProjectRole;
        }>;
    }>> {
        try {
            return await service.post(`/project-members`, data, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('添加项目成员失败:', error);
            throw error;
        }
    }
    /**
     * 修改成员角色
     * PUT /project-members/{memberId}/role?project_id={projectId}
     */
    async updateMemberRole(projectId: number, memberId: number, data: UpdateMemberRoleRequest): Promise<ApiResponse<{
        id: number;
        project_role: ProjectRole;
    }>> {
        try {
            return await service.put(`/project-members/${memberId}/role`, data, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('修改成员角色失败:', error);
            throw error;
        }
    }
    /**
     * 移除项目成员
     * DELETE /project-members/{memberId}?project_id={projectId}
     */
    async removeProjectMember(projectId: number, memberId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/project-members/${memberId}`, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('移除项目成员失败:', error);
            throw error;
        }
    }
    /**
     * 退出项目
     * POST /project-members/quit?project_id={projectId}
     */
    async quitProject(projectId: number): Promise<ApiResponse<null>> {
        try {
            return await service.post(`/project-members/quit`, null, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('退出项目失败:', error);
            throw error;
        }
    }
    /**
     * 获取用户在项目中的权限
     * GET /project-members/permissions?project_id={projectId}
     */
    async getMemberPermissions(projectId: number): Promise<ApiResponse<MemberPermissionsResponse>> {
        try {
            return await service.get(`/project-members/permissions`, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('获取成员权限失败:', error);
            throw error;
        }
    }
    /**
     * 转让项目
     * POST /project-members/transfer?project_id={projectId}
     */
    async transferProject(projectId: number, data: TransferProjectRequest): Promise<ApiResponse<{
        from_user_id: number;
        to_user_id: number;
        from_user_new_role: string;
        to_user_new_role: string;
    }>> {
        try {
            return await service.post(`/project-members/transfer`, data, { params: { project_id: projectId } });
        }
        catch (error) {
            console.error('转让项目失败:', error);
            throw error;
        }
    }
    /**
     * 项目概览仪表盘聚合统计
     * GET /projects/{projectId}/dashboard?days=7|30
     */
    async getProjectDashboard(projectId: number, days: number = 7): Promise<ApiResponse<ProjectDashboardData>> {
        try {
            return await service.get(`/projects/${projectId}/dashboard`, {
                params: { days },
            });
        }
        catch (error) {
            console.error('获取项目概览统计失败:', error);
            throw error;
        }
    }
}
// ==================== 导出 ====================
export const projectApi = new ProjectApi();
