<template>
  <div class="req-page">
    <!-- 1. 页头 -->
    <AppPageHeader
      icon="i-solar-clipboard-list-bold"
      :illustration="illustRequirement"
      title="需求管理"
      description="管理项目功能需求，支持审核、发布与 AI 用例生成"
      :breadcrumbs="['功能测试', '需求管理']"
    >
      <template #actions>
        <el-button
          v-permission="'test_case:create'"
          :loading="sweeping"
          @click="handleAiSweep"
        >
          <i class="i-solar-radar-2-bold btn-icon" />
          AI 盘点需求
        </el-button>
        <el-button v-permission="'test_case:create'" type="primary" @click="goCreate">
          <i class="i-solar-add-circle-bold btn-icon" />
          新建需求
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 2. 统计卡（module-stats 全量口径，可点击联动） -->
    <div class="stat-grid">
      <AppStatCard
        label="需求总数"
        :value="stats.total"
        color="brand"
        clickable
        extra="点击清除筛选"
        @click="handleResetFilter"
      >
        <template #icon><i class="i-solar-document-text-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard
        label="待审核"
        :value="stats.by_status.pending_review || 0"
        color="warning"
        clickable
        :class="{ 'stat-active is-warning': activeTab === 'pending' }"
        :extra="activeTab === 'pending' ? '待审核列表 · 点击返回' : '点击进入待审核'"
        @click="switchTab(activeTab === 'pending' ? 'all' : 'pending')"
      >
        <template #icon><i class="i-solar-clock-circle-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard
        label="已发布"
        :value="stats.by_status.published || 0"
        color="success"
        clickable
        :class="{ 'stat-active is-success': query.status === 'published' }"
        :extra="query.status === 'published' ? '已筛选 · 点击取消' : '点击筛选'"
        @click="toggleStatusFilter('published')"
      >
        <template #icon><i class="i-solar-check-circle-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard
        label="AI 生成"
        :value="stats.ai_generated"
        color="purple"
        clickable
        :class="{ 'stat-active is-purple': query.source === 'ai_generated' }"
        :extra="query.source === 'ai_generated' ? '已筛选 · 点击取消' : '点击筛选'"
        @click="toggleSourceFilter('ai_generated')"
      >
        <template #icon><i class="i-solar-cpu-bolt-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <!-- 3. 筛选区 -->
    <div class="filter-bar">
      <div class="filter-fields">
        <div v-if="activeTab === 'all'" class="filter-field">
          <label>状态</label>
          <el-select
            v-model="query.status"
            placeholder="全部状态"
            clearable
            @change="handleSearch"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="待审核" value="pending_review" />
            <el-option label="已审核" value="reviewed" />
            <el-option label="已发布" value="published" />
            <el-option label="已废弃" value="deprecated" />
          </el-select>
        </div>
        <div class="filter-field">
          <label>来源</label>
          <el-select
            v-model="query.source"
            placeholder="全部来源"
            clearable
            @change="handleSearch"
          >
            <el-option label="手工创建" value="manual" />
            <el-option label="AI 生成" value="ai_generated" />
          </el-select>
        </div>
        <div class="filter-field filter-search">
          <label>关键词</label>
          <el-input
            v-model="query.keyword"
            placeholder="搜索需求标题或编号"
            clearable
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <i class="i-solar-magnifer-linear" />
            </template>
          </el-input>
        </div>
      </div>
      <div class="filter-actions">
        <el-button @click="handleResetFilter">
          <i class="i-solar-refresh-linear btn-icon" />
          重置
        </el-button>
        <el-button type="primary" @click="handleSearch">
          <i class="i-solar-magnifer-bold btn-icon" />
          查询
        </el-button>
      </div>
    </div>

    <!-- 4. 内容区：卡片 / 列表双视图 -->
    <AppSectionCard padless class="table-card">
      <div class="view-bar">
        <div class="seg-tabs">
          <button
            class="seg-tab"
            :class="{ active: activeTab === 'all' }"
            @click="switchTab('all')"
          >
            全部需求
          </button>
          <button
            class="seg-tab"
            :class="{ active: activeTab === 'pending' }"
            @click="switchTab('pending')"
          >
            待审核
            <span
              v-if="stats.by_status.pending_review"
              class="tab-badge"
            >{{ stats.by_status.pending_review }}</span>
          </button>
        </div>
        <div class="view-right">
          <span class="result-hint">共 {{ total }} 条</span>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="card">
              <i class="i-solar-widget-2-bold" style="margin-right:4px" />
              卡片
            </el-radio-button>
            <el-radio-button value="table">
              <i class="i-solar-list-bold" style="margin-right:4px" />
              列表
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'" v-loading="loading" class="card-view">
        <AppEmpty
          v-if="!loading && reqList.length === 0"
          scene="data"
          :description="activeTab === 'pending'
            ? '没有待审核的需求，全部处理完毕'
            : '还没有任何需求，开始创建吧'"
        >
          <template #actions>
            <el-button
              v-if="activeTab === 'all'"
              v-permission="'test_case:create'"
              type="primary"
              @click="goCreate"
            >
              <i class="i-solar-add-circle-bold btn-icon" />
              立即创建
            </el-button>
          </template>
        </AppEmpty>
        <div v-else class="card-grid">
          <div
            v-for="item in reqList"
            :key="item.id"
            class="req-card"
            @click="goDetail(item)"
          >
            <div class="card-head">
              <span class="cell-code">{{ item.code || `#${item.id}` }}</span>
              <span class="prio-pill" :class="`prio-${item.priority}`">
                {{ priorityLabel(item.priority) }}
              </span>
              <span class="status-pill" :class="`status-${item.status}`">
                <span class="status-dot" />
                {{ statusLabel(item.status) }}
              </span>
              <span v-if="item.source === 'ai_generated'" class="cell-badge is-ai">AI</span>
            </div>

            <div class="card-title-text">{{ item.title }}</div>
            <div class="card-desc" :class="{ 'is-empty': !item.description }">
              {{ item.description || '暂无描述' }}
            </div>

            <div class="card-foot">
              <span class="foot-item">
                <i class="i-solar-gallery-bold" />
                {{ item.attachments?.length || 0 }} 附件
              </span>
              <span class="foot-item" :class="{ 'has-cases': (item.case_count || 0) > 0 }">
                <i class="i-solar-clipboard-list-bold" />
                {{ item.case_count || 0 }} 用例
              </span>
              <span class="foot-date">{{ formatDate(item.created_at) }}</span>
            </div>

            <div class="card-actions" @click.stop>
              <button
                v-permission="'test_case:execute'"
                class="icon-btn-sm brand"
                title="AI 生成用例"
                @click="goGenerateCases(item)"
              >
                <i class="i-solar-cpu-bolt-bold" />
              </button>
              <button
                v-if="item.status === 'draft' || item.status === 'pending_review'"
                class="icon-btn-sm success"
                title="审核"
                @click="openReviewDialog(item, 'approve')"
              >
                <i class="i-solar-check-circle-linear" />
              </button>
              <button class="icon-btn-sm" title="详情" @click="goDetail(item)">
                <i class="i-solar-eye-linear" />
              </button>
              <el-popconfirm
                v-permission="'test_case:delete'"
                :title="`确定删除需求「${item.title}」?`"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="handleDelete(item)"
              >
                <template #reference>
                  <button class="icon-btn-sm danger" title="删除">
                    <i class="i-solar-trash-bin-trash-linear" />
                  </button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>

      <!-- 列表视图 -->
      <div v-else class="table-wrap">
        <el-table
          v-loading="loading"
          :data="reqList"
          style="width: 100%"
        >
          <el-table-column prop="code" label="需求编号" width="130">
            <template #default="{ row }">
              <span class="cell-code">{{ row.code || '—' }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="title" label="需求标题" min-width="260">
            <template #default="{ row }">
              <div class="cell-title" @click="goDetail(row)">
                <i class="i-solar-document-text-linear cell-title-icon" />
                <span class="cell-title-main">{{ row.title }}</span>
                <span v-if="row.source === 'ai_generated'" class="cell-badge is-ai">AI</span>
              </div>
              <div v-if="row.description" class="cell-sub">{{ row.description }}</div>
            </template>
          </el-table-column>

          <el-table-column label="优先级" width="90">
            <template #default="{ row }">
              <span class="prio-pill" :class="`prio-${row.priority}`">
                {{ priorityLabel(row.priority) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <span class="status-pill" :class="`status-${row.status}`">
                <span class="status-dot" />
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="用例数" width="80" align="center">
            <template #default="{ row }">
              <span class="case-count-badge" :class="{ 'is-zero': !(row.case_count || 0) }">
                {{ row.case_count || 0 }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="创建时间" width="150">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="400" fixed="right" align="center">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  v-permission="'test_case:execute'"
                  size="small"
                  type="primary"
                  plain
                  @click="goGenerateCases(row)"
                >
                  <i class="i-solar-cpu-bolt-bold btn-icon-sm" />
                  AI 生成用例
                </el-button>
                <el-button
                  v-if="row.status === 'draft' || row.status === 'pending_review'"
                  size="small"
                  @click="openReviewDialog(row, 'approve')"
                >
                  <i class="i-solar-check-circle-linear btn-icon-sm" />
                  审核
                </el-button>
                <el-button size="small" @click="goDetail(row)">
                  <i class="i-solar-eye-linear btn-icon-sm" />
                  详情
                </el-button>
                <el-popconfirm
                  v-permission="'test_case:delete'"
                  :title="`确定删除需求「${row.title}」?`"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  @confirm="handleDelete(row)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain>
                      <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>

          <!-- 空状态 -->
          <template #empty>
            <AppEmpty
              v-if="!loading"
              scene="data"
              description="还没有任何需求，开始创建吧"
            >
              <template #actions>
                <el-button v-permission="'test_case:create'" type="primary" @click="goCreate">
                  <i class="i-solar-add-circle-bold btn-icon" />
                  立即创建
                </el-button>
              </template>
            </AppEmpty>
          </template>
        </el-table>
      </div>

      <!-- 分页（双视图共用） -->
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
    </AppSectionCard>

    <!-- 审核对话框 -->
    <RequirementReviewDialog
      v-model="reviewDialog.visible"
      :project-id="projectId"
      :requirement="reviewDialog.row"
      :initial-action="reviewDialog.action"
      @reviewed="handleReviewed"
    />

    <!-- AI 生成用例对话框 -->
    <CaseGenerateDialog
      v-model="generateDialog.visible"
      :project-id="projectId"
      :requirement-id="generateDialog.requirementId"
      :requirement="generateDialog.requirement"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { funcRequirementApi } from '@/api/funcTest'
import { aiTaskApi } from '@/api/aiTask'
import { moduleStatsApi, type RequirementsStats } from '@/api/module-stats'
import type {
  FuncRequirement,
  RequirementStatus,
  RequirementSource,
} from '@/types/func-test'
import { formatDate } from '@/utils/format'
import CaseGenerateDialog from '@/components/func-test/CaseGenerateDialog.vue'
import RequirementReviewDialog from '@/components/func-test/RequirementReviewDialog.vue'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import illustRequirement from '@/assets/illustrations/requirement.svg'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

// ---------- 列表 ----------
const loading = ref(false)
const reqList = ref<FuncRequirement[]>([])
const total = ref(0)
const query = reactive({
  status: '' as RequirementStatus | '',
  source: '' as RequirementSource | '',
  keyword: '',
  page: 1,
  page_size: 20,
})

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: query.page,
      page_size: query.page_size,
    }
    if (activeTab.value === 'pending') params.status = 'pending_review'
    else if (query.status) params.status = query.status
    if (query.source) params.source = query.source
    if (query.keyword) params.keyword = query.keyword
    const res = await funcRequirementApi.list(projectId.value, params)
    reqList.value = res.data.items
    total.value = res.data.total
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadData()
}

// ---------- 视图模式 ----------
const viewMode = ref<'card' | 'table'>('card')

// ---------- 待审核 tab ----------
const activeTab = ref<'all' | 'pending'>('all')

function switchTab(tab: 'all' | 'pending') {
  if (activeTab.value === tab) return
  activeTab.value = tab
  if (tab === 'pending') query.status = ''
  handleSearch()
}

// ---------- 全量统计（module-stats） ----------
const stats = ref<RequirementsStats>({
  total: 0,
  by_status: {},
  ai_generated: 0,
})

async function loadStats() {
  try {
    const res = await moduleStatsApi.get(projectId.value, 'requirements')
    stats.value = res.data
  } catch (err) {
    console.error(err)
  }
}

function handleReviewed() {
  loadData()
  loadStats()
}

function toggleStatusFilter(status: RequirementStatus) {
  if (activeTab.value === 'pending') activeTab.value = 'all'
  query.status = query.status === status ? '' : status
  handleSearch()
}

function toggleSourceFilter(source: RequirementSource) {
  query.source = query.source === source ? '' : source
  handleSearch()
}

// ---------- 重置筛选 ----------
function handleResetFilter() {
  activeTab.value = 'all'
  query.status = ''
  query.source = ''
  query.keyword = ''
  query.page = 1
  loadData()
}

// ---------- 删除 ----------
async function handleDelete(row: FuncRequirement) {
  try {
    await funcRequirementApi.remove(projectId.value, row.id)
    ElMessage.success('删除成功')
    loadData()
    loadStats()
  } catch (err) {
    console.error(err)
  }
}

// ---------- 审核（弹框逻辑在 RequirementReviewDialog 组件内） ----------
const reviewDialog = reactive({
  visible: false,
  row: null as FuncRequirement | null,
  action: 'approve' as 'approve' | 'reject',
})

function openReviewDialog(row: FuncRequirement, defaultAction: 'approve' | 'reject') {
  reviewDialog.row = row
  reviewDialog.action = defaultAction
  reviewDialog.visible = true
}

// ---------- 跳转 ----------
/** AI 需求盘点：全库扫描知识库文档，批量提取需求草稿（任务式，去任务中心看进度） */
const sweeping = ref(false)
async function handleAiSweep() {
  try {
    await ElMessageBox.confirm(
      '将扫描本项目知识库的全部文档（含跨文档合并与原型图挂靠），把提取到的需求以草稿落库，已存在的自动跳过。确认发起？',
      'AI 盘点需求',
      { type: 'info', confirmButtonText: '发起盘点', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  sweeping.value = true
  try {
    const res = await aiTaskApi.submit(projectId.value, {
      task_type: 'extract_requirements',
      biz_ref_type: 'project',
      biz_ref_id: projectId.value,
      params: { project_id: projectId.value },
    })
    ElMessage.success('盘点任务已提交')
    router.push({
      name: 'AiTaskDetail',
      params: { id: projectId.value, taskId: res.data.id },
    })
  } catch (e) {
    console.error('发起 AI 盘点失败', e)
  } finally {
    sweeping.value = false
  }
}

function goCreate() {
  router.push({
    name: 'FuncTestRequirementCreate',
    params: { id: projectId.value },
  })
}

function goDetail(row: FuncRequirement) {
  router.push({
    name: 'FuncTestRequirementDetail',
    params: { id: projectId.value, reqId: row.id },
  })
}

// ---------- AI 生成用例（弹框） ----------
const generateDialog = reactive({
  visible: false,
  requirementId: null as number | null,
  requirement: null as FuncRequirement | null,
})

function goGenerateCases(row: FuncRequirement) {
  generateDialog.requirementId = row.id
  generateDialog.requirement = row
  generateDialog.visible = true
}

// ---------- 标签 ----------
function priorityLabel(p: string) {
  return ({ urgent: '紧急', high: '高', medium: '中', low: '低' } as Record<string, string>)[p] || p
}

function statusLabel(s: string) {
  return (
    {
      draft: '草稿',
      pending_review: '待审核',
      reviewed: '已审核',
      published: '已发布',
      deprecated: '已废弃',
    } as Record<string, string>
  )[s] || s
}

onMounted(() => {
  if (route.query.tab === 'pending') activeTab.value = 'pending'
  loadStats()
  loadData()
})
</script>

<style scoped lang="scss">
.req-page {
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
.dash-card-icon { font-size: 26px; }

/* 统计卡激活态（点击筛选中） */
.stat-active {
  border-radius: var(--radius-lg);

  &.is-warning { outline: 2px solid var(--color-warning-500); }
  &.is-success { outline: 2px solid var(--color-success-500); }
  &.is-purple  { outline: 2px solid var(--color-purple-500); }
}

@media (max-width: 1100px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px)  { .stat-grid { grid-template-columns: 1fr; } }

/* ============ 筛选区 ============ */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.filter-fields {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
}
.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
  }
  :deep(.el-select),
  :deep(.el-input) { width: 100%; }
}
.filter-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
@media (max-width: 900px) {
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-actions { justify-content: flex-end; }
}

/* ============ 内容区 ============ */
.table-card { overflow: hidden; }
.table-wrap { padding: var(--space-3) var(--space-2) var(--space-2); }

.view-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);

  .result-hint {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
  }
}
.view-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* ============ 待审核 tabs ============ */
.seg-tabs {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.seg-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    color: var(--text-primary);
    background: var(--gray-100);
  }
  &.active {
    color: var(--brand-600);
    background: var(--brand-50);
    font-weight: var(--font-weight-semibold);
  }
}
.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--color-warning-500);
  color: #fff;
  font-size: 10px;
  font-weight: var(--font-weight-bold);
  line-height: 1;
}

