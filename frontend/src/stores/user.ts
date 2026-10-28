/**
 * 用户认证状态管理
 *
 * AI 智能测试平台 - 用户认证状态管理
 * 对应需求文档：01-用户与权限管理模块.md - 第2.2节 用户登录
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { authApi } from '@/api/auth'
import type { LoginRequest, RegisterRequest, FullUserInfo } from '@/types/auth'
import { ElMessage } from 'element-plus'

/**
 * 用户认证状态 Store
 */
export const useUserStore = defineStore(
  'user',
  () => {
    // ==================== 状态 ====================

    /** 访问令牌 */
    const token: Ref<string> = ref('')
    /** 刷新令牌 */
    const refreshToken: Ref<string> = ref('')
    /** 用户信息 */
    const userInfo: Ref<FullUserInfo | null> = ref(null)
    /** 用户 ID（持久化，用于页面刷新后获取用户信息） */
    const currentUserId: Ref<number | null> = ref(null)
    /** 登录加载状态 */
    const loading: Ref<boolean> = ref(false)

    // ==================== 计算属性 ====================

    /** 是否已登录 */
    const isLoggedIn = computed(() => !!token.value)
    /** 用户ID */
    const userId = computed(() => userInfo.value?.id ?? 0)
    /** 用户名 */
    const username = computed(() => userInfo.value?.username ?? '')
    /** 真实姓名 */
    const realName = computed(() => userInfo.value?.real_name ?? '')
    /** 邮箱 */
    const email = computed(() => userInfo.value?.email ?? '')
    /** 头像 */
    const avatar = computed(() => userInfo.value?.avatar ?? '')
    /** 账户状态 */
    const status = computed(() => userInfo.value?.status ?? 'active')
    /** 角色列表（角色代码数组） */
    const roles = computed(() => {
      const roleList = userInfo.value?.roles
      if (!roleList) return []
      // 将 Role 对象数组转换为角色代码数组
      return roleList.map((r) => (typeof r === 'string' ? r : r.code))
    })
    /** 权限列表 */
    const permissions = computed(() => userInfo.value?.permissions ?? [])

    // ==================== 方法 ====================

    /**
     * 设置 Token
     */
    const setToken = (accessToken: string, refreshTokenValue?: string) => {
      token.value = accessToken
      if (refreshTokenValue) {
        refreshToken.value = refreshTokenValue
      }
    }

    /**
     * 设置用户信息
     */
    const setUserInfo = (info: FullUserInfo) => {
      userInfo.value = info
      currentUserId.value = info.id
    }

    /**
     * 用户登录
     * @param loginData 登录请求参数
     * @returns 登录是否成功
     */
    const login = async (
      loginData: LoginRequest,
      options?: { silent?: boolean },
    ): Promise<boolean> => {
      loading.value = true
      try {
        const res = await authApi.login(loginData)
        if (res.code === 200) {
          const { access_token, refresh_token, user_info } = res.data
          setToken(access_token, refresh_token)
          setUserInfo(user_info)
          // silent：注册后的自动登录不重复弹「登录成功」，由调用方统一提示
          if (!options?.silent) ElMessage.success('登录成功')
          return true
        }
        // 业务错误（非 200）— 拦截器已经弹过 ElMessage
        return false
      } catch (error: any) {
        // HTTP 错误 — 拦截器已经弹过 ElMessage
        console.error('登录失败:', error?.message || error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 用户注册
     * @param registerData 注册请求参数
     * @returns 注册是否成功
     */
    const register = async (registerData: RegisterRequest): Promise<boolean> => {
      loading.value = true
      try {
        const res = await authApi.register(registerData)
        if (res.code === 200) {
          // 检查响应数据是否包含 token（后端可能直接返回登录信息）
          const data = res.data as any
          // 注册成功的提示统一由调用方(RegisterView)弹出，避免与「自动登录」叠成多条
          if (data.access_token && data.user_info) {
            // 后端直接返回了登录信息，直接保存登录状态
            setToken(data.access_token, data.refresh_token)
            setUserInfo(data.user_info)
            return true
          }
          // 后端只返回用户信息，由调用方决定后续（自动登录）
          return true
        }
        return false
      } catch (error) {
        console.error('注册失败:', error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 用户登出
     */
    const logout = async () => {
      try {
        await authApi.logout(refreshToken.value || undefined)
      } catch (error) {
        console.error('登出请求失败:', error)
      } finally {
        // 清除本地状态
        token.value = ''
        refreshToken.value = ''
        userInfo.value = null
        currentUserId.value = null
        // 清除 Grafana 嵌入门票 cookie（=平台 JWT，无服务端吊销，登出须显式删，免残留）
        document.cookie = 'perf_grafana_token=; path=/api/v1/perf-grafana; SameSite=Lax; max-age=0'
        ElMessage.success('已登出')
      }
    }

    /** 只清理本地会话，供 401/刷新失败时使用，避免再触发登出请求循环。 */
    const clearSession = () => {
      token.value = ''
      refreshToken.value = ''
      userInfo.value = null
      currentUserId.value = null
      document.cookie = 'perf_grafana_token=; path=/api/v1/perf-grafana; SameSite=Lax; max-age=0'
    }

    /**
     * 刷新 Token
     */
    const refreshAccessToken = async (): Promise<boolean> => {
      if (!refreshToken.value) {
        return false
      }
      try {
        const res = await authApi.refreshToken({ refresh_token: refreshToken.value })
        if (res.code === 200) {
          const { access_token, refresh_token } = res.data
          setToken(access_token, refresh_token)
          return true
        }
        return false
      } catch (error) {
        console.error('刷新Token失败:', error)
        // 刷新失败，清除登录状态
        await logout()
        return false
      }
    }

    /**
     * 获取当前用户信息（个人资料）
     * 注意：需要先设置 token 和 currentUserId 才能获取用户信息
     */
    const fetchUserInfo = async (): Promise<boolean> => {
      try {
        // 使用持久化的 currentUserId
        if (!currentUserId.value) {
          console.error('无法获取用户 ID，请先登录')
          return false
        }

        const res = await authApi.getProfile(currentUserId.value)
        if (res.code === 200) {
          setUserInfo(res.data)
          return true
        }
        return false
      } catch (error) {
        console.error('获取用户信息失败:', error)
        return false
      }
    }

    /**
     * 检查是否有指定权限
     * @param permission 权限码
     */
    const hasPermission = (permission: string): boolean => {
      return permissions.value.includes(permission)
    }

    /**
     * 检查是否有指定权限中的任意一个
     * @param permissionList 权限码列表
     */
    const hasAnyPermission = (...permissionList: string[]): boolean => {
      return permissionList.some((p) => permissions.value.includes(p))
    }

    /**
     * 检查是否有指定权限中的全部
     * @param permissionList 权限码列表
     */
    const hasAllPermissions = (...permissionList: string[]): boolean => {
      return permissionList.every((p) => permissions.value.includes(p))
    }

    /**
     * 检查是否有指定角色
     * @param role 角色码
     */
    const hasRole = (role: string): boolean => {
      return roles.value.includes(role)
    }

    /**
     * 检查是否有指定角色中的任意一个
     * @param roleList 角色码列表
     */
    const hasAnyRole = (...roleList: string[]): boolean => {
      return roleList.some((role) => hasRole(role))
    }

    return {
      // 状态
      token,
      refreshToken,
      userInfo,
      loading,
      currentUserId,
      // 计算属性
      isLoggedIn,
      userId,
      username,
      realName,
      email,
      avatar,
      status,
      roles,
      permissions,
      // 方法
      setToken,
      setUserInfo,
      login,
      register,
      logout,
      clearSession,
      refreshAccessToken,
      fetchUserInfo,
      hasPermission,
      hasAnyPermission,
      hasAllPermissions,
      hasRole,
      hasAnyRole,
    }
  },
  {
    // 持久化配置
    persist: {
      // 存储的 key
      key: 'ai-test-platform-user',
      // 存储位置
      storage: localStorage,
      // 只持久化指定状态
      paths: ['token', 'refreshToken', 'currentUserId'],
    },
  },
)
