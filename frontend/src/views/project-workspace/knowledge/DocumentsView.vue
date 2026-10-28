<template>
  <div class="documents-view">
    <AppPageHeader
      icon="i-app-knowledge"
      :illustration="illustAiKnowledge"
      title="内容管理"
      description="管理项目知识库文档 —— 上传后自动解析、分块、向量化（自研检索引擎）"
    >
      <template #actions>
        <el-button v-permission="'knowledge:manage'" type="danger" plain @click="showClearDialog = true">
          <i class="i-solar-trash-bin-trash-bold mr-1" />
          清空
        </el-button>
        <el-button v-permission="'knowledge:manage'" type="primary" @click="showUploadDialog = true">
          <i class="i-solar-upload-bold mr-1" />
          上传文档
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 状态统计 -->
    <div class="stat-row">
      <AppStatCard
        label="全部"
        :value="getCount('all')"
        icon-name="i-solar-folder-with-files-bold"
        color="brand"
      />
      <AppStatCard
        label="已就绪"
        :value="getCount('ready')"
        icon-name="i-solar-check-circle-bold"
        color="success"
      />
      <AppStatCard
        label="处理中"
        :value="processingCount"
        icon-name="i-solar-refresh-circle-bold"
        color="warning"
      />
      <AppStatCard
        label="等待中"
        :value="getCount('pending')"
        icon-name="i-solar-clock-circle-bold"
        color="info"
      />
      <AppStatCard
        label="失败"
        :value="getCount('failed')"
        icon-name="i-solar-danger-triangle-bold"
        color="danger"
      />
    </div>

    <!-- 筛选 + 列表 -->
    <AppSectionCard padless class="docs-card">
      <div class="filter-bar">
        <button
          class="status-pill"
          :class="{ active: !statusFilter }"
          @click="setFilter('')"
        >
          全部（{{ getCount('all') }}）
        </button>
        <button
          v-for="s in statusOptions"
          :key="s.value"
          class="status-pill"
          :class="[s.cls, { active: statusFilter === s.value }]"
          @click="setFilter(s.value)"
        >
          {{ s.label }}（{{ getCount(s.value) }}）
        </button>
        <el-select
          v-model="docTypeFilter"
          class="type-select"
          placeholder="全部类型"
          clearable
          size="default"
          @change="onFilterChange"
        >
          <el-option
            v-for="t in docTypeOptions"
            :key="t.value"
            :label="t.label"
            :value="t.value"
          />
        </el-select>
        <el-input
          v-model="keyword"
          class="keyword-input"
          placeholder="搜索文件名"
          clearable
          @keyup.enter="onFilterChange"
          @clear="onFilterChange"
        >
          <template #prefix><i class="i-solar-magnifer-linear" /></template>
        </el-input>
        <div class="filter-spacer" />
        <el-button
          v-permission="'knowledge:manage'"
          size="default"
          plain
          :loading="batchExtracting"
          @click="handleExtractBatch"
        >
          <i class="i-solar-graph-new-linear mr-1" />
          批量提取图谱
        </el-button>
        <button class="refresh-btn" @click="fetchData" title="刷新">
          <i class="i-solar-refresh-bold" />
        </button>
      </div>

      <!-- 文档列表 -->
      <div v-loading="loading" class="doc-list">
        <AppEmpty
          v-if="!loading && documents.length === 0"
          scene="data"
          title="暂无文档"
          description="上传需求/接口/设计等项目文档，入库后即可被检索与 AI 助手引用"
        >
          <template #actions>
            <el-button v-permission="'knowledge:manage'" type="primary" @click="showUploadDialog = true">
              <i class="i-solar-upload-bold mr-1" />
              上传文档
            </el-button>
          </template>
        </AppEmpty>

        <div v-else>
          <div v-for="doc in documents" :key="doc.id" class="doc-card">
            <div class="doc-main">
              <div class="doc-icon">
                <i class="i-solar-document-text-bold" />
              </div>
              <div class="doc-info">
                <div class="doc-name">
                  {{ doc.file_name }}
                  <span v-if="doc.truncated" class="trunc-badge" title="文档超长，解析时已截断尾部">已截断</span>
                </div>
                <div class="doc-meta">
                  <span class="type-tag">{{ docTypeLabel(doc.doc_type) }}</span>
                  <span v-if="doc.source_type === 'func_doc'" class="src-tag">来自项目文档</span>
                  <span><i class="i-solar-archive-linear mr-1" />{{ formatFileSize(doc.file_size) }}</span>
                  <span v-if="doc.chunk_count">
                    <i class="i-solar-hashtag-square-linear mr-1" />{{ doc.chunk_count }} 个分块
                  </span>
                  <span><i class="i-solar-clock-circle-linear mr-1" />{{ formatDate(doc.created_at) }}</span>
                </div>
                <div v-if="doc.error_message" class="doc-error">{{ doc.error_message }}</div>
              </div>
            </div>
            <div class="doc-actions">
              <span
                v-if="doc.graph_status && doc.graph_status !== 'none'"
                class="graph-tag"
                :class="`gs-${doc.graph_status}`"
                :title="doc.entity_count ? `贡献 ${doc.entity_count} 个实体` : ''"
                @click="doc.graph_task_id && goGraphTask(doc)"
              >
                <i class="i-solar-graph-new-linear" />
                {{ graphStatusLabel(doc.graph_status) }}
              </span>
              <span class="status-tag" :class="`st-${(doc.status || '').toLowerCase()}`">
                <span class="status-dot" />
                {{ getStatusLabel(doc.status) }}
              </span>
              <button
                v-if="doc.ai_task_id && doc.status !== 'ready'"
                class="icon-btn"
                title="查看入库任务进度"
                @click="goTask(doc)"
              >
                <i class="i-solar-eye-linear" />
              </button>
              <button
                v-if="doc.status === 'ready'"
                v-permission="'knowledge:manage'"
                class="icon-btn"
                :title="doc.graph_status === 'extracted' ? '重新提取图谱（内容未变会自动跳过）' : '提取图谱'"
                :disabled="extractingIds.has(doc.id)"
                @click="handleExtract(doc)"
              >
                <i class="i-solar-graph-new-linear" />
              </button>
              <button v-permission="'knowledge:manage'" class="icon-btn danger" @click="handleDelete(doc)" title="删除">
                <i class="i-solar-trash-bin-trash-linear" />
              </button>
            </div>
          </div>

          <!-- 分页 -->
          <el-pagination
            v-if="total > 0"
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            background
            @size-change="fetchData"
            @current-change="fetchData"
          />
        </div>
      </div>
    </AppSectionCard>

    <!-- 上传弹框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传文档"
      width="520px"
      @close="resetUpload"
    >
      <div class="upload-form">
        <div class="form-row">
          <span class="form-label">文档类型</span>
          <el-select v-model="uploadDocType" class="form-control" placeholder="选择文档类型">
            <el-option
              v-for="t in docTypeOptions"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
        </div>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="5"
          :on-change="handleFileChange"
          :file-list="fileList"
          multiple
          drag
        >
          <i class="i-solar-cloud-upload-bold upload-icon" />
          <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">
              支持 PDF / Word / TXT / Markdown / 图片，单次最多 5 个文件；
              上传后自动解析分块向量化，进度可在任务中心查看
            </div>
          </template>
        </el-upload>
      </div>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleSubmitUpload">
          {{ uploading ? '提交中...' : '开始上传' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 清空确认弹框 -->
    <el-dialog
      v-model="showClearDialog"
      title="清空文档"
      width="460px"
      :close-on-click-modal="false"
    >
      <div class="clear-dialog-body">
        <div class="clear-warning-icon">
          <i class="i-solar-danger-triangle-bold" />
        </div>
        <p class="clear-desc">此操作将删除本项目全部知识库文档及其分块索引</p>
        <p class="clear-danger">警告：此操作不可恢复！</p>
        <p class="clear-desc">确定要清空吗？</p>

        <div class="clear-confirm">
          <div class="clear-hint">请输入 <strong>yes</strong> 确认操作</div>
          <el-input v-model="clearConfirmText" placeholder="输入 yes 确认" size="large" />
        </div>
      </div>
      <template #footer>
        <el-button @click="showClearDialog = false">取消</el-button>
        <el-button
          type="danger"
          :disabled="clearConfirmText !== 'yes'"
          :loading="clearing"
          @click="handleClearDocuments"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeDocApi } from '@/api/knowledge'
import type { KbDocType, KbDocument } from '@/types/knowledge'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import illustAiKnowledge from '@/assets/illustrations/ai-knowledge.svg'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ─────────── 数据 ───────────
const loading = ref(false)
const documents = ref<KbDocument[]>([])
const statusCounts = ref<Record<string, number>>({})
const total = ref(0)
const statusFilter = ref('')
const docTypeFilter = ref('')
const keyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)

