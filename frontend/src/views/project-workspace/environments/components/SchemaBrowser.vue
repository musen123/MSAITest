<template>
  <div v-loading="loading" class="schema-browser">
    <div v-if="!connId" class="schema-empty">
      <el-empty description="先选择一个数据库连接" :image-size="72" />
    </div>
    <div v-else-if="!loading && !tables.length" class="schema-empty">
      <el-empty description="没有读到表（检查连接与账号权限）" :image-size="72" />
    </div>
    <div v-else class="schema-layout">
      <!-- 左：表名列表 -->
      <div class="table-list" :style="{ maxHeight: height + 'px' }">
        <el-input
          v-model="filter"
          size="small"
          clearable
          placeholder="筛选表名"
          class="table-filter"
        >
          <template #prefix><i class="i-solar-magnifer-linear" /></template>
        </el-input>
        <div
          v-for="t in filteredTables"
          :key="t.name"
          class="table-item"
          :class="{ active: t.name === activeName }"
          @click="activeName = t.name"
        >
          <i class="i-solar-database-linear ti-icon" />
          <span class="ti-name">{{ t.name }}</span>
          <span v-if="t.comment" class="ti-comment">{{ t.comment }}</span>
        </div>
      </div>
      <!-- 右：字段表 / 表数据 -->
      <div class="col-panel">
        <div v-if="active" class="col-head">
          <strong>{{ active.name }}</strong>
          <span v-if="active.comment" class="col-head-comment">{{ active.comment }}</span>
          <el-radio-group v-model="view" size="small" class="view-toggle">
            <el-radio-button value="structure">结构</el-radio-button>
            <el-radio-button value="data">数据</el-radio-button>
          </el-radio-group>
          <el-button
            size="small"
            class="col-refresh"
            :loading="view === 'structure' ? loading : rowsLoading"
            @click="view === 'structure' ? load(true) : loadRows()"
          >
            <i class="i-solar-refresh-linear mr-1" /> 刷新
          </el-button>
        </div>

        <!-- 结构视图 -->
        <el-table
          v-if="active && view === 'structure'"
          :data="active.columns"
          size="small"
          :height="height - 40"
          border
          class="compact-table"
        >
          <el-table-column prop="name" label="字段" min-width="150" />
          <el-table-column prop="type" label="类型" min-width="140" />
          <el-table-column label="可空" width="70" align="center">
            <template #default="{ row }">{{ row.nullable ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="键" width="70" align="center">
            <template #default="{ row }">
              <span v-if="row.key" class="soft-pill pill-brand">{{ row.key }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="comment" label="注释" min-width="180" show-overflow-tooltip />
        </el-table>

        <!-- 数据视图：只读分页（默认每页 20 条） -->
        <template v-else-if="active && view === 'data'">
          <el-table
            v-loading="rowsLoading"
            :data="rowsData.rows"
            size="small"
            :height="height - 84"
            border
            class="compact-table"
          >
            <el-table-column
              v-for="c in rowsData.columns"
              :key="c"
              :prop="c"
              :label="c"
              min-width="140"
              show-overflow-tooltip
            >
              <template #default="{ row }">
                <span v-if="row[c] === null" class="cell-null">NULL</span>
                <template v-else>{{ row[c] }}</template>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="没有数据" :image-size="56" />
            </template>
          </el-table>
          <!-- 底部分页（表格高度已让位，分页条保证在组件高度内） -->
          <div class="rows-pager">
            <el-select
              v-model="pageSize"
              size="small"
              style="width: 96px"
              @change="page = 0; loadRows()"
            >
              <el-option v-for="n in [20, 50, 100]" :key="n" :label="`${n} 条/页`" :value="n" />
            </el-select>
            <span class="pager-info">第 {{ page + 1 }} 页</span>
            <el-button size="small" :disabled="page === 0 || rowsLoading" @click="page--; loadRows()">
              上一页
            </el-button>
            <el-button size="small" :disabled="!rowsData.has_more || rowsLoading" @click="page++; loadRows()">
              下一页
            </el-button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 数据库表结构浏览器（内联组件）：左表名列表（可筛选）+ 右字段明细。
 * 用于数据库连接页的表结构弹窗。
 * connId 变化自动加载；refresh=true 走后端强制重新内省。
 */
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { databaseSchemaApi, type SchemaTable, type TableRowsData } from '@/api/databaseSchema'

const props = withDefaults(
  defineProps<{
    projectId: number
    connId: number | null
    /** 内容区高度（px），弹窗里用小值、页面 tab 里用大值 */
    height?: number
  }>(),
  { height: 520 },
)

const loading = ref(false)
const tables = ref<SchemaTable[]>([])
const activeName = ref('')
const filter = ref('')

const filteredTables = computed(() =>
  filter.value
    ? tables.value.filter((t) => t.name.toLowerCase().includes(filter.value.toLowerCase()))
    : tables.value,
)
const active = computed(() => tables.value.find((t) => t.name === activeName.value) || null)

const load = async (refresh = false) => {
  if (!props.connId) {
    tables.value = []
    activeName.value = ''
    return
  }
  loading.value = true
  try {
    const res = await databaseSchemaApi.getSchema(props.projectId, props.connId, refresh)
    tables.value = res.data?.tables || []
    activeName.value = tables.value[0]?.name || ''
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '读取表结构失败')
  } finally {
    loading.value = false
  }
}

