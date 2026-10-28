/**
 * 权限管理页面
 *
 * AI 智能测试平台 - 权限管理
 * 对应需求文档：01-用户与权限管理模块.md
 * 视图聚焦"角色管理"：通过 Tabs 切换自定义角色 vs 系统角色
 */

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePermissionStore } from '@/stores/permissions'
import { useRoleManageStore } from '@/stores/roleManage'
import type { RoleListItem } from '@/types/role'
import AppSectionCard from '@/components/common/AppSectionCard.vue'
import AppStatCard from '@/components/common/AppStatCard.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import RoleDialog from '@/components/permission/RoleDialog.vue'

const permissionStore = usePermissionStore()
const roleManageStore = useRoleManageStore()

// ==================== 状态 ====================
const tableLoading = ref(false)
const activeTab = ref<'custom' | 'system' | 'permissions'>('custom')

const roleDialogVisible = ref(false)
const roleDialogMode = ref<'create' | 'edit'>('create')
const currentRole = ref<RoleListItem | null>(null)

// 搜索表单
const searchFormRef = ref()
const searchForm = ref({
  keyword: '',
  isSystem: '' as '' | 'yes' | 'no',
  status: '' as string,
})

// ==================== 角色头像 / 图标映射 ====================
type RoleIconStyle = {
  icon: string
  color: 'brand' | 'info' | 'success' | 'warning' | 'danger' | 'purple' | 'cyan'
  bg: string
}

const roleIconMap: Record<string, RoleIconStyle> = {
  // 系统角色（决定实际权限）
  super_admin:        { icon: 'i-solar-crown-bold',           color: 'success', bg: 'var(--color-success-50, #f0fdf4)' },
  admin:              { icon: 'i-solar-shield-user-bold',     color: 'info',    bg: 'var(--color-info-50, #eff6ff)' },
  project_admin:      { icon: 'i-solar-user-hand-up-bold',    color: 'purple',  bg: 'var(--color-purple-50, #faf5ff)' },
  tester:             { icon: 'i-solar-case-bold',            color: 'warning', bg: 'var(--color-warning-50, #fffbeb)' },
  developer:          { icon: 'i-solar-code-bold',            color: 'info',    bg: 'var(--color-info-50, #eff6ff)' },
  user:               { icon: 'i-solar-user-bold',            color: 'success', bg: 'var(--color-success-50, #f0fdf4)' },
  // 项目角色（仅组织标签，不控权）
  project_owner:      { icon: 'i-solar-user-hand-up-bold',        color: 'purple', bg: 'var(--color-purple-50, #faf5ff)' },
  project_member:     { icon: 'i-solar-users-group-rounded-bold', color: 'info',   bg: 'var(--color-info-50, #eff6ff)' },
}

const colorVarMap: Record<RoleIconStyle['color'], string> = {
  brand:   'var(--brand-500)',
  info:    'var(--color-info-500)',
  success: 'var(--color-success-500)',
  warning: 'var(--color-warning-500)',
  danger:  'var(--color-danger-500)',
  purple:  'var(--color-purple-500)',
  cyan:    'var(--color-cyan-500)',
}

const getRoleIcon = (row: RoleListItem): RoleIconStyle =>
  roleIconMap[row.code] || {
    icon: 'i-solar-user-circle-bold',
    color: 'brand',
    bg: 'var(--brand-glow-soft)',
  }

// ==================== 数据计算 ====================

const allRoles = computed<RoleListItem[]>(() => roleManageStore.roleList)

const customRoles = computed(() => allRoles.value.filter((r) => !r.is_system))
const systemRoles = computed(() => allRoles.value.filter((r) =>  r.is_system))

// 当前 tab 展示的数据（应用筛选）
const currentList = computed(() => {
  const kw = searchForm.value.keyword.trim().toLowerCase()
  const isSystem = activeTab.value === 'system'
  return (isSystem ? systemRoles.value : customRoles.value).filter((r) => {
    if (!kw) return true
    return (
      r.name.toLowerCase().includes(kw) ||
      r.code.toLowerCase().includes(kw) ||
      (r.description || '').toLowerCase().includes(kw)
    )
  })
})

// 总权限数（所有角色权限去重并集的大小，简单起见按 role.permissions 总和）
const totalPermissions = computed(() => {
  const set = new Set<string>()
  allRoles.value.forEach((r) => (r.permissions || []).forEach((p) => set.add(p)))
  return set.size
})