/* ============ 卡片视图 ============ */
.card-view {
  padding: var(--space-4);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: var(--space-4);
}

.req-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  cursor: pointer;
  transition: var(--transition-base);

  &:hover {
    border-color: var(--brand-300);
    box-shadow: var(--shadow-md);

    .card-actions { opacity: 1; }
  }

  .card-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
  }

  .card-title-text {
    font-size: 15px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    margin-bottom: var(--space-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-desc {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    line-height: 1.6;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 2.4em;
    margin-bottom: var(--space-3);

    &.is-empty { color: var(--text-placeholder); }
  }

  .card-foot {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-light);

    .foot-item {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: var(--font-size-xs);
      color: var(--text-secondary);

      > i { font-size: 14px; }

      &.has-cases { color: var(--brand-600); }
    }

    .foot-date {
      margin-left: auto;
      font-size: var(--font-size-xs);
      color: var(--text-placeholder);
    }
  }

  .card-actions {
    position: absolute;
    right: var(--space-3);
    top: var(--space-3);
    display: flex;
    gap: 4px;
    padding: 4px;
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    opacity: 0;
    transition: opacity 0.15s;
  }
}

/* 图标按钮（卡片 + 列表共用） */
.icon-btn-sm {
  width: 28px;
  height: 28px;
  border: none;
  background: var(--gray-50);
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 15px;
  transition: var(--transition-fast);

  &:hover {
    background: var(--brand-50);
    color: var(--brand-600);
  }

  &.brand {
    background: var(--brand-50);
    color: var(--brand-500);

    &:hover { background: var(--brand-100); color: var(--brand-600); }
  }

  &.success:hover {
    background: var(--color-success-50);
    color: var(--color-success-600);
  }

  &.danger:hover {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
  }
}

