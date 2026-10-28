/**
 * 测试环境管理模块 API
 *
 * AI 智能测试平台 - 测试环境管理模块
 * 对应需求文档：03-测试环境管理模块.md
 * 对应 API 文档：03-测试环境管理模块API.md
 */
import service from './request';
import type { ApiResponse } from './request';
// ==================== 类型定义 ====================
/**
 * 环境状态
 */
export type EnvironmentStatus = 'connected' | 'disconnected' | 'unknown';
/**
 * 变量类型
 */
export type VariableType = 'text' | 'password' | 'json' | 'dynamic';
/**
 * 数据库类型
 */
export type DatabaseType = 'MySQL' | 'PostgreSQL' | 'Oracle' | 'SQLServer' | 'MongoDB' | 'Redis';
/**
 * 连接状态
 */
export type ConnectionStatus = 'connected' | 'disconnected' | 'unknown';
/**
 * 编程语言
 */
export type ScriptLanguage = 'python' | 'javascript';
// ==================== 环境管理类型定义 ====================
/**
 * 脚本配置
 */
export interface ScriptConfig {
    language: ScriptLanguage;
    code: string;
    is_active: boolean;
}
/**
 * 环境类型：1=功能测试 2=App测试
 */
export type EnvType = 1 | 2;
/**
 * 测试环境
 */
export interface Environment {
    id: number;
    project_id: number;
    name: string;
    base_url: string;
    description?: string;
    env_type: EnvType;
    is_default: boolean;
    is_global: boolean;
    proxy_url?: string;
    timeout: number;
    verify_ssl: boolean;
    allow_redirects: boolean;
    keep_cookies: boolean;
    retry_times: number;
    pre_script?: ScriptConfig;
    post_script?: ScriptConfig;
    variable_count: number;
    created_at: string;
    updated_at: string;
}
/**
 * 创建环境请求
 */
export interface CreateEnvironmentRequest {
    name: string;
    base_url: string;
    description?: string;
    env_type?: EnvType;
    is_default?: boolean;
    is_global?: boolean;
    proxy_url?: string;
    timeout?: number;
    verify_ssl?: boolean;
    allow_redirects?: boolean;
    keep_cookies?: boolean;
    retry_times?: number;
    pre_script?: ScriptConfig;
    post_script?: ScriptConfig;
}
/**
 * 更新环境请求
 */
export interface UpdateEnvironmentRequest {
    name?: string;
    base_url?: string;
    description?: string;
    env_type?: EnvType;
    is_default?: boolean;
    is_global?: boolean;
    proxy_url?: string;
    timeout?: number;
    verify_ssl?: boolean;
    allow_redirects?: boolean;
    keep_cookies?: boolean;
    retry_times?: number;
    pre_script?: ScriptConfig;
    post_script?: ScriptConfig;
}
/**
 * 克隆环境请求
 */
export interface CloneEnvironmentRequest {
    name: string;
}
/**
 * 克隆环境响应
 */
export interface CloneEnvironmentResponse {
    id: number;
    name: string;
    source_env_id: number;
}
/**
 * 环境列表查询参数
 */
export interface EnvironmentListQuery {
    is_global?: boolean;
    env_type?: EnvType;
    keyword?: string;
}
// ==================== 环境变量类型定义 ====================
/**
 * 环境变量
 */
export interface EnvironmentVariable {
    id: number;
    env_id: number;
    name: string;
    value: string;
    type: VariableType;
    description?: string;
    is_active: boolean;
    sort_order: number;
    created_at: string;
    updated_at: string;
}
/**
 * 创建变量请求
 */
export interface CreateVariableRequest {
    name: string;
    value: string;
    type: VariableType;
    description?: string;
    is_active?: boolean;
    sort_order?: number;
}
/**
 * 更新变量请求
 */
export interface UpdateVariableRequest {
    value?: string;
    type?: VariableType;
    description?: string;
    is_active?: boolean;
    sort_order?: number;
}
/**
 * 批量更新变量请求
 */
export interface BatchUpdateVariablesRequest {
    variables: Array<{
        id: number;
        value?: string;
        is_active?: boolean;
    }>;
}
/**
 * 批量删除变量请求
 */
export interface BatchDeleteVariablesRequest {
    ids: number[];
}
/**
 * 导出变量响应
 */
