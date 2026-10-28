<template>
  <div class="func-documents-page">
    <!-- 页头 -->
    <AppPageHeader
      icon="i-solar-document-text-bold"
      :illustration="illustRequirement"
      title="文档管理"
      description="上传需求、原型、字典等文档，支持 AI 智能解析并一键导入知识库"
      :breadcrumbs="['功能测试', '文档管理']"
    >
      <template #actions>
        <el-button v-permission="'test_case:create'" type="primary" @click="openUploadDialog">
          <i class="i-solar-cloud-upload-bold btn-icon" />
          上传文档
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 统计卡 -->
    <div class="stat-grid">
      <AppStatCard label="文档总数" :value="total" color="brand">
        <template #icon><i class="i-solar-folder-with-files-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="已解析" :value="statParsed" color="success">
        <template #icon><i class="i-solar-cpu-bolt-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="已入库" :value="statIngested" color="info">
        <template #icon><i class="i-app-knowledge dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="待处理" :value="statPending" color="warning">
        <template #icon><i class="i-solar-clock-circle-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <!-- 文档类型 Tabs + 文档列表 -->
    <AppSectionCard padless class="docs-tabs-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange" class="type-tabs">
          <el-tab-pane name="all">
            <template #label>
              <span class="tab-label">
                <i class="i-solar-folder-bold tab-icon" />
                <span>全部</span>
                <span v-if="tabCounts.all" class="tab-count">{{ tabCounts.all }}</span>
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane name="requirement">
            <template #label>
              <span class="tab-label">
                <i class="i-solar-document-text-bold tab-icon" />
                <span>需求文档</span>
                <span v-if="tabCounts.requirement" class="tab-count">{{ tabCounts.requirement }}</span>
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane name="prototype">
            <template #label>
              <span class="tab-label">
                <i class="i-solar-gallery-bold tab-icon" />
                <span>原型图</span>
                <span v-if="tabCounts.prototype" class="tab-count">{{ tabCounts.prototype }}</span>
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane name="db_dict">
            <template #label>
              <span class="tab-label">
                <i class="i-solar-database-bold tab-icon" />
                <span>数据库字典</span>
                <span v-if="tabCounts.db_dict" class="tab-count">{{ tabCounts.db_dict }}</span>
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane name="other">
            <template #label>
              <span class="tab-label">
                <i class="i-solar-file-bold tab-icon" />
                <span>其他</span>
                <span v-if="tabCounts.other" class="tab-count">{{ tabCounts.other }}</span>
              </span>
            </template>
          </el-tab-pane>
        </el-tabs>

      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="docList"
          :empty-text="loading ? '加载中...' : ''"
          style="width: 100%"
        >
          <el-table-column label="文档名称" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="doc-name-cell">
                <span class="doc-type-icon" :class="`dt-${row.doc_type}`">
                  <i :class="docTypeIcon(row.doc_type)" />
                </span>
                <div class="doc-name-text">
                  <span class="doc-title">{{ row.name }}</span>
                  <span class="doc-file">{{ row.file_name }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <span class="type-pill" :class="`dt-${row.doc_type}`">
                {{ docTypeLabel(row.doc_type) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="大小" width="100">
            <template #default="{ row }">
              <span class="muted-text">{{ formatFileSize(row.file_size) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="版本" width="90">
            <template #default="{ row }">
              <span v-if="row.version" class="version-tag">{{ row.version }}</span>
              <span v-else class="muted-text">—</span>
            </template>
          </el-table-column>

          <el-table-column label="上传时间" width="150">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>

          <!-- 解析状态 -->
          <el-table-column label="解析" width="100" align="center">
            <template #default="{ row }">
              <span class="status-pill" :class="`parse-${row.parse_status}`">
                <span class="status-dot" />
                {{ parseStatusLabel(row.parse_status) }}
              </span>
            </template>
          </el-table-column>

          <!-- 知识库状态 -->
          <el-table-column label="知识库" width="100" align="center">
            <template #default="{ row }">
              <span class="status-pill" :class="`kb-${row.kb_status}`">
                <span class="status-dot" />
                {{ kbStatusLabel(row.kb_status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="400" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" @click="handlePreview(row)">
                  <i class="i-solar-eye-linear btn-icon-sm" />预览
                </el-button>
                <el-button
                  v-permission="'test_case:execute'"
                  size="small"
                  type="primary"
                  plain
                  :loading="parsingDocIds.has(row.id)"
                  @click="handleAiParse(row)"
                >
                  <i class="i-solar-cpu-bolt-linear btn-icon-sm" />
                  {{ row.parse_status === 'parsed' ? '重新解析' : 'AI 解析' }}
                </el-button>
                <el-button
                  v-permission="'test_case:create'"
                  size="small"
                  :disabled="row.parse_status !== 'parsed' && row.kb_status !== 'ingested'"
                  :loading="ingestingDocIds.has(row.id)"
                  @click="handleToKb(row)"
                >
                  <i
                    :class="
                      row.kb_status === 'ingested'
                        ? 'i-solar-undo-left-round-linear'
                        : 'i-solar-database-linear'
                    "
                    class="btn-icon-sm"
                  />
                  {{ row.kb_status === 'ingested' ? '撤回' : '入库' }}
                </el-button>

                <el-dropdown trigger="click">
                  <el-button size="small">
                    <i class="i-solar-menu-dots-bold btn-icon-sm" />更多
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        :disabled="!row.download_url"
                        @click="handleDownload(row)"
                      >
                        <i class="i-solar-download-minimalistic-linear drop-icon" /> 下载原文件
                      </el-dropdown-item>
                      <el-dropdown-item v-permission="'test_case:edit'" @click="handleEdit(row)">
                        <i class="i-solar-pen-linear drop-icon" /> 编辑信息
                      </el-dropdown-item>
                      <el-dropdown-item v-permission="'test_case:delete'" divided @click="confirmDelete(row)">
                        <i class="i-solar-trash-bin-trash-linear drop-icon drop-danger" />
                        <span class="drop-danger">删除文档</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <AppEmpty
              v-if="!loading"
              scene="data"
              description="还没有任何文档，上传需求或原型，让 AI 帮你解析吧"
            >
              <template #actions>
                <el-button v-permission="'test_case:create'" type="primary" @click="openUploadDialog">
                  <i class="i-solar-cloud-upload-bold btn-icon" />
                  上传文档
                </el-button>
              </template>
            </AppEmpty>
          </template>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="query.page"
            v-model:page-size="query.page_size"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="loadData"
            @current-change="loadData"
          />
        </div>
      </div>
    </AppSectionCard>

    <!-- 上传 / 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '上传文档' : '编辑文档'"
      width="540px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form label-position="top"
        ref="formRef"
        :model="form"
        :rules="formRules"
        @submit.prevent
      >
        <el-form-item v-if="dialogMode === 'create'" label="文件" prop="file">
          <el-upload
            v-model:file-list="fileList"
            class="upload-area"
            drag
            :limit="1"
            :auto-upload="false"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
          >
            <div class="upload-content">
              <i class="i-solar-cloud-upload-bold upload-icon" />
              <div class="upload-text">拖拽或点击上传</div>
              <div class="upload-hint">
                支持 PDF / Word / Markdown / TXT / 图片
              </div>
            </div>
          </el-upload>
        </el-form-item>

        <el-form-item label="文档名称" prop="name">
          <el-input v-model="form.name" placeholder="给文档起个名字" maxlength="200" />
        </el-form-item>

        <el-form-item label="文档类型" prop="doc_type">
          <el-select v-model="form.doc_type" style="width: 100%">
            <el-option label="需求文档" value="requirement" />
            <el-option label="原型图" value="prototype" />
            <el-option label="数据库字典" value="db_dict" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>

        <el-form-item label="版本号">
          <el-input v-model="form.version" placeholder="如 v1.0" maxlength="50" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="文档说明（可选）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ dialogMode === 'create' ? '上传' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 文档预览对话框 -->
    <FuncDocumentPreviewDialog
      v-model="previewVisible"
      :preview="previewData"
      :loading="previewLoading"
      :parsing="previewDoc ? parsingDocIds.has(previewDoc.id) : false"
      :ingesting="previewDoc ? ingestingDocIds.has(previewDoc.id) : false"
      :parse-status="previewDoc?.parse_status"
      :parse-error="previewDoc?.parse_error_message"
      :file-name-title="previewDoc?.name"
      @trigger-parse="handleAiParseFromDialog"
      @trigger-ingest="handleToKbFromDialog"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadUserFile,
} from 'element-plus'
import { funcDocumentApi } from '@/api/funcTest'
import { aiTaskApi } from '@/api/aiTask'
import type {
  FuncDocument,
  DocType,
  FuncDocumentPreview,
  DocParseStatus,
  DocKbStatus,
} from '@/types/func-test'
import { formatDate, formatFileSize } from '@/utils/format'
import FuncDocumentPreviewDialog from '@/components/func-test/FuncDocumentPreviewDialog.vue'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import illustRequirement from '@/assets/illustrations/requirement.svg'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ---------- 列表 ----------
const loading = ref(false)
const docList = ref<FuncDocument[]>([])
const total = ref(0)
const query = reactive({
  doc_type: '' as DocType | '',
  keyword: '',
  page: 1,
  page_size: 20,
})

// Tabs 当前选中（'all' = 全部）
const activeTab = ref<'all' | DocType>('all')

// 统计每个 tab 下的文档数量（基于 doc_type 字段，仅在 "全部" tab 加载时计算）
const tabCounts = computed<Record<'all' | DocType, number>>(() => {
  const counts: Record<'all' | DocType, number> = {
    all: docList.value.length,
    requirement: 0,
    prototype: 0,
    db_dict: 0,
    other: 0,
  }
  for (const d of docList.value) {
    if (d.doc_type && d.doc_type in counts) {
      counts[d.doc_type as DocType]++
    }
  }
  return counts
})

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: query.page,
      page_size: query.page_size,
    }
    if (query.doc_type) params.doc_type = query.doc_type
    if (query.keyword) params.keyword = query.keyword
    const res = await funcDocumentApi.list(projectId.value, params)
    docList.value = res.data.items
    total.value = res.data.total
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

function handleTabChange(name: string | number) {
  activeTab.value = name as 'all' | DocType
  query.doc_type = name === 'all' ? '' : (name as DocType)
  query.page = 1
  loadData()
}

// ---------- 统计 ----------
const statParsed = computed(
  () => docList.value.filter((d) => d.parse_status === 'parsed').length,
)
const statIngested = computed(
  () => docList.value.filter((d) => d.kb_status === 'ingested').length,
)
const statPending = computed(
  () =>
    docList.value.filter(
      (d) => d.parse_status === 'pending' || d.parse_status === 'parsing',
    ).length,
)

// ---------- 对话框 ----------
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formRef = ref<FormInstance>()
const fileList = ref<UploadUserFile[]>([])
const submitting = ref(false)
const form = reactive({
  id: 0,
  name: '',
  doc_type: 'other' as DocType,
  description: '',
  version: '',
  file: null as File | null,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入文档名称', trigger: 'blur' }],
  doc_type: [{ required: true, message: '请选择文档类型', trigger: 'change' }],
  file: [
    {
      validator: (_r, _v, cb) => {
        if (dialogMode.value === 'create' && !form.file) {
          cb(new Error('请上传文件'))
        } else {
          cb()
        }
      },
      trigger: 'change',
    },
  ],
}

function openUploadDialog() {
  resetForm()
  dialogMode.value = 'create'
  dialogVisible.value = true
}

function handleEdit(row: FuncDocument) {
  resetForm()
  dialogMode.value = 'edit'
  form.id = row.id
  form.name = row.name
  form.doc_type = row.doc_type
  form.description = row.description || ''
  form.version = row.version || ''
  dialogVisible.value = true
}

function resetForm() {
  form.id = 0
  form.name = ''
  form.doc_type = 'other'
  form.description = ''
  form.version = ''
  form.file = null
  fileList.value = []
  formRef.value?.clearValidate()
}

function onFileChange(file: UploadUserFile) {
  form.file = (file.raw as File) || null
  // 文件名同步到 name（如果用户没输入过）
  if (!form.name && file.name) {
    form.name = file.name.replace(/\.[^.]+$/, '')
  }
  formRef.value?.validateField('file').catch(() => {})
}

function onFileRemove() {
  form.file = null
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await funcDocumentApi.upload(projectId.value, form.file!, {
        name: form.name,
        doc_type: form.doc_type,
        description: form.description || undefined,
        version: form.version || undefined,
      })
      ElMessage.success('上传成功')
    } else {
      await funcDocumentApi.update(projectId.value, form.id, {
        name: form.name,
        doc_type: form.doc_type,
        description: form.description || undefined,
        version: form.version || undefined,
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (err) {
    console.error(err)
  } finally {
    submitting.value = false
  }
}

// ---------- 行操作 ----------
async function confirmDelete(row: FuncDocument) {
  try {
    await ElMessageBox.confirm(
      row.kb_status === 'ingested'
        ? `文档「${row.name}」已入知识库，删除会同时从知识库中移除。确定继续吗？`
        : `确定要删除文档「${row.name}」吗？`,
      '删除确认',
      { type: 'warning' },
    )
    await handleDelete(row)
  } catch {
    /* 取消 */
  }
}

async function handleDelete(row: FuncDocument) {
  try {
    await funcDocumentApi.remove(projectId.value, row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (err) {
    console.error(err)
  }
}

// ---------- 预览 ----------
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewData = ref<FuncDocumentPreview | null>(null)
const previewDoc = ref<FuncDocument | null>(null)

async function handlePreview(row: FuncDocument) {
  previewDoc.value = row
  previewVisible.value = true
  previewLoading.value = true
  previewData.value = null
  try {
    const { data } = await funcDocumentApi.preview(projectId.value, row.id)
    previewData.value = data
  } catch (err) {
    console.error(err)
  } finally {
    previewLoading.value = false
  }
}

// ---------- AI 解析为知识库 Markdown ----------
const parsingDocIds = ref(new Set<number>())

async function handleAiParse(row: FuncDocument) {
  if (parsingDocIds.value.has(row.id)) return
  parsingDocIds.value.add(row.id)
  try {
    // 提交统一 AI 任务（异步执行，进度可在 AI 任务中心实时查看）
    const { data } = await aiTaskApi.submit(projectId.value, {
      task_type: 'parse_document',
      params: { doc_id: row.id, doc_name: row.name },
      biz_ref_type: 'document',
      biz_ref_id: row.id,
    })
    ElMessage.success('AI 解析任务已提交')
    // 跳转任务详情页，实时查看进度与输出
    router.push({
      name: 'AiTaskDetail',
      params: { id: projectId.value, taskId: data.id },
    })
  } catch (err) {
    console.error(err)
  } finally {
    parsingDocIds.value.delete(row.id)
  }
}

async function handleAiParseFromDialog() {
  if (previewDoc.value) await handleAiParse(previewDoc.value)
}

// ---------- 导入/移出 知识库 ----------
const ingestingDocIds = ref(new Set<number>())

async function handleToKb(row: FuncDocument) {
  if (ingestingDocIds.value.has(row.id)) return
  ingestingDocIds.value.add(row.id)
  try {
    if (row.kb_status === 'ingested') {
      await funcDocumentApi.removeFromKnowledge(projectId.value, row.id)
      ElMessage.success('已从知识库移除')
    } else {
      if (row.parse_status !== 'parsed') {
        ElMessage.warning('请先 AI 解析，再导入知识库')
        return
      }
      await funcDocumentApi.toKnowledge(projectId.value, row.id)
      ElMessage.success('已导入知识库')
    }
    loadData()
  } catch (err) {
    console.error(err)
  } finally {
    ingestingDocIds.value.delete(row.id)
  }
}

async function handleToKbFromDialog() {
  if (previewDoc.value) await handleToKb(previewDoc.value)
}

// ---------- 状态映射 ----------
function parseStatusLabel(s: DocParseStatus): string {
  return (
    { pending: '未解析', parsing: '解析中', parsed: '已解析', failed: '失败' }[
      s
    ] || s
  )
}

function kbStatusLabel(s: DocKbStatus): string {
  return (
    {
      not_ingested: '未入库',
      ingesting: '入库中',
      ingested: '已入库',
      ingest_failed: '失败',
    }[s] || s
  )
}

function handleDownload(row: FuncDocument) {
  if (!row.download_url) {
    ElMessage.warning('下载链接不可用')
    return
  }
  window.open(row.download_url, '_blank')
}

// ---------- 工具函数 ----------
function docTypeLabel(t: string) {
  return (
    {
      requirement: '需求文档',
      prototype: '原型图',
      db_dict: '数据库字典',
      other: '其他',
    } as Record<string, string>
  )[t] || t
}

function docTypeIcon(t: string) {
  return (
    {
      requirement: 'i-solar-document-text-bold',
      prototype: 'i-solar-gallery-bold',
      db_dict: 'i-solar-database-bold',
      other: 'i-solar-file-bold',
    } as Record<string, string>
  )[t] || 'i-solar-file-bold'
}

onMounted(loadData)
</script>

<style scoped lang="scss">
.func-documents-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 统计卡 ============ */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.dash-card-icon {
  font-size: 26px;
}
@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 600px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
}

/* ============ Tabs 容器：占满卡片 header，去掉默认下边距 ============ */
.docs-tabs-card {
  overflow: hidden;
}
.type-tabs {
  padding: 0 var(--space-5);
}
.type-tabs :deep(.el-tabs__header) {
  margin: 0;
}
.type-tabs :deep(.el-tabs__nav-wrap)::after {
  background: var(--border-light);
}

/* Tab label：图标 + 文字 + 计数 */
.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 2px;
}
.tab-icon {
  font-size: 16px;
  color: var(--text-secondary);
  transition: color 0.18s ease;
}
.type-tabs :deep(.el-tabs__item.is-active) .tab-icon {
  color: var(--brand-500);
}
.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  margin-left: 2px;
  background: var(--gray-100);
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  transition: all 0.18s ease;
}
.type-tabs :deep(.el-tabs__item.is-active) .tab-count {
  background: var(--brand-50);
  color: var(--brand-600);
}
.type-tabs :deep(.el-tabs__item:hover) .tab-count {
  background: var(--brand-50);
  color: var(--brand-600);
}

/* ============ 表格 ============ */
.table-wrap {
  padding: var(--space-3) var(--space-2) var(--space-2);
}

/* 文档名称单元格 */
.doc-name-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.doc-type-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  font-size: 18px;

  &.dt-requirement {
    background: var(--brand-50);
    color: var(--brand-600);
  }
  &.dt-prototype {
    background: var(--color-success-50);
    color: var(--color-success-600);
  }
  &.dt-db_dict {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }
  &.dt-other {
    background: var(--gray-100);
    color: var(--gray-600);
  }
}
.doc-name-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.doc-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc-file {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 类型药丸 */
.type-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  border-radius: var(--radius-xs);

  &.dt-requirement {
    background: var(--brand-50);
    color: var(--brand-700);
  }
  &.dt-prototype {
    background: var(--color-success-50);
    color: var(--color-success-600);
  }
  &.dt-db_dict {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }
  &.dt-other {
    background: var(--gray-100);
    color: var(--gray-600);
  }
}

.version-tag {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--brand-700);
  background: var(--brand-50);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
}

.muted-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

/* 状态药丸 */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  /* 解析状态 */
  &.parse-pending {
    background: var(--gray-100);
    color: var(--gray-600);
  }
  &.parse-parsing {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }
  &.parse-parsed {
    background: var(--color-success-50);
    color: var(--color-success-600);
  }
  &.parse-failed {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
  }

  /* 知识库状态 */
  &.kb-not_ingested {
    background: var(--gray-100);
    color: var(--gray-600);
  }
  &.kb-ingesting {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }
  &.kb-ingested {
    background: var(--color-purple-50);
    color: var(--color-purple-600);
  }
  &.kb-ingest_failed {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
  }
}

/* 操作列 */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;

  :deep(.el-button) {
    margin: 0;
  }
}
.drop-icon {
  margin-right: 6px;
  font-size: 15px;
  vertical-align: -2px;
}
.drop-danger {
  color: var(--color-danger-500);
}

/* 分页 */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) var(--space-2);
  border-top: 1px solid var(--border-light);
}

/* 表头 token 化 */
:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  td.el-table__cell {
    padding: 12px 0;
    font-size: var(--font-size-sm);
  }
}

/* ============ 上传区 ============ */
.upload-area :deep(.el-upload-dragger) {
  padding: 20px;
  border-radius: var(--radius-md);
  transition: var(--transition-base);

  &:hover {
    border-color: var(--brand-400);
    background: var(--brand-50);
  }
}
.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.upload-icon {
  font-size: 42px;
  color: var(--brand-500);
}
.upload-text {
  color: var(--text-regular);
  font-size: 14px;
}
.upload-hint {
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
