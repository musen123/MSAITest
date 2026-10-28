/**
 * 全局类型定义
 *
 * AI 智能测试平台 - TypeScript 类型定义
 */

// 导出各模块类型
export * from './auth'
export * from './user'
export * from './role'

/**
 * 用户信息（通用，保持向后兼容）
 * @deprecated 请使用 auth.ts 中的 UserInfo 或 FullUserInfo
 */
export interface User {
  id: number
  username: string
  email: string
  nickname: string
  avatar?: string
  roles: string[]
  permissions: string[]
  createdAt: string
  updatedAt: string
}

/**
 * 项目信息
 */
export interface Project {
  id: number
  name: string
  description?: string
  status: 'active' | 'archived'
  ownerId: number
  createdAt: string
  updatedAt: string
}

/**
 * 项目模块
 */
export interface ProjectModule {
  id: number
  projectId: number
  name: string
  description?: string
  parentId?: number
  sort: number
  createdAt: string
  updatedAt: string
}

/**
 * 测试环境
 */
export interface TestEnvironment {
  id: number
  projectId: number
  name: string
  baseUrl: string
  description?: string
  variables: Record<string, string>
  createdAt: string
  updatedAt: string
}

/**
 * 分页参数
 */
export interface PaginationParams {
  page: number
  pageSize: number
  keyword?: string
}

/**
 * 分页响应
 */
export interface PaginationResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

/**
 * API 响应
 */
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}
