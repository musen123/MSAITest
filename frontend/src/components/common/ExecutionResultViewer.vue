<template>
  <div class="execution-result-viewer">
    <!-- 顶部：用例基本信息 -->
    <div v-if="!hideHeader" class="result-header">
      <div class="header-left">
        <el-tag :type="getStatusType(executionData?.status)" size="large" effect="dark">
          {{ getStatusText(executionData?.status) }}
        </el-tag>
        <span class="case-name">{{ executionData?.case_name || '未知用例' }}</span>
      </div>
      <div class="header-right">
        <span v-if="executionData?.duration" class="duration-text">
          <el-icon><Timer /></el-icon>
          {{ executionData.duration }} ms
        </span>
      </div>
    </div>

    <!-- 执行时间和进度 -->
    <div v-if="!hideHeader && executionData && (executionData.start_time || executionData.end_time)" class="execution-meta">
      <div v-if="executionData.start_time" class="meta-item">
        <el-icon><Clock /></el-icon>
        <span>开始时间: {{ executionData.start_time }}</span>
      </div>
      <div v-if="executionData.end_time" class="meta-item">
        <el-icon><Timer /></el-icon>
        <span>结束时间: {{ executionData.end_time }}</span>
      </div>
    </div>

    <!-- Tab 标签页展示详细信息 -->
    <el-tabs v-if="executionData" v-model="activeTab" class="result-tabs">
      <!-- 请求信息 Tab -->
      <el-tab-pane label="请求信息" name="request">
        <div v-if="executionData.api_request_info?.length" class="request-list">
          <div
            v-for="(request, index) in executionData.api_request_info"
            :key="index"
            class="request-card"
          >
            <div class="request-header" @click="toggleCard(index, 'request')">
              <el-icon class="collapse-icon" :class="{ collapsed: isCardCollapsed(index, 'request') }">
                <ArrowRight />
              </el-icon>
              <span class="request-index">#{{ index + 1 }}</span>
              <el-tag :type="getMethodType(request.method)" size="small">
                {{ request.method }}
              </el-tag>
              <span class="request-name">{{ request.name || `请求 ${index + 1}` }}</span>
              <el-tag
                v-if="request.kind === 'sql'"
                :type="request.status === 'failed' ? 'danger' : 'success'"
                size="small"
                class="status-code"
              >
                {{ request.status === 'failed' ? '失败' : '通过' }}
              </el-tag>
              <el-tag
                v-else
                :type="getResponseStatusType(request.status_code)"
                size="small"
                class="status-code"
              >
                {{ request.status_code || 'N/A' }}
              </el-tag>
            </div>

            <div v-show="!isCardCollapsed(index, 'request')" class="request-content">
              <!-- SQL 步骤：语句 + 参数 + 结果（自包含，无需切到响应 Tab） -->
              <template v-if="request.kind === 'sql'">
                <div class="info-section">
                  <div class="section-title">
                    <el-icon><Document /></el-icon>
                    SQL 语句
                    <span class="section-hint">
                      {{ request.is_write ? '写操作' : '查询' }}
                      <template v-if="request.connection"> · 连接：{{ request.connection }}</template>
                      <template v-if="request.saved_sql_name"> · 全局 SQL：{{ request.saved_sql_name }}</template>
                    </span>
                  </div>
                  <div class="body-editor">
                    <CodeEditor
                      :model-value="request.sql || ''"
                      language="sql"
                      theme="auto"
                      :auto-height="true"
                      :readonly="true"
                      :lineNumbers="true"
                    />
                  </div>
                </div>
                <div v-if="request.params && Object.keys(request.params).length" class="info-section">
                  <div class="section-title"><el-icon><Document /></el-icon> 参数</div>
                  <div class="kv-table">
                    <div v-for="(value, key) in request.params" :key="key" class="kv-row">
                      <span class="kv-key">{{ key }}</span>
                      <span class="kv-value">{{ value }}</span>
                    </div>
                  </div>
                </div>
                <div class="sql-stat" :class="{ 'is-write': request.is_write }">
                  <i class="i-solar-database-bold sql-stat-ic" />
                  <span class="sql-stat-label">{{ request.is_write ? '受影响行数' : '返回行数' }}</span>
                  <span class="sql-stat-value">{{ request.row_count }}</span>
                </div>
                <div v-if="request.rows && request.rows.length" class="info-section">
                  <div class="section-title">
                    <el-icon><Document /></el-icon>
                    返回数据
                    <span v-if="request.row_truncated" class="section-hint">（仅前 {{ request.rows.length }} 行）</span>
                  </div>
                  <div class="sql-table-wrap">
                    <table class="sql-result-table">
                      <thead>
                        <tr><th v-for="col in sqlCols(request.rows)" :key="col">{{ col }}</th></tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, ri) in request.rows" :key="ri">
                          <td v-for="col in sqlCols(request.rows)" :key="col">{{ row[col] }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <div
                  v-if="request.extracts_result && Object.keys(request.extracts_result).length"
                  class="info-section"
                >
                  <div class="section-title"><el-icon><Document /></el-icon> 提取变量</div>
                  <div class="kv-table">
                    <div v-for="(value, key) in request.extracts_result" :key="key" class="kv-row">
                      <span class="kv-key">{{ key }}</span>
                      <span class="kv-value">{{ value }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="request.asserts_result && request.asserts_result.length" class="info-section">
                  <div class="section-title"><el-icon><Document /></el-icon> 断言</div>
                  <div class="sql-assert-list">
                    <div v-for="(a, ai) in request.asserts_result" :key="ai" class="sql-assert-item">
                      <el-tag :type="a.passed ? 'success' : 'danger'" size="small">
                        {{ a.passed ? '通过' : '失败' }}
                      </el-tag>
                      <span class="sql-assert-desc">{{ a.desc }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="request.error_message" class="info-section">
                  <div class="section-title error"><el-icon><WarningFilled /></el-icon> 失败原因</div>
                  <div class="error-content"><pre class="error-message">{{ request.error_message }}</pre></div>
                </div>
              </template>

              <!-- 基础信息（HTTP） -->
              <div v-if="request.kind !== 'sql'" class="info-section">
                <div class="info-row">
                  <span class="info-label">请求地址:</span>
                  <el-text class="info-value url">{{ request.url || 'N/A' }}</el-text>
                  <el-button
                    text
                    size="small"
                    class="curl-btn"
                    @click="copyCurl(request)"
                  >
                    <el-icon><DocumentCopy /></el-icon>
                    复制 cURL
                  </el-button>
                </div>
              </div>

              <!-- 请求头 -->
              <div v-if="request.headers && Object.keys(request.headers).length" class="info-section">
                <div class="section-title">
                  <el-icon><Document /></el-icon>
                  请求头
                </div>
                <div class="kv-table">
                  <div
                    v-for="(value, key) in request.headers"
                    :key="key"
                    class="kv-row"
                  >
                    <span class="kv-key">{{ key }}</span>
                    <span class="kv-value">{{ value }}</span>
                  </div>
                </div>
              </div>

              <!-- 实际发出的请求头（含 requests 自动补的 Content-Length/Authorization/Cookie） -->
              <div
                v-if="request.sent_headers && Object.keys(request.sent_headers).length"
                class="info-section"
              >
                <div class="section-title">
                  <el-icon><Document /></el-icon>
                  实际请求头
                  <span class="section-hint">（真正发出，含自动补充的头）</span>
                </div>
                <div class="kv-table">
                  <div
                    v-for="(value, key) in request.sent_headers"
                    :key="key"
                    class="kv-row"
                  >
                    <span class="kv-key">{{ key }}</span>
                    <span class="kv-value">{{ value }}</span>
                  </div>
                </div>
              </div>

              <!-- 查询参数（HTTP） -->
              <div
                v-if="request.kind !== 'sql' && request.params && Object.keys(request.params).length"
                class="info-section"
              >
                <div class="section-title">
                  <el-icon><Document /></el-icon>
                  查询参数
                </div>
                <div class="kv-table">
                  <div
                    v-for="(value, key) in request.params"
                    :key="key"
                    class="kv-row"
                  >
                    <span class="kv-key">{{ key }}</span>
                    <span class="kv-value">{{ value }}</span>
                  </div>
                </div>
              </div>

              <!-- 请求体 -->
              <div v-if="request.body" class="info-section">
                <div class="section-title">
                  <el-icon><Document /></el-icon>
                  请求体
                </div>
                <div class="body-editor">
                  <CodeEditor
                    :model-value="formatJson(request.body)"
                    language="json"
                    theme="light"
                    :minHeight="'120px'"
                    :maxHeight="'250px'"
                    :readonly="true"
                    :lineNumbers="true"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无请求信息" :image-size="60" />
      </el-tab-pane>

      <!-- 响应信息 Tab -->
      <el-tab-pane label="响应信息" name="response">
        <div v-if="executionData.api_request_info?.length" class="response-list">
          <div
            v-for="(request, index) in executionData.api_request_info"
            :key="index"
            class="response-card"
          >
            <div class="response-header" @click="toggleCard(index, 'response')">
              <el-icon class="collapse-icon" :class="{ collapsed: isCardCollapsed(index, 'response') }">
                <ArrowRight />
              </el-icon>
              <span class="request-index">#{{ index + 1 }}</span>
              <el-tag :type="getMethodType(request.method)" size="small">
                {{ request.method }}
              </el-tag>
              <span class="request-name">{{ request.name || `请求 ${index + 1}` }}</span>
              <el-tag
                v-if="request.kind === 'sql'"
                :type="request.status === 'failed' ? 'danger' : 'success'"
                size="small"
                class="status-code"
              >
                {{ request.status === 'failed' ? '失败' : '通过' }}
              </el-tag>
              <el-tag
                v-else
                :type="getResponseStatusType(request.status_code)"
                size="small"
                class="status-code"
              >
                {{ request.status_code || 'N/A' }} {{ getStatusTextByCode(request.status_code) }}
              </el-tag>
              <span v-if="request.duration_ms != null" class="req-duration">
                {{ request.duration_ms }}ms
              </span>
            </div>

            <div v-show="!isCardCollapsed(index, 'response')" class="response-content">
              <!-- SQL 步骤结果：行数/受影响 + 返回数据 + 提取 + 断言 -->
              <template v-if="request.kind === 'sql'">
                <div class="sql-stat" :class="{ 'is-write': request.is_write }">
                  <i class="i-solar-database-bold sql-stat-ic" />
                  <span class="sql-stat-label">{{ request.is_write ? '受影响行数' : '返回行数' }}</span>
                  <span class="sql-stat-value">{{ request.row_count }}</span>
                </div>
                <div v-if="request.rows && request.rows.length" class="info-section">
                  <div class="section-title">
                    <el-icon><Document /></el-icon>
                    返回数据
                    <span v-if="request.row_truncated" class="section-hint">（仅前 {{ request.rows.length }} 行）</span>
                  </div>
                  <div class="sql-table-wrap">
                    <table class="sql-result-table">
                      <thead>
                        <tr><th v-for="col in sqlCols(request.rows)" :key="col">{{ col }}</th></tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, ri) in request.rows" :key="ri">
                          <td v-for="col in sqlCols(request.rows)" :key="col">{{ row[col] }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <div
                  v-if="request.extracts_result && Object.keys(request.extracts_result).length"
                  class="info-section"
                >
                  <div class="section-title"><el-icon><Document /></el-icon> 提取变量</div>
                  <div class="kv-table">
                    <div v-for="(value, key) in request.extracts_result" :key="key" class="kv-row">
                      <span class="kv-key">{{ key }}</span>
                      <span class="kv-value">{{ value }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="request.asserts_result && request.asserts_result.length" class="info-section">
                  <div class="section-title"><el-icon><Document /></el-icon> 断言</div>
                  <div class="sql-assert-list">
                    <div
                      v-for="(a, ai) in request.asserts_result"
                      :key="ai"
                      class="sql-assert-item"
                    >
                      <el-tag :type="a.passed ? 'success' : 'danger'" size="small">
                        {{ a.passed ? '通过' : '失败' }}
                      </el-tag>
                      <span class="sql-assert-desc">{{ a.desc }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="request.error_message" class="info-section">
                  <div class="section-title error"><el-icon><WarningFilled /></el-icon> 失败原因</div>
                  <div class="error-content"><pre class="error-message">{{ request.error_message }}</pre></div>
                </div>
              </template>

              <!-- 响应状态（HTTP） -->
              <div v-if="request.kind !== 'sql'" class="info-section">
                <div class="info-row">
                  <span class="info-label">响应状态:</span>
                  <el-tag
                    :type="getResponseStatusType(request.status_code)"
                    size="small"
                  >
                    {{ request.status_code || 'N/A' }} {{ getStatusTextByCode(request.status_code) }}
                  </el-tag>
                  <span v-if="request.duration_ms != null" class="req-duration">
                    耗时 {{ request.duration_ms }}ms
                  </span>
                </div>
              </div>

              <!-- 响应头 -->
              <div
                v-if="request.response_headers && Object.keys(request.response_headers).length"
                class="info-section"
              >
                <div class="section-title">
                  <el-icon><Document /></el-icon>
                  响应头
                </div>
                <pre class="resp-headers">{{
                  Object.entries(request.response_headers)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join('\n')
                }}</pre>
              </div>

              <!-- 错误信息（HTTP） -->
              <div v-if="request.kind !== 'sql' && request.error_message" class="info-section">
                <div class="section-title error">
                  <el-icon><WarningFilled /></el-icon>
                  错误信息
                </div>
                <div class="error-content">
                  <pre class="error-message">{{ request.error_message }}</pre>
                </div>
              </div>

              <!-- 响应体 -->
              <div v-if="request.response_body" class="info-section">
                <div class="section-title">
                  <el-icon><Document /></el-icon>
                  响应内容
                </div>
                <div class="body-editor">
                  <CodeEditor
                    :model-value="formatJson(request.response_body)"
                    language="json"
                    theme="light"
                    :minHeight="'150px'"
                    :maxHeight="'400px'"
                    :readonly="true"
                    :lineNumbers="true"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无响应信息" :image-size="60" />
      </el-tab-pane>

      <!-- 执行日志 Tab -->
      <el-tab-pane label="执行日志" name="logs">
        <div v-if="executionData.logs?.length" class="logs-container">
          <div class="logs-header">
            <span>共 {{ executionData.logs.length }} 条日志</span>
            <el-button-group size="small">
              <el-button @click="filterLogLevel('all')" :type="logFilter === 'all' ? 'primary' : ''">全部</el-button>
              <el-button @click="filterLogLevel('info')" :type="logFilter === 'info' ? 'primary' : ''">INFO</el-button>
              <el-button @click="filterLogLevel('warning')" :type="logFilter === 'warning' ? 'primary' : ''">WARNING</el-button>
              <el-button @click="filterLogLevel('error')" :type="logFilter === 'error' ? 'primary' : ''">ERROR</el-button>
            </el-button-group>
          </div>
          <div class="logs-content">
            <div
              v-for="(log, index) in filteredLogs"
              :key="index"
              class="log-item"
              :class="log.level"
            >
              <span class="log-index">{{ index + 1 }}</span>
              <span class="log-level" :class="log.level">{{ log.level.toUpperCase() }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无执行日志" :image-size="60" />
      </el-tab-pane>
    </el-tabs>

    <!-- 错误堆栈（放在最后） -->
    <div v-if="executionData?.error_traceback" class="error-traceback-section">
      <div class="section-title error">
        <el-icon><WarningFilled /></el-icon>
        <span>错误堆栈</span>
      </div>
      <div class="error-content">
        <pre class="error-traceback">{{ executionData.error_traceback }}</pre>
      </div>
    </div>

    <!-- 无数据提示 -->
    <el-empty
      v-if="!executionData"
      description="暂无执行结果"
      :image-size="80"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document,
  WarningFilled,
  Clock,
  Timer,
  ArrowRight,
  DocumentCopy,
} from '@element-plus/icons-vue'
import CodeEditor from './CodeEditor.vue'

/**
 * 执行汇总数据
 */
interface ExecutionSummary {
  total?: number
  pass?: number
  fail?: number
  error?: number
  skip?: number
  duration?: number
}

/**
 * 单个 API 请求信息
 */
interface ApiRequestInfo {
  interface_id?: number
  name?: string
  url?: string
  method?: string
  headers?: Record<string, string>
  params?: Record<string, string>
  body?: any
  status_code?: number
  response_body?: any
  duration_ms?: number | null
  response_headers?: Record<string, string>
  sent_headers?: Record<string, string>
  error_message?: string | null
  // —— SQL 步骤（kind='sql'）专属字段 ——
  kind?: string
  sql?: string
  connection?: string
  saved_sql_name?: string | null
  is_write?: boolean
  row_count?: number
  rows?: Record<string, any>[]
  row_truncated?: boolean
  extracts_result?: Record<string, any>
  asserts_result?: { desc: string; passed: boolean }[]
  status?: string
}

/**
 * 日志条目
 */
interface LogItem {
  level: string
  message: string
  timestamp?: string
}

/**
 * 执行结果详情
 */
interface ExecutionResultDetail {
  case_name?: string
  case_id?: string
  status?: string
  start_time?: string | null
  end_time?: string | null
  duration?: number
  api_request_info?: ApiRequestInfo[]
  error_message?: string
  error_traceback?: string
  logs?: LogItem[]
}

/**
 * 完整的执行结果（包含 summary 和 result）
 */
interface ExecutionResultData {
  summary?: ExecutionSummary
  result?: ExecutionResultDetail
}

// Props - 支持两种模式：
// 1. 传入 summary 和 result 分开的两个 prop（兼容旧用法）
// 2. 传入完整的 executionData（包含 summary 和 result）
interface Props {
  summary?: ExecutionSummary
  result?: ExecutionResultDetail
  executionData?: ExecutionResultData
  /** 隐藏顶部用例标题/状态/时间栏，只保留请求/响应/日志三 Tab（如业务流构建结果里每步的详情——标题状态已由外层步骤行展示） */
  hideHeader?: boolean
}

const props = withDefaults(defineProps<Props>(), {})

// 计算执行数据
const executionData = computed(() => {
  // 如果有 executionData，直接使用
  if (props.executionData?.result) {
    return props.executionData.result
  }
  // 否则使用 result prop
  return props.result
})

// 计算汇总数据
const summary = computed(() => {
  // 如果有 executionData，从中提取
  if (props.executionData?.summary) {
    return props.executionData.summary
  }
  // 否则使用 summary prop
  return props.summary
})

// State
const activeTab = ref('request')
const logFilter = ref<'all' | 'info' | 'warning' | 'error'>('all')

// 折叠状态管理
const collapsedCards = ref<Record<string, boolean>>({})

const toggleCard = (index: number, type: 'request' | 'response') => {
  const key = `${type}-${index}`
  collapsedCards.value[key] = !collapsedCards.value[key]
}

const isCardCollapsed = (index: number, type: 'request' | 'response') => {
  const key = `${type}-${index}`
  return collapsedCards.value[key] ?? false
}

// 用记录的请求信息拼一条可复现的 cURL（排查"实际发的和以为的对不上"用）
const buildCurl = (req: ApiRequestInfo): string => {
  const q = (s: string) => `'${String(s).replace(/'/g, "'\\''")}'`
  let url = req.url || ''
  const params = req.params || {}
  const qs = Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&')
  if (qs) url += (url.includes('?') ? '&' : '?') + qs
  const parts = [`curl -X ${(req.method || 'GET').toUpperCase()} ${q(url)}`]
  for (const [k, v] of Object.entries(req.headers || {})) {
    parts.push(`-H ${q(`${k}: ${v}`)}`)
  }
  if (req.body && (typeof req.body !== 'object' || Object.keys(req.body).length)) {
    const data = typeof req.body === 'string' ? req.body : JSON.stringify(req.body)
    parts.push(`-d ${q(data)}`)
  }
  return parts.join(' \\\n  ')
}

const copyCurl = async (req: ApiRequestInfo) => {
  try {
    await navigator.clipboard.writeText(buildCurl(req))
    ElMessage.success('cURL 已复制')
  } catch {
    ElMessage.error('复制失败，请检查浏览器剪贴板权限')
  }
}

// Methods
const getStatusType = (status?: string) => {
  const types: Record<string, string> = {
    pass: 'success',
    passed: 'success',
    fail: 'danger',
    failed: 'danger',
    error: 'danger',
    skip: 'warning',
    skipped: 'warning',
    success: 'success',
  }
  return types[status || ''] || 'info'
}

const getStatusText = (status?: string) => {
  const texts: Record<string, string> = {
    pass: '通过',
    passed: '通过',
    fail: '失败',
    failed: '失败',
    error: '错误',
    skip: '跳过',
    skipped: '跳过',
    success: '成功',
  }
  return texts[status || ''] || status || '未知'
}

const getStatusTextByCode = (code?: number) => {
  if (!code) return ''
  if (code >= 200 && code < 300) return 'OK'
  if (code >= 400 && code < 500) return 'Client Error'
  if (code >= 500) return 'Server Error'
  return ''
}

const getMethodType = (method?: string) => {
  const types: Record<string, string> = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'warning',
    SQL: 'warning',
  }
  return types[method?.toUpperCase()] || 'info'
}

/** SQL 返回数据表的列名（取首行的键，各行结构一致） */
const sqlCols = (rows?: Record<string, any>[]) =>
  rows && rows.length ? Object.keys(rows[0]) : []

const getResponseStatusType = (code?: number) => {
  if (!code) return 'info'
  if (code >= 200 && code < 300) return 'success'
  if (code >= 400 && code < 500) return 'warning'
  if (code >= 500) return 'danger'
  return 'info'
}

const formatDuration = (duration?: number) => {
  if (!duration) return '0ms'
  if (duration < 1) return `${(duration * 1000).toFixed(0)}ms`
  return `${duration.toFixed(2)}s`
}

const formatJson = (data: any) => {
  if (!data) return ''
  if (typeof data === 'string') {
    try {
      return JSON.stringify(JSON.parse(data), null, 2)
    } catch {
      return data
    }
  }
  return JSON.stringify(data, null, 2)
}

const filterLogLevel = (level: 'all' | 'info' | 'warning' | 'error') => {
  logFilter.value = level
}

const filteredLogs = computed(() => {
  if (!executionData.value?.logs) return []
  if (logFilter.value === 'all') return executionData.value.logs
  return executionData.value.logs.filter(log => log.level === logFilter.value)
})
</script>

<style scoped lang="scss">
.execution-result-viewer {
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    background: linear-gradient(135deg, var(--el-fill-color-extra-light) 0%, var(--el-fill-color-light) 100%);
    border-radius: 12px;
    margin-bottom: 16px;
    border: 1px solid var(--el-border-color-light);

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .case-name {
        font-size: 16px;
        font-weight: 600;
        color: var(--theme-text-strong);
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 16px;

      .duration-text {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;
        color: var(--el-text-color-secondary);

        .el-icon {
          color: var(--theme-color-3b82f6);
        }
      }
    }
  }

  .execution-meta {
    display: flex;
    gap: 24px;
    padding: 12px 16px;
    background: var(--el-fill-color-extra-light);
    border-radius: 8px;
    margin-bottom: 16px;

    .meta-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--el-text-color-secondary);

      .el-icon {
        color: var(--el-color-primary);
      }
    }
  }

  .result-tabs {
    :deep(.el-tabs__header) {
      margin-bottom: 16px;
    }

    :deep(.el-tabs__nav-wrap::after) {
      height: 1px;
    }

    :deep(.el-tabs__item) {
      font-size: 14px;
      font-weight: 500;
      padding: 0 20px;
      height: 40px;
      line-height: 40px;

      &.is-active {
        color: var(--el-color-primary);
      }
    }

    :deep(.el-tabs__active-bar) {
      height: 2px;
    }
  }

  .request-list,
  .response-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .request-card,
  .response-card {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    overflow: hidden;

    .request-header,
    .response-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 16px;
      background: var(--el-fill-color-extra-light);
      border-bottom: 1px solid var(--el-border-color-light);
      cursor: pointer;
      user-select: none;
      transition: background-color 0.2s;

      &:hover {
        background: var(--el-fill-color-light);
      }

      .collapse-icon {
        font-size: 14px;
        color: var(--el-text-color-secondary);
        transition: transform 0.2s;
        flex-shrink: 0;

        &.collapsed {
          transform: rotate(0deg);
        }

        &:not(.collapsed) {
          transform: rotate(90deg);
        }
      }

      .request-index {
        font-size: 12px;
        color: var(--theme-color-94a3b8);
        font-weight: 600;
      }

      .request-name {
        font-weight: 500;
        color: var(--theme-text-strong);
      }

      .status-code {
        margin-left: 4px;
      }
    }

    .request-content,
    .response-content {
      padding: 16px;
    }
  }

  .req-duration {
    margin-left: 8px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    font-variant-numeric: tabular-nums;
  }

  .curl-btn {
    margin-left: auto;
    flex-shrink: 0;
    color: var(--el-color-primary);

    .el-icon {
      margin-right: 2px;
    }
  }

  .section-hint {
    font-size: 12px;
    font-weight: 400;
    color: var(--el-text-color-secondary);
  }

  .resp-headers {
    margin: 0;
    padding: 10px 12px;
    background: var(--el-fill-color-light);
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--el-text-color-regular);
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 220px;
    overflow-y: auto;
  }

  .info-section {
    margin-bottom: 16px;

    &:last-child {
      margin-bottom: 0;
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
      color: var(--el-text-color-regular);
      margin-bottom: 10px;

      .el-icon {
        color: var(--el-color-primary);
      }

      &.error .el-icon {
        color: var(--el-color-danger);
      }
    }

    .info-row {
      display: flex;
      align-items: flex-start;
      gap: 8px;

      .info-label {
        font-size: 13px;
        font-weight: 500;
        color: var(--el-text-color-secondary);
        min-width: 70px;
      }

      .info-value {
        font-size: 13px;
        color: var(--theme-text-strong);

        &.url {
          font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
          word-break: break-all;
          background: var(--el-fill-color-extra-light);
          padding: 8px 12px;
          border-radius: 4px;
        }
      }
    }

    .kv-table {
      background: var(--el-fill-color-extra-light);
      border-radius: 6px;
      padding: 8px 12px;

      .kv-row {
        display: flex;
        font-size: 12px;
        font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
        padding: 4px 0;

        .kv-key {
          color: var(--el-text-color-secondary);
          min-width: 120px;
          flex-shrink: 0;
        }

        .kv-value {
          color: var(--theme-text-strong);
          word-break: break-all;
        }
      }
    }

    .body-editor {
      max-height: 240px;
      overflow: auto;

      :deep(.code-editor) {
        border: 1px solid var(--el-border-color-light);
        border-radius: 6px;
      }
    }

    .error-content {
      background: var(--el-color-danger-light-9);
      border: 1px solid var(--el-color-danger-light-7);
      border-radius: 6px;
      padding: 12px;

      .error-message,
      .error-traceback {
        font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
        font-size: 12px;
        color: var(--el-color-danger-dark-2);
        white-space: pre-wrap;
        word-break: break-all;
        margin: 0;
        line-height: 1.6;
        max-height: 300px;
        overflow-y: auto;
      }
    }
  }

  .assertion-content {
    .assertion-error {
      max-height: 400px;
      overflow-y: auto;

      .error-traceback,
      .error-message {
        font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
        font-size: 12px;
        color: var(--el-color-danger-dark-2);
        white-space: pre-wrap;
        word-break: break-all;
        margin: 12px 0 0 0;
        line-height: 1.6;
      }
    }
  }

  .error-traceback-section {
    margin-top: 16px;

    .section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 600;
      color: var(--el-text-color-regular);
      margin-bottom: 12px;

      &.error {
        color: var(--el-color-danger);

        .el-icon {
          color: var(--el-color-danger);
        }
      }

      .el-icon {
        color: var(--el-color-primary);
      }
    }

    .error-content {
      background: var(--el-color-danger-light-9);
      border: 1px solid var(--el-color-danger-light-7);
      border-radius: 8px;
      padding: 12px;
      max-height: 400px;
      overflow-y: auto;

      .error-traceback {
        font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
        font-size: 12px;
        color: var(--el-color-danger-dark-2);
        white-space: pre-wrap;
        word-break: break-all;
        margin: 0;
        line-height: 1.6;
      }
    }
  }

  .logs-container {
    .logs-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
      padding: 8px 12px;
      background: var(--el-fill-color-extra-light);
      border-radius: 6px;

      span {
        font-size: 13px;
        color: var(--el-text-color-secondary);
      }
    }

    .logs-content {
      background: var(--theme-text-strong);
      border-radius: 8px;
      padding: 12px;
      max-height: 500px;
      overflow-y: auto;
      font-family: 'Monaco', 'Menlo', 'Courier New', monospace;

      .log-item {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        font-size: 12px;
        padding: 6px 0;
        border-bottom: 1px solid rgba(var(--theme-rgb-white), 0.05);

        &:last-child {
          border-bottom: none;
        }

        .log-index {
          flex-shrink: 0;
          min-width: 30px;
          color: var(--el-text-color-secondary);
          font-size: 10px;
        }

        .log-level {
          flex-shrink: 0;
          min-width: 60px;
          font-weight: 600;
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 3px;
          text-align: center;

          &.info {
            background: rgba(var(--theme-rgb-59-130-246), 0.2);
            color: var(--theme-color-60a5fa);
          }

          &.success {
            background: rgba(var(--theme-rgb-primary), 0.2);
            color: var(--el-color-primary-light-3);
          }

          &.warning {
            background: rgba(var(--theme-rgb-251-191-36), 0.2);
            color: var(--el-color-warning);
          }

          &.error {
            background: rgba(var(--theme-rgb-danger), 0.2);
            color: var(--el-color-danger-light-3);
          }

          &.debug {
            background: rgba(var(--theme-rgb-148-163-184), 0.2);
            color: var(--theme-color-94a3b8);
          }
        }

        .log-message {
          color: var(--el-border-color-light);
          word-break: break-all;
          white-space: pre-wrap;
          line-height: 1.5;
          flex: 1;
        }
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .execution-result-viewer {
    .result-header {
      flex-direction: column;
      gap: 12px;

      .header-left {
        width: 100%;
        justify-content: center;
        flex-wrap: wrap;
      }

      .header-right {
        width: 100%;
        justify-content: center;
      }
    }

    .execution-meta {
      flex-direction: column;
      gap: 8px;
    }
  }
}

/* ==================== SQL 步骤展示 ==================== */
// 返回/受影响行数：紧凑统计条，替代裸文字
.sql-stat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  margin-bottom: 16px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  font-size: 13px;

  .sql-stat-ic {
    font-size: 14px;
    color: var(--el-color-primary);
  }
  .sql-stat-label {
    color: var(--el-text-color-secondary);
  }
  .sql-stat-value {
    font-weight: 700;
    font-size: 15px;
    color: var(--el-color-primary);
    font-variant-numeric: tabular-nums;
  }

  // 写操作用告警色，与查询区分
  &.is-write {
    background: var(--el-color-warning-light-9);
    border-color: var(--el-color-warning-light-7);
    .sql-stat-ic,
    .sql-stat-value {
      color: var(--el-color-warning);
    }
  }
}

.sql-table-wrap {
  overflow: auto;
  max-height: 300px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.sql-result-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 12px;

  th,
  td {
    padding: 7px 12px;
    text-align: left;
    border-bottom: 1px solid var(--el-border-color-lighter);
    white-space: nowrap;
  }
  th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--el-fill-color-light);
    font-weight: 700;
    color: var(--el-text-color-primary);
    // sticky 表头下边线（border 在 sticky 下会滚掉，用 box-shadow 补）
    box-shadow: inset 0 -1px 0 var(--el-border-color-light);
    border-bottom: none;
  }
  td {
    color: var(--el-text-color-primary);
    font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  }
  tbody tr:nth-child(even) td {
    background: var(--el-fill-color-lighter);
  }
  tbody tr:hover td {
    background: var(--el-fill-color-light);
  }
  tbody tr:last-child td {
    border-bottom: none;
  }
}
.sql-assert-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sql-assert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-extra-light);
}
.sql-assert-desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
