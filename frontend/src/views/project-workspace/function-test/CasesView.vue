<template>
  <div class="func-cases-page">
    <!-- ============ 页头 ============ -->
    <AppPageHeader
      icon="i-app-test-case"
      :illustration="illustAiCaseGen"
      title="用例管理"
      description="管理功能测试用例，支持手工创建和 AI 智能生成"
      :breadcrumbs="['功能测试', '用例管理']"
    >
      <template #actions>
        <el-button
          v-if="selectedReviewable.length > 0"
          type="success"
          plain
          @click="openReview(selectedReviewable, 'approve')"
        >
          <i class="i-solar-clipboard-check-bold btn-icon" />
          批量评审 ({{ selectedReviewable.length }})
        </el-button>
        <el-button
          v-if="selectedIds.size > 0"
          v-permission="'test_case:delete'"
          type="danger"
          plain
          @click="handleBatchDelete"
        >
          <i class="i-solar-trash-bin-trash-bold btn-icon" />
          批量删除 ({{ selectedIds.size }})
        </el-button>
        <el-button
          :disabled="selectedIds.size === 0"
          @click="handleExport"
        >
          <i class="i-solar-download-minimalistic-bold btn-icon" />
          {{ selectedIds.size > 0 ? `导出选中 (${selectedIds.size})` : '导出 Excel' }}
        </el-button>
        <el-button v-permission="'test_case:create'" type="primary" @click="goCreate">
          <i class="i-solar-add-circle-bold btn-icon" />
          新建用例
        </el-button>
      </template>
    </AppPageHeader>

    <!-- ============ 统计卡（module-stats 全量口径） ============ -->
    <div class="stat-grid">
      <AppStatCard
        label="用例总数"
        :value="stats.total"
        color="brand"
        clickable
        @click="switchTab('all')"
      >
        <template #icon><i class="i-app-test-case dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard
        label="待评审"
        :value="stats.by_status.pending_review || 0"
        color="warning"
        clickable
        @click="switchTab('pending')"
      >
        <template #icon><i class="i-solar-clock-circle-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard
        label="已评审"
        :value="stats.by_status.reviewed || 0"
        color="success"
      >
        <template #icon><i class="i-solar-check-circle-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="AI 生成" :value="stats.ai_generated" color="purple">
        <template #icon><i class="i-app-ai-spark dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <!-- ============ 筛选区 ============ -->
    <div class="filter-bar">
      <div class="filter-fields">
        <div class="filter-field">
          <label>关联需求</label>
          <el-select
            v-model="query.requirement_id"
            placeholder="全部需求"
            clearable
            filterable
            @change="handleSearch"
          >
            <el-option
              v-for="r in requirementOptions"
              :key="r.id"
              :label="`${r.code || r.id} · ${r.title}`"
              :value="r.id"
            />
          </el-select>
        </div>

        <div v-if="activeTab === 'all'" class="filter-field">
          <label>状态</label>
          <el-select v-model="query.status" placeholder="全部状态" clearable @change="handleSearch">
            <el-option label="草稿" value="draft" />
            <el-option label="待评审" value="pending_review" />
            <el-option label="已评审" value="reviewed" />
            <el-option label="已废弃" value="deprecated" />
          </el-select>
        </div>

        <div class="filter-field">
          <label>优先级</label>
          <el-select v-model="query.priority" placeholder="全部" clearable @change="handleSearch">
            <el-option label="P0 紧急" value="urgent" />
            <el-option label="P1 高" value="high" />
            <el-option label="P2 中" value="medium" />
            <el-option label="P3 低" value="low" />
          </el-select>
        </div>

        <div class="filter-field">
          <label>来源</label>
          <el-select v-model="query.source" placeholder="全部" clearable @change="handleSearch">
            <el-option label="手工" value="manual" />
            <el-option label="AI 生成" value="ai_generated" />
          </el-select>
        </div>

        <div class="filter-field filter-search">
          <label>关键词</label>
          <el-input
            v-model="query.keyword"
            placeholder="搜索用例标题"
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

    <!-- ============ 视图切换 + 内容 ============ -->
    <AppSectionCard padless>
      <div class="view-bar">
        <div class="view-left">
          <div class="seg-tabs">
            <button
              class="seg-tab"
              :class="{ active: activeTab === 'all' }"
              @click="switchTab('all')"
            >
              全部用例
            </button>
            <button
              class="seg-tab"
              :class="{ active: activeTab === 'pending' }"
              @click="switchTab('pending')"
            >
              待评审
              <span
                v-if="stats.by_status.pending_review"
                class="tab-badge"
              >{{ stats.by_status.pending_review }}</span>
            </button>
          </div>
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
          v-if="!loading && cases.length === 0"
          scene="data"
          :description="activeTab === 'pending'
            ? '没有待评审的用例，全部处理完毕'
            : '还没有测试用例，开始创建吧'"
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
            v-for="item in cases"
            :key="item.id"
            class="case-card"
            :class="{ selected: selectedIds.has(item.id) }"
            @click="goDetail(item)"
          >
            <div class="card-check" @click.stop="toggleSelect(item.id)">
              <el-checkbox :model-value="selectedIds.has(item.id)" @change="toggleSelect(item.id)" />
            </div>

            <div class="card-head">
              <div class="card-head-row">
                <span class="case-code">{{ item.code || `#${item.id}` }}</span>
                <div class="card-actions">
                  <button
                    v-if="item.status === 'pending_review' || item.status === 'draft'"
                    class="icon-btn-sm success"
                    title="评审"
                    @click.stop="openReview([item], 'approve')"
                  >
                    <i class="i-solar-clipboard-check-bold" />
                  </button>
                  
                  <button v-permission="'test_case:delete'" class="icon-btn-sm danger" title="删除" @click.stop="confirmDelete(item)">
                    <i class="i-solar-trash-bin-trash-linear" />
                  </button>
                </div>
              </div>
              <div class="case-title">{{ item.title }}</div>
            </div>

            <div class="card-body">
              <p v-if="item.preconditions" class="desc">{{ truncate(item.preconditions, 100) }}</p>
              <p v-else class="desc muted">暂无前置条件</p>
            </div>

            <div class="card-foot">
              <div class="meta-left">
                <span class="prio-pill" :class="`prio-${item.priority}`">{{ priorityLabel(item.priority) }}</span>
                <span class="status-pill" :class="`st-${item.status}`">
                  <span class="st-dot" />
                  {{ statusLabel(item.status) }}
                </span>
                <span v-if="item.source === 'ai_generated'" class="ai-tag">AI</span>
              </div>
              <span class="card-date">{{ formatDate(item.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 表格视图 -->
      <div v-else class="table-view">
        <el-table
          v-loading="loading"
          :data="cases"
          style="width: 100%"
          row-class-name="case-row"
          @selection-change="handleSelectionChange"
          @row-click="goDetail"
        >
          <el-table-column type="selection" width="48" />
          <el-table-column label="用例" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="cell-case">
                <i class="i-app-test-case cell-icon" />
                <div class="cell-case-info">
                  <span class="cell-title">{{ row.title }}</span>
                  <span class="cell-code">{{ row.code || `#${row.id}` }}</span>
                </div>
                <span v-if="row.source === 'ai_generated'" class="ai-tag sm">AI</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="关联需求" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span
                v-if="row.requirement_id"
                class="req-link"
                @click.stop="goRequirement(row.requirement_id)"
              >
                {{ getReqLabel(row.requirement_id) }}
              </span>
              <span v-else class="muted-text">—</span>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="100" align="center">
            <template #default="{ row }">
              <span class="prio-pill" :class="`prio-${row.priority}`">{{ priorityLabel(row.priority) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">
              <span class="status-pill" :class="`st-${row.status}`">
                <span class="st-dot" />
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="UI自动化" width="96" align="center">
            <template #default="{ row }">
              <span
                v-if="row.ui_automatable === true"
                class="ua-pill ua-yes"
                title="评审判定：适合界面层验证"
              >适合</span>
              <span
                v-else-if="row.ui_automatable === false"
                class="ua-pill ua-no"
                title="评审判定：属于业务或服务层验证"
              >不适合</span>
              <span v-else class="muted-text" title="未评估">—</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="300" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  v-if="row.status === 'pending_review' || row.status === 'draft'"
                  size="small"
                  @click.stop="openReview([row], 'approve')"
                >
                  <i class="i-solar-clipboard-check-bold btn-icon-sm" />评审
                </el-button>
                <el-button size="small" @click.stop="goDetail(row)">
                  <i class="i-solar-eye-linear btn-icon-sm" />详情
                </el-button>
                
                <el-popconfirm
                  v-permission="'test_case:delete'"
                  :title="`确定删除用例「${row.title}」?`"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  @confirm="handleDelete(row)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain @click.stop>
                      <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <AppEmpty
              v-if="!loading"
              scene="data"
              description="还没有测试用例，开始创建吧"
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
    </AppSectionCard>

    <!-- 评审弹框（单条 / 批量共用） -->
    <CaseReviewDialog
      v-model="reviewVisible"
      :project-id="projectId"
      :cases="reviewTargets"
      :initial-action="reviewInitialAction"
      @reviewed="handleReviewed"
    />

    
  </div>
</template>

<script setup lang="ts">import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common';
import CaseReviewDialog from '@/components/func-test/CaseReviewDialog.vue';
import { funcTestCaseApi, funcRequirementApi } from '@/api/funcTest';
import { moduleStatsApi, type FuncCasesStats } from '@/api/module-stats';
import type { FuncTestCase, FuncRequirement, CasePriority, CaseStatus, CaseSource, } from '@/types/func-test';
import { formatDate } from '@/utils/format';
import illustAiCaseGen from '@/assets/illustrations/ai-case-gen.svg';
const route = useRoute();
const router = useRouter();
const projectId = computed(() => Number(route.params.id));
// ---------- 列表数据 ----------
const loading = ref(false);
const cases = ref<FuncTestCase[]>([]);
const total = ref(0);
const viewMode = ref<'card' | 'table'>('card');
const selectedIds = ref<Set<number>>(new Set());
const activeTab = ref<'all' | 'pending'>('all');
const query = reactive({
    requirement_id: undefined as number | undefined,
    status: '' as CaseStatus | '',
    priority: '' as CasePriority | '',
    source: '' as CaseSource | '',
    keyword: '',
    page: 1,
    page_size: 20,
});
// ---------- 全量统计（module-stats） ----------
const stats = ref<FuncCasesStats>({
    total: 0,
    by_status: {},
    ai_generated: 0,
});
async function loadStats() {
    try {
        const res = await moduleStatsApi.get(projectId.value, 'func_cases');
        stats.value = res.data;
    }
    catch (err) {
        console.error(err);
    }
}
function switchTab(tab: 'all' | 'pending') {
    if (activeTab.value === tab)
        return;
    activeTab.value = tab;
    if (tab === 'pending')
        query.status = '';
    handleSearch();
}
// ---------- 评审 ----------
const reviewVisible = ref(false);
const reviewTargets = ref<FuncTestCase[]>([]);
const reviewInitialAction = ref<'approve' | 'reject'>('approve');
const selectedCases = computed(() => cases.value.filter((c) => selectedIds.value.has(c.id)));
const selectedReviewable = computed(() => selectedCases.value.filter((c) => c.status === 'draft' || c.status === 'pending_review'));
function openReview(targets: FuncTestCase[], action: 'approve' | 'reject') {
    if (!targets.length)
        return;
    reviewTargets.value = targets;
    reviewInitialAction.value = action;
    reviewVisible.value = true;
}
function handleReviewed() {
    // 待评审 tab 下整页都被评审走时回退一页，避免停在越界空页
    if (activeTab.value === 'pending' &&
        reviewTargets.value.length >= cases.value.length &&
        query.page > 1) {
        query.page -= 1;
    }
    selectedIds.value = new Set();
    loadData();
    loadStats();
}
// ---------- 关联需求 ----------
const requirementOptions = ref<FuncRequirement[]>([]);
const reqMap = computed(() => {
    const m = new Map<number, FuncRequirement>();
    for (const r of requirementOptions.value)
        m.set(r.id, r);
    return m;
});
function getReqLabel(reqId: number): string {
    const r = reqMap.value.get(reqId);
    return r ? `${r.code || r.id} · ${r.title}` : `#${reqId}（已删除）`;
}
async function loadRequirements() {
    try {
        const res = await funcRequirementApi.list(projectId.value, {
            page: 1,
            page_size: 200,
        });
        requirementOptions.value = res.data.items;
    }
    catch (err) {
        console.error(err);
    }
}
async function loadData() {
    loading.value = true;
    try {
        const params: Record<string, unknown> = {
            page: query.page,
            page_size: query.page_size,
        };
        if (query.requirement_id)
            params.requirement_id = query.requirement_id;
        if (activeTab.value === 'pending')
            params.status = 'pending_review';
        else if (query.status)
            params.status = query.status;
        if (query.priority)
            params.priority = query.priority;
        if (query.source)
            params.source = query.source;
        if (query.keyword)
            params.keyword = query.keyword;
        const res = await funcTestCaseApi.list(projectId.value, params);
        cases.value = res.data.items;
        total.value = res.data.total;
        selectedIds.value = new Set();
    }
    catch (err) {
        console.error(err);
    }
    finally {
        loading.value = false;
    }
}
function handleSearch() {
    query.page = 1;
    loadData();
}
function handleResetFilter() {
    query.requirement_id = undefined;
    query.status = '';
    query.priority = '';
    query.source = '';
    query.keyword = '';
    handleSearch();
}
// ---------- 初始化 ----------
onMounted(async () => {
    const reqIdQuery = route.query.requirement_id;
    if (reqIdQuery)
        query.requirement_id = Number(reqIdQuery);
    if (route.query.tab === 'pending')
        activeTab.value = 'pending';
    loadStats();
    await loadRequirements();
    await loadData();
});
// ---------- 选中 ----------
function toggleSelect(id: number) {
    const next = new Set(selectedIds.value);
    if (next.has(id))
        next.delete(id);
    else
        next.add(id);
    selectedIds.value = next;
}
function handleSelectionChange(rows: FuncTestCase[]) {
    selectedIds.value = new Set(rows.map((r) => r.id));
}
// ---------- 批量删除 ----------
async function handleBatchDelete() {
    try {
        await ElMessageBox.confirm(`确定要删除选中的 ${selectedIds.value.size} 个用例吗？`, '批量删除', { type: 'warning' });
        for (const id of selectedIds.value) {
            await funcTestCaseApi.remove(projectId.value, id);
        }
        ElMessage.success(`已删除 ${selectedIds.value.size} 个用例`);
        selectedIds.value = new Set();
        loadData();
        loadStats();
    }
    catch {
        // 取消
    }
}
// ---------- 删除 ----------
async function confirmDelete(row: FuncTestCase) {
    try {
        await ElMessageBox.confirm(`确定要删除用例「${row.title}」吗？`, '提示', { type: 'warning' });
        await handleDelete(row);
    }
    catch {
        // 取消
    }
}
async function handleDelete(row: FuncTestCase) {
    try {
        await funcTestCaseApi.remove(projectId.value, row.id);
        ElMessage.success('删除成功');
        if (cases.value.length === 1 && query.page > 1)
            query.page -= 1;
        loadData();
        loadStats();
    }
    catch (err) {
        console.error(err);
    }
}

// ---------- 导出 Excel ----------
async function handleExport() {
    const targets = selectedIds.value.size > 0
        ? cases.value.filter((c) => selectedIds.value.has(c.id))
        : cases.value;
    if (!targets.length) {
        ElMessage.warning('暂无可导出数据');
        return;
    }
    try {
        const XLSX = await import('xlsx');
        const data = targets.map((c, i) => ({
            序号: i + 1,
            用例编号: c.code || '',
            用例标题: c.title,
            优先级: priorityLabel(c.priority),
            状态: statusLabel(c.status),
            关联需求: c.requirement_id ? getReqLabel(c.requirement_id) : '',
            前置条件: c.preconditions || '',
            测试步骤: formatStepsForExport(c),
            预期结果: formatExpectedForExport(c),
            来源: c.source === 'ai_generated' ? 'AI 生成' : '手工创建',
            创建时间: formatDate(c.created_at),
        }));
        const ws = XLSX.utils.json_to_sheet(data);
        ws['!cols'] = [
            { wch: 6 },
            { wch: 18 },
            { wch: 30 },
            { wch: 8 },
            { wch: 10 },
            { wch: 22 },
            { wch: 25 },
            { wch: 40 },
            { wch: 30 },
            { wch: 10 },
            { wch: 18 },
        ];
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, '测试用例');
        const filename = `测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`;
        XLSX.writeFile(wb, filename);
        ElMessage.success(`已导出 ${targets.length} 条用例`);
    }
    catch (err) {
        console.error(err);
        ElMessage.error('导出失败');
    }
}
function formatStepsForExport(c: FuncTestCase): string {
    if (!c.steps || !c.steps.length)
        return '';
    return c.steps
        .map((s) => `${s.step_no}. ${s.action}`)
        .join('\n');
}
function formatExpectedForExport(c: FuncTestCase): string {
    if (c.expected_result && c.expected_result.length) {
        return c.expected_result
            .map((v, i) => `${i + 1}. ${v}`)
            .join('\n');
    }
    if (c.steps && c.steps.length) {
        return c.steps
            .filter((s) => s.expected)
            .map((s) => `${s.step_no}. ${s.expected}`)
            .join('\n');
    }
    return '';
}
// ---------- 跳转 ----------
function goCreate() {
    router.push({
        name: 'FuncTestCaseCreate',
        params: { id: projectId.value },
        query: query.requirement_id
            ? { reqId: query.requirement_id }
            : undefined,
    });
}
function goDetail(row: FuncTestCase) {
    router.push({
        name: 'FuncTestCaseDetail',
        params: { id: projectId.value, caseId: row.id },
    });
}
function goRequirement(reqId: number) {
    router.push({
        name: 'FuncTestRequirementDetail',
        params: { id: projectId.value, reqId },
    });
}
// ---------- 工具 ----------
function truncate(text: string, max: number): string {
    if (!text)
        return '';
    return text.length <= max ? text : text.slice(0, max) + '…';
}
function priorityLabel(p: string): string {
    return ({ urgent: 'P0 紧急', high: 'P1 高', medium: 'P2 中', low: 'P3 低' } as Record<string, string>)[p] || p;
}
function statusLabel(s: string): string {
    return ({
        draft: '草稿',
        pending_review: '待评审',
        reviewed: '已评审',
        deprecated: '已废弃',
    } as Record<string, string>)[s] || s;
}
</script>

<style scoped lang="scss">
.func-cases-page {
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

/* ============ 视图切换栏 ============ */
.view-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.view-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.view-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.result-hint {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

/* ============ 待评审 tabs ============ */
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
  padding: var(--space-4) var(--space-5);
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}
.case-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 160px;

  &:hover {
    border-color: var(--brand-300);
    box-shadow: var(--shadow-card-hover);
    transform: translateY(-1px);
  }
  &.selected {
    border-color: var(--brand-400);
    background: var(--brand-50);
  }
}
.card-check {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1;
}
.card-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 32px;
}
.card-head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.case-code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--gray-100);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
}
.card-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}
.case-card:hover .card-actions {
  opacity: 1;
}
.icon-btn-sm {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.15s;

  &:hover {
    background: var(--brand-50);
    color: var(--brand-600);
  }
  &.danger:hover {
    background: var(--color-danger-50);
    color: var(--color-danger-500);
  }
  &.success:hover {
    background: var(--color-success-50);
    color: var(--color-success-600);
  }
}
.case-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-body {
  flex: 1;
}
.desc {
  font-size: var(--font-size-xs);
  color: var(--text-regular);
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;

  &.muted {
    color: var(--text-placeholder);
    font-style: italic;
  }
}
.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.meta-left {
  display: flex;
  gap: 6px;
  align-items: center;
}
.card-date {
  font-size: 11px;
  color: var(--text-placeholder);
}