/** 处理中 = 解析/分块/向量化三个瞬态 */
const TRANSIENT = ['parsing', 'chunking', 'embedding']

const statusOptions = [
  { value: 'ready', label: '已就绪', cls: 'completed' },
  { value: 'pending', label: '等待中', cls: 'pending' },
  { value: 'failed', label: '失败', cls: 'failed' },
]

const docTypeOptions: { value: KbDocType; label: string }[] = [
  { value: 'requirement', label: '需求文档' },
  { value: 'api_doc', label: '接口文档' },
  { value: 'design', label: '设计文档' },
  { value: 'test_case', label: '测试用例' },
  { value: 'bug_review', label: '缺陷复盘' },
  { value: 'meeting', label: '会议纪要' },
  { value: 'other', label: '其他' },
]

const docTypeLabel = (t: string): string =>
  docTypeOptions.find((o) => o.value === t)?.label || '其他'

const getCount = (key: string): number => {
  const sc = statusCounts.value
  if (key === 'all') return Object.values(sc).reduce((a, b) => a + b, 0)
  return sc[key] || 0
}

const processingCount = computed(() =>
  TRANSIENT.reduce((sum, k) => sum + (statusCounts.value[k] || 0), 0),
)

const setFilter = (val: string) => {
  statusFilter.value = val
  currentPage.value = 1
  fetchData()
}

