<template>
  <div class="databases-view">
    <AppPageHeader
      icon="i-solar-database-bold"
      :illustration="illustEnvironment"
      title="数据库连接"
      description="管理测试用的数据库连接配置"
    >
      <template #actions>
        <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
          <i class="i-solar-add-circle-bold mr-1" />
          新建连接
        </el-button>
      </template>
    </AppPageHeader>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <AppStatCard
        label="连接总数"
        :value="databases.length"
        icon-name="i-solar-server-bold"
        color="brand"
      />
      <AppStatCard
        label="已连接"
        :value="connectedCount"
        icon-name="i-solar-link-circle-bold"
        color="success"
      />
      <AppStatCard
        label="未连接"
        :value="disconnectedCount"
        icon-name="i-solar-link-broken-bold"
        color="danger"
      />
      <AppStatCard
        label="数据库类型"
        :value="dbTypeCount"
        icon-name="i-solar-database-bold"
        color="info"
      />
    </div>

    <!-- 筛选栏 -->
    <AppSectionCard>
      <div class="filter-bar">
        <el-select
          v-model="filters.db_type"
          placeholder="筛选数据库类型"
          clearable
          class="filter-select"
          @change="handleSearch"
        >
          <el-option label="全部类型" value="" />
          <el-option label="MySQL" value="MySQL" />
          <el-option label="PostgreSQL" value="PostgreSQL" />
          <el-option label="Oracle" value="Oracle" />
          <el-option label="SQLServer" value="SQLServer" />
          <el-option label="MongoDB" value="MongoDB" />
          <el-option label="Redis" value="Redis" />
        </el-select>

        <el-input
          v-model="filters.keyword"
          placeholder="搜索连接名称"
          clearable
          class="filter-input"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <i class="i-solar-magnifer-linear" />
          </template>
        </el-input>

        <el-button @click="handleSearch">
          <i class="i-solar-magnifer-linear mr-1" /> 搜索
        </el-button>
        <el-button @click="handleReset">
          <i class="i-solar-refresh-linear mr-1" /> 重置
        </el-button>

        <div class="filter-spacer" />

        <el-button-group>
          <el-button
            :type="viewMode === 'card' ? 'primary' : 'default'"
            @click="viewMode = 'card'"
          >
            <i class="i-solar-widget-2-bold" />
          </el-button>
          <el-button
            :type="viewMode === 'table' ? 'primary' : 'default'"
            @click="viewMode = 'table'"
          >
            <i class="i-solar-list-bold" />
          </el-button>
        </el-button-group>
      </div>
    </AppSectionCard>

    <!-- 数据库连接列表 -->
    <div v-loading="loading" class="databases-list">
      <AppEmpty
        v-if="!loading && databases.length === 0"
        scene="data"
        title="暂无数据库连接"
        description="创建第一个数据库连接开始测试"
      >
        <template #actions>
          <el-button v-permission="'environment:create'" type="primary" @click="handleCreate">
            <i class="i-solar-add-circle-bold mr-1" />
            创建连接
          </el-button>
        </template>
      </AppEmpty>

      <!-- 卡片视图 -->
      <div v-else-if="viewMode === 'card'" class="card-grid">
        <div
          v-for="db in databases"
          :key="db.id"
          class="db-card"
          :class="{ 'is-connected': db.connection_status === 'connected' }"
        >
          <!-- 头部：图标 + 名称 + 状态 + 操作 -->
          <div class="db-card-header">
            <div class="db-card-icon">
              <i :class="getDbIconClass(db.db_type)" />
            </div>
            <div class="db-card-title-wrap">
              <h3 class="db-card-title">{{ db.name }}</h3>
              <span class="soft-pill" :class="getStatusPill(db.connection_status)">
                <span class="status-dot" />
                {{ getStatusText(db.connection_status) }}
              </span>
            </div>
            <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, db)">
              <el-button text size="small" class="more-btn">
                <i class="i-solar-menu-dots-bold" />
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="test">
                    <i class="i-solar-link-circle-bold mr-1" /> 测试连接
                  </el-dropdown-item>
                  <el-dropdown-item command="edit">
                    <i class="i-solar-pen-2-linear mr-1" /> 编辑
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <i class="i-solar-trash-bin-trash-linear mr-1" /> 删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 主体信息 -->
          <div class="db-card-body">
            <div class="db-info-row">
              <i class="i-solar-server-2-linear info-icon" />
              <span class="db-info-label">类型</span>
              <span class="db-info-value">{{ db.db_type }}</span>
            </div>
            <div class="db-info-row">
              <i class="i-solar-global-linear info-icon" />
              <span class="db-info-label">主机</span>
              <code class="db-info-url">{{ db.host }}:{{ db.port }}</code>
            </div>
            <div class="db-info-row">
              <i class="i-solar-database-linear info-icon" />
              <span class="db-info-label">数据库</span>
              <span class="db-info-value">{{ db.database }}</span>
            </div>
            <div class="db-info-row">
              <i class="i-solar-user-circle-linear info-icon" />
              <span class="db-info-label">用户名</span>
              <span class="db-info-value">{{ db.username }}</span>
            </div>
            <div v-if="db.last_test_time" class="db-info-row">
              <i class="i-solar-clock-circle-linear info-icon" />
              <span class="db-info-label">最后测试</span>
              <span class="db-info-value">{{ formatDateTime(db.last_test_time) }}</span>
            </div>
          </div>

          <!-- 底部操作 -->
          <div class="db-card-footer">
            <el-button
              size="small"
              :loading="testingIds.has(db.id)"
              @click="handleTest(db)"
            >
              <i class="i-solar-link-circle-bold mr-1" /> 测试
            </el-button>
            <el-button size="small" @click="handleViewSchema(db)">
              <i class="i-solar-database-linear mr-1" /> 表结构
            </el-button>
            <el-button v-permission="'environment:edit'" size="small" type="primary" @click="handleEdit(db)">
              <i class="i-solar-pen-2-linear mr-1" /> 编辑
            </el-button>
          </div>
        </div>
      </div>

      <!-- 表格视图 -->
      <AppSectionCard v-else padless>
        <el-table :data="databases">
          <el-table-column label="名称" min-width="160">
            <template #default="{ row }">
              <div class="table-name-cell">
                <i :class="getDbIconClass(row.db_type)" class="table-db-icon" />
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="120" align="center">
            <template #default="{ row }">
              <span class="soft-pill pill-brand">{{ row.db_type }}</span>
            </template>
          </el-table-column>
          <el-table-column label="主机" min-width="180">
            <template #default="{ row }">
              <code class="table-host">{{ row.host }}:{{ row.port }}</code>
            </template>
          </el-table-column>
          <el-table-column label="数据库" min-width="140">
            <template #default="{ row }">{{ row.database }}</template>
          </el-table-column>
          <el-table-column label="用户名" width="120">
            <template #default="{ row }">{{ row.username }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120" align="center">
            <template #default="{ row }">
              <span class="soft-pill" :class="getStatusPill(row.connection_status)">
                <span class="status-dot" />
                {{ getStatusText(row.connection_status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="最后测试" width="140">
            <template #default="{ row }">
              {{ row.last_test_time ? formatDateTime(row.last_test_time) : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="290" align="center" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  type="primary"
                  plain
                  size="small"
                  :loading="testingIds.has(row.id)"
                  @click.stop="handleTest(row)"
                >
                  <i class="i-solar-link-circle-bold mr-1" /> 测试
                </el-button>
                <el-button size="small" @click.stop="handleViewSchema(row)">
                  <i class="i-solar-database-linear mr-1" /> 表结构
                </el-button>
                <el-button v-permission="'environment:edit'" size="small" @click.stop="handleEdit(row)">
                  <i class="i-solar-pen-2-linear mr-1" /> 编辑
                </el-button>
                <el-button v-permission="'environment:delete'" type="danger" plain size="small" @click.stop="handleDelete(row)">
                  <i class="i-solar-trash-bin-trash-linear mr-1" /> 删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </AppSectionCard>
    </div>

    <!-- 创建/编辑数据库连接对话框 -->
    <DatabaseFormDialog
      v-if="formDialogVisible"
      v-model="formDialogVisible"
      :database="currentDatabase"
      :project-id="projectId"
      @success="handleFormSuccess"
    />

    <!-- 表结构查看 -->
    <SchemaViewerDialog
      v-model="schemaVisible"
      :project-id="projectId"
      :conn-id="schemaConn?.id || 0"
      :conn-name="schemaConn?.name || ''"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type { DatabaseConnection, DatabaseType, ConnectionStatus } from '@/api/environments'
import DatabaseFormDialog from './components/DatabaseFormDialog.vue'
import SchemaViewerDialog from './components/SchemaViewerDialog.vue'
import { AppPageHeader, AppStatCard, AppSectionCard, AppEmpty } from '@/components/common'
import illustEnvironment from '@/assets/illustrations/environment.svg'

const route = useRoute()
const projectId = computed(() => {
  const id = Number(route.params.id)
  return isNaN(id) ? 0 : id
})

const viewMode = ref<'card' | 'table'>('card')
const loading = ref(false)
const databases = ref<DatabaseConnection[]>([])
const testingIds = ref<Set<number>>(new Set())

const filters = ref<{ db_type: DatabaseType | ''; keyword: string }>({
  db_type: '',
  keyword: '',
})

const formDialogVisible = ref(false)
const currentDatabase = ref<DatabaseConnection | null>(null)

const schemaVisible = ref(false)
const schemaConn = ref<DatabaseConnection | null>(null)
const handleViewSchema = (db: DatabaseConnection) => {
  schemaConn.value = db
  schemaVisible.value = true
}

// 统计
const connectedCount = computed(() => databases.value.filter(d => d.connection_status === 'connected').length)
const disconnectedCount = computed(() => databases.value.filter(d => d.connection_status !== 'connected').length)
const dbTypeCount = computed(() => new Set(databases.value.map(d => d.db_type)).size)

// 图标 class（静态映射，不动态拼接）
const getDbIconClass = (dbType: DatabaseType) => {
  const map: Record<DatabaseType, string> = {
    MySQL: 'i-solar-server-bold',
    PostgreSQL: 'i-solar-database-bold',
    Oracle: 'i-solar-database-bold',
    SQLServer: 'i-solar-database-bold',
    MongoDB: 'i-solar-database-bold',
    Redis: 'i-solar-key-bold',
  }
  return map[dbType] || 'i-solar-database-bold'
}

const getStatusPill = (status: ConnectionStatus) => {
  const map: Record<ConnectionStatus, string> = {
    connected: 'pill-success',
    disconnected: 'pill-danger',
    unknown: 'pill-info',
  }
  return map[status] || 'pill-info'
}

const getStatusText = (status: ConnectionStatus) => {
  const map: Record<ConnectionStatus, string> = {
    connected: '已连接',
    disconnected: '未连接',
    unknown: '未知',
  }
  return map[status] || '未知'
}

const formatDateTime = (datetime?: string) => {
  if (!datetime) return '-'
  const date = new Date(datetime)
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const loadDatabases = async () => {
  loading.value = true
  try {
    const params: { db_type?: DatabaseType; keyword?: string } = {}
    if (filters.value.db_type) params.db_type = filters.value.db_type
    if (filters.value.keyword) params.keyword = filters.value.keyword
    const res = await environmentApi.getDatabaseList(projectId.value, params)
    databases.value = res.data || []
  } catch (error) {
    console.error('加载数据库连接列表失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { loadDatabases() }
const handleReset = () => { filters.value = { db_type: '', keyword: '' }; loadDatabases() }
const handleCreate = () => { currentDatabase.value = null; formDialogVisible.value = true }
const handleEdit = (db: DatabaseConnection) => { currentDatabase.value = db; formDialogVisible.value = true }

const handleTest = async (db: DatabaseConnection) => {
  testingIds.value.add(db.id)
  try {
    const res = await environmentApi.testDatabase(projectId.value, db.id)
    if (res.data.status === 'connected') {
      ElMessage.success(res.data.message || '连接成功')
    } else {
      ElMessage.warning(res.data.message || '连接失败')
    }
    loadDatabases()
  } catch (error) {
    console.error('测试数据库连接失败:', error)
  } finally {
    testingIds.value.delete(db.id)
  }
}

const handleDelete = async (db: DatabaseConnection) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据库连接 "${db.name}" 吗？删除后将无法恢复。`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
    await environmentApi.deleteDatabase(projectId.value, db.id)
    ElMessage.success('删除成功')
    loadDatabases()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除数据库连接失败:', error)
    }
  }
}

const handleCommand = (command: string, db: DatabaseConnection) => {
  switch (command) {
    case 'test': handleTest(db); break
    case 'edit': handleEdit(db); break
    case 'delete': handleDelete(db); break
  }
}

const handleFormSuccess = () => { formDialogVisible.value = false; loadDatabases() }

onMounted(() => { loadDatabases() })
</script>

<style scoped lang="scss">
.databases-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-bottom: var(--space-5);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);

  .filter-select { width: 160px; }
  .filter-input { width: 240px; }
  .filter-spacer { flex: 1; }
}

.databases-list {
  min-height: 400px;
  flex: 1;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

/* 数据库卡片 */
.db-card {
  background: var(--bg-card);
  border: 0;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: var(--transition-base);
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &:hover {
    box-shadow: var(--shadow-hover);
  }
}

/* 顶部 header：图标 + 名称 + 状态 + 操作 */
.db-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);

  .more-btn { margin-left: auto; flex-shrink: 0; }
}

.db-card-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
  background: var(--bg-hover);
  color: var(--brand-500);
}

.db-card-title-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.db-card-title {
  font-size: 15px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 信息行：图标 + label + value */
.db-card-body {
  flex: 1;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.db-info-row {
  display: grid;
  grid-template-columns: 18px auto 1fr;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 6px 0;
}

.info-icon {
  color: var(--text-placeholder);
  font-size: 15px;
}

.db-info-label {
  color: var(--text-secondary);
  font-size: 12px;
}

.db-info-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  font-size: 13px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.db-info-url {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--gray-50);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 底部操作 */
.db-card-footer {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--gray-50);

  .el-button { flex: 1; }
}

/* 软色 pill */
.soft-pill {
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;

  &.pill-brand { background: var(--brand-50); color: var(--brand-600); }
  &.pill-info { background: var(--color-info-50); color: var(--color-info-600); }
  &.pill-success { background: var(--color-success-50); color: var(--color-success-600); }
  &.pill-warning { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.pill-danger { background: var(--color-danger-50); color: var(--color-danger-600); }
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;

  .pill-success & {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-success-500) 20%, transparent);
  }
}

/* 表格 */
.table-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);

  .table-db-icon {
    font-size: 18px;
    color: var(--brand-500);
  }
}

.table-host {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--gray-50);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

/* 操作列按钮容器 */
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 响应式 */
@media (max-width: 768px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .card-grid { grid-template-columns: 1fr; }
  .filter-bar { flex-wrap: wrap; }
  .filter-select, .filter-input { width: 100%; }
}
</style>