// ==================== 权限列表（按模块分组） ====================

const permKeyword = ref('')
const permModuleFilter = ref('')
const permTypeFilter = ref('')

/** 模块 → 图标 class 映射（覆盖后端实际 16 个模块） */
const moduleIconMap: Record<string, string> = {
  '用户管理': 'i-solar-users-group-rounded-bold',
  '角色管理': 'i-solar-shield-user-bold',
  '权限管理': 'i-solar-key-square-2-bold',
  '项目管理': 'i-solar-folder-bold',
  '功能测试': 'i-app-test-case',
  '接口测试': 'i-app-api',
  'Web自动化': 'i-app-browser',
  '缺陷管理': 'i-app-bug',
  '测试报告': 'i-app-test-report',
  '测试环境': 'i-solar-server-2-bold',
  '定时调度': 'i-solar-clock-circle-bold',
  'AI 任务': 'i-app-ai-agent',
  'AI 助手': 'i-app-ai-spark',
  '知识库': 'i-app-knowledge',
  '系统管理': 'i-solar-settings-bold',
  '认证授权': 'i-solar-lock-keyhole-bold',
}

const getModuleIcon = (moduleName: string): string =>
  moduleIconMap[moduleName] || 'i-solar-widget-bold'

/** 模块配色 */
const moduleColorMap: Record<string, string> = {
  '用户管理': 'info',
  '角色管理': 'purple',
  '权限管理': 'warning',
  '项目管理': 'brand',
  '功能测试': 'success',
  '接口测试': 'purple',
  'Web自动化': 'cyan',
  '缺陷管理': 'danger',
  '测试报告': 'cyan',
  '测试环境': 'info',
  '定时调度': 'warning',
  'AI 任务': 'purple',
  'AI 助手': 'purple',
  '知识库': 'cyan',
  '系统管理': 'danger',
  '认证授权': 'success',
}

const colorVarMapLight: Record<string, string> = {
  brand:   'var(--brand-glow-soft, rgba(64, 158, 255, 0.10))',
  info:    'var(--color-info-50, #eff6ff)',
  success: 'var(--color-success-50, #f0fdf4)',
  warning: 'var(--color-warning-50, #fffbeb)',
  danger:  'var(--color-danger-50, #fef2f2)',
  purple:  'var(--color-purple-50, #faf5ff)',
  cyan:    'rgba(6, 182, 212, 0.10)',
}

const colorVarMapFg: Record<string, string> = {
  brand:   'var(--brand-500)',
  info:    'var(--color-info-500)',
  success: 'var(--color-success-500)',
  warning: 'var(--color-warning-500)',
  danger:  'var(--color-danger-500)',
  purple:  'var(--color-purple-500)',
  cyan:    'var(--color-cyan-500)',
}

const getModuleColor = (moduleName: string): string =>
  moduleColorMap[moduleName] || 'brand'

/** 操作类型：从权限编码 action 段派生（读取/新增/编辑/删除/执行/管理/认证） */
type PermTypeKey = 'read' | 'create' | 'update' | 'delete' | 'execute' | 'manage' | 'auth'

const ACTION_TYPE: Record<string, PermTypeKey> = {
  view: 'read', log: 'read', monitor: 'read', export: 'read',
  create: 'create', add: 'create', register: 'create',
  edit: 'update', edit_own: 'update', edit_role: 'update', config: 'update',
  assign: 'update', close: 'update', resolve: 'update', archive: 'update',
  reset_pwd: 'update', manage_member: 'update',
  delete: 'delete', remove: 'delete',
  execute: 'execute', use: 'execute',
  manage: 'manage',
  login: 'auth', logout: 'auth',
}

const PERM_TYPE_META: Record<PermTypeKey, { label: string; cls: string }> = {
  read:    { label: '读取', cls: 'ptype-read' },
  create:  { label: '新增', cls: 'ptype-create' },
  update:  { label: '编辑', cls: 'ptype-update' },
  delete:  { label: '删除', cls: 'ptype-delete' },
  execute: { label: '执行', cls: 'ptype-execute' },
  manage:  { label: '管理', cls: 'ptype-manage' },
  auth:    { label: '认证', cls: 'ptype-auth' },
}

