import dayjs from 'dayjs'

export const formatDate = (date: string | Date, format: string = 'YYYY-MM-DD HH:mm') => {
  return dayjs(date).format(format)
}

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

export const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
}

/**
 * 将可能是 JSON 数组、换行/序号分隔的字符串解析为字符串数组
 * 用于把 AI 生成时是 list、存储后变成字符串的字段还原为可结构化展示的形式
 */
export const parseListField = (raw: string | undefined | null): string[] => {
  if (raw == null) return []
  const trimmed = String(raw).trim()
  if (!trimmed) return []

  // 1. JSON 数组
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return parsed.map(v => (v == null ? '' : String(v))).filter(s => s.length > 0)
      }
    } catch { /* fallthrough */ }
  }

  // 2. 多行 / 序号分隔
  const lines = trimmed
    .split(/\r?\n/)
    .map(line => line.replace(/^\s*(?:[-*•·]|\d+[.)、])\s*/, '').trim())
    .filter(line => line.length > 0)

  return lines
}

/** 将字段统一为字符串（避免 undefined/None 显示） */
export const safeStr = (v: unknown): string => {
  if (v == null) return ''
  return String(v)
}
