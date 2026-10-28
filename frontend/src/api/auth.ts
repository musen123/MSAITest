/**
 * 认证授权 API
 *
 * AI 智能测试平台 - 认证授权接口封装
 * 对应 API 文档：01-用户与权限管理模块API.md - 第3节 认证授权接口
 */

import { request } from './request'
import { userApi } from './user'
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  RefreshTokenRequest,
  RefreshTokenResponse,
  CaptchaResponse,
  FullUserInfo,
} from '@/types/auth'
import type { ApiResponse } from '@/types'

/**
 * 认证授权 API
 */
export const authApi = {
  /**
   * 用户登录
   * @param data 登录请求参数
   * @returns 登录响应数据
   */
  login(data: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    return request.post('/auth/login', data)
  },

  /**
   * 用户注册
   * @param data 注册请求参数
   * @returns 注册响应数据
   */
  register(data: RegisterRequest): Promise<ApiResponse<RegisterResponse>> {
    return request.post('/auth/register', data)
  },

  /**
   * 用户登出
   * @returns 登出响应
   */
  logout(refresh_token?: string): Promise<ApiResponse<null>> {
    return request.post('/auth/logout', { refresh_token })
  },

  /**
   * 刷新Token
   * @param data 刷新Token请求参数
   * @returns 新的访问令牌
   */
  refreshToken(data: RefreshTokenRequest): Promise<ApiResponse<RefreshTokenResponse>> {
    return request.post('/auth/refresh', data)
  },

  /**
   * 获取当前用户信息（个人资料）
   * 注意：此方法内部调用 userApi.getDetail()
   * @param userId 用户ID
   * @returns 当前用户完整信息
   */
  getProfile(userId: number): Promise<ApiResponse<FullUserInfo>> {
    return userApi.getDetail(userId) as Promise<ApiResponse<FullUserInfo>>
  },

  /**
   * @deprecated 使用 getProfile(userId) 替代
   * 获取当前用户信息
   * @param userId 用户ID
   * @returns 当前用户完整信息
   */
  getCurrentUser(userId: number): Promise<ApiResponse<FullUserInfo>> {
    return this.getProfile(userId)
  },

  /**
   * 获取验证码
   * @returns 验证码数据
   */
  getCaptcha(): Promise<ApiResponse<CaptchaResponse>> {
    return request.get('/auth/captcha')
  },

  /**
   * 更新当前用户信息
   * 注意：此方法内部调用 userApi.update()
   * @param userId 用户ID
   * @param data 更新请求参数
   * @returns 更新后的用户信息
   */
  updateProfile(
    userId: number,
    data: {
      real_name?: string
      email?: string
      phone?: string
      bio?: string
    },
  ): Promise<ApiResponse<{ id: number; email: string }>> {
    return userApi.update(userId, data)
  },

  /**
   * 修改密码
   * 注意：此方法内部调用 userApi.changePassword()
   * @param userId 用户ID
   * @param data 修改密码请求参数
   * @returns 修改结果
   */
  changePassword(
    userId: number,
    data: {
      old_password: string
      new_password: string
    },
  ): Promise<ApiResponse<null>> {
    return userApi.changePassword(userId, data)
  },

  /**
   * 上传当前用户头像
   * 注意：此方法内部调用 userApi.uploadAvatar()
   * @param userId 用户ID
   * @param file 图片文件
   * @returns 头像URL
   */
  uploadAvatar(userId: number, file: File): Promise<ApiResponse<{ url: string }>> {
    return userApi.uploadAvatar(userId, file) as Promise<ApiResponse<{ url: string }>>
  },
}

export default authApi
