/**
 * 用户管理 API
 *
 * AI 智能测试平台 - 用户管理接口封装
 * 对应 API 文档：01-用户与权限管理模块API.md - 第4节 用户管理接口
 */

import { request } from './request'
import type {
  UserListParams,
  UserListResponse,
  UserDetail,
  CreateUserRequest,
  CreateUserResponse,
  UpdateUserRequest,
  ChangePasswordRequest,
  ResetPasswordRequest,
  UploadAvatarResponse,
  UpdateUserStatusRequest,
} from '@/types/user'
import type { ApiResponse } from '@/types'

/**
 * 用户管理 API
 */
export const userApi = {
  /**
   * 获取用户列表
   * @param params 查询参数
   * @returns 用户列表
   */
  getList(params: UserListParams): Promise<ApiResponse<UserListResponse>> {
    return request.get('/users', { params })
  },

  /**
   * 获取用户详情
   * @param userId 用户ID
   * @returns 用户详细信息
   */
  getDetail(userId: number): Promise<ApiResponse<UserDetail>> {
    return request.get(`/users/${userId}`)
  },

  /**
   * 创建用户（管理员）
   * @param data 创建用户请求参数
   * @returns 创建的用户信息
   */
  create(data: CreateUserRequest): Promise<ApiResponse<CreateUserResponse>> {
    return request.post('/users', data)
  },

  /**
   * 更新用户信息
   * @param userId 用户ID
   * @param data 更新请求参数
   * @returns 更新后的用户信息
   */
  update(userId: number, data: UpdateUserRequest): Promise<ApiResponse<{ id: number; email: string }>> {
    return request.put(`/users/${userId}`, data)
  },

  /**
   * 修改密码
   * @param userId 用户ID
   * @param data 修改密码请求参数
   * @returns 修改结果
   */
  changePassword(userId: number, data: ChangePasswordRequest): Promise<ApiResponse<null>> {
    return request.put(`/users/${userId}/password`, data)
  },

  /**
   * 重置密码（管理员）
   * @param userId 用户ID
   * @param data 重置密码请求参数
   * @returns 重置结果
   */
  resetPassword(userId: number, data: ResetPasswordRequest): Promise<ApiResponse<null>> {
    return request.post(`/users/${userId}/reset-password`, data)
  },

  /**
   * 上传头像
   * @param userId 用户ID
   * @param file 图片文件
   * @returns 头像URL
   */
  uploadAvatar(userId: number, file: File): Promise<ApiResponse<UploadAvatarResponse>> {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/users/${userId}/avatar`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  /**
   * 启用/禁用用户
   * @param userId 用户ID
   * @param data 状态更新请求参数
   * @returns 更新结果
   */
  updateStatus(userId: number, data: UpdateUserStatusRequest): Promise<ApiResponse<null>> {
    return request.put(`/users/${userId}/status`, data)
  },

  /**
   * 删除用户
   * @param userId 用户ID
   * @returns 删除结果
   */
  delete(userId: number): Promise<ApiResponse<null>> {
    return request.delete(`/users/${userId}`)
  },

  /**
   * 批量删除用户
   * @param userIds 用户ID列表
   * @returns 删除结果
   */
  batchDelete(userIds: number[]): Promise<ApiResponse<null>> {
    return request.delete('/users/batch', { data: { user_ids: userIds } })
  },

  /**
   * 批量更新用户状态
   * @param userIds 用户ID列表
   * @param status 状态
   * @returns 更新结果
   */
  batchUpdateStatus(userIds: number[], status: 'active' | 'disabled'): Promise<ApiResponse<null>> {
    return request.put('/users/batch/status', { user_ids: userIds, status })
  },
}

export default userApi
