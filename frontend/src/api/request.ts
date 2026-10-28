/**
 * API 请求配置
 *
 * AI 智能测试平台 - Axios 配置
 */

import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
  AxiosError,
} from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

/**
 * 统一响应结构
 */
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

/**
 * 创建 Axios 实例
 */
const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const userStore = useUserStore()
  if (!userStore.refreshToken) return null
  if (!refreshPromise) {
    refreshPromise = axios
      .post(
        `${service.defaults.baseURL}/auth/refresh`,
        { refresh_token: userStore.refreshToken },
        { timeout: 60000 },
      )
      .then((response) => {
        const data = response.data?.data
        if (!data?.access_token || !data?.refresh_token) return null
        userStore.setToken(data.access_token, data.refresh_token)
        return data.access_token as string
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

/**
 * 请求拦截器
 */
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 添加 Token
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  },
)

/**
 * 从错误响应体中提取后端返回的错误信息。
 * 提取不到时返回 null（由调用方按状态码兜底），不再返回占位文案，
 * 以免把「无 message 的错误」统一显示成无意义的通用句。
 */
function extractErrorMessage(error: AxiosError): string | null {
  const responseData = error.response?.data as any

  // 优先业务格式的 message
  if (responseData?.message) {
    return responseData.message
  }

  // FastAPI 的 detail 字段
  if (responseData?.detail) {
    if (typeof responseData.detail === 'string') {
      return responseData.detail
    }
    // detail 是数组（pydantic 校验错误）
    if (Array.isArray(responseData.detail)) {
      return responseData.detail
        .map((d: any) => {
          if (typeof d === 'string') return d
          if (d.loc && d.msg) {
            const field = d.loc[d.loc.length - 1] || '字段'
            return `${field}: ${d.msg}`
          }
          if (d.msg) return d.msg
          return JSON.stringify(d)
        })
        .join('; ')
    }
  }

  // 其它可能的错误字段
  if (responseData?.error) {
    return responseData.error
  }

  return null
}

/**
 * 响应拦截器
 */
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const res = response.data as ApiResponse

    if (res.code === 200) {
      return res as any
    }

    // 拦截器是错误提示的「唯一来源」：统一弹后端 message。
    // 调用方若想自行处理错误文案，给请求 config 传 { silent: true } 关闭本次自动提示，
    // 切勿在 catch 里再 ElMessage.error（否则会重复弹两次）。
    if (!(response.config as any)?.silent) {
      ElMessage.error(res.message || '请求失败')
    }
    return Promise.reject(new Error(res.message || '请求失败'))
  },
  async (error: AxiosError) => {
    // 请求被主动取消（组件卸载 / 防抖中断）——不提示
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject(error)
    }

    // 一、服务器有响应：优先弹后端返回的 message，状态码文案仅作兜底
    if (error.response) {
      const status = error.response.status
      const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
      const isAuthRequest = original?.url?.includes('/auth/login') || original?.url?.includes('/auth/refresh')
      if (status === 401 && original && !original._retry && !isAuthRequest) {
        original._retry = true
        const accessToken = await refreshAccessToken()
        if (accessToken) {
          original.headers.Authorization = `Bearer ${accessToken}`
          return service(original)
        }
        const userStore = useUserStore()
        userStore.clearSession()
        const redirect = `${window.location.pathname}${window.location.search}`
        if (!window.location.pathname.startsWith('/login')) {
          window.location.assign(`/login?redirect=${encodeURIComponent(redirect)}`)
        }
        return Promise.reject(error)
      }
      // silent 只禁止弹窗，401 的刷新与重放仍然必须执行。
      if ((error.config as any)?.silent) {
        return Promise.reject(error)
      }
      const backendMsg = extractErrorMessage(error)
      const fallbackByStatus: Record<number, string> = {
        400: '请求参数有误',
        401: '登录已过期，请重新登录',
        403: '没有权限执行此操作',
        404: '请求的资源不存在',
        405: '请求方法不被允许',
        409: '操作冲突，请刷新后重试',
        422: '提交的数据校验未通过',
        500: '服务器内部错误，请稍后重试',
        502: '网关错误，服务暂不可用',
        503: '服务暂不可用，请稍后重试',
        504: '网关超时，请稍后重试',
      }
      ElMessage.error(backendMsg || fallbackByStatus[status] || `请求失败 (${status})`)
      return Promise.reject(error)
    }

    // 二、无响应：区分「超时」与「连不上服务器」（断网 / 服务未启动 / 跨域被拦截）
    if (error.code === 'ECONNABORTED' || /timeout/i.test(error.message || '')) {
      ElMessage.error('请求超时，请稍后重试')
    } else {
      ElMessage.error('无法连接服务器，请检查网络或服务状态')
    }
    return Promise.reject(error)
  },
)

/**
 * 封装请求方法
 */
export const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.get(url, config)
  },

  post<T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    return service.post(url, data, config)
  },

  put<T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    return service.put(url, data, config)
  },

  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.delete(url, config)
  },

  patch<T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    return service.patch(url, data, config)
  },
}

export default service
