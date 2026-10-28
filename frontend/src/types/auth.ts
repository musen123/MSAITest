/**
 * 认证授权模块 - TypeScript 类型定义
 *
 * AI 智能测试平台 - 认证授权类型定义
 * 对应 API 文档：01-用户与权限管理模块API.md - 第3节 认证授权接口
 */

// ==================== 认证相关类型 ====================

/**
 * 用户登录请求参数
 *
 * 验证码字段已废弃（前端 UI 已移除验证码输入），保留以做兼容。
 */
export interface LoginRequest {
  /** 用户名或邮箱 */
  account: string
  /** 密码 */
  password: string
  /** [已废弃] 验证码 */
  captcha_code?: string
  /** [已废弃] 验证码Key */
  captcha_key?: string
  /** 记住登录状态 */
  remember_me?: boolean
}

/**
 * 用户注册请求参数
 */
export interface RegisterRequest {
  /** 用户名，4-20字符 */
  username: string
  /** 密码，8-20字符 */
  password: string
  /** 邮箱 */
  email: string
  /** 手机号 */
  phone?: string
  /** 真实姓名 */
  real_name?: string
  /** 验证码 */
  captcha_code: string
  /** 验证码Key */
  captcha_key: string
}

/**
 * 刷新Token请求参数
 */
export interface RefreshTokenRequest {
  /** 刷新令牌 */
  refresh_token: string
}

/**
 * 登录响应数据
 */
export interface LoginResponse {
  /** 访问令牌 */
  access_token: string
  /** 刷新令牌 */
  refresh_token: string
  /** 过期时间（秒） */
  expires_in: number
  /** 用户信息 */
  user_info: UserInfo
}

/**
 * 注册响应数据
 */
export interface RegisterResponse {
  /** 用户ID */
  user_id: number
  /** 用户名 */
  username: string
  /** 邮箱 */
  email: string
  /** 创建时间 */
  created_at: string
}

/**
 * 刷新Token响应数据
 */
export interface RefreshTokenResponse {
  /** 新的访问令牌 */
  access_token: string
  /** 轮换后的刷新令牌 */
  refresh_token: string
  /** 过期时间（秒） */
  expires_in: number
}

/**
 * 验证码响应数据
 */
export interface CaptchaResponse {
  /** 验证码Key */
  captcha_key: string
  /** 验证码图片（base64） */
  captcha_image: string
}

/**
 * 用户基本信息
 */
export interface UserInfo {
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
  roles?: string[] | Role[]
  /** 权限列表 */
  permissions?: string[]
}

/**
 * 用户账户状态
 */
export type UserStatus = 'active' | 'disabled' | 'locked'

/**
 * 完整用户信息（包含角色对象）
 */
export interface FullUserInfo extends UserInfo {
  /** 个人简介 */
  bio?: string
  /** 角色列表（对象形式） */
  roles?: Role[]
  /** 创建时间 */
  created_at: string
  /** 更新时间 */
  updated_at: string
  /** 最后登录时间 */
  last_login_at?: string
}

// ==================== 角色权限类型 ====================

/**
 * 角色信息
 */
export interface Role {
  /** 角色ID */
  id: number
  /** 角色编码 */
  code: string
  /** 角色名称 */
  name: string
  /** 角色描述 */
  description?: string
  /** 是否系统角色 */
  is_system: boolean
  /** 权限列表 */
  permissions?: string[]
  /** 创建时间 */
  created_at?: string
}

/**
 * 权限分组
 */
export interface PermissionGroup {
  /** 模块名称 */
  module: string
  /** 权限列表 */
  permissions: Permission[]
}

/**
 * 权限信息
 */
export interface Permission {
  /** 权限编码 */
  code: string
  /** 权限名称 */
  name: string
}

/**
 * 用户权限响应
 */
export interface UserPermissionsResponse {
  /** 角色列表 */
  roles: Role[]
  /** 权限列表 */
  permissions: string[]
}

/**
 * 修改密码请求
 */
export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}
