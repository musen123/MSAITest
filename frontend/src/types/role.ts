/**
 * 角色管理模块 - TypeScript 类型定义
 *
 * AI 智能测试平台 - 角色管理类型定义
 * 对应 API 文档：01-用户与权限管理模块API.md - 第5、6节 角色与权限管理接口
 */

// ==================== 角色管理类型 ====================

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
 * 角色列表项
 */
export interface RoleListItem {
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
  permissions: string[]
  /** 创建时间 */
  created_at: string
}

/**
 * 角色详细信息
 */
export interface RoleDetail extends Role {
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
  permissions: string[]
  /** 拥有此角色的用户列表 */
  users?: RoleUser[]
  /** 创建时间 */
  created_at: string
}

/**
 * 角色用户
 */
export interface RoleUser {
  /** 用户ID */
  id: number
  /** 用户名 */
  username: string
  /** 真实姓名 */
  real_name?: string
}

/**
 * 创建角色请求参数
 */
export interface CreateRoleRequest {
  /** 角色编码 */
  code: string
  /** 角色名称 */
  name: string
  /** 角色描述 */
  description?: string
  /** 权限列表 */
  permissions: string[]
}

/**
 * 创建角色响应
 */
export interface CreateRoleResponse {
  /** 角色ID */
  id: number
  /** 角色编码 */
  code: string
  /** 角色名称 */
  name: string
}

/**
 * 更新角色请求参数
 */
export interface UpdateRoleRequest {
  /** 角色名称 */
  name?: string
  /** 角色描述 */
  description?: string
  /** 权限列表 */
  permissions?: string[]
}

/**
 * 更新角色响应
 */
export interface UpdateRoleResponse {
  /** 角色ID */
  id: number
  /** 角色名称 */
  name: string
}

/**
 * 分配角色请求参数
 */
export interface AssignRoleRequest {
  /** 角色ID列表 */
  role_ids: number[]
}

// ==================== 权限管理类型 ====================

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
 * 权限分组
 */
export interface PermissionGroup {
  /** 模块名称 */
  module: string
  /** 权限列表 */
  permissions: Permission[]
}

/**
 * 权限列表响应（后端嵌套结构）
 */
export interface PermissionListResponse {
  data: PermissionGroup[]
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
 * 权限树节点（用于权限选择组件）
 */
export interface PermissionTreeNode {
  /** 权限编码 */
  code: string
  /** 权限名称 */
  name: string
  /** 子权限 */
  children?: PermissionTreeNode[]
  /** 是否选中 */
  checked?: boolean
  /** 是否半选 */
  indeterminate?: boolean
}

// ==================== 预定义角色 ====================

/**
 * 预定义角色编码
 */
export enum SystemRoleCode {
  /** 超级管理员 */
  SUPER_ADMIN = 'super_admin',
  /** 管理员 */
  ADMIN = 'admin',
  /** 项目管理员 */
  PROJECT_ADMIN = 'project_admin',
  /** 测试人员 */
  TESTER = 'tester',
  /** 访客 */
  VIEWER = 'viewer',
}

/**
 * 预定义角色信息
 */
export const SYSTEM_ROLES: Record<SystemRoleCode, { code: string; name: string; description: string }> = {
  [SystemRoleCode.SUPER_ADMIN]: {
    code: 'super_admin',
    name: '超级管理员',
    description: '拥有所有权限',
  },
  [SystemRoleCode.ADMIN]: {
    code: 'admin',
    name: '管理员',
    description: '拥有管理权限',
  },
  [SystemRoleCode.PROJECT_ADMIN]: {
    code: 'project_admin',
    name: '项目管理员',
    description: '可管理项目内的资源和成员',
  },
  [SystemRoleCode.TESTER]: {
    code: 'tester',
    name: '测试人员',
    description: '可执行测试用例',
  },
  [SystemRoleCode.VIEWER]: {
    code: 'viewer',
    name: '访客',
    description: '只读权限',
  },
}