export interface ExportVariablesResponse {
    filename: string;
    content: {
        environment: string;
        exported_at: string;
        variables: EnvironmentVariable[];
    };
}
/**
 * 导入变量请求
 */
export interface ImportVariablesRequest {
    content: {
        environment?: string;
        variables?: EnvironmentVariable[];
    };
    mode: 'merge' | 'replace';
}
/**
 * 导入变量响应
 */
export interface ImportVariablesResponse {
    imported_count: number;
    skipped_count: number;
    failed_count: number;
}
// ==================== 数据库连接类型定义 ====================
/**
 * 数据库连接
 */
export interface DatabaseConnection {
    id: number;
    project_id: number;
    name: string;
    db_type: DatabaseType;
    host: string;
    port: number;
    database: string;
    username: string;
    password?: string;
    charset?: string;
    connection_params?: Record<string, any>;
    /** 是否允许写操作（造数/清理等破坏性 SQL），默认关闭 */
    allow_write?: boolean;
    connection_status: ConnectionStatus;
    last_test_time?: string;
    last_test_result?: string;
    created_at: string;
    updated_at: string;
}
/**
 * 创建数据库连接请求
 */
export interface CreateDatabaseRequest {
    name: string;
    db_type: DatabaseType;
    host: string;
    port: number;
    database: string;
    username: string;
    password: string;
    charset?: string;
    connection_params?: Record<string, any>;
    /** 是否允许写操作，默认关闭 */
    allow_write?: boolean;
}
/**
 * 更新数据库连接请求
 */
export interface UpdateDatabaseRequest {
    name?: string;
    host?: string;
    port?: number;
    database?: string;
    username?: string;
    password?: string;
    charset?: string;
    connection_params?: Record<string, any>;
    /** 是否允许写操作，默认关闭 */
    allow_write?: boolean;
}
/**
 * 数据库列表查询参数
 */
export interface DatabaseListQuery {
    db_type?: DatabaseType;
    keyword?: string;
}
/**
 * 测试数据库连接请求
 */
export interface TestDatabaseRequest {
}
/**
 * 测试数据库连接响应
 */
export interface TestDatabaseResponse {
    status: ConnectionStatus;
    response_time?: number;
    message: string;
    error?: string;
    tested_at: string;
}
// ==================== 全局函数类型定义 ====================
/**
 * 函数参数
 */
export interface FunctionParam {
    name: string;
    type: string;
    description: string;
    required: boolean;
    default?: any;
}
/**
 * 全局函数
 */
export interface GlobalFunction {
    id?: number;
    project_id?: number;
    name: string;
    display_name: string;
    language: ScriptLanguage;
    description?: string;
    code?: string;
    params?: FunctionParam[];
    return_type?: string;
    example?: string;
    is_built_in: boolean;
    is_active: boolean;
    created_at?: string;
    updated_at?: string;
}
/**
 * 创建函数请求
 */
export interface CreateFunctionRequest {
    name: string;
    display_name: string;
    language: ScriptLanguage;
    description?: string;
    code: string;
    params?: FunctionParam[];
    return_type?: string;
    example?: string;
}
/**
 * 更新函数请求
 */
export interface UpdateFunctionRequest {
    display_name?: string;
    description?: string;
    code?: string;
    params?: FunctionParam[];
    return_type?: string;
    example?: string;
}
/**
 * 测试函数请求
 */
export interface TestFunctionRequest {
    params?: Record<string, any>;
}
/**
 * 测试函数响应
 */
export interface TestFunctionResponse {
    success: boolean;
    result?: any;
    error?: string;
    execution_time?: number;
}
/**
 * 启用/禁用函数请求
 */
export interface ToggleFunctionStatusRequest {
    is_active: boolean;
}
/**
 * 函数列表查询参数
 */
export interface FunctionListQuery {
    type?: 'built-in' | 'custom';
    language?: ScriptLanguage;
    keyword?: string;
}
/**
 * 函数列表响应
 */
export interface FunctionListResponse {
    built_in: GlobalFunction[];
    custom: GlobalFunction[];
}
// ==================== API 请求 ====================
/**
 * 测试环境管理 API 类
 */