/* AI 标签 */
.ai-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-weight-bold);
  background: var(--color-purple-50);
  color: var(--color-purple-600);
  letter-spacing: 0.5px;

  &.sm {
    height: 18px;
    padding: 0 5px;
    font-size: 9px;
  }
}

/* ============ 优先级药丸 ============ */
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

/* ============ 状态药丸 ============ */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  .st-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  &.st-draft          { background: var(--gray-100);         color: var(--gray-500); }
  &.st-pending_review { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.st-reviewed       { background: var(--color-success-50); color: var(--color-success-600); }
  &.st-deprecated     { background: var(--color-danger-50);  color: var(--color-danger-600); }
}

/* ============ 表格视图 ============ */
.table-view {
  padding: 0 var(--space-3);
}
.cell-case {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.cell-icon {
  font-size: 18px;
  color: var(--brand-500);
  flex-shrink: 0;
}
.cell-case-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cell-title {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}
.cell-code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
}
.muted-text {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.ua-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  line-height: 1.6;
  cursor: default;
}
.ua-pill.ua-yes {
  background: var(--color-success-50);
  color: var(--color-success-600);
}
.ua-pill.ua-no {
  background: var(--color-danger-50);
  color: var(--color-danger-600);
}
.req-link {
  color: var(--brand-500);
  cursor: pointer;
  font-size: var(--font-size-sm);
  &:hover { color: var(--brand-700); text-decoration: underline; }
}
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  :deep(.el-button) {
    margin: 0;
  }
}

/* 行 hover */
:deep(.case-row) {
  cursor: pointer;
  transition: background 0.15s;
  &:hover td { background: var(--brand-50) !important; }
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
    letter-spacing: 0.5px;
  }
  td.el-table__cell {
    padding: 14px 0;
    font-size: var(--font-size-sm);
  }
}
</style>