/* 用例数徽标 */
.case-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-xs);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  background: var(--brand-50);
  color: var(--brand-600);

  &.is-zero {
    background: var(--gray-100);
    color: var(--text-placeholder);
    font-weight: 400;
  }
}

/* 标题副行（描述摘要） */
.cell-sub {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 420px;
}

.cell-code {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.cell-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--brand-500);
  cursor: pointer;
  transition: var(--transition-fast);

  &:hover { color: var(--brand-600); }
}
.cell-title-icon {
  font-size: 16px;
  color: var(--brand-500);
  flex-shrink: 0;
}
.cell-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  font-size: 10px;
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-xs);

  &.is-ai {
    background: var(--color-purple-50);
    color: var(--color-purple-600);
  }
}

.cell-attach {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);

  > i { font-size: 14px; color: var(--color-info-500); }
  > em { font-style: normal; }
}

.muted-text {
  color: var(--text-placeholder);
  font-size: var(--font-size-sm);
}

/* 优先级药丸 */
.prio-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);

  &.prio-urgent { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.prio-high   { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.prio-medium { background: var(--color-info-50);    color: var(--color-info-600); }
  &.prio-low    { background: var(--gray-100);         color: var(--gray-600); }
}

/* 状态药丸（带圆点） */
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

  &.status-draft          { background: var(--gray-100);         color: var(--gray-600); }
  &.status-pending_review { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.status-reviewed       { background: var(--color-info-50);    color: var(--color-info-600); }
  &.status-published      { background: var(--color-success-50); color: var(--color-success-600); }
  &.status-deprecated     { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.status-done           { background: var(--color-success-50); color: var(--color-success-600); }
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

/* 分页 */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) var(--space-2);
  border-top: 1px solid var(--border-light);
}

/* 表格头 Token 化 */
:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
    letter-spacing: 0.3px;
  }
  td.el-table__cell {
    padding: 14px 0;
    font-size: var(--font-size-sm);
  }
}

/* ============ 审核对话框 ============ */
.review-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.review-info {
  padding: var(--space-3);
  background: var(--gray-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}
.review-label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.review-value {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.review-title {
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
</style>
