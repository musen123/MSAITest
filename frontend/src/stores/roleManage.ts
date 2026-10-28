/**
 * 角色权限管理状态管理
 *
 * AI 智能测试平台 - 角色权限管理状态管理
 * 对应需求文档：01-用户与权限管理模块.md - 第2.6节 角色管理
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Ref } from 'vue'
import { roleApi, permissionApi } from '@/api/role'
import type {
  RoleListItem,
  RoleDetail,
  CreateRoleRequest,
  UpdateRoleRequest,
  PermissionListResponse,
  PermissionGroup,
  PermissionTreeNode,
} from '@/types/role'
import { ElMessage } from 'element-plus'

/**
 * 角色管理状态 Store
 * 注意：此 Store 不使用持久化，数据总是从后端获取
 */
export const useRoleManageStore = defineStore('roleManage', () => {
  // ==================== 状态 ====================

  /** 角色列表 */
  const roleList: Ref<RoleListItem[]> = ref([])
  /** 加载状态 */
  const loading: Ref<boolean> = ref(false)
  /** 当前选中的角色 */
  const selectedRoleId: Ref<number | null> = ref(null)
  /** 角色详情 */
  const roleDetail: Ref<RoleDetail | null> = ref(null)
  /** 所有权限列表（按模块分组） */
  const permissionList: Ref<PermissionListResponse> = ref([])
  /** 权限树结构 */
  const permissionTree: Ref<PermissionTreeNode[]> = ref([])

  // ==================== 方法 ====================

  /**
   * 获取角色列表
   */
  const fetchRoleList = async (): Promise<void> => {
    loading.value = true
    try {
      const res = await roleApi.getList()
      if (res.code === 200) {
        roleList.value = res.data
      }
    } catch (error) {
      console.error('获取角色列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取角色详情
   * @param roleId 角色ID
   */
  const fetchRoleDetail = async (roleId: number): Promise<RoleDetail | null> => {
    loading.value = true
    try {
      const res = await roleApi.getDetail(roleId)
      if (res.code === 200) {
        roleDetail.value = res.data
        return res.data
      }
      return null
    } catch (error) {
      console.error('获取角色详情失败:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建角色
   * @param data 创建角色请求参数
   */
  const createRole = async (data: CreateRoleRequest): Promise<boolean> => {
    loading.value = true
    try {
      const res = await roleApi.create(data)
      if (res.code === 200) {
        ElMessage.success('创建角色成功')
        await fetchRoleList()
        return true
      }
      return false
    } catch (error) {
      console.error('创建角色失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新角色
   * @param roleId 角色ID
   * @param data 更新请求参数
   */
  const updateRole = async (roleId: number, data: UpdateRoleRequest): Promise<boolean> => {
    loading.value = true
    try {
      const res = await roleApi.update(roleId, data)
      if (res.code === 200) {
        ElMessage.success('更新角色成功')
        await fetchRoleList()
        return true
      }
      return false
    } catch (error) {
      console.error('更新角色失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除角色
   * @param roleId 角色ID
   */
  const deleteRole = async (roleId: number): Promise<boolean> => {
    loading.value = true
    try {
      const res = await roleApi.delete(roleId)
      if (res.code === 200) {
        ElMessage.success('删除角色成功')
        await fetchRoleList()
        return true
      }
      return false
    } catch (error) {
      console.error('删除角色失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取权限列表
   */
  const fetchPermissionList = async (): Promise<void> => {
    loading.value = true
    try {
      const res = await permissionApi.getList()
      if (res.code === 200) {
        // 后端返回 data.data，因为 PermissionsResponse 又嵌套了一层 data
        const permissionData = res.data.data || []
        permissionList.value = permissionData
        // 构建权限树
        permissionTree.value = buildPermissionTree(permissionData)
      }
    } catch (error) {
      console.error('获取权限列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 构建权限树结构
   * @param permissionGroups 权限分组列表
   */
  const buildPermissionTree = (permissionGroups: PermissionGroup[]): PermissionTreeNode[] => {
    return permissionGroups.map((group) => ({
      code: group.module,
      name: group.module,
      children: group.permissions.map((p) => ({
        code: p.code,
        name: p.name,
      })),
    }))
  }

  /**
   * 为用户分配角色
   * @param userId 用户ID
   * @param roleIds 角色ID列表
   */
  const assignRolesToUser = async (userId: number, roleIds: number[]): Promise<boolean> => {
    loading.value = true
    try {
      const res = await permissionApi.assignRoles(userId, { role_ids: roleIds })
      if (res.code === 200) {
        ElMessage.success('分配角色成功')
        return true
      }
      return false
    } catch (error) {
      console.error('分配角色失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 设置选中的角色
   * @param roleId 角色ID
   */
  const setSelectedRoleId = (roleId: number | null) => {
    selectedRoleId.value = roleId
  }

  /**
   * 重置状态
   */
  const resetState = () => {
    roleList.value = []
    selectedRoleId.value = null
    roleDetail.value = null
    permissionList.value = []
    permissionTree.value = []
  }

  return {
    // 状态
    roleList,
    loading,
    selectedRoleId,
    roleDetail,
    permissionList,
    permissionTree,
    // 方法
    fetchRoleList,
    fetchRoleDetail,
    createRole,
    updateRole,
    deleteRole,
    fetchPermissionList,
    assignRolesToUser,
    setSelectedRoleId,
    resetState,
  }
})
