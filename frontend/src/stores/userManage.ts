/**
 * 用户管理状态管理
 *
 * AI 智能测试平台 - 用户管理状态管理
 * 对应需求文档：01-用户与权限管理模块.md - 第2.5节 系统用户管理
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Ref } from 'vue'
import { userApi } from '@/api/user'
import type {
  UserListParams,
  UserListItem,
  UserListResponse,
  UserDetail,
  CreateUserRequest,
  UpdateUserRequest,
} from '@/types/user'
import { ElMessage } from 'element-plus'

/**
 * 用户管理状态 Store
 * 注意：此 Store 不使用持久化，数据总是从后端获取
 */
export const useUserManageStore = defineStore('userManage', () => {
  // ==================== 状态 ====================

  /** 用户列表 */
  const userList: Ref<UserListItem[]> = ref([])
  /** 用户总数 */
  const total: Ref<number> = ref(0)
  /** 当前页码 */
  const currentPage: Ref<number> = ref(1)
  /** 每页数量 */
  const pageSize: Ref<number> = ref(20)
  /** 加载状态 */
  const loading: Ref<boolean> = ref(false)
  /** 当前选中的用户 */
  const selectedUserIds: Ref<number[]> = ref([])
  /** 用户详情 */
  const userDetail: Ref<UserDetail | null> = ref(null)

  // ==================== 方法 ====================

  /**
   * 获取用户列表
   * @param params 查询参数
   */
  const fetchUserList = async (params?: Partial<UserListParams>): Promise<void> => {
    loading.value = true
    try {
      const requestParams: UserListParams = {
        page: params?.page ?? currentPage.value,
        page_size: params?.page_size ?? pageSize.value,
        keyword: params?.keyword,
        status: params?.status,
        role_id: params?.role_id,
        order_by: params?.order_by,
        order: params?.order,
      }

      const res = await userApi.getList(requestParams)
      if (res.code === 200) {
        const data = res.data
        userList.value = data.items
        total.value = data.total
        currentPage.value = data.page
        pageSize.value = data.page_size
      }
    } catch (error) {
      console.error('获取用户列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取用户详情
   * @param userId 用户ID
   */
  const fetchUserDetail = async (userId: number): Promise<UserDetail | null> => {
    loading.value = true
    try {
      const res = await userApi.getDetail(userId)
      if (res.code === 200) {
        userDetail.value = res.data
        return res.data
      }
      return null
    } catch (error) {
      console.error('获取用户详情失败:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建用户
   * @param data 创建用户请求参数
   */
  const createUser = async (data: CreateUserRequest): Promise<boolean> => {
    loading.value = true
    try {
      const res = await userApi.create(data)
      if (res.code === 200) {
        ElMessage.success('创建用户成功')
        await fetchUserList()
        return true
      }
      return false
    } catch (error) {
      console.error('创建用户失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新用户信息
   * @param userId 用户ID
   * @param data 更新请求参数
   */
  const updateUser = async (userId: number, data: UpdateUserRequest): Promise<boolean> => {
    loading.value = true
    try {
      const res = await userApi.update(userId, data)
      if (res.code === 200) {
        ElMessage.success('更新用户成功')
        await fetchUserList()
        return true
      }
      return false
    } catch (error) {
      console.error('更新用户失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除用户
   * @param userId 用户ID
   */
  const deleteUser = async (userId: number): Promise<boolean> => {
    loading.value = true
    try {
      const res = await userApi.delete(userId)
      if (res.code === 200) {
        ElMessage.success('删除用户成功')
        await fetchUserList()
        return true
      }
      return false
    } catch (error) {
      console.error('删除用户失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 批量删除用户
   */
  const batchDeleteUsers = async (): Promise<boolean> => {
    if (selectedUserIds.value.length === 0) {
      ElMessage.warning('请选择要删除的用户')
      return false
    }
    loading.value = true
    try {
      const res = await userApi.batchDelete(selectedUserIds.value)
      if (res.code === 200) {
        ElMessage.success('批量删除成功')
        selectedUserIds.value = []
        await fetchUserList()
        return true
      }
      return false
    } catch (error) {
      console.error('批量删除用户失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新用户状态
   * @param userId 用户ID
   * @param status 状态
   */
  const updateUserStatus = async (userId: number, status: 'active' | 'disabled'): Promise<boolean> => {
    loading.value = true
    try {
      const res = await userApi.updateStatus(userId, { status })
      if (res.code === 200) {
        ElMessage.success('更新状态成功')
        await fetchUserList()
        return true
      }
      return false
    } catch (error) {
      console.error('更新用户状态失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 批量更新用户状态
   * @param status 状态
   */
  const batchUpdateUserStatus = async (status: 'active' | 'disabled'): Promise<boolean> => {
    if (selectedUserIds.value.length === 0) {
      ElMessage.warning('请选择要操作的用户')
      return false
    }
    loading.value = true
    try {
      const res = await userApi.batchUpdateStatus(selectedUserIds.value, status)
      if (res.code === 200) {
        ElMessage.success('批量更新成功')
        selectedUserIds.value = []
        await fetchUserList()
        return true
      }
      return false
    } catch (error) {
      console.error('批量更新用户状态失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 设置选中的用户
   * @param userIds 用户ID列表
   */
  const setSelectedUserIds = (userIds: number[]) => {
    selectedUserIds.value = userIds
  }

  /**
   * 重置状态
   */
  const resetState = () => {
    userList.value = []
    total.value = 0
    currentPage.value = 1
    pageSize.value = 20
    selectedUserIds.value = []
    userDetail.value = null
  }

  /**
   * 重置用户密码（管理员）
   * @param userId 用户ID
   * @param newPassword 新密码
   */
  const resetPassword = async (userId: number, newPassword: string): Promise<boolean> => {
    loading.value = true
    try {
      const res = await userApi.resetPassword(userId, { new_password: newPassword })
      if (res.code === 200) {
        ElMessage.success('密码重置成功')
        return true
      }
      return false
    } catch (error: any) {
      console.error('重置密码失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    // 状态
    userList,
    total,
    currentPage,
    pageSize,
    loading,
    selectedUserIds,
    userDetail,
    // 方法
    fetchUserList,
    fetchUserDetail,
    createUser,
    updateUser,
    deleteUser,
    batchDeleteUsers,
    updateUserStatus,
    batchUpdateUserStatus,
    setSelectedUserIds,
    resetState,
    resetPassword,
  }
})