class EnvironmentApi {
    // ==================== 环境管理 ====================
    /**
     * 获取环境列表
     * GET /projects/{projectId}/environments
     */
    async getEnvironmentList(projectId: number, params?: EnvironmentListQuery): Promise<ApiResponse<Environment[]>> {
        try {
            return await service.get(`/projects/${projectId}/environments`, { params });
        }
        catch (error) {
            console.error('获取环境列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取环境详情
     * GET /projects/{projectId}/environments/{envId}
     */
    async getEnvironmentDetail(projectId: number, envId: number): Promise<ApiResponse<Environment>> {
        try {
            return await service.get(`/projects/${projectId}/environments/${envId}`);
        }
        catch (error) {
            console.error('获取环境详情失败:', error);
            throw error;
        }
    }
    /**
     * 创建环境
     * POST /projects/{projectId}/environments
     */
    async createEnvironment(projectId: number, data: CreateEnvironmentRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/environments`, data);
        }
        catch (error) {
            console.error('创建环境失败:', error);
            throw error;
        }
    }
    /**
     * 更新环境
     * PUT /projects/{projectId}/environments/{envId}
     */
    async updateEnvironment(projectId: number, envId: number, data: UpdateEnvironmentRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.put(`/projects/${projectId}/environments/${envId}`, data);
        }
        catch (error) {
            console.error('更新环境失败:', error);
            throw error;
        }
    }
    /**
     * 测试被测系统 Prometheus 连接(SSRF 防护 + GET /api/v1/query?query=up)
     * POST /projects/{projectId}/environments/test-prometheus
     * 项目级:直接测表单里的 url/auth(新建/编辑保存前都可验证)
     */
    async testSutPrometheus(projectId: number, body: {
        url?: string;
        auth?: string;
    }): Promise<ApiResponse<{
        ok: boolean;
        message: string;
        series?: number;
    }>> {
        return await service.post(`/projects/${projectId}/environments/test-prometheus`, body);
    }
    /**
     * 设置默认环境
     * POST /projects/{projectId}/environments/{envId}/set-default
     */
    async setDefaultEnvironment(projectId: number, envId: number): Promise<ApiResponse<{
        id: number;
        is_default: boolean;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/environments/${envId}/set-default`);
        }
        catch (error) {
            console.error('设置默认环境失败:', error);
            throw error;
        }
    }
    /**
     * 克隆环境
     * POST /projects/{projectId}/environments/{envId}/clone
     */
    async cloneEnvironment(projectId: number, envId: number, data: CloneEnvironmentRequest): Promise<ApiResponse<CloneEnvironmentResponse>> {
        try {
            return await service.post(`/projects/${projectId}/environments/${envId}/clone`, data);
        }
        catch (error) {
            console.error('克隆环境失败:', error);
            throw error;
        }
    }
    /**
     * 删除环境
     * DELETE /projects/{projectId}/environments/{envId}
     */
    async deleteEnvironment(projectId: number, envId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/projects/${projectId}/environments/${envId}`);
        }
        catch (error) {
            console.error('删除环境失败:', error);
            throw error;
        }
    }
    async debugScript(projectId: number, envId: number, scriptType: 'pre' | 'post'): Promise<ApiResponse<{
        success: boolean;
        output: string;
        env_data?: Record<string, any>;
        error?: string;
        traceback?: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/environments/${envId}/debug-script`, null, { params: { script_type: scriptType } });
        }
        catch (error) {
            console.error('调试脚本失败:', error);
            throw error;
        }
    }
    // ==================== 环境变量管理 ====================
    /**
     * 获取环境变量列表
     * GET /projects/{projectId}/environments/{envId}/variables
     */
    async getVariableList(projectId: number, envId: number, params?: {
        keyword?: string;
    }): Promise<ApiResponse<EnvironmentVariable[]>> {
        try {
            return await service.get(`/projects/${projectId}/environments/${envId}/variables`, { params });
        }
        catch (error) {
            console.error('获取环境变量列表失败:', error);
            throw error;
        }
    }
    /**
     * 创建变量
     * POST /projects/{projectId}/environments/{envId}/variables
     */
    async createVariable(projectId: number, envId: number, data: CreateVariableRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/environments/${envId}/variables`, data);
        }
        catch (error) {
            console.error('创建变量失败:', error);
            throw error;
        }
    }
    /**
     * 更新变量
     * PUT /projects/{projectId}/environments/{envId}/variables/{varId}
     */
    async updateVariable(projectId: number, envId: number, varId: number, data: UpdateVariableRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.put(`/projects/${projectId}/environments/${envId}/variables/${varId}`, data);
        }
        catch (error) {
            console.error('更新变量失败:', error);
            throw error;
        }
    }
    /**
     * 批量更新变量
     * PUT /projects/{projectId}/environments/{envId}/variables/batch
     */
    async batchUpdateVariables(projectId: number, envId: number, data: BatchUpdateVariablesRequest): Promise<ApiResponse<{
        updated_count: number;
    }>> {
        try {
            return await service.put(`/projects/${projectId}/environments/${envId}/variables/batch`, data);
        }
        catch (error) {
            console.error('批量更新变量失败:', error);
            throw error;
        }
    }
    /**
     * 删除变量
     * DELETE /projects/{projectId}/environments/{envId}/variables/{varId}
     */
    async deleteVariable(projectId: number, envId: number, varId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/projects/${projectId}/environments/${envId}/variables/${varId}`);
        }
        catch (error) {
            console.error('删除变量失败:', error);
            throw error;
        }
    }
    /**
     * 批量删除变量
     * DELETE /projects/{projectId}/environments/{envId}/variables/batch
     */
    async batchDeleteVariables(projectId: number, envId: number, data: BatchDeleteVariablesRequest): Promise<ApiResponse<{
        deleted_count: number;
    }>> {
        try {
            return await service.delete(`/projects/${projectId}/environments/${envId}/variables/batch`, { data });
        }
        catch (error) {
            console.error('批量删除变量失败:', error);
            throw error;
        }
    }
    /**
     * 导出变量
     * GET /projects/{projectId}/environments/{envId}/variables/export
     */
    async exportVariables(projectId: number, envId: number): Promise<ApiResponse<ExportVariablesResponse>> {
        try {
            return await service.get(`/projects/${projectId}/environments/${envId}/variables/export`);
        }
        catch (error) {
            console.error('导出变量失败:', error);
            throw error;
        }
    }
    /**
     * 导入变量
     * POST /projects/{projectId}/environments/{envId}/variables/import
     */
    async importVariables(projectId: number, envId: number, data: ImportVariablesRequest): Promise<ApiResponse<ImportVariablesResponse>> {
        try {
            return await service.post(`/projects/${projectId}/environments/${envId}/variables/import`, data);
        }
        catch (error) {
            console.error('导入变量失败:', error);
            throw error;
        }
    }
    // ==================== 数据库连接管理 ====================
    /**
     * 获取数据库连接列表
     * GET /projects/{projectId}/databases
     */
    async getDatabaseList(projectId: number, params?: DatabaseListQuery): Promise<ApiResponse<DatabaseConnection[]>> {
        try {
            return await service.get(`/projects/${projectId}/databases`, { params });
        }
        catch (error) {
            console.error('获取数据库连接列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取数据库连接详情
     * GET /projects/{projectId}/databases/{dbId}
     */
    async getDatabaseDetail(projectId: number, dbId: number): Promise<ApiResponse<DatabaseConnection>> {
        try {
            return await service.get(`/projects/${projectId}/databases/${dbId}`);
        }
        catch (error) {
            console.error('获取数据库连接详情失败:', error);
            throw error;
        }
    }
    /**
     * 创建数据库连接
     * POST /projects/{projectId}/databases
     */
    async createDatabase(projectId: number, data: CreateDatabaseRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/databases`, data);
        }
        catch (error) {
            console.error('创建数据库连接失败:', error);
            throw error;
        }
    }
    /**
     * 更新数据库连接
     * PUT /projects/{projectId}/databases/{dbId}
     */
    async updateDatabase(projectId: number, dbId: number, data: UpdateDatabaseRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.put(`/projects/${projectId}/databases/${dbId}`, data);
        }
        catch (error) {
            console.error('更新数据库连接失败:', error);
            throw error;
        }
    }
    /**
     * 测试数据库连接
     * POST /projects/{projectId}/databases/{dbId}/test
     */
    async testDatabase(projectId: number, dbId: number, data?: TestDatabaseRequest): Promise<ApiResponse<TestDatabaseResponse>> {
        try {
            return await service.post(`/projects/${projectId}/databases/${dbId}/test`, data || {});
        }
        catch (error) {
            console.error('测试数据库连接失败:', error);
            throw error;
        }
    }
    /**
     * 删除数据库连接
     * DELETE /projects/{projectId}/databases/{dbId}
     */
    async deleteDatabase(projectId: number, dbId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/projects/${projectId}/databases/${dbId}`);
        }
        catch (error) {
            console.error('删除数据库连接失败:', error);
            throw error;
        }
    }
    // ==================== 全局函数管理 ====================
    /**
     * 获取函数列表
     * GET /projects/{projectId}/functions
     */
    async getFunctionList(projectId: number, params?: FunctionListQuery): Promise<ApiResponse<FunctionListResponse>> {
        try {
            return await service.get(`/projects/${projectId}/functions`, { params });
        }
        catch (error) {
            console.error('获取函数列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取内置函数列表
     * GET /projects/{projectId}/functions/built-in
     */
    async getBuiltinFunctionList(projectId: number): Promise<ApiResponse<GlobalFunction[]>> {
        try {
            return await service.get(`/projects/${projectId}/functions/built-in`);
        }
        catch (error) {
            console.error('获取内置函数列表失败:', error);
            throw error;
        }
    }
    /**
     * 获取函数详情
     * GET /projects/{projectId}/functions/{functionId}
     */
    async getFunctionDetail(projectId: number, functionId: number): Promise<ApiResponse<GlobalFunction>> {
        try {
            return await service.get(`/projects/${projectId}/functions/${functionId}`);
        }
        catch (error) {
            console.error('获取函数详情失败:', error);
            throw error;
        }
    }
    /**
     * 创建函数
     * POST /projects/{projectId}/functions
     */
    async createFunction(projectId: number, data: CreateFunctionRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.post(`/projects/${projectId}/functions`, data);
        }
        catch (error) {
            console.error('创建函数失败:', error);
            throw error;
        }
    }
    /**
     * 更新函数
     * PUT /projects/{projectId}/functions/{functionId}
     */
    async updateFunction(projectId: number, functionId: number, data: UpdateFunctionRequest): Promise<ApiResponse<{
        id: number;
        name: string;
    }>> {
        try {
            return await service.put(`/projects/${projectId}/functions/${functionId}`, data);
        }
        catch (error) {
            console.error('更新函数失败:', error);
            throw error;
        }
    }
    /**
     * 测试函数
     * POST /projects/{projectId}/functions/{functionId}/test
     */
    async testFunction(projectId: number, functionId: number, data: TestFunctionRequest): Promise<ApiResponse<TestFunctionResponse>> {
        try {
            return await service.post(`/projects/${projectId}/functions/${functionId}/test`, data);
        }
        catch (error) {
            console.error('测试函数失败:', error);
            throw error;
        }
    }
    /**
     * 测试内置函数
     * POST /projects/{projectId}/functions/built-in/{funcName}/test
     */
    async testBuiltinFunction(projectId: number, funcName: string, data: TestFunctionRequest): Promise<ApiResponse<TestFunctionResponse>> {
        try {
            return await service.post(`/projects/${projectId}/functions/built-in/${funcName}/test`, data);
        }
        catch (error) {
            console.error('测试内置函数失败:', error);
            throw error;
        }
    }
    /**
     * 启用/禁用函数
     * PUT /projects/{projectId}/functions/{functionId}/status
     */
    async toggleFunctionStatus(projectId: number, functionId: number, data: ToggleFunctionStatusRequest): Promise<ApiResponse<{
        id: number;
        is_active: boolean;
    }>> {
        try {
            return await service.put(`/projects/${projectId}/functions/${functionId}/status`, data);
        }
        catch (error) {
            console.error('更新函数状态失败:', error);
            throw error;
        }
    }
    /**
     * 删除函数
     * DELETE /projects/{projectId}/functions/{functionId}
     */
    async deleteFunction(projectId: number, functionId: number): Promise<ApiResponse<null>> {
        try {
            return await service.delete(`/projects/${projectId}/functions/${functionId}`);
        }
        catch (error) {
            console.error('删除函数失败:', error);
            throw error;
        }
    }
    /**
     * AI 生成函数
     * POST /projects/{projectId}/functions/ai-generate
     */
    async aiGenerateFunction(projectId: number, data: {
        requirement: string;
    }): Promise<ApiResponse<GlobalFunction>> {
        try {
            return await service.post(`/projects/${projectId}/functions/ai-generate`, data);
        }
        catch (error) {
            console.error('AI 生成函数失败:', error);
            throw error;
        }
    }
}
// ==================== 导出 ====================
export const environmentApi = new EnvironmentApi();
