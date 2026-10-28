/**
 * 用户管理模块 - TypeScript 类型定义
 *
 * AI 智能测试平台 - 用户管理类型定义
 * 对应 API 文档：01-用户与权限管理模块API.md - 第4节 用户管理接口
 */

import type { PaginationParams, PaginationResponse } from './index'
import type { Role } from './role'

// ==================== 用户管理类型 ====================

/**
 * 用户列表查询参数
 */
export interface UserListParams extends PaginationParams {
  /** 搜索关键词（用户名/邮箱/手机号） */
  keyword?: string
  /** 状态筛选 */
  status?: UserStatus
  /** 角色筛选 */
  role_id?: number
  /** 排序字段 */
  order_by?: 'created_at' | 'last_login_at'
  /** 排序方向 */
  order?: 'asc' | 'desc'
}

/**
 * 用户列表项
 */
export interface UserListItem {
  /** 用户ID */
  id: number
  /** 用户名 */
  username: string
  /** 邮箱 */
  email: string
  /** 手机号 */
  phone?: string
  /** 真实姓名 */
  real_name?: string
  /** 头像URL */
  avatar?: string
  /** 账户状态 */
  status: UserStatus
  /** 角色列表 */
  roles: string[]
  /** 创建时间 */
  created_at: string
  /** 最后登录时间 */
  last_login_at?: string
}

/**
 * 用户列表响应
 */
export type UserListResponse = PaginationResponse<UserListItem>

/**
 * 用户详细信息
 */
export interface UserDetail {
  /** 用户ID */
  id: number
  /** 用户名 */
  username: string
  /** 邮箱 */
  email: string
  /** 手机号 */
  phone?: string
  /** 真实姓名 */
  real_name?: string
  /** 头像URL */
  avatar?: string
  /** 账户状态 */
  status: UserStatus
  /** 个人简介 */
  bio?: string
  /** 角色列表 */
  roles: Role[]
  /** 权限列表 */
  permissions: string[]
  /** 参与的项目 */
  projects?: UserProject[]
  /** 创建时间 */
  created_at: string
  /** 更新时间 */
  updated_at: string
  /** 最后登录时间 */
  last_login_at?: string
}

/**
 * 用户项目角色
 */
export interface UserProject {
  /** 项目ID */
  id: number
  /** 项目名称 */
  name: string
  /** 项目角色 */
  role: string
}

/**
 * 创建用户请求参数
 */
export interface CreateUserRequest {
  /** 用户名 */
  username: string
  /** 密码 */
  password: string
  /** 邮箱 */
  email: string
  /** 手机号 */
  phone?: string
  /** 真实姓名 */
  real_name?: string
  /** 角色ID列表 */
  role_ids?: number[]
}

/**
 * 创建用户响应
 */
export interface CreateUserResponse {
  /** 用户ID */
  id: number
  /** 用户名 */
  username: string
  /** 邮箱 */
  email: string
}

/**
 * 更新用户信息请求参数
 */
export interface UpdateUserRequest {
  /** 邮箱 */
  email?: string
  /** 手机号 */
  phone?: string
  /** 真实姓名 */
  real_name?: string
  /** 个人简介 */
  bio?: string
}

/**
 * 修改密码请求参数
 */
export interface ChangePasswordRequest {
  /** 原密码 */
  old_password: string
  /** 新密码 */
  new_password: string
}

/**
 * 重置密码请求参数（管理员）
 */
export interface ResetPasswordRequest {
  /** 新密码 */
  new_password: string
}

/**
 * 上传头像响应
 */
export interface UploadAvatarResponse {
  /** 图片URL */
  url: string
}

/**
 * 修改用户状态请求参数
 */
export interface UpdateUserStatusRequest {
  /** 状态 */
  status: UserStatus
}

/**
 * 用户账户状态
 */
export type UserStatus = 'active' | 'disabled' | 'locked'

/**
 * 用户统计信息
 */
export interface UserStatistics {
  /** 总用户数 */
  total: number
  /** 启用用户数 */
  active: number
  /** 禁用用户数 */
  disabled: number
  /** 锁定用户数 */
  locked: number
  /** 今日新增 */
  today_new: number
}