const permTypeKey = (code?: string): PermTypeKey =>
  ACTION_TYPE[(code || '').split(':')[1] || ''] ?? 'manage'

const permTypeMeta = (code?: string) => PERM_TYPE_META[permTypeKey(code)]

/** 类型筛选下拉项 */
const permTypeOptions = (Object.keys(PERM_TYPE_META) as PermTypeKey[]).map((k) => ({
  value: k,
  label: PERM_TYPE_META[k].label,
}))

/** 模块筛选下拉项（带计数） */
const moduleOptions = computed(() =>
  Object.keys(permissionStore.permissionsByModule).map((name) => ({
    name,
    count: (permissionStore.permissionsByModule[name] || []).length,
  })),
)

/** 按模块分组的权限目录（应用 搜索 + 模块 + 类型 过滤） */
const permissionsByModuleList = computed(() => {
  const modules = permissionStore.permissionsByModule
  const kw = permKeyword.value.trim().toLowerCase()
  const modFilter = permModuleFilter.value
  const typeFilter = permTypeFilter.value
  const out: { name: string; perms: typeof permissionStore.permissions }[] = []

  Object.keys(modules).forEach((moduleName) => {
    if (modFilter && moduleName !== modFilter) return
    let perms = modules[moduleName] || []
    if (kw) {
      perms = perms.filter(
        (p) => p.code?.toLowerCase().includes(kw) || p.name?.toLowerCase().includes(kw),
      )
    }
    if (typeFilter) {
      perms = perms.filter((p) => permTypeKey(p.code) === typeFilter)
    }
    if (perms.length > 0) out.push({ name: moduleName, perms })
  })
  return out
})

/** 过滤后的权限总数 */
const filteredPermTotal = computed(() =>
  permissionsByModuleList.value.reduce((sum, m) => sum + m.perms.length, 0),
)

/** 复制权限编码 */
const copyCode = async (code?: string) => {
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success(`已复制：${code}`)
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

// 统计卡（带趋势百分比，演示数据）
const stats = computed(() => [
  { label: '角色总数',     value: allRoles.value.length,  trend: 14.3, iconName: 'i-solar-users-group-rounded-bold', color: 'success' as const },
  { label: '系统角色',     value: systemRoles.value.length, trend: 10.0, iconName: 'i-solar-shield-keyhole-bold',   color: 'info' as const },
  { label: '自定义角色',   value: customRoles.value.length, trend: 50.0, iconName: 'i-solar-user-plus-bold',         color: 'purple' as const },
  { label: '总策略数量',   value: totalPermissions.value,  trend: 8.5,  iconName: 'i-solar-key-minimalistic-square-2-bold', color: 'warning' as const },
])

// ==================== 方法 ====================

const fetchRoles = async () => {
  tableLoading.value = true
  await roleManageStore.fetchRoleList()
  tableLoading.value = false
}

const handleRefresh = async () => {
  await fetchRoles()
}

const handleSearch = () => {
  // 过滤为纯前端
}

const handleReset = () => {
  searchFormRef.value?.resetFields()
  handleSearch()
}

// 创建角色（弹窗）
const handleCreateRole = () => {
  roleDialogMode.value = 'create'
  currentRole.value = null
  roleDialogVisible.value = true
}

// 编辑角色
const handleEdit = (row: RoleListItem) => {
  roleDialogMode.value = 'edit'
  currentRole.value = row
  roleDialogVisible.value = true
}

// 删除角色
const handleDelete = async (row: RoleListItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除角色「${row.name}」吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    const success = await permissionStore.deleteRole(row.id)
    if (success) {
      ElMessage.success('删除成功')
      await fetchRoles()
    }
  } catch {
    // 用户取消
  }
}

// ==================== 查看权限弹窗 ====================

const viewDialogVisible = ref(false)
const viewDialogRole = ref<RoleListItem | null>(null)
const viewPermKeyword = ref('')

/** 全量权限（code → 详情）索引 */
const permissionIndex = computed(() => {
  const map = new Map<string, typeof permissionStore.permissions[number]>()
  permissionStore.permissions.forEach((p) => map.set(p.code, p))
  return map
})

