/**
 * 权限管理模块 API
 *
 * AI 智能测试平台 - 权限管理模块
 * 对应需求文档：01-用户与权限管理模块.md
 * 对应 API 文档：01-用户与权限管理模块API.md
 */
import { request } from './request';
import type { ApiResponse } from './request';
import { ElMessage } from 'element-plus';
// ==================== 类型定义 ====================
/**
 * 系统角色编码（单层全局 RBAC）
 *
 * 与后端 init_db.SYSTEM_ROLE_DEFINITIONS 对齐：
 *   super_admin 超级管理员 / admin 系统管理员 / project_admin 项目管理员
 *   / tester 测试工程师 / developer 开发工程师 / user 普通用户(自助注册默认)
 * 注：project_* 是「项目成员角色」(见 MembersView)，不在此系统角色枚举内。
 */
export type RoleCode = 'super_admin' | 'admin' | 'project_admin' | 'tester' | 'developer' | 'user';
/**
 * 权限编码
 */
export type PermissionCode = 'user:view' // 查看用户
 | 'user:create' // 创建用户
 | 'user:edit' // 编辑用户
 | 'user:delete' // 删除用户
 | 'role:view' // 查看角色
 | 'role:create' // 创建角色
 | 'role:edit' // 编辑角色
 | 'role:delete' // 删除角色
 | 'permission:view' // 查看权限
 | 'permission:create' // 创建权限
 | 'permission:edit' // 编辑权限
 | 'permission:delete' // 删除权限
 | 'project:view' // 查看项目
 | 'project:create' // 创建项目
 | 'project:edit' // 编辑项目
 | 'project:delete' // 删除项目
 | 'project:manage_member' // 管理项目成员
 | 'test_case:view' // 查看功能测试
 | 'test_case:create' // 创建功能测试
 | 'test_case:edit' // 编辑功能测试
 | 'test_case:delete' // 删除功能测试
 | 'test_case:execute' // 执行功能测试
 | 'bug:view' // 查看 Bug
 | 'bug:create' // 创建 Bug
 | 'bug:edit' // 编辑 Bug
 | 'bug:delete' // 删除 Bug
 | 'bug:assign' // 分配 Bug
 | 'bug:resolve' // 解决 Bug
 | 'bug:close' // 关闭 Bug
 | 'report:view' // 查看测试报告
 | 'report:export' // 导出测试报告
 | 'report:delete' // 删除测试报告
 | 'system:config' // 系统配置
 | 'system:log' // 查看操作日志
// —— 新模块权限点 ——
 | 'scheduler:view' // 查看定时计划
 | 'scheduler:create' // 创建定时计划
 | 'scheduler:edit' // 编辑定时计划
 | 'scheduler:delete' // 删除定时计划
 | 'scheduler:execute' // 触发 / 启停定时计划
 | 'environment:view' // 查看测试环境
 | 'environment:create' // 创建测试环境
 | 'environment:edit' // 编辑测试环境
 | 'environment:delete' // 删除测试环境
 | 'knowledge:view' // 查看知识库
 | 'knowledge:manage' // 管理知识库
 | 'chat:use' // 使用 AI 助手
 | 'ai_task:view' // 查看 AI 任务
 | 'ai_task:manage' // 管理 AI 任务
 | 'app_device:view' // 查看设备/执行机
 | 'app_device:control' // 占用与控制设备
 | 'app_device:manage' // 执行机注册/轮转/强制释放
 | 'app_test:view' // 查看 App 用例/执行
 | 'app_test:create' // 创建 App 用例
 | 'app_test:edit' // 编辑 App 用例
 | 'app_test:delete' // 删除 App 用例
 | 'app_test:execute'
/**
 * 角色基本信息
 */
; // 回放 App 用例
/**
 * 角色基本信息
 */
export interface Role {
    id: number;
    code: RoleCode;
    name: string;
    description?: string;
    is_system: boolean;
    permissions: PermissionCode[];
    created_at: string;
    updated_at: string;
}
/**
 * 权限基本信息
 */
export interface Permission {
    id: number;
    code: PermissionCode;
    name: string;
    module: string;
    description?: string;
    created_at: string;
    updated_at: string;
}
/**
 * 创建角色请求
 */
export interface CreateRoleRequest {
    name: string;
    code?: RoleCode;
    description?: string;
    permissions: PermissionCode[];
}
/**
 * 更新角色请求
 */
export interface UpdateRoleRequest {
    name?: string;
    description?: string;
    permissions?: PermissionCode[];
}
/**
 * 获取角色列表查询参数
 */
export interface RoleListQuery {
    keyword?: string;
    page?: number;
    page_size?: number;
}
/**
 * 角色列表响应
 */
export interface RoleListResponse {
    total: number;
    page: number;
    page_size: number;
    items: Role[];
}
/**
 * 获取权限列表查询参数
 */
export interface PermissionListQuery {
    keyword?: string;
    module?: string;
    page?: number;
    page_size?: number;
}
/**
 * 权限列表响应
 */
export interface PermissionListResponse {
    data: PermissionModule[];
}
/**
 * 权限模块
 */
export interface PermissionModule {
    module: string;
    permissions: PermissionListItem[];
}
/**
 * 权限列表项（简化版）
 */
export interface PermissionListItem {
    code: string;
    name: string;
}
/**
 * 获取所有权限响应
 */
export interface AllPermissionsResponse {
    data: PermissionModule[];
}
// ==================== API 请求 ====================
/**
 * 权限管理 API 类
 */
class PermissionApi {
    /**
     * 获取角色列表
     */
    async getRoleList(params?: RoleListQuery): Promise<ApiResponse<RoleListResponse>> {
        try {
            return await request.get<RoleListResponse>('/roles', { params });
        }
        catch (error) {
            console.error('获取角色列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取角色详情
     */
    async getRoleDetail(roleId: number): Promise<ApiResponse<Role>> {
        try {
            return await request.get<Role>(`/roles/${roleId}`);
        }
        catch (error) {
            console.error('获取角色详情失败:', error);
            throw error;
        }
    }
    /**
     * 创建角色
     */
    async createRole(data: CreateRoleRequest): Promise<ApiResponse<Role>> {
        try {
            return await request.post<Role>('/roles', data);
        }
        catch (error) {
            console.error('创建角色失败:', error);
            throw error;
        }
    }
    /**
     * 更新角色
     */
    async updateRole(roleId: number, data: UpdateRoleRequest): Promise<ApiResponse<Role>> {
        try {
            return await request.put<Role>(`/roles/${roleId}`, data);
        }
        catch (error) {
            console.error('更新角色失败:', error);
            throw error;
        }
    }
    /**
     * 删除角色
     */
    async deleteRole(roleId: number): Promise<ApiResponse<null>> {
        try {
            return await request.delete<null>(`/roles/${roleId}`);
        }
        catch (error) {
            console.error('删除角色失败:', error);
            throw error;
        }
    }
    /**
     * 获取权限列表
     */
    async getPermissionList(params?: PermissionListQuery): Promise<ApiResponse<PermissionListResponse>> {
        try {
            return await request.get<PermissionListResponse>('/roles/permissions', { params });
        }
        catch (error) {
            console.error('获取权限列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取所有权限（不分页）
     */
    async getAllPermissions(): Promise<ApiResponse<AllPermissionsResponse>> {
        try {
            return await request.get<AllPermissionsResponse>('/roles/permissions');
        }
        catch (error) {
            console.error('获取所有权限失败:', error);
            throw error;
        }
    }
}
// ==================== 导出 ====================
export const permissionApi = new PermissionApi();
