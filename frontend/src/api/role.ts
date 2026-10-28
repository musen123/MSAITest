/**
 * 角色权限管理 API
 *
 * AI 智能测试平台 - 角色权限管理接口封装
 * 对应 API 文档：01-用户与权限管理模块API.md - 第5、6节 角色与权限管理接口
 */

import { request } from './request'
import type {
  RoleListItem,
  RoleDetail,
  CreateRoleRequest,
  CreateRoleResponse,
  UpdateRoleRequest,
  UpdateRoleResponse,
  PermissionListResponse,
  UserPermissionsResponse,
  AssignRoleRequest,
} from '@/types/role'
import type { ApiResponse } from '@/types'

/**
 * 角色管理 API
 */
export const roleApi = {
  /**
   * 获取角色列表
   * @returns 角色列表
   */
  getList(): Promise<ApiResponse<RoleListItem[]>> {
    return request.get('/roles')
  },

  /**
   * 获取角色详情
   * @param roleId 角色ID
   * @returns 角色详细信息
   */
  getDetail(roleId: number): Promise<ApiResponse<RoleDetail>> {
    return request.get(`/roles/${roleId}`)
  },

  /**
   * 创建角色
   * @param data 创建角色请求参数
   * @returns 创建的角色信息
   */
  create(data: CreateRoleRequest): Promise<ApiResponse<CreateRoleResponse>> {
    return request.post('/roles', data)
  },

  /**
   * 更新角色
   * @param roleId 角色ID
   * @param data 更新请求参数
   * @returns 更新后的角色信息
   */
  update(roleId: number, data: UpdateRoleRequest): Promise<ApiResponse<UpdateRoleResponse>> {
    return request.put(`/roles/${roleId}`, data)
  },

  /**
   * 删除角色
   * @param roleId 角色ID
   * @returns 删除结果
   */
  delete(roleId: number): Promise<ApiResponse<null>> {
    return request.delete(`/roles/${roleId}`)
  },
}

/**
 * 权限管理 API
 */
export const permissionApi = {
  /**
   * 获取所有权限列表（按模块分组）
   * @returns 权限列表
   */
  getList(): Promise<ApiResponse<PermissionListResponse>> {
    return request.get('/roles/permissions')
  },

  /**
   * 获取用户权限
   * @param userId 用户ID
   * @returns 用户权限信息
   */
  getUserPermissions(userId: number): Promise<ApiResponse<UserPermissionsResponse>> {
    return request.get(`/users/${userId}/permissions`)
  },

  /**
   * 为用户分配角色
   * @param userId 用户ID
   * @param data 角色分配请求参数
   * @returns 分配结果
   */
  assignRoles(userId: number, data: AssignRoleRequest): Promise<ApiResponse<null>> {
    return request.put(`/users/${userId}/roles`, data)
  },
}

export default { roleApi, permissionApi }