/** 当前查看角色拥有的权限详情 */
const viewRoleOwnedPerms = computed(() => {
  if (!viewDialogRole.value) return [] as typeof permissionStore.permissions
  const codes = new Set(viewDialogRole.value.permissions || [])
  return permissionStore.permissions.filter((p) => codes.has(p.code))
})

/** 按模块分组的该角色所拥有的权限 */
const viewRoleGroupedPerms = computed<{ name: string; perms: typeof permissionStore.permissions }[]>(() => {
  const kw = viewPermKeyword.value.trim().toLowerCase()
  const all = viewRoleOwnedPerms.value
  const filtered = kw
    ? all.filter(
        (p) =>
          p.code?.toLowerCase().includes(kw) ||
          p.name?.toLowerCase().includes(kw),
      )
    : all
  const groups: Record<string, typeof permissionStore.permissions> = {}
  filtered.forEach((p) => {
    const mod = p.module || '其他'
    if (!groups[mod]) groups[mod] = []
    groups[mod].push(p)
  })
  return Object.keys(groups).map((name) => ({
    name,
    perms: groups[name] as typeof permissionStore.permissions,
  }))
})

const openViewPermissions = (row: RoleListItem) => {
  viewDialogRole.value = row
  viewPermKeyword.value = ''
  viewDialogVisible.value = true
}

const closeViewPermissions = () => {
  viewDialogVisible.value = false
  viewDialogRole.value = null
  viewPermKeyword.value = ''
}

// 系统角色 - 复制为自定义角色
const handleClone = (row: RoleListItem) => {
  roleDialogMode.value = 'create'
  currentRole.value = row
  roleDialogVisible.value = true
}

const handleDialogSuccess = async () => {
  roleDialogVisible.value = false
  await fetchRoles()
}

onMounted(async () => {
  await Promise.all([
    fetchRoles(),
    permissionStore.fetchAllPermissions(),
  ])
})
</script>

