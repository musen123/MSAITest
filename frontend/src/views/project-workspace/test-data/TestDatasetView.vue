<!--
  测试数据集(AI 造数中心)

  数据驱动:维护一张 N 行参数表,列名即变量引用键(${{列名}}),执行时按策略取行注入为变量覆盖。
  与压测数据集同构(columns/rows/kind),但服务于接口/Web 执行配置绑定。
  样式对齐压测数据集页;AI 造走统一任务框架(generate_test_dataset)。
-->
<template>
  <div class="data-page">
    <AppPageHeader
      icon="i-solar-database-bold"
      title="测试数据集"
      description="数据驱动:维护一张 N 行参数表,列名即变量引用键;执行时每条用例/请求分到不同的一行(账号/搜索词…)"
    >
      <template #actions>
        <el-button v-if="can.create" @click="openGenerate">
          <i class="i-solar-cpu-bolt-bold btn-icon" />
          AI 造数
        </el-button>
        <el-button v-if="can.create" type="primary" @click="openCreate">
          <i class="i-solar-add-circle-bold btn-icon" />
          新建数据集
        </el-button>
      </template>
    </AppPageHeader>

    <div class="stat-grid">
      <AppStatCard label="数据集总数" :value="datasetsTotal" color="brand">
        <template #icon><i class="i-solar-database-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="数据行(本页累计)" :value="stats.rows" color="cyan">
        <template #icon><i class="i-solar-list-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="含敏感列(本页)" :value="stats.sensitive" color="warning">
        <template #icon><i class="i-solar-lock-keyhole-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <AppSectionCard padless>
      <div class="card-toolbar">
        <span class="result-hint">共 {{ datasetsTotal }} 个数据集</span>
        <div class="toolbar-right">
          <el-input
            v-model="keyword"
            size="small"
            placeholder="搜索名称"
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

      <el-table v-loading="loading" :data="datasets" style="width: 100%">
        <el-table-column label="名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="cell-ds">
              <i class="i-solar-database-linear cell-ds-icon" />
              <span class="cell-ds-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="列" min-width="260">
          <template #default="{ row }">
            <div class="col-chips">
              <span
                v-for="c in row.columns || []"
                :key="c.name"
                class="col-chip"
                :class="`kind-${c.kind}`"
                :title="`${c.desc || ''}(${kindLabel(c.kind)});点击复制引用`"
                @click="copyRef(c.name)"
              >
                <i v-if="isSensitive(c.kind)" class="i-solar-lock-keyhole-minimalistic-bold chip-lock" />
                {{ c.name }}
              </span>
              <span v-if="!(row.columns || []).length" class="muted">—</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="行数" min-width="90" align="center">
          <template #default="{ row }">
            <span class="row-count">{{ row.row_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="100" align="center">
          <template #default="{ row }">
            <span class="src-chip" :class="`src-${row.source}`">{{ sourceLabel(row.source) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="340" align="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openView(row)">
              <i class="i-solar-eye-linear btn-icon-sm" />查看
            </el-button>
            <el-button v-if="can.edit" size="small" text @click="openImport(row)">
              <i class="i-solar-upload-minimalistic-linear btn-icon-sm" />导入
            </el-button>
            <el-button v-if="can.edit" size="small" text @click="openEdit(row)">
              <i class="i-solar-pen-linear btn-icon-sm" />编辑
            </el-button>
            <el-button v-if="can.delete" size="small" text type="danger" @click="onDelete(row)">
              <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <AppEmpty description="还没有数据集">
            <el-button v-if="can.create" type="primary" @click="openCreate">新建数据集</el-button>
          </AppEmpty>
        </template>
      </el-table>

      <div v-if="datasetsTotal > pageSize" class="pager">
        <el-pagination
          layout="prev, pager, next"
          :total="datasetsTotal"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </AppSectionCard>

    <!-- ============ 新建/编辑/查看 弹窗 ============ -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="860px" top="6vh" destroy-on-close>
      <div class="ds-form">
        <!-- 只读详情视图 -->
        <div v-if="readonly" class="ds-view">
          <div class="ds-view-head">
            <i class="i-solar-database-bold ds-vh-icon" />
            <span class="ds-vh-name">{{ form.name }}</span>
            <span class="src-chip" :class="`src-${form.source}`">{{ sourceLabel(form.source) }}</span>
            <span class="ds-vh-rows">{{ form.rows.length }} 行</span>
          </div>
          <div v-if="form.description" class="ds-view-desc">{{ form.description }}</div>

          <div class="ds-view-sec">
            <div class="ds-view-sec-t">列定义({{ form.columns.length }})</div>
            <div class="col-chips">
              <span
                v-for="c in form.columns"
                :key="c.name"
                class="col-chip"
                :class="`kind-${c.kind}`"
                :title="c.desc || ''"
              >
                <i v-if="isSensitive(c.kind)" class="i-solar-lock-keyhole-minimalistic-bold chip-lock" />
                {{ c.name }}
                <span class="chip-kind">{{ kindLabel(c.kind) }}</span>
              </span>
            </div>
          </div>

          <div class="ds-view-sec">
            <div class="ds-view-sec-t">数据行({{ form.rows.length }})</div>
            <div class="rows-table">
              <el-table :data="pagedRows" size="small" max-height="340" border>
                <el-table-column type="index" label="#" width="48" :index="rowIndexBase" />
                <el-table-column v-for="c in form.columns" :key="c.name" :label="c.name" min-width="120">
                  <template #default="{ row }">
                    <span class="cell-ro">{{ display(row[c.name]) }}</span>
                  </template>
                </el-table-column>
                <template #empty><span class="muted">无数据行</span></template>
              </el-table>
              <div class="rows-foot">
                <span class="muted">共 {{ form.rows.length }} 行</span>
                <el-pagination
                  v-if="form.rows.length > rowPageSize"
                  small
                  layout="prev, pager, next"
                  :total="form.rows.length"
                  :page-size="rowPageSize"
                  :current-page="rowPage"
                  @current-change="(p: number) => (rowPage = p)"
                />
              </div>
            </div>
          </div>
        </div>

        <el-form v-else label-position="top">
          <div class="form-row2">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" placeholder="如:登录数据驱动集" />
            </el-form-item>
            <el-form-item label="来源">
              <el-input :model-value="sourceLabel(form.source)" disabled />
            </el-form-item>
          </div>
          <el-form-item label="描述">
            <el-input v-model="form.description" placeholder="可选" />
          </el-form-item>

          <!-- 列定义 -->
          <el-form-item>
            <template #label>
              <span class="lbl-with-hint">
                列定义
                <span class="lbl-hint">列名即 <code class="ph">{{ phRef }}</code> 引用键(执行时注入为变量覆盖)</span>
              </span>
            </template>
            <div class="cols-editor">
              <div v-for="(c, i) in form.columns" :key="i" class="col-row">
                <el-input v-model="c.name" placeholder="列名(如 username)" class="col-name" />
                <el-input v-model="c.desc" placeholder="说明(给 AI/人看)" class="col-desc" />
                <el-select v-model="c.kind" class="col-kind">
                  <el-option label="合成(AI 填)" value="synthetic" />
                  <el-option label="身份(账号)" value="identity" />
                  <el-option label="密钥(口令)" value="secret" />
                </el-select>
                <el-button text type="danger" @click="removeColumn(i)">
                  <i class="i-solar-close-circle-linear" />
                </el-button>
              </div>
              <el-button size="small" @click="addColumn">
                <i class="i-solar-add-circle-linear btn-icon-sm" />添加列
              </el-button>
            </div>
          </el-form-item>

          <!-- 数据行 -->
          <el-form-item>
            <template #label>
              <span class="lbl-with-hint">
                数据行 <span class="lbl-hint">共 {{ form.rows.length }} 行(明文)</span>
              </span>
            </template>

            <el-collapse class="csv-collapse">
              <el-collapse-item title="从 CSV / 表格粘贴批量导入">
                <div class="csv-tip">
                  首行为表头(对齐列名),逗号或制表符分隔。例:<code>username,password,sku</code> 换行 <code>u001,p001,A1</code>
                </div>
                <CodeEditor
                  v-model="csvText"
                  language="text"
                  :theme="isDark ? 'dark' : 'light'"
                  min-height="130px"
                  max-height="280px"
                  :show-line-count="true"
                  class="csv-editor"
                />
                <div class="csv-actions">
                  <el-button size="small" type="primary" @click="parseCsv">解析并追加</el-button>
                  <span v-if="csvHint" class="csv-hint">{{ csvHint }}</span>
                </div>
              </el-collapse-item>
            </el-collapse>

            <div class="rows-table">
              <el-table :data="pagedRows" size="small" max-height="280" border>
                <el-table-column type="index" label="#" width="48" :index="rowIndexBase" />
                <el-table-column v-for="c in form.columns" :key="c.name" :label="c.name" min-width="120">
                  <template #default="{ row }">
                    <el-input v-model="row[c.name]" size="small" :placeholder="c.name" />
                  </template>
                </el-table-column>
                <el-table-column label="" width="48" align="center">
                  <template #default="{ $index }">
                    <el-button text type="danger" size="small" @click="removeRow(rowIndexBase($index))">
                      <i class="i-solar-close-circle-linear" />
                    </el-button>
                  </template>
                </el-table-column>
                <template #empty><span class="muted">无数据行</span></template>
              </el-table>
              <div class="rows-foot">
                <el-button size="small" @click="addRow">
                  <i class="i-solar-add-circle-linear btn-icon-sm" />添加行
                </el-button>
                <el-pagination
                  v-if="form.rows.length > rowPageSize"
                  small
                  layout="prev, pager, next"
                  :total="form.rows.length"
                  :page-size="rowPageSize"
                  :current-page="rowPage"
                  @current-change="(p: number) => (rowPage = p)"
                />
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button
          v-if="readonly && can.edit && form.rows.length"
          type="danger"
          plain
          :loading="clearing"
          @click="clearDataset"
        >
          <i class="i-solar-trash-bin-minimalistic-linear btn-icon-sm" />清空数据
        </el-button>
        <el-button @click="dialogVisible = false">{{ readonly ? '关闭' : '取消' }}</el-button>
        <el-button v-if="!readonly" type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- ============ AI 造数 弹窗(新建)============ -->
    <el-dialog v-model="genVisible" title="AI 生成测试数据集" width="720px" top="8vh" destroy-on-close>
      <el-form label-position="top">
        <div class="form-row2">
          <el-form-item label="数据集名称" required>
            <el-input v-model="genForm.dataset_name" placeholder="如:登录数据驱动集" />
          </el-form-item>
          <el-form-item label="生成行数">
            <el-input-number v-model="genForm.count" :min="1" :max="200" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item label="数据意图(给 AI 的领域上下文)">
          <el-input
            v-model="genForm.intent"
            type="textarea"
            :rows="2"
            placeholder="如:电商登录+搜索的数据驱动,账号唯一、搜索词贴近真实用户习惯"
          />
        </el-form-item>
        <el-form-item>
          <template #label>
            <span class="lbl-with-hint">
              列定义
              <span class="lbl-hint">所有列均由 AI 生成;kind 仅作生成风格提示(identity=唯一账号 / secret=口令)</span>
            </span>
          </template>
          <div class="cols-editor">
            <div v-for="(c, i) in genForm.columns" :key="i" class="col-row">
              <el-input v-model="c.name" placeholder="列名(如 username)" class="col-name" />
              <el-input v-model="c.desc" placeholder="说明(给 AI 看)" class="col-desc" />
              <el-select v-model="c.kind" class="col-kind">
                <el-option label="合成(AI 填)" value="synthetic" />
                <el-option label="身份(唯一账号)" value="identity" />
                <el-option label="密钥(口令)" value="secret" />
              </el-select>
              <el-button text type="danger" @click="genForm.columns.splice(i, 1)">
                <i class="i-solar-close-circle-linear" />
              </el-button>
            </div>
            <el-button size="small" @click="genForm.columns.push({ name: '', desc: '', kind: 'synthetic' })">
              <i class="i-solar-add-circle-linear btn-icon-sm" />添加列
            </el-button>
          </div>
        </el-form-item>
        <div class="dataset-hint">
          AI 离线造数(零运行时 token),完成后数据集出现在列表。<b>所有列都会生成</b>(含账号/口令等自测数据;
          需真实账号请人工预置)。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="onGenerate">发起生成</el-button>
      </template>
    </el-dialog>

    <!-- ============ 导入数据 弹窗 ============ -->
    <el-dialog v-model="importVisible" :title="`导入数据 — ${importTarget?.name || ''}`" width="640px" destroy-on-close>
      <div class="imp">
        <ol class="imp-steps">
          <li>
            <b>1. 下载模板</b>(表头即该数据集的列,含 2 行示例)
            <el-button size="small" type="primary" plain class="imp-dl" @click="downloadTemplate">
              <i class="i-solar-download-minimalistic-linear btn-icon-sm" />下载 CSV 模板
            </el-button>
          </li>
          <li><b>2. 按格式填写</b>:保留首行列名,删除/替换示例行,逐行填入数据(逗号分隔,UTF-8)</li>
          <li><b>3. 上传导入</b>:选择填好的 CSV 文件</li>
        </ol>

        <el-upload
          drag
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          accept=".csv,.txt"
          :on-change="onImportFile"
          class="imp-upload"
        >
          <i class="i-solar-cloud-upload-bold imp-up-icon" />
          <div class="imp-up-text">把 CSV 拖到此处,或<em>点击选择</em></div>
        </el-upload>

        <div v-if="importFileName" class="imp-result">
          <i class="i-solar-document-text-linear" />
          <span>{{ importFileName }} → 解析到 <b>{{ importRows.length }}</b> 行</span>
          <span v-if="importSkipped" class="imp-skip">(跳过 {{ importSkipped }} 行空/格式异常)</span>
        </div>

        <el-form-item label="导入方式" class="imp-mode">
          <el-radio-group v-model="importMode">
            <el-radio value="append">追加到现有行</el-radio>
            <el-radio value="replace">替换全部行</el-radio>
          </el-radio-group>
        </el-form-item>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importRows.length" @click="confirmImport">
          确认导入({{ importMode === 'append' ? '追加' : '替换为' }} {{ importRows.length }} 行)
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import CodeEditor from '@/components/common/CodeEditor.vue'
import { testDataApi, type TestDataset, type TestDatasetCreate } from '@/api/test-data'
import { aiTaskApi } from '@/api/aiTask'
import { useUserStore } from '@/stores/user'

type Col = { name: string; desc: string; kind: string }

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => Number(route.params.id))
const pageSize = 20
const rowPageSize = 10
const phRef = '${{列名}}' // 字面占位符示例(不能直接写进模板,会被当插值)
// 镜像 web/perf 变量框架保留键:列名(=变量键)不得撞框架保留键
const RESERVED_COL_NAMES = new Set([
  'base_url',
  'timeout',
  'default_timeout',
  '__perf_quiet__',
  '__runtime_global_function__',
  '__env_post_script__',
])

const can = reactive({
  create: userStore.hasPermission('test_data:create'),
  edit: userStore.hasPermission('test_data:edit'),
  delete: userStore.hasPermission('test_data:delete'),
})

const datasets = ref<TestDataset[]>([])
const datasetsTotal = ref(0)
const loading = ref(false)
const keyword = ref('')
const page = ref(1)

const stats = computed(() => ({
  rows: datasets.value.reduce((s, d) => s + (d.row_count || 0), 0),
  sensitive: datasets.value.filter((d) => (d.columns || []).some((c) => isSensitive(c.kind))).length,
}))

function isSensitive(kind?: string) {
  return kind === 'identity' || kind === 'secret'
}
function kindLabel(kind: string) {
  return { identity: '身份', secret: '密钥', synthetic: '合成' }[kind] || kind
}
function sourceLabel(s?: string) {
  return { manual: '手动', csv: 'CSV', ai: 'AI 造数' }[s || 'manual'] || s
}
function display(v: unknown) {
  return v === undefined || v === null || v === '' ? '—' : v
}

async function loadDatasets() {
  loading.value = true
  try {
    const res = await testDataApi.listDatasets(projectId.value, {
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    datasets.value = res.data.items || []
    datasetsTotal.value = res.data.total || 0
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  loadDatasets()
}
function onPageChange(p: number) {
  page.value = p
  loadDatasets()
}

function copyRef(name: string) {
  const ref = `\${{${name}}}`
  navigator.clipboard?.writeText(ref)
  ElMessage.success(`已复制 ${ref}`)
}

// ── 新建/编辑/查看 弹窗 ──────────────────────────────────────
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit' | 'view'>('create')
const saving = ref(false)
const clearing = ref(false)
const editingId = ref<number | null>(null)
const rowPage = ref(1)
const isDark = computed(() => document.documentElement.getAttribute('data-theme') === 'dark')
const csvText = ref('')
const csvHint = ref('')

const form = reactive<{
  name: string
  description: string
  source: string
  columns: Col[]
  rows: Record<string, string>[]
}>({ name: '', description: '', source: 'manual', columns: [], rows: [] })

const readonly = computed(() => dialogMode.value === 'view')
const dialogTitle = computed(
  () => ({ create: '新建数据集', edit: '编辑数据集', view: '数据集详情' })[dialogMode.value],
)

const rowIndexBase = (i: number) => (rowPage.value - 1) * rowPageSize + i
const pagedRows = computed(() =>
  form.rows.slice((rowPage.value - 1) * rowPageSize, rowPage.value * rowPageSize),
)

function resetForm() {
  form.name = ''
  form.description = ''
  form.source = 'manual'
  form.columns = []
  form.rows = []
  csvText.value = ''
  csvHint.value = ''
  rowPage.value = 1
  editingId.value = null
}

function openCreate() {
  resetForm()
  form.columns = [{ name: 'username', desc: '账号', kind: 'identity' }]
  dialogMode.value = 'create'
  dialogVisible.value = true
}

function fillForm(ds: TestDataset) {
  form.name = ds.name
  form.description = ds.description || ''
  form.source = ds.source || 'manual'
  form.columns = (ds.columns || []).map((c) => ({ name: c.name, desc: c.desc || '', kind: c.kind }))
  form.rows = (ds.rows || []).map((r) => ({ ...r }))
}

async function openView(row: TestDataset) {
  resetForm()
  dialogMode.value = 'view'
  const ds = (await testDataApi.getDataset(projectId.value, row.id)).data
  editingId.value = ds.id
  fillForm(ds)
  dialogVisible.value = true
}

async function openEdit(row: TestDataset) {
  resetForm()
  dialogMode.value = 'edit'
  const ds = (await testDataApi.getDataset(projectId.value, row.id)).data
  editingId.value = ds.id
  fillForm(ds)
  dialogVisible.value = true
}

function addColumn() {
  form.columns.push({ name: '', desc: '', kind: 'synthetic' })
}
function removeColumn(i: number) {
  const removed = form.columns[i]
  form.columns.splice(i, 1)
  if (removed?.name) form.rows.forEach((r) => delete r[removed.name])
}
function addRow() {
  const r: Record<string, string> = {}
  form.columns.forEach((c) => (r[c.name] = ''))
  form.rows.push(r)
  rowPage.value = Math.ceil(form.rows.length / rowPageSize)
}
function removeRow(i: number) {
  form.rows.splice(i, 1)
}

function parseCsv() {
  const text = csvText.value.trim()
  if (!text) {
    csvHint.value = '粘贴内容为空'
    return
  }
  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (lines.length < 2) {
    csvHint.value = '至少需表头 + 1 行数据'
    return
  }
  const sep = lines[0].includes('\t') ? '\t' : ','
  const rawHeaders = lines[0].split(sep).map((h) => h.trim())
  const skipped: string[] = []
  const headers = rawHeaders.map((h) => {
    if (!h) return ''
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(h) || RESERVED_COL_NAMES.has(h)) {
      skipped.push(h)
      return ''
    }
    return h
  })
  headers.forEach((h) => {
    if (h && !form.columns.some((c) => c.name === h)) {
      form.columns.push({ name: h, desc: '', kind: 'synthetic' })
    }
  })
  let added = 0
  for (const line of lines.slice(1)) {
    const cells = line.split(sep)
    const r: Record<string, string> = {}
    headers.forEach((h, i) => {
      if (h) r[h] = (cells[i] ?? '').trim()
    })
    form.rows.push(r)
    added++
  }
  csvHint.value =
    `已追加 ${added} 行` + (skipped.length ? `;跳过非法/保留列名 ${skipped.join('、')}` : '')
  csvText.value = ''
  rowPage.value = Math.ceil(form.rows.length / rowPageSize)
}

function validate(): string | null {
  if (!form.name.trim()) return '请填写名称'
  const names = form.columns.map((c) => c.name.trim()).filter(Boolean)
  if (new Set(names).size !== names.length) return '列名重复'
  for (const c of form.columns) {
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(c.name)) return `列名「${c.name}」非法(须字母/下划线开头)`
  }
  return null
}

async function onSave() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }
  const colset = new Set(form.columns.map((c) => c.name))
  const rows = form.rows.map((r) => {
    const o: Record<string, string> = {}
    Object.keys(r).forEach((k) => {
      if (colset.has(k)) o[k] = r[k]
    })
    return o
  })
  const payload: TestDatasetCreate = {
    name: form.name.trim(),
    description: form.description || undefined,
    columns: form.columns.map((c) => ({ name: c.name.trim(), desc: c.desc, kind: c.kind })),
    rows,
  }
  saving.value = true
  try {
    if (dialogMode.value === 'edit' && editingId.value) {
      await testDataApi.updateDataset(projectId.value, editingId.value, payload)
      ElMessage.success('已保存')
    } else {
      await testDataApi.createDataset(projectId.value, payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadDatasets()
  } finally {
    saving.value = false
  }
}

async function onDelete(row: TestDataset) {
  await ElMessageBox.confirm(`确定删除数据集「${row.name}」?`, '删除确认', { type: 'warning' })
  await testDataApi.deleteDataset(projectId.value, row.id)
  ElMessage.success('已删除')
  loadDatasets()
}

async function clearDataset() {
  if (!editingId.value) return
  await ElMessageBox.confirm(
    `确定清空数据集「${form.name}」的全部 ${form.rows.length} 行数据?(列定义保留)`,
    '清空确认',
    { type: 'warning', confirmButtonText: '清空', confirmButtonClass: 'el-button--danger' },
  )
  clearing.value = true
  try {
    await testDataApi.updateDataset(projectId.value, editingId.value, { rows: [] })
    form.rows = []
    rowPage.value = 1
    ElMessage.success('已清空')
    loadDatasets()
  } finally {
    clearing.value = false
  }
}

// ── AI 造数(新建)──────────────────────────────────────
const genVisible = ref(false)
const generating = ref(false)
const genForm = reactive<{ dataset_name: string; count: number; intent: string; columns: Col[] }>({
  dataset_name: '',
  count: 50,
  intent: '',
  columns: [],
})

function openGenerate() {
  genForm.dataset_name = ''
  genForm.count = 50
  genForm.intent = ''
  genForm.columns = [{ name: 'username', desc: '账号', kind: 'identity' }]
  genVisible.value = true
}

async function onGenerate() {
  if (!genForm.dataset_name.trim()) {
    ElMessage.warning('请填写数据集名称')
    return
  }
  const names = genForm.columns.map((c) => c.name.trim()).filter(Boolean)
  if (!names.length) {
    ElMessage.warning('请至少定义一列')
    return
  }
  if (!genForm.columns.some((c) => c.kind === 'synthetic' || c.kind === 'identity' || c.kind === 'secret')) {
    ElMessage.warning('请至少定义一列供 AI 生成')
    return
  }
  generating.value = true
  try {
    const { data } = await aiTaskApi.submit(projectId.value, {
      task_type: 'generate_test_dataset',
      biz_ref_type: 'project',
      biz_ref_id: projectId.value,
      params: {
        dataset_name: genForm.dataset_name.trim(),
        columns: genForm.columns.map((c) => ({ name: c.name.trim(), desc: c.desc, kind: c.kind })),
        count: genForm.count,
        intent: genForm.intent || undefined,
      },
    })
    ElMessage.success('已发起 AI 造数,完成后数据集将出现在列表')
    genVisible.value = false
    router.push({ name: 'AiTaskDetail', params: { id: projectId.value, taskId: data.id } })
  } finally {
    generating.value = false
  }
}

// ── 导入数据(CSV 模板下载 + 文件导入)──────────────────────────────────────
const importVisible = ref(false)
const importing = ref(false)
const importTarget = ref<TestDataset | null>(null)
const importRows = ref<Record<string, string>[]>([])
const importFileName = ref('')
const importSkipped = ref(0)
const importMode = ref<'append' | 'replace'>('append')

function openImport(row: TestDataset) {
  if (!(row.columns || []).length) {
    ElMessage.warning('该数据集未定义列,请先编辑添加列再导入')
    return
  }
  importTarget.value = row
  importRows.value = []
  importFileName.value = ''
  importSkipped.value = 0
  importMode.value = 'append'
  importVisible.value = true
}

function downloadTemplate() {
  const cols = importTarget.value?.columns || []
  const header = cols.map((c) => c.name).join(',')
  const sample = (n: number) =>
    cols.map((c) => (isSensitive(c.kind) ? '' : `示例${c.name}${n}`)).join(',')
  const csv = '﻿' + [header, sample(1), sample(2)].join('\r\n') + '\r\n'
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${importTarget.value?.name || 'dataset'}_导入模板.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

function parseImportCsv(text: string) {
  const cols = (importTarget.value?.columns || []).map((c) => c.name)
  const lines = text
    .replace(/^﻿/, '')
    .split(/\r?\n/)
    .filter((l) => l.trim())
  if (lines.length < 2) return { rows: [] as Record<string, string>[], skipped: 0 }
  const sep = lines[0].includes('\t') ? '\t' : ','
  const headers = lines[0].split(sep).map((h) => h.trim())
  const idxOf = (name: string) => {
    const i = headers.indexOf(name)
    return i >= 0 ? i : headers.findIndex((h) => h.toLowerCase() === name.toLowerCase())
  }
  const colIdx = cols.map((name) => ({ name, i: idxOf(name) }))
  const rows: Record<string, string>[] = []
  let skipped = 0
  for (const line of lines.slice(1)) {
    const cells = line.split(sep)
    const r: Record<string, string> = {}
    for (const { name, i } of colIdx) r[name] = i >= 0 ? (cells[i] ?? '').trim() : ''
    if (cols.every((n) => !r[n])) {
      skipped++
      continue
    }
    rows.push(r)
  }
  return { rows, skipped }
}

function onImportFile(uploadFile: { name: string; raw?: File }) {
  const file = uploadFile.raw
  if (!file) return
  importFileName.value = uploadFile.name
  const reader = new FileReader()
  reader.onload = () => {
    const { rows, skipped } = parseImportCsv(String(reader.result || ''))
    importRows.value = rows
    importSkipped.value = skipped
    if (!rows.length) ElMessage.warning('未解析到有效数据行(检查表头是否与列名一致、是否只剩空行)')
  }
  reader.readAsText(file, 'utf-8')
}

async function confirmImport() {
  if (!importTarget.value || !importRows.value.length) return
  importing.value = true
  try {
    let merged = importRows.value
    if (importMode.value === 'append') {
      const ds = (await testDataApi.getDataset(projectId.value, importTarget.value.id)).data
      merged = [...(ds.rows || []), ...importRows.value]
    }
    await testDataApi.updateDataset(projectId.value, importTarget.value.id, { rows: merged })
    ElMessage.success(
      `已导入 ${importRows.value.length} 行(${importMode.value === 'append' ? '追加' : '替换'})`,
    )
    importVisible.value = false
    loadDatasets()
  } finally {
    importing.value = false
  }
}

onMounted(loadDatasets)
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

.cell-ds {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cell-ds-icon {
  font-size: 18px;
  color: var(--brand-600, #2563eb);
}
.cell-ds-name {
  font-weight: 500;
}

.col-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.col-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  background: var(--fill-light, #f1f5f9);
  color: var(--text-secondary);
  cursor: pointer;
}
.col-chip.kind-identity {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}
.col-chip.kind-secret {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}
.chip-lock {
  font-size: 11px;
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
.src-chip.src-csv {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}
.muted {
  color: var(--text-placeholder, #9ca3af);
}
.pager {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-3) var(--space-4);
}

/* 弹窗表单 */
.form-row2 {
  display: grid;
  grid-template-columns: 1fr 160px;
  gap: var(--space-3);
}
.lbl-with-hint {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.lbl-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-placeholder, #9ca3af);
}
.ph {
  font-family: var(--font-mono, monospace);
  background: var(--gray-100);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  color: var(--brand-700);
}
.cols-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.col-row {
  display: grid;
  grid-template-columns: 1fr 1fr 130px 32px;
  gap: 8px;
  align-items: center;
}
.csv-collapse {
  width: 100%;
  flex: 1 1 100%;
  margin-bottom: 10px;
}
.csv-tip {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
  code {
    font-family: var(--font-mono, monospace);
    background: var(--gray-100);
    padding: 1px 5px;
    border-radius: var(--radius-sm);
    color: var(--brand-700);
  }
}
.csv-editor {
  width: 100%;
}
.csv-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.csv-hint {
  font-size: 12px;
  color: var(--text-secondary);
}
.rows-table {
  width: 100%;
}
.rows-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.cell-ro {
  font-size: 13px;
  font-family: var(--font-mono);
}

/* 只读详情视图 */
.ds-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.ds-view-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ds-vh-icon {
  font-size: 20px;
  color: var(--brand-600, #2563eb);
}
.ds-vh-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.ds-vh-rows {
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--fill-light, #f1f5f9);
  border-radius: 6px;
  padding: 2px 8px;
}
.ds-view-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: var(--space-2) var(--space-3);
  background: var(--fill-light, #f8fafc);
  border-radius: var(--radius-sm);
}
.ds-view-sec-t {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.chip-kind {
  font-size: 10px;
  opacity: 0.7;
  margin-left: 2px;
}
.dataset-hint {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-top: 4px;
}

/* 导入数据弹窗 */
.imp {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.imp-steps {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.imp-dl {
  margin-left: 8px;
}
.imp-upload {
  width: 100%;
}
.imp-upload :deep(.el-upload),
.imp-upload :deep(.el-upload-dragger) {
  width: 100%;
}
.imp-up-icon {
  font-size: 30px;
  color: var(--brand-600, #2563eb);
}
.imp-up-text {
  font-size: 13px;
  color: var(--text-secondary);
  em {
    color: var(--brand-600, #2563eb);
    font-style: normal;
  }
}
.imp-result {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-regular);
  background: var(--fill-light, #f1f5f9);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
}
.imp-skip {
  color: var(--text-placeholder, #9ca3af);
  font-size: 12px;
}
.imp-mode {
  margin-bottom: 0;
}
</style>
