<!--
  文件数据集(AI 造数中心)

  维护测试用文件资产:AI 造(八格式)或手动上传,落资产库。
  Web 脚本 upload 步骤用 ${{file:资产名}} 引用,回放期换成真实 storage_key。
  样式对齐压测数据集页(AppPageHeader + 统计卡 + padless 表格)。
-->
<template>
  <div class="data-page">
    <AppPageHeader
      icon="i-solar-folder-with-files-bold"
      title="文件数据集"
      description="AI 造 / 手动上传测试文件;脚本 upload 步骤用占位符引用,回放时自动换成真实文件(告别编造的假路径)"
    >
      <template #actions>
        <el-button v-if="can.create" @click="openForge">
          <i class="i-solar-cpu-bolt-bold btn-icon" />
          AI 造文件
        </el-button>
        <el-button v-if="can.create" type="primary" @click="openUpload">
          <i class="i-solar-upload-minimalistic-bold btn-icon" />
          上传文件
        </el-button>
      </template>
    </AppPageHeader>

    <div class="stat-grid">
      <AppStatCard label="文件总数" :value="filesTotal" color="brand">
        <template #icon><i class="i-solar-file-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="AI 生成(本页)" :value="aiCount" color="warning">
        <template #icon><i class="i-solar-cpu-bolt-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="手动上传(本页)" :value="manualCount" color="cyan">
        <template #icon><i class="i-solar-upload-minimalistic-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <AppSectionCard padless>
      <div class="card-toolbar">
        <span class="result-hint">共 {{ filesTotal }} 个文件</span>
        <div class="toolbar-right">
          <el-input
            v-model="keyword"
            size="small"
            placeholder="搜索资产名"
            clearable
            class="search-input"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button size="small" @click="reload">
            <i class="i-solar-refresh-linear btn-icon-sm" />
            刷新
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="files" style="width: 100%">
        <el-table-column label="资产名(引用键)" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="cell-name">
              <i class="i-solar-file-linear cell-name-icon" />
              <span class="cell-name-text">{{ row.name }}</span>
              <el-tooltip :content="`复制 ${fileRefPh} 引用`" placement="top">
                <el-button text size="small" class="copy-btn" @click="copyRef(row.name)">
                  <i class="i-solar-copy-linear" />
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="文件名" min-width="160" show-overflow-tooltip>
          <template #default="{ row }"><span class="muted-strong">{{ row.file_name }}</span></template>
        </el-table-column>
        <el-table-column label="大小" min-width="100" align="center">
          <template #default="{ row }"><span class="row-count">{{ humanSize(row.size_bytes) }}</span></template>
        </el-table-column>
        <el-table-column label="来源" min-width="100" align="center">
          <template #default="{ row }">
            <span class="src-chip" :class="`src-${row.source}`">{{ sourceLabel(row.source) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="160" align="center">
          <template #default="{ row }"><span class="muted">{{ fmt(row.updated_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" min-width="200" align="right">
          <template #default="{ row }">
            <el-button size="small" text @click="download(row)">
              <i class="i-solar-download-minimalistic-linear btn-icon-sm" />下载
            </el-button>
            <el-button v-if="can.delete" size="small" text type="danger" @click="onDelete(row)">
              <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <AppEmpty description="还没有文件资产">
            <el-button v-if="can.create" type="primary" @click="openUpload">上传文件</el-button>
          </AppEmpty>
        </template>
      </el-table>

      <div v-if="filesTotal > pageSize" class="pager">
        <el-pagination
          layout="prev, pager, next"
          :total="filesTotal"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </AppSectionCard>

    <!-- ============ 上传文件 弹窗 ============ -->
    <el-dialog v-model="uploadVisible" title="上传测试文件" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="选择文件" required>
          <el-upload
            drag
            action="#"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="onFilePick"
            class="up-drag"
          >
            <i class="i-solar-cloud-upload-bold up-icon" />
            <div class="up-text">
              <template v-if="pickedFile">已选:<em>{{ pickedFile.name }}</em>({{ humanSize(pickedFile.size) }})</template>
              <template v-else>把文件拖到此处,或<em>点击选择</em></template>
            </div>
          </el-upload>
        </el-form-item>
        <el-form-item label="资产名(引用键)">
          <el-input v-model="uploadForm.name" placeholder="留空则用文件名;不含空格/冒号/花括号" />
        </el-form-item>
        <el-form-item label="用途说明">
          <el-input v-model="uploadForm.spec" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- ============ AI 造文件 弹窗 ============ -->
    <el-dialog v-model="forgeVisible" title="AI 造测试文件" width="620px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="文件需求(自然语言描述,可一次多份)">
          <el-input
            v-model="forgeForm.requirement"
            type="textarea"
            :rows="5"
            placeholder="如:1 份采购合同 PDF(含甲乙方/金额/条款)、1 份用户导入 Excel(姓名/手机号/邮箱 3 行)、1 份 5MB 大文件"
          />
        </el-form-item>
        <el-form-item label="文件数量">
          <el-input-number v-model="forgeForm.count" :min="1" :max="30" style="width: 160px" />
        </el-form-item>
        <div class="dataset-hint">
          支持 <b>pdf / docx / xlsx / csv / txt / json / md / png</b> 等格式;LLM 只产规格,二进制由代码封装(格式合法)。
          完成后文件出现在列表,可用 <code class="ph">{{ fileRefPh }}</code> 在脚本里引用。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="forgeVisible = false">取消</el-button>
        <el-button type="primary" :loading="forging" @click="submitForge">提交造数任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import { testDataApi, type TestFileAsset } from '@/api/test-data'
import { aiTaskApi } from '@/api/aiTask'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => Number(route.params.id))
const pageSize = 20
const fileRefPh = '${{file:资产名}}' // 字面占位符示例(不能直接写进模板,会被当插值)

const can = reactive({
  create: userStore.hasPermission('test_data:create'),
  delete: userStore.hasPermission('test_data:delete'),
})

const files = ref<TestFileAsset[]>([])
const filesTotal = ref(0)
const loading = ref(false)
const keyword = ref('')
const page = ref(1)

const aiCount = computed(() => files.value.filter((f) => f.source === 'ai').length)
const manualCount = computed(() => files.value.filter((f) => f.source !== 'ai').length)

function sourceLabel(s?: string) {
  return { manual: '手动', ai: 'AI 造' }[s || 'manual'] || s
}
function humanSize(n: number | null): string {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
function fmt(s: string | null): string {
  return s ? s.replace('T', ' ').slice(0, 19) : '—'
}

async function loadFiles() {
  loading.value = true
  try {
    const res = await testDataApi.listFiles(projectId.value, {
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    files.value = res.data.items || []
    filesTotal.value = res.data.total || 0
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  loadFiles()
}
function onPageChange(p: number) {
  page.value = p
  loadFiles()
}

function copyRef(name: string) {
  const ref = `\${{file:${name}}}`
  navigator.clipboard?.writeText(ref)
  ElMessage.success(`已复制 ${ref}`)
}

function download(row: TestFileAsset) {
  if (row.url) window.open(row.url, '_blank')
  else ElMessage.warning('该文件暂无下载地址')
}

async function onDelete(row: TestFileAsset) {
  await ElMessageBox.confirm(
    `删除文件资产「${row.name}」?若有 Web 脚本以 \${{file:${row.name}}} 引用它,回放会失败。`,
    '删除确认',
    { type: 'warning' },
  )
  await testDataApi.deleteFile(projectId.value, row.id)
  ElMessage.success('已删除')
  loadFiles()
}

// ── 上传文件 ──────────────────────────────────────
const uploadVisible = ref(false)
const uploading = ref(false)
const pickedFile = ref<File | null>(null)
const uploadForm = reactive({ name: '', spec: '' })

function openUpload() {
  pickedFile.value = null
  uploadForm.name = ''
  uploadForm.spec = ''
  uploadVisible.value = true
}
function onFilePick(file: { raw?: File }) {
  pickedFile.value = file.raw || null
}
async function doUpload() {
  if (!pickedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', pickedFile.value)
    if (uploadForm.name) fd.append('name', uploadForm.name)
    if (uploadForm.spec) fd.append('spec', uploadForm.spec)
    await testDataApi.uploadFile(projectId.value, fd)
    ElMessage.success('上传成功')
    uploadVisible.value = false
    reload()
  } finally {
    uploading.value = false
  }
}

// ── AI 造文件 ──────────────────────────────────────
const forgeVisible = ref(false)
const forging = ref(false)
const forgeForm = reactive({ requirement: '', count: 3 })

function openForge() {
  forgeForm.requirement = ''
  forgeForm.count = 3
  forgeVisible.value = true
}
async function submitForge() {
  if (!forgeForm.requirement.trim()) {
    ElMessage.warning('请描述文件需求')
    return
  }
  forging.value = true
  try {
    const { data } = await aiTaskApi.submit(projectId.value, {
      task_type: 'generate_test_files',
      biz_ref_type: 'project',
      biz_ref_id: projectId.value,
      params: { requirement: forgeForm.requirement, count: forgeForm.count },
    })
    ElMessage.success('造数任务已提交,可在任务中心查看进度')
    forgeVisible.value = false
    router.push({ name: 'AiTaskDetail', params: { id: projectId.value, taskId: data.id } })
  } finally {
    forging.value = false
  }
}

onMounted(loadFiles)
</script>

<style scoped lang="scss">
.data-page {
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

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}
.dash-card-icon {
  font-size: 26px;
}
@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
}

.card-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.search-input {
  width: 180px;
}
.result-hint {
  font-size: 13px;
  color: var(--text-secondary);
}

.cell-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cell-name-icon {
  font-size: 18px;
  color: var(--brand-600, #2563eb);
}
.cell-name-text {
  font-weight: 500;
}
.copy-btn {
  padding: 0 2px;
  color: var(--text-placeholder, #9ca3af);
  &:hover {
    color: var(--brand-600, #2563eb);
  }
}
.muted-strong {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-regular);
}
.row-count {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.src-chip {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  background: var(--fill-light, #f1f5f9);
  color: var(--text-secondary);
}
.src-chip.src-ai {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
}
.muted {
  color: var(--text-placeholder, #9ca3af);
}
.pager {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-3) var(--space-4);
}

/* 上传拖拽区 */
.up-drag {
  width: 100%;
}
.up-drag :deep(.el-upload),
.up-drag :deep(.el-upload-dragger) {
  width: 100%;
}
.up-icon {
  font-size: 30px;
  color: var(--brand-600, #2563eb);
}
.up-text {
  font-size: 13px;
  color: var(--text-secondary);
  em {
    color: var(--brand-600, #2563eb);
    font-style: normal;
  }
}

.dataset-hint {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-top: 4px;
  code.ph {
    font-family: var(--font-mono, monospace);
    background: var(--gray-100);
    padding: 1px 5px;
    border-radius: var(--radius-sm);
    color: var(--brand-700);
  }
}
</style>