<template>
  <div class="permissions-view">
    <!-- 页头 -->
    <div class="page-header">
      <div class="page-title">
        <div class="title-row">
          <i class="i-solar-shield-check-bold title-icon" />
          <h2>权限管理</h2>
          <span class="title-badge">1</span>
        </div>
        <p class="page-description">管理系统角色和权限分配，确保不同角色拥有合适的系统访问权限</p>
      </div>
      <div class="page-actions">
        <el-button @click="handleRefresh">
          <i class="i-solar-refresh-bold" />
          刷新
        </el-button>
        <el-button v-permission="'role:create'" type="primary" @click="handleCreateRole">
          <i class="i-solar-add-circle-bold" />
          创建角色
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <AppStatCard
        v-for="stat in stats"
        :key="stat.label"
        :label="stat.label"
        :value="stat.value"
        :trend="stat.trend"
        :icon-name="stat.iconName"
        :color="stat.color"
      />
    </div>

    <!-- 筛选区 -->
    <AppSectionCard>
      <div v-if="activeTab !== 'permissions'" class="filter-bar">
        <el-form ref="searchFormRef" :model="searchForm" inline class="filter-form">
          <el-form-item>
            <el-input
              v-model="searchForm.keyword"
              placeholder="搜索角色名称/编码/描述"
              clearable
              class="filter-input"
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #prefix>
                <i class="i-solar-magnifer-linear" />
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-select
              v-model="searchForm.isSystem"
              placeholder="系统角色"
              clearable
              class="filter-select"
              @change="handleSearch"
            >
              <el-option label="全部" value="" />
              <el-option label="系统角色" value="yes" />
              <el-option label="自定义角色" value="no" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-select
              v-model="searchForm.status"
              placeholder="全部状态"
              class="filter-select"
              disabled
            >
              <el-option label="全部状态" value="" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleSearch">
              <i class="i-solar-magnifer-bold" />
              搜索
            </el-button>
            <el-button @click="handleReset">
              <i class="i-solar-restart-bold" />
              重置
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- Tabs -->
      <el-tabs v-model="activeTab" class="role-tabs">
        <el-tab-pane name="custom">
          <template #label>
            <span class="tab-label">
              自定义角色
              <span class="tab-badge">{{ customRoles.length }}</span>
            </span>
          </template>

          <!-- 自定义角色：空状态 / 表格 -->
          <div v-if="customRoles.length === 0" class="empty-wrapper">
            <AppEmpty
              scene="data"
              description="点击右上角'创建角色'按钮创建"
              empty-title="暂无自定义角色"
            >
              <template #actions>
                <el-button v-permission="'role:create'" type="primary" @click="handleCreateRole">
                  <i class="i-solar-add-circle-bold" />
                  创建角色
                </el-button>
              </template>
            </AppEmpty>
          </div>

          <el-table
            v-else
            v-loading="tableLoading"
            :data="currentList"
            class="role-table"
          >
            <el-table-column label="角色名称" min-width="200">
              <template #default="{ row }">
                <div class="role-cell">
                  <div
                    class="role-avatar"
                    :style="{ background: getRoleIcon(row).bg, color: colorVarMap[getRoleIcon(row).color] }"
                  >
                    <i :class="getRoleIcon(row).icon" />
                  </div>
                  <div class="role-info">
                    <span class="role-name">{{ row.name }}</span>
                    <span class="role-code">{{ row.code }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="description" label="描述" min-width="240">
              <template #default="{ row }">
                <span class="desc-text">{{ row.description || '-' }}</span>
              </template>
            </el-table-column>

            <el-table-column label="权限数量" width="110" align="center">
              <template #default="{ row }">
                <span class="perm-num">{{ row.permissions?.length || 0 }}</span>
              </template>
            </el-table-column>

            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">
                {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
              </template>
            </el-table-column>

            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button
                    v-permission="'role:edit'"
                    size="small"
                    @click="handleEdit(row)"
                  >
                    <i class="i-solar-pen-2-bold action-icon" />
                    编辑
                  </el-button>
                  <el-button
                    v-permission="'role:delete'"
                    type="danger"
                    plain
                    size="small"
                    @click="handleDelete(row)"
                  >
                    <i class="i-solar-trash-bin-trash-bold action-icon" />
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane name="system">
          <template #label>
            <span class="tab-label">
              系统角色
              <span class="tab-badge">{{ systemRoles.length }}</span>
            </span>
          </template>

          <el-table
            v-loading="tableLoading"
            :data="currentList"
            class="role-table"
          >
            <el-table-column label="角色名称" min-width="200">
              <template #default="{ row }">
                <div class="role-cell">
                  <div
                    class="role-avatar"
                    :style="{ background: getRoleIcon(row).bg, color: colorVarMap[getRoleIcon(row).color] }"
                  >
                    <i :class="getRoleIcon(row).icon" />
                  </div>
                  <div class="role-info">
                    <span class="role-name">{{ row.name }}</span>
                    <span class="role-code">{{ row.code }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="description" label="描述" min-width="240">
              <template #default="{ row }">
                <span class="desc-text">{{ row.description || '-' }}</span>
              </template>
            </el-table-column>

            <el-table-column label="权限数量" width="110" align="center">
              <template #default="{ row }">
                <span class="perm-num">{{ row.permissions?.length || 0 }}</span>
              </template>
            </el-table-column>

            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">
                {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
              </template>
            </el-table-column>

            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" @click="openViewPermissions(row)">
                    <i class="i-solar-key-minimalistic-square-2-bold action-icon" />
                    查看权限
                  </el-button>
                  <el-dropdown v-permission="'role:create'" trigger="click" @command="(c: string) => c === 'clone' && handleClone(row)">
                    <el-button size="small" class="more-btn">
                      <i class="i-solar-menu-dots-bold" />
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="clone">
                          <i class="i-solar-copy-bold" />
                          复制为自定义角色
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 权限列表 Tab -->
        <el-tab-pane name="permissions">
          <template #label>
            <span class="tab-label">
              权限列表
              <span class="tab-badge">{{ permissionStore.permissions.length }}</span>
            </span>
          </template>

          <!-- 工具条：搜索 + 模块 + 类型 + 计数 -->
          <div class="perm-toolbar">
            <el-input
              v-model="permKeyword"
              placeholder="搜索权限名称或编码"
              clearable
              class="perm-toolbar-search"
            >
              <template #prefix>
                <i class="i-solar-magnifer-linear" />
              </template>
            </el-input>
            <el-select
              v-model="permModuleFilter"
              placeholder="全部模块"
              clearable
              class="perm-toolbar-select"
            >
              <el-option
                v-for="m in moduleOptions"
                :key="m.name"
                :label="`${m.name}（${m.count}）`"
                :value="m.name"
              />
            </el-select>
            <el-select
              v-model="permTypeFilter"
              placeholder="全部类型"
              clearable
              class="perm-toolbar-select"
            >
              <el-option
                v-for="t in permTypeOptions"
                :key="t.value"
                :label="t.label"
                :value="t.value"
              />
            </el-select>
            <span class="perm-toolbar-count">共 <b>{{ filteredPermTotal }}</b> 项</span>
          </div>

          <!-- 权限目录表（按模块分组） -->
          <div v-loading="permissionStore.loading" class="perm-catalog">
            <div class="perm-row perm-row--head">
              <span>权限名称</span>
              <span>权限编码</span>
              <span>操作类型</span>
            </div>

            <template v-for="module in permissionsByModuleList" :key="module.name">
              <div class="perm-group-bar">
                <span
                  class="pg-icon"
                  :style="{
                    background: colorVarMapLight[getModuleColor(module.name)],
                    color: colorVarMapFg[getModuleColor(module.name)],
                  }"
                >
                  <i :class="getModuleIcon(module.name)" />
                </span>
                <span class="pg-name">{{ module.name }}</span>
                <span class="pg-count">{{ module.perms.length }}</span>
              </div>

              <div
                v-for="perm in module.perms"
                :key="perm.code || perm.name"
                class="perm-row"
              >
                <span class="pr-name">{{ perm.name }}</span>
                <code class="pr-code" title="点击复制编码" @click="copyCode(perm.code)">
                  <span class="pr-code-text">{{ perm.code }}</span>
                  <i class="i-solar-copy-linear pr-code-copy" />
                </code>
                <span class="pr-type" :class="permTypeMeta(perm.code).cls">
                  {{ permTypeMeta(perm.code).label }}
                </span>
              </div>
            </template>

            <div v-if="permissionsByModuleList.length === 0" class="perm-empty">
              <AppEmpty scene="search" description="没有匹配的权限项" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 分页（仅角色 tab 显示） -->
      <div v-if="activeTab !== 'permissions'" class="pagination-wrap">
        <span class="pagination-total">共 {{ currentList.length }} 条</span>
        <el-pagination
          layout="sizes, prev, pager, next, jumper"
          :total="currentList.length"
          :page-sizes="[10, 20, 50]"
          :default-page-size="20"
          background
        />
      </div>
    </AppSectionCard>

    <!-- 查看权限弹窗 -->
    <el-dialog
      v-model="viewDialogVisible"
      :width="720"
      align-center
      class="view-perm-dialog"
      :close-on-click-modal="false"
      @close="closeViewPermissions"
    >
      <template #header>
        <div v-if="viewDialogRole" class="view-dialog-header">
          <div
            class="view-role-avatar"
            :style="{
              background: getRoleIcon(viewDialogRole).bg,
              color: colorVarMap[getRoleIcon(viewDialogRole).color],
            }"
          >
            <i :class="getRoleIcon(viewDialogRole).icon" />
          </div>
          <div class="view-role-meta">
            <span class="view-role-name">{{ viewDialogRole.name }}</span>
            <span class="view-role-code">{{ viewDialogRole.code }}</span>
            <span v-if="viewDialogRole.description" class="view-role-desc">
              {{ viewDialogRole.description }}
            </span>
          </div>
          <div class="view-role-total">
            <span class="total-num">{{ viewRoleOwnedPerms.length }}</span>
            <span class="total-label">项权限</span>
          </div>
        </div>
      </template>

      <div class="view-dialog-body">
        <el-input
          v-model="viewPermKeyword"
          placeholder="搜索权限名或编码"
          clearable
          class="view-perm-search"
        >
          <template #prefix>
            <i class="i-solar-magnifer-linear" />
          </template>
        </el-input>

        <div v-if="viewRoleGroupedPerms.length === 0" class="view-empty">
          <AppEmpty scene="search" description="没有匹配的权限项" />
        </div>

        <div v-else class="view-perm-groups">
          <div
            v-for="group in viewRoleGroupedPerms"
            :key="group.name"
            class="view-perm-group"
          >
            <div class="view-perm-group-header">
              <div
                class="view-perm-group-icon"
                :style="{
                  background: colorVarMapLight[getModuleColor(group.name)],
                  color: colorVarMapFg[getModuleColor(group.name)],
                }"
              >
                <i :class="getModuleIcon(group.name)" />
              </div>
              <span class="view-perm-group-name">{{ group.name }}</span>
              <span class="view-perm-group-count">{{ group.perms.length }} 项</span>
            </div>

            <div class="view-perm-table">
              <div class="view-perm-row view-perm-row--head">
                <span class="col-name">权限名称</span>
                <span class="col-code">权限编码</span>
              </div>
              <div
                v-for="perm in group.perms"
                :key="perm.code"
                class="view-perm-row"
              >
                <span class="col-name">{{ perm.name }}</span>
                <span class="col-code">{{ perm.code }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="closeViewPermissions">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑角色对话框 -->
    <RoleDialog
      v-model="roleDialogVisible"
      :mode="roleDialogMode"
      :role="currentRole"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped lang="scss">
.permissions-view {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// ==================== 页头 ====================
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;

  h2 {
    font-size: 22px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title-icon {
  font-size: 22px;
  color: var(--brand-500);
}

.title-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  border-radius: 9px;
  background: var(--color-success-50, #f0fdf4);
  color: var(--color-success-600, #16a34a);
  font-size: 11px;
  font-weight: 600;
  border: 1px solid var(--color-success-200, #bbf7d0);
}

.page-description {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.page-actions {
  display: flex;
  gap: 12px;
}

// ==================== 统计卡片 ====================
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

// ==================== 筛选区 ====================
.filter-bar {
  margin-bottom: 8px;
}

.filter-form {
  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.filter-input {
  width: 260px;
}

.filter-select {
  width: 160px;
}

// ==================== Tabs ====================
.role-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }

  :deep(.el-tabs__item) {
    font-size: 14px;
    font-weight: 500;
    padding: 0 16px;
  }

  // 激活 tab 主色下划线
  :deep(.el-tabs__active-bar) {
    background-color: var(--brand-500);
    height: 3px;
    border-radius: 2px;
  }

  :deep(.el-tabs__item.is-active) {
    color: var(--brand-500);
  }

  :deep(.el-tabs__item:hover) {
    color: var(--brand-500);
  }
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  border-radius: 9px;
  background: var(--brand-glow-soft, rgba(64, 158, 255, 0.10));
  color: var(--brand-500);
  font-size: 11px;
  font-weight: 600;
}

// ==================== 表格 ====================
.role-table {
  :deep(th) {
    background: var(--bg-hover, #f8fafc) !important;
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 13px;
  }

  :deep(td) {
    font-size: 13px;
  }
}

.role-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.role-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.role-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.role-code {
  font-size: 12px;
  color: var(--text-placeholder);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.desc-text {
  color: var(--text-secondary);
  line-height: 1.5;
}

.perm-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  padding: 2px 10px;
  border-radius: var(--radius-full, 9999px);
  background: var(--color-success-50, #f0fdf4);
  color: var(--color-success-600, #16a34a);
  font-size: 12px;
  font-weight: 600;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.action-icon {
  font-size: 14px;
  margin-right: 2px;
}

.more-btn {
  font-size: 16px;
}

// ==================== 空状态 ====================
.empty-wrapper {
  padding: 12px 0;
}

// ==================== 分页 ====================
.pagination-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding-top: 16px;
}

.pagination-total {
  font-size: 13px;
  color: var(--text-secondary);
}

// ==================== 权限列表（企业级目录表） ====================
.perm-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.perm-toolbar-search { width: 280px; }
.perm-toolbar-select { width: 168px; }
.perm-toolbar-count {
  margin-left: auto;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);

  b {
    color: var(--brand-600);
    font-weight: var(--font-weight-semibold);
  }
}

.perm-catalog {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-card);
}

/* 行：三列网格；列头与数据行共用同一模板，全局对齐 */
.perm-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 360px) 96px;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-5);
  height: 44px;
  border-top: 1px solid var(--border-light);
}
.perm-row--head {
  height: 40px;
  border-top: none;
  background: var(--gray-50);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  letter-spacing: 0.3px;
}
.perm-row:not(.perm-row--head):hover { background: var(--brand-50); }

/* 模块分组条 */
.perm-group-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-5);
  height: 40px;
  background: var(--gray-50);
  border-top: 1px solid var(--border-light);
}
.pg-icon {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}
.pg-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.pg-count {
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  font-size: 11px;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pr-name {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 编码（等宽 + 点击复制） */
.pr-code {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-self: start;
  max-width: 100%;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--gray-100);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-regular);
  cursor: pointer;
  transition: var(--transition-fast);

  &:hover {
    background: var(--brand-50);
    color: var(--brand-600);
  }
}
.pr-code-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pr-code-copy {
  flex-shrink: 0;
  font-size: 12px;
  opacity: 0;
  transition: opacity var(--duration-fast);
}
.pr-code:hover .pr-code-copy { opacity: 0.7; }

/* 操作类型药丸（令牌着色，零硬编码） */
.pr-type {
  justify-self: start;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  background: var(--tone-bg);
  color: var(--tone-fg);
}
.ptype-read    { --tone-bg: var(--color-info-50);    --tone-fg: var(--color-info-600); }
.ptype-create  { --tone-bg: var(--color-success-50); --tone-fg: var(--color-success-600); }
.ptype-update  { --tone-bg: var(--color-warning-50); --tone-fg: var(--color-warning-600); }
.ptype-delete  { --tone-bg: var(--color-danger-50);  --tone-fg: var(--color-danger-600); }
.ptype-execute { --tone-bg: var(--color-purple-50);  --tone-fg: var(--color-purple-600); }
.ptype-manage  { --tone-bg: var(--color-cyan-50);    --tone-fg: var(--color-cyan-600); }
.ptype-auth    { --tone-bg: var(--gray-100);         --tone-fg: var(--text-secondary); }

.perm-empty { padding: var(--space-8) 0; }

@media (max-width: 768px) {
  .stat-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .perm-toolbar-search,
  .perm-toolbar-select {
    width: 100%;
  }
  .perm-toolbar-count { margin-left: 0; }
  .perm-row {
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) 64px;
    gap: var(--space-2);
    padding: 0 var(--space-3);
  }
  .perm-group-bar { padding: 0 var(--space-3); }
}

// ==================== 查看权限弹窗 ====================
:deep(.view-perm-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

.view-dialog-header {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
}

.view-role-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.view-role-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.view-role-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.view-role-code {
  font-size: 12px;
  color: var(--text-placeholder);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.view-role-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: 2px;
}

.view-role-total {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 6px 14px;
  background: var(--brand-glow-soft, rgba(64, 158, 255, 0.10));
  color: var(--brand-500);
  border-radius: 10px;
  flex-shrink: 0;
}

.total-num {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
}

.total-label {
  font-size: 12px;
}

.view-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px 2px;
}

.view-perm-search {
  width: 100%;
  max-width: 360px;
}

.view-perm-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.view-perm-group {
  border: 1px solid var(--border-light, #e5e7eb);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-card, #fff);
}

.view-perm-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--gray-50, #f9fafb);
  border-bottom: 1px solid var(--border-light, #e5e7eb);
}

.view-perm-group-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.view-perm-group-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
}

.view-perm-group-count {
  font-size: 12px;
  color: var(--text-placeholder);
}

.view-perm-table {
  display: flex;
  flex-direction: column;
}

.view-perm-row {
  display: grid;
  grid-template-columns: 1fr 200px;
  align-items: center;
  padding: 9px 14px;
  border-bottom: 1px solid var(--gray-100, #f3f4f6);
  font-size: 13px;
  transition: background 0.15s ease;

  &:last-child {
    border-bottom: none;
  }

  &:hover:not(.view-perm-row--head) {
    background: var(--brand-glow-soft, rgba(64, 158, 255, 0.04));
  }
}

.view-perm-row--head {
  background: var(--bg-hover, #f8fafc);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
}

.col-name {
  color: var(--text-regular);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.view-perm-row--head .col-name {
  font-weight: 600;
  color: var(--text-secondary);
}

.col-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--color-info-600, #2563eb);
  background: var(--color-info-50, #eff6ff);
  padding: 2px 8px;
  border-radius: 6px;
  width: max-content;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  justify-self: start;
}

.view-perm-row--head .col-code {
  background: transparent;
  color: var(--text-placeholder);
  font-family: inherit;
  padding: 0;
}

.view-empty {
  padding: 24px 0;
}

@media (max-width: 600px) {
  .view-perm-row {
    grid-template-columns: 1fr 140px;
  }
  .view-role-total {
    display: none;
  }
}
</style>