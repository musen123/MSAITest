import request from './request'

/**
 * 获取操作日志列表
 */
export const getOperationLogs = (params: {
  page: number
  page_size: number
  module?: string
  action?: string
  start_time?: number
  end_time?: number
}) => {
  return request({
    url: '/logs/operation-logs',
    method: 'get',
    params
  })
}

/**
 * 获取操作日志详情
 */
export const getOperationLogDetail = (logId: number) => {
  return request({
    url: `/logs/operation-logs/${logId}`,
    method: 'get'
  })
}

/**
 * 获取操作日志筛选选项
 */
export const getOperationLogOptions = () => {
  return request({
    url: '/logs/operation-logs/options',
    method: 'get'
  })
}

/**
 * 操作日志统计响应（后端聚合接口约定）
 *
 * 约定接口路径：GET /logs/operation-logs/stats
 * Query 参数：
 *   - start_time?: number  // Unix 秒；不传时由后端按业务默认值（如"今日 0 点起"）
 *   - end_time?:   number  // Unix 秒；不传时取当前时间
 *
 * 期望返回 data 字段：
 *   {
 *     total:    number    // 当前区间操作总数
 *     users:    number    // 不重复的操作用户数
 *     actions:  number    // 不重复的操作类型数
 *     abnormal: number    // 异常操作数（response_status >= 400）
 *     // 趋势字段（可选，后端可一并算好后返回，便于前端展示"较昨日 ↑X%"）
 *     prev_total?:    number
 *     prev_users?:    number
 *     prev_actions?:  number
 *     prev_abnormal?: number
 *   }
 */
export interface OperationLogStats {
  total: number
  users: number
  actions: number
  abnormal: number
  prev_total?: number
  prev_users?: number
  prev_actions?: number
  prev_abnormal?: number
}

/**
 * 获取操作日志聚合统计（约定接口，需后端实现）
 */
export const getOperationLogStats = (params?: {
  start_time?: number
  end_time?: number
}) => {
  return request<OperationLogStats>({
    url: '/logs/operation-logs/stats',
    method: 'get',
    params,
  })
}
