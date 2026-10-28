/**
 * 系统监控 API —— Celery worker/队列快照（系统级，权限 system:monitor）
 */

import { request } from './request'

export type QueueLevel = 'ok' | 'warn' | 'danger'

export interface CeleryWorker {
  name: string
  alive: boolean
  concurrency: number
  processed: number
  active: number
  queues: string[]
  mem_rss_kb: number
}

export interface CeleryQueue {
  name: string
  backlog: number
  worker_count: number
  has_worker: boolean
  level: QueueLevel
}

export interface CeleryBeatJob {
  name: string
  task: string
  schedule: string
}

export interface CeleryMonitor {
  summary: {
    workers_online: number
    total_concurrency: number
    total_backlog: number
    active_tasks: number
    alerts: number
  }
  workers: CeleryWorker[]
  queues: CeleryQueue[]
  beat_jobs: CeleryBeatJob[]
  degraded: boolean
  inspected_at: string
}

class SystemApi {
  getCeleryMonitor(force = false) {
    return request.get<CeleryMonitor>('/system/celery/monitor', {
      params: { force },
    })
  }
}

export const systemApi = new SystemApi()