const onFilterChange = () => {
  currentPage.value = 1
  fetchData()
}

// ─────────── 上传 ───────────
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadDocType = ref<KbDocType>('other')
const fileList = ref<{ raw: File; name: string }[]>([])

// ─────────── 清空 ───────────
const showClearDialog = ref(false)
const clearConfirmText = ref('')
const clearing = ref(false)

// ─────────── 格式化 ───────────
const formatFileSize = (bytes: number): string => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return v.toFixed(1) + ' ' + units[i]
}

const formatDate = (dateStr: string): string => {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    return (
      d.getFullYear() +
      '-' +
      String(d.getMonth() + 1).padStart(2, '0') +
      '-' +
      String(d.getDate()).padStart(2, '0') +
      ' ' +
      String(d.getHours()).padStart(2, '0') +
      ':' +
      String(d.getMinutes()).padStart(2, '0')
    )
  } catch {
    return dateStr
  }
}

// ─────────── 图谱抽取（P1b） ───────────
const batchExtracting = ref(false)
const extractingIds = ref(new Set<number>())

const graphStatusLabel = (s: string): string => {
  const map: Record<string, string> = {
    pending: '图谱·待抽取',
    extracting: '图谱·抽取中',
    extracted: '图谱·已抽取',
    failed: '图谱·失败',
    skipped: '图谱·已跳过',
  }
  return map[s] || s
}

const goGraphTask = (doc: KbDocument) => {
  if (!doc.graph_task_id) return
  router.push({
    name: 'AiTaskDetail',
    params: { id: projectId.value, taskId: doc.graph_task_id },
  })
}

const handleExtract = async (doc: KbDocument) => {
  extractingIds.value.add(doc.id)
  try {
    await knowledgeDocApi.extract(projectId.value, doc.id)
    ElMessage.success('已提交图谱提取任务（约 ¥0.03-0.06/篇）')
    fetchData()
  } catch (e) {
    console.error('提交图谱提取失败', e)
  } finally {
    extractingIds.value.delete(doc.id)
  }
}