// —— 数据视图：只读分页（默认每页 20 条，LIMIT n+1 判断有无下一页，不做 COUNT） ——
const view = ref<'structure' | 'data'>('structure')
const rowsLoading = ref(false)
const rowsData = ref<TableRowsData>({ columns: [], rows: [], has_more: false })
const page = ref(0)
const pageSize = ref(20)

const loadRows = async () => {
  if (!props.connId || !activeName.value) return
  rowsLoading.value = true
  try {
    const res = await databaseSchemaApi.getTableRows(props.projectId, props.connId, activeName.value, {
      limit: pageSize.value,
      offset: page.value * pageSize.value,
    })
    rowsData.value = res.data || { columns: [], rows: [], has_more: false }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '查询表数据失败')
  } finally {
    rowsLoading.value = false
  }
}

// 切表/切视图：数据视图回第一页重查
watch(activeName, () => {
  page.value = 0
  rowsData.value = { columns: [], rows: [], has_more: false }
  if (view.value === 'data') loadRows()
})
watch(view, (v) => {
  if (v === 'data') {
    page.value = 0
    loadRows()
  }
})

watch(
  () => props.connId,
  () => {
    filter.value = ''
    view.value = 'structure'
    page.value = 0
    load(false)
  },
)
onMounted(() => load(false))

defineExpose({ load })
</script>

<style scoped lang="scss">
.schema-browser { min-height: 200px; }
.schema-empty { padding: 60px 0; }
.schema-layout { display: flex; gap: 14px; }

.table-list {
  width: 240px;
  flex-shrink: 0;
  overflow-y: auto;
  border-right: 1px solid var(--el-border-color-lighter);
  padding-right: 8px;
}
.table-filter { margin-bottom: 8px; }
.table-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;

  &:hover { background: var(--el-fill-color-light); }
  &.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }

  .ti-icon { flex-shrink: 0; color: var(--el-text-color-secondary); }
  .ti-name { font-weight: 500; }
  .ti-comment {
    margin-left: auto;
    max-width: 90px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: var(--el-text-color-secondary);
  }
}
.col-panel { flex: 1; min-width: 0; }
.col-head {
  margin-bottom: 8px;
  font-size: 14px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.col-head-comment { font-size: 12px; color: var(--el-text-color-secondary); }
.view-toggle { margin-left: auto; }
.col-refresh { flex-shrink: 0; }

// 结构表 / 数据表：紧凑行高 + 表头加黑（一屏多看几行）
.compact-table {
  :deep(.el-table__cell) {
    padding: 3px 0;
    font-size: 12px;
  }
  :deep(thead th.el-table__cell) {
    font-weight: 700;
    color: var(--el-text-color-primary);
    background: var(--el-fill-color-light);
  }
}

.rows-pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.pager-info {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.cell-null {
  color: var(--el-text-color-placeholder);
  font-style: italic;
  font-size: 12px;
}
</style>
