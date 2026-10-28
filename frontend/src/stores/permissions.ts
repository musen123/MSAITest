/**
 * 权限管理状态管理
 *
 * AI 智能测试平台 - 权限管理状态
 * 对应需求文档：01-用户与权限管理模块.md
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { permissionApi } from '@/api/permissions'
import type { Role, Permission, RoleListResponse, PermissionListResponse } from '@/api/permissions'
import { ElMessage } from 'element-plus'

/**
 * 权限管理状态 Store
 */
export const usePermissionStore = defineStore(
  'permissions',
  () => {
    // ==================== 状态 ====================

    /** 角色列表 */
    const roles: Ref<Role[]> = ref([])

    /** 权限列表 */
    const permissions: Ref<Permission[]> = ref([])

    /** 加载状态 */
    const loading: Ref<boolean> = ref(false)

    /** 当前页码 */
    const currentPage = ref(1)

    /** 每页数量 */
    const pageSize = ref(20)

    /** 列表总数 */
    const total = ref(0)

    /** 搜索关键词 */
    const keyword = ref('')

    /** 选中的权限（用于分配） */
    const selectedPermissions: Ref<Permission[]> = ref([])

    // ==================== 计算属性 ====================

    /**
     * 系统角色列表
     */
    const systemRoles = computed(() => {
      return roles.value.filter((role) => role.is_system)
    })

    /**
     * 自定义角色列表
     */
    const customRoles = computed(() => {
      return roles.value.filter((role) => !role.is_system)
    })

    /**
     * 所有权限列表（扁平化）
     */
    const allPermissions = computed(() => {
      const perms: Permission[] = []
      permissions.value.forEach((perm) => {
        perms.push(perm)
        if (perm.children && perm.children.length > 0) {
          perm.children.forEach((child) => perms.push(child))
        }
      })
      return perms
    })

    /**
     * 按模块分组的权限
     */
    const permissionsByModule = computed(() => {
      const modules: Record<string, Permission[]> = {}
      permissions.value.forEach((perm) => {
        if (!modules[perm.module]) {
          modules[perm.module] = []
        }
        modules[perm.module].push(perm)
      })
      return modules
    })

    // ==================== 方法 ====================

    /**
     * 获取角色列表
     */
    const fetchRoles = async (params?: { keyword?: string; page?: number }) => {
      loading.value = true
      try {
        const response = await permissionApi.getRoleList(params)

        // request.ts 响应拦截器已经处理了，response 是 ApiResponse<RoleListItem[]>
        // response.code = 200 表示成功
        // response.data = 角色数组
        roles.value = response.data || []
        total.value = roles.value.length
      } catch (error: any) {
        console.error('获取角色列表失败:', error)
        // 响应拦截器已经显示了错误消息
      } finally {
        loading.value = false
      }
    }

    /**
     * 获取权限列表
     */
    const fetchPermissions = async (params?: { keyword?: string; module?: string; page?: number }) => {
      loading.value = true
      try {
        const response = await permissionApi.getPermissionList(params)

        // response.data = PermissionsResponse = { data: PermissionModule[] }
        const permissionsResponse = response.data
        const modules = permissionsResponse.data || []
        // 扁平化处理所有权限
        const allPerms: Permission[] = []
        modules.forEach((module: any) => {
          module.permissions.forEach((perm: any) => {
            allPerms.push({
              id: 0,
              code: perm.code,
              name: perm.name,
              module: module.module,
              created_at: '',
              updated_at: '',
            })
          })
        })
        permissions.value = allPerms
      } catch (error: any) {
        console.error('获取权限列表失败:', error)
        // 响应拦截器已经显示了错误消息
      } finally {
        loading.value = false
      }
    }

    /**
     * 获取所有权限（不分页）
     */
    const fetchAllPermissions = async () => {
      loading.value = true
      try {
        const response = await permissionApi.getAllPermissions()

        // response.data = AllPermissionsResponse = { data: PermissionModule[] }
        const permissionsResponse = response.data
        const modules = permissionsResponse.data || []
        // 扁平化处理所有权限
        const allPerms: Permission[] = []
        modules.forEach((module: any) => {
          module.permissions.forEach((perm: any) => {
            allPerms.push({
              id: 0,
              code: perm.code,
              name: perm.name,
              module: module.module,
              created_at: '',
              updated_at: '',
            })
          })
        })
        permissions.value = allPerms
        return true
      } catch (error: any) {
        console.error('获取所有权限失败:', error)
        // 响应拦截器已经显示了错误消息
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 创建角色
     */
    const createRole = async (data: { name: string; code?: string; description?: string; permissions?: string[] }): Promise<boolean> => {
      loading.value = true
      try {
        const response = await permissionApi.createRole(data)
        // 响应拦截器已经处理了成功消息
        await fetchRoles() // 刷新角色列表
        return true
      } catch (error: any) {
        console.error('创建角色失败:', error)
        // 响应拦截器已经显示了错误消息
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 更新角色
     */
    const updateRole = async (roleId: number, data: { name?: string; description?: string; permissions?: string[] }): Promise<boolean> => {
      loading.value = true
      try {
        const response = await permissionApi.updateRole(roleId, data)
        // 响应拦截器已经处理了成功消息
        await fetchRoles() // 刷新角色列表
        return true
      } catch (error: any) {
        console.error('更新角色失败:', error)
        // 响应拦截器已经显示了错误消息
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 删除角色
     */
    const deleteRole = async (roleId: number): Promise<boolean> => {
      loading.value = true
      try {
        const response = await permissionApi.deleteRole(roleId)
        // 响应拦截器已经处理了成功消息
        await fetchRoles() // 刷新角色列表
        return true
      } catch (error: any) {
        console.error('删除角色失败:', error)
        // 响应拦截器已经显示了错误消息
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 重置搜索
     */
    const resetSearch = () => {
      keyword.value = ''
      currentPage.value = 1
    }

    /**
     * 清空选中权限
     */
    const clearSelectedPermissions = () => {
      selectedPermissions.value = []
    }

    /**
     * 获取角色的权限详情
     */
    const getRolePermissions = (roleId: number): Permission[] => {
      const role = roles.value.find((r) => r.id === roleId)
      return role?.permissions || []
    }

    return {
      // 状态
      roles,
      permissions,
      loading,
      currentPage,
      pageSize,
      total,
      keyword,
      selectedPermissions,

      // 计算属性
      systemRoles,
      customRoles,
      allPermissions,
      permissionsByModule,
      getRolePermissions,

      // 方法
      fetchRoles,
      fetchPermissions,
      fetchAllPermissions,
      createRole,
      updateRole,
      deleteRole,
      resetSearch,
      clearSelectedPermissions,
    }
  },
)