const handleExtractBatch = async () => {
  try {
    await ElMessageBox.confirm(
      '将对所有「已就绪且未抽取/抽取失败」的文档批量提取图谱（单次最多 100 份）。' +
        '提取消耗大模型 token，约 ¥0.03-0.06/篇，确认继续？',
      '批量提取图谱',
      { type: 'info', confirmButtonText: '开始提取', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  batchExtracting.value = true
  try {
    const res = await knowledgeDocApi.extractBatch(projectId.value)
    const { dispatched = 0, remaining = 0 } = res.data || {}
    if (dispatched === 0) {
      ElMessage.info('没有待提取的文档')
    } else {
      ElMessage.success(
        `已派发 ${dispatched} 个提取任务` +
          (remaining ? `，还有 ${remaining} 份可再次批量提取` : ''),
      )
    }
    fetchData()
  } catch (e) {
    console.error('批量提取失败', e)
  } finally {
    batchExtracting.value = false
  }
}

// ─────────── 状态映射（自研分阶段状态机） ───────────
const getStatusLabel = (s: string): string => {
  const map: Record<string, string> = {
    pending: '等待中',
    parsing: '解析中',
    chunking: '分块中',
    embedding: '向量化',
    ready: '已就绪',
    failed: '失败',
    deleted: '已删除',
  }
  return map[(s || '').toLowerCase()] || s
}

// ─────────── 网络请求 ───────────
const fetchData = async () => {
  loading.value = true
  try {
    const res = await knowledgeDocApi.list(projectId.value, {
      status: statusFilter.value || undefined,
      doc_type: docTypeFilter.value || undefined,
      keyword: keyword.value.trim() || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    documents.value = res.data?.items || []
    total.value = res.data?.total || 0
    statusCounts.value = res.data?.status_counts || {}
    syncAutoRefresh()
  } catch (err) {
    console.error(err)
    documents.value = []
  } finally {
    loading.value = false
  }
}

// 有瞬态文档时轻量自动刷新（任务事件驱动状态，5s 拉一次列表即可）
let refreshTimer: ReturnType<typeof setInterval> | null = null
const syncAutoRefresh = () => {
  const hasTransient = documents.value.some(
    (d) => TRANSIENT.includes(d.status) || d.status === 'pending',
  )
  if (hasTransient && !refreshTimer) {
    refreshTimer = setInterval(fetchData, 5000)
  } else if (!hasTransient && refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// ─────────── 操作 ───────────
const goTask = (doc: KbDocument) => {
  if (!doc.ai_task_id) return
  router.push({
    name: 'AiTaskDetail',
    params: { id: projectId.value, taskId: doc.ai_task_id },
  })
}

const handleFileChange = (_file: unknown, list: { raw: File; name: string }[]) => {
  fileList.value = list
}

const resetUpload = () => {
  fileList.value = []
  uploadDocType.value = 'other'
}

const handleSubmitUpload = async () => {
  if (uploading.value) return // 双击重入守卫（:loading 渲染前的间隙仍可能二次触发）
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    for (const f of fileList.value) {
      await knowledgeDocApi.upload(projectId.value, f.raw, uploadDocType.value)
    }
    ElMessage.success('已提交入库任务，处理进度可在任务中心查看')
    showUploadDialog.value = false
    resetUpload()
    fetchData()
  } catch (e) {
    console.error('上传文档失败', e)
  } finally {
    uploading.value = false
  }
}

const handleDelete = async (doc: KbDocument) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档「${doc.file_name}」吗？其全部分块索引将一并删除。`,
      '提示',
      { type: 'warning' },
    )
    await knowledgeDocApi.remove(projectId.value, doc.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (err) {
    if (err !== 'cancel') {
      console.error('删除文档失败', err)
    }
  }
}

const handleClearDocuments = async () => {
  if (clearConfirmText.value !== 'yes') return
  clearing.value = true
  try {
    const r = await knowledgeDocApi.clearAll(projectId.value)
    ElMessage.success(`已清空 ${r.data?.deleted ?? 0} 份文档（回收 ${r.data?.chunks ?? 0} 个分块）`)
    showClearDialog.value = false
    clearConfirmText.value = ''
    fetchData()
  } catch (e) {
    console.error('清空文档失败', e)
  } finally {
    clearing.value = false
  }
}

// ─────────── 生命周期 ───────────
onMounted(() => {
  fetchData()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped lang="scss">
.documents-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-bottom: var(--space-5);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-4);
}

/* ==================== 筛选 + 列表 卡片 ==================== */
.docs-card {
  overflow: hidden;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}

.filter-spacer { flex: 1; }

.type-select {
  width: 128px;
  margin-left: var(--space-2);
}

.keyword-input {
  width: 180px;
}

/* 状态筛选 pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 14px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: var(--transition-base);
  white-space: nowrap;

  &:hover {
    border-color: var(--brand-300);
    color: var(--brand-600);
  }

  &.active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    color: var(--brand-600);
    font-weight: var(--font-weight-semibold);
  }

  &.completed.active {
    background: var(--color-success-50);
    border-color: var(--color-success-500);
    color: var(--color-success-600);
  }
  &.pending.active {
    background: var(--color-info-50);
    border-color: var(--color-info-500);
    color: var(--color-info-600);
  }
  &.failed.active {
    background: var(--color-danger-50);
    border-color: var(--color-danger-500);
    color: var(--color-danger-600);
  }
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-base);
  border-radius: 50%;
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-base);

  &:hover {
    color: var(--brand-500);
    border-color: var(--brand-500);
  }

  > i {
    font-size: 15px;
  }
}

/* 文档列表 */
.doc-list {
  padding: var(--space-4) var(--space-5);
  min-height: 200px;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.doc-card {
  background: var(--bg-card);
  border: 0;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: var(--transition-base);
  gap: var(--space-3);

  &:hover {
    box-shadow: var(--shadow-hover);
  }
}

.doc-main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 1;
  min-width: 0;
}

.doc-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--brand-50);
  color: var(--brand-600);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-name {
  font-size: 14px;
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.trunc-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  color: var(--color-warning-600);
  background: var(--color-warning-50);
  border-radius: var(--radius-full);
  padding: 1px 8px;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;

  > span {
    display: inline-flex;
    align-items: center;

    > i {
      font-size: 13px;
    }
  }
}

.type-tag,
.src-tag {
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-full);
  padding: 1px 8px;
  background: var(--brand-50);
  color: var(--brand-600);
}

.src-tag {
  background: var(--color-info-50);
  color: var(--color-info-600);
}

.doc-error {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-danger-600);
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

/* 软色状态标签（自研分阶段状态机） */
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  background: var(--gray-100);
  color: var(--gray-600);

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  &.st-ready,
  &.st-processed {
    background: var(--color-success-50);
    color: var(--color-success-600);
    .status-dot {
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-success-500) 20%, transparent);
    }
  }
  &.st-parsing,
  &.st-chunking,
  &.st-embedding,
  &.st-processing,
  &.st-uploading {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }
  &.st-pending {
    background: var(--color-info-50);
    color: var(--color-info-600);
  }
  &.st-failed {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
  }
}

/* 图谱抽取状态徽标（与文档主状态独立，P1b） */
.graph-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  background: var(--gray-100);
  color: var(--gray-600);
  cursor: default;

  > i {
    font-size: 12px;
  }

  &.gs-extracted {
    background: var(--brand-50);
    color: var(--brand-600);
  }
  &.gs-pending,
  &.gs-extracting {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
    cursor: pointer;
  }
  &.gs-failed {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
    cursor: pointer;
  }
  &.gs-skipped {
    background: var(--gray-100);
    color: var(--gray-500);
  }
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  transition: var(--transition-base);
  color: var(--text-secondary);

  &:hover {
    color: var(--brand-600);
    background: var(--brand-50);
  }

  &.danger:hover {
    color: var(--color-danger-600);
    background: var(--color-danger-50);
  }
}

/* 分页 */
.doc-list :deep(.el-pagination) {
  margin-top: var(--space-4);
  justify-content: flex-end;
}

/* 上传弹框 */
.upload-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.form-label {
  font-size: 14px;
  color: var(--text-primary);
  flex-shrink: 0;
}

.form-control {
  width: 200px;
}

.upload-icon {
  font-size: 48px;
  color: var(--brand-500);
}

/* 清空弹框 */
.clear-dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.clear-warning-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-danger-50);
  color: var(--color-danger-500);
  margin-bottom: var(--space-1);

  > i { font-size: 22px; }
}

.clear-desc {
  font-size: 14px;
  color: var(--text-primary);
  margin: 0;
}

.clear-danger {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--color-danger-600);
  margin: 0;
}

.clear-confirm {
  margin-top: var(--space-1);
}

.clear-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);

  strong { color: var(--color-danger-600); }
}

/* 响应式 */
@media (max-width: 1100px) {
  .stat-row { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 600px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .doc-card {
    flex-direction: column;
    align-items: flex-start;
  }
  .doc-actions { width: 100%; justify-content: space-between; }
}
</style>
