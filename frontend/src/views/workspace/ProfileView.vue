<!--
  个人中心
  严格遵循 design-system 视觉基线（views/dev/DesignSystemView.vue）：
  AppPageHeader + AppSectionCard + AppStatCard + AppAvatar，全部走设计令牌，零硬编码色值。
  「我的权限」由 userInfo.permissions 本地归类得出，对所有角色可用（不依赖管理员权限目录接口）。
-->
<template>
  <AppGlowBg variant="soft" :orbs="false">
    <div class="profile-view">
      <!-- 页头 -->
      <AppPageHeader
        title="个人中心"
        description="查看你的账户信息、角色与平台权限"
        icon="i-solar-user-circle-bold"
      >
        <template #actions>
          <el-button @click="showEditDialog = true">
            <i class="i-solar-pen-2-bold ds-btn-icon" /> 编辑资料
          </el-button>
          <el-button type="primary" @click="showPasswordDialog = true">
            <i class="i-solar-lock-password-bold ds-btn-icon" /> 修改密码
          </el-button>
        </template>
      </AppPageHeader>

      <!-- 加载骨架 -->
      <div v-if="loading" class="ds-loading">
        <el-skeleton :rows="6" animated />
      </div>

      <template v-else-if="userInfo">
        <!-- ============ 身份卡 + 概览统计：同一行，左右布局 ============ -->
        <div class="profile-top">
          <AppSectionCard class="identity-card">
            <div class="identity">
              <!-- 头像 + 名称 + 角色/状态 -->
              <div class="identity-side">
                <AppAvatar :name="displayName" :size="88" />
                <div class="identity-name">{{ displayName }}</div>
                <div class="identity-account">
                  @{{ userInfo.username }} · ID {{ userInfo.id }}
                </div>
                <div class="identity-tags">
                  <span
                    v-for="role in roleList"
                    :key="role.code"
                    class="role-pill"
                    :class="roleStyle(role.code).tone"
                  >
                    <i :class="roleStyle(role.code).icon" />
                    {{ role.name }}
                  </span>
                  <span v-if="!roleList.length" class="role-pill tone-info">
                    <i class="i-solar-user-bold" /> 未分配角色
                  </span>
                  <span
                    class="status-pill"
                    :class="statusActive ? 'is-active' : 'is-inactive'"
                  >
                    ● {{ statusText }}
                  </span>
                </div>
              </div>

              <!-- 基础信息 -->
              <div class="identity-info">
                <div class="info-cell">
                  <div class="info-cell-icon">
                    <i class="i-solar-letter-bold" />
                  </div>
                  <div class="info-cell-body">
                    <span class="info-cell-label">邮箱</span>
                    <span class="info-cell-value">{{
                      userInfo.email || '—'
                    }}</span>
                  </div>
                </div>
                <div class="info-cell">
                  <div class="info-cell-icon">
                    <i class="i-solar-phone-bold" />
                  </div>
                  <div class="info-cell-body">
                    <span class="info-cell-label">手机号</span>
                    <span class="info-cell-value">{{
                      userInfo.phone || '—'
                    }}</span>
                  </div>
                </div>
                <div class="info-cell">
                  <div class="info-cell-icon">
                    <i class="i-solar-calendar-bold" />
                  </div>
                  <div class="info-cell-body">
                    <span class="info-cell-label">注册时间</span>
                    <span class="info-cell-value">{{
                      formatTime(userInfo.created_at)
                    }}</span>
                  </div>
                </div>
                <div class="info-cell">
                  <div class="info-cell-icon">
                    <i class="i-solar-clock-circle-bold" />
                  </div>
                  <div class="info-cell-body">
                    <span class="info-cell-label">最后登录</span>
                    <span class="info-cell-value">{{
                      formatTime(userInfo.last_login_at)
                    }}</span>
                  </div>
                </div>
              </div>
            </div>
          </AppSectionCard>

          <!-- 概览统计：右侧 2×2 -->
          <div class="profile-top-stats">
            <AppStatCard
              label="拥有权限"
              :value="permissionCount"
              color="brand"
              icon-name="i-solar-key-square-2-bold"
              extra="项功能操作"
            />
            <AppStatCard
              label="可访问模块"
              :value="permissionGroups.length"
              color="info"
              icon-name="i-app-workflow"
              extra="个功能模块"
            />
            <AppStatCard
              label="我的角色"
              :value="roleList.length"
              color="purple"
              icon-name="i-solar-shield-user-bold"
              :extra="roleList.map((r) => r.name).join(' / ') || '未分配'"
            />
            <AppStatCard
              label="加入天数"
              :value="daysSinceRegister"
              color="cyan"
              icon-name="i-solar-calendar-bold"
              :extra="`注册于 ${registerDate}`"
            />
          </div>
        </div>

        <!-- ============ 我的权限 ============ -->
        <AppSectionCard
          title="我的权限"
          description="你在平台上被授予的功能操作，按模块归类"
        >
          <div v-if="permissionGroups.length" class="perm-grid">
            <div
              v-for="group in permissionGroups"
              :key="group.name"
              class="perm-group"
            >
              <div class="perm-group-head">
                <span class="perm-group-icon" :class="group.tone">
                  <i :class="group.icon" />
                </span>
                <span class="perm-group-name">{{ group.name }}</span>
                <span class="perm-group-count">{{ group.actions.length }}</span>
              </div>
              <div class="perm-chips">
                <span
                  v-for="action in group.actions"
                  :key="action"
                  class="perm-chip"
                >
                  {{ actionLabel(action) }}
                </span>
              </div>
            </div>
          </div>

          <AppEmpty
            v-else
            scene="permission"
            description="当前账号尚未分配任何功能权限，请联系管理员"
          />
        </AppSectionCard>
      </template>

      <!-- 编辑资料 -->
      <ProfileEditDialog
        v-model="showEditDialog"
        @success="handleEditSuccess"
      />
      <!-- 修改密码 -->
      <ChangePasswordDialog
        v-model="showPasswordDialog"
        @success="handlePasswordSuccess"
      />
    </div>
  </AppGlowBg>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/user'
import {
  AppGlowBg,
  AppAvatar,
  AppSectionCard,
  AppPageHeader,
  AppStatCard,
  AppEmpty,
} from '@/components/common'
import ProfileEditDialog from '@/components/user/ProfileEditDialog.vue'
import ChangePasswordDialog from '@/components/user/ChangePasswordDialog.vue'

const userStore = useUserStore()

// ==================== 状态 ====================
const loading = ref(false)
const showEditDialog = ref(false)
const showPasswordDialog = ref(false)

// ==================== 展示映射（字面字符串，便于 UnoCSS 静态扫描图标） ====================

/** 系统角色 → 图标 + 色调 */
const ROLE_STYLE: Record<string, { icon: string; tone: string }> = {
  super_admin: { icon: 'i-solar-crown-star-bold', tone: 'tone-danger' },
  admin: { icon: 'i-solar-shield-keyhole-bold', tone: 'tone-warning' },
  project_admin: { icon: 'i-solar-shield-user-bold', tone: 'tone-purple' },
  tester: { icon: 'i-solar-test-tube-bold', tone: 'tone-info' },
  developer: { icon: 'i-solar-code-bold', tone: 'tone-cyan' },
  user: { icon: 'i-solar-user-bold', tone: 'tone-brand' },
}
const roleStyle = (code: string) =>
  ROLE_STYLE[code] ?? { icon: 'i-solar-user-bold', tone: 'tone-info' }

/** 权限码前缀 → 模块（名称 / 图标 / 色调）；多前缀可归并到同一模块 */
const MODULE_MAP: Record<string, { name: string; icon: string; tone: string }> =
  {
    web_element: {
      name: 'Web 自动化',
      icon: 'i-app-browser',
      tone: 'tone-info',
    },
    test_case: {
      name: '功能测试',
      icon: 'i-app-test-case',
      tone: 'tone-brand',
    },
    bug: { name: '缺陷管理', icon: 'i-app-bug', tone: 'tone-danger' },
    report: { name: '测试报告', icon: 'i-app-test-report', tone: 'tone-cyan' },
    scheduler: {
      name: '定时调度',
      icon: 'i-solar-clock-circle-bold',
      tone: 'tone-warning',
    },
    environment: {
      name: '测试环境',
      icon: 'i-solar-server-2-bold',
      tone: 'tone-info',
    },
    ai_task: { name: 'AI 任务', icon: 'i-app-ai-agent', tone: 'tone-purple' },
    chat: { name: 'AI 助手', icon: 'i-app-ai-spark', tone: 'tone-purple' },
    knowledge: { name: '知识库', icon: 'i-app-knowledge', tone: 'tone-cyan' },
    project: {
      name: '项目管理',
      icon: 'i-solar-folder-bold',
      tone: 'tone-brand',
    },
    member: {
      name: '项目管理',
      icon: 'i-solar-folder-bold',
      tone: 'tone-brand',
    },
    module: {
      name: '项目管理',
      icon: 'i-solar-folder-bold',
      tone: 'tone-brand',
    },
    config: {
      name: '项目管理',
      icon: 'i-solar-folder-bold',
      tone: 'tone-brand',
    },
    user: {
      name: '用户管理',
      icon: 'i-solar-users-group-rounded-bold',
      tone: 'tone-info',
    },
    role: {
      name: '角色管理',
      icon: 'i-solar-shield-user-bold',
      tone: 'tone-purple',
    },
    permission: {
      name: '权限管理',
      icon: 'i-solar-key-square-2-bold',
      tone: 'tone-warning',
    },
    system: {
      name: '系统管理',
      icon: 'i-solar-settings-bold',
      tone: 'tone-danger',
    },
    auth: {
      name: '认证授权',
      icon: 'i-solar-lock-keyhole-bold',
      tone: 'tone-success',
    },
  }

/** 操作动词 → 中文 */
const ACTION_LABEL: Record<string, string> = {
  view: '查看',
  create: '新建',
  edit: '编辑',
  delete: '删除',
  execute: '执行',
  add: '添加',
  remove: '移除',
  assign: '指派',
  close: '关闭',
  resolve: '解决',
  archive: '归档',
  config: '配置',
  export: '导出',
  log: '日志',
  login: '登录',
  logout: '登出',
  manage: '管理',
  monitor: '监控',
  register: '注册',
  use: '使用',
  edit_own: '改自己的',
  edit_role: '改成员角色',
  manage_member: '管理成员',
  reset_pwd: '重置密码',
}
const actionLabel = (action: string) => ACTION_LABEL[action] ?? action

// ==================== 计算属性 ====================
const userInfo = computed(() => userStore.userInfo)
const currentUserId = computed(() => userStore.currentUserId)

const displayName = computed(
  () => userInfo.value?.real_name || userInfo.value?.username || '—',
)

const roleList = computed(() => userInfo.value?.roles ?? [])

const statusActive = computed(() => userInfo.value?.status === 'active')
const statusText = computed(() => {
  const s = userInfo.value?.status
  if (s === 'active') return '正常'
  if (s === 'disabled') return '已禁用'
  return s || '未知'
})

const permissionCount = computed(() => userInfo.value?.permissions?.length ?? 0)

/** 按模块归类当前用户的权限码 */
const permissionGroups = computed(() => {
  const codes = userInfo.value?.permissions ?? []
  const groups = new Map<
    string,
    { name: string; icon: string; tone: string; actions: string[] }
  >()
  for (const code of codes) {
    const parts = code.split(':')
    const prefix = parts[0] ?? ''
    const action = parts[1] ?? ''
    const meta = MODULE_MAP[prefix]
    if (!meta) continue
    let group = groups.get(meta.name)
    if (!group) {
      group = {
        name: meta.name,
        icon: meta.icon,
        tone: meta.tone,
        actions: [],
      }
      groups.set(meta.name, group)
    }
    if (!group.actions.includes(action)) group.actions.push(action)
  }
  return [...groups.values()]
})

const daysSinceRegister = computed(() => {
  const created = userInfo.value?.created_at
  if (!created) return 0
  const ms = Date.now() - new Date(created).getTime()
  return Math.max(0, Math.floor(ms / 86_400_000))
})

const registerDate = computed(() => {
  const created = userInfo.value?.created_at
  if (!created) return '—'
  return new Date(created).toLocaleDateString('zh-CN')
})

// ==================== 工具方法 ====================
function formatTime(time?: string): string {
  if (!time) return '—'
  return new Date(time).toLocaleString('zh-CN', { hour12: false })
}

// ==================== 数据加载 ====================
const fetchUserInfo = async () => {
  const userId = currentUserId.value
  if (!userId) return
  try {
    const res = await userApi.getDetail(userId)
    if (res.code === 200) userStore.setUserInfo(res.data)
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

const handleEditSuccess = () => {
  loading.value = true
  fetchUserInfo().finally(() => {
    loading.value = false
  })
}

const handlePasswordSuccess = () => {
  // 密码修改成功后由对话框触发登出，无需额外处理
}

onMounted(async () => {
  if (!currentUserId.value) {
    ElMessage.error('无法获取用户信息，请先登录')
    return
  }
  loading.value = true
  try {
    await fetchUserInfo()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.profile-view {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.ds-btn-icon {
  margin-right: 6px;
  vertical-align: -2px;
}

.ds-loading {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-8);
}

/* ========== 色调（全部走令牌，零硬编码） ========== */
.tone-brand {
  --tone-bg: var(--brand-50);
  --tone-fg: var(--brand-600);
}
.tone-info {
  --tone-bg: var(--color-info-50);
  --tone-fg: var(--color-info-600);
}
.tone-success {
  --tone-bg: var(--color-success-50);
  --tone-fg: var(--color-success-600);
}
.tone-warning {
  --tone-bg: var(--color-warning-50);
  --tone-fg: var(--color-warning-600);
}
.tone-danger {
  --tone-bg: var(--color-danger-50);
  --tone-fg: var(--color-danger-600);
}
.tone-purple {
  --tone-bg: var(--color-purple-50);
  --tone-fg: var(--color-purple-600);
}
.tone-cyan {
  --tone-bg: var(--color-cyan-50);
  --tone-fg: var(--color-cyan-600);
}

/* ========== 身份卡 ========== */
/* 让卡片随右侧 2×2 等高，body 撑满 */
.identity-card {
  display: flex;
  flex-direction: column;

  :deep(.section-body) {
    flex: 1;
    display: flex;
  }
}

.identity {
  flex: 1;
  display: flex;
  gap: var(--space-6);
  align-items: stretch;
  min-width: 0;
}

.identity-side {
  flex: 0 0 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding-right: var(--space-6);
  border-right: 1px solid var(--border-light);
  text-align: center;
}

.identity-name {
  margin-top: var(--space-2);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: 1.3;
}

.identity-account {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.identity-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.role-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  background: var(--tone-bg);
  color: var(--tone-fg);

  i {
    font-size: 13px;
  }
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 24px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);

  &.is-active {
    background: var(--color-success-50);
    color: var(--color-success-600);
  }
  &.is-inactive {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
  }
}

/* 信息网格（窄带内单列，避免邮箱/时间被截断） */
.identity-info {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4) var(--space-6);
  align-content: center;
  min-width: 0;
}

.info-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.info-cell-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--brand-50);
  color: var(--brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.info-cell-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.info-cell-label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.info-cell-value {
  font-size: var(--font-size-base);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ========== 身份卡 + 概览统计：同一行 ========== */
.profile-top {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: var(--space-4);
  align-items: stretch;
}

/* 右侧 2×2 统计卡 */
.profile-top-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: var(--space-4);
}

/* ========== 我的权限 ========== */
.perm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}

.perm-group {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--gray-50);
  padding: var(--space-4);
  transition: var(--transition-base);

  &:hover {
    background: var(--bg-card);
    box-shadow: var(--shadow-sm);
    border-color: var(--brand-200);
  }
}

.perm-group-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.perm-group-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  background: var(--tone-bg);
  color: var(--tone-fg);
}

.perm-group-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
}

.perm-group-count {
  flex-shrink: 0;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.perm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.perm-chip {
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  font-size: var(--font-size-xs);
  color: var(--text-regular);
}

/* ========== 响应式 ========== */
/* 窄屏：身份卡与统计卡上下堆叠 */
@media (max-width: 1180px) {
  .profile-top {
    grid-template-columns: 1fr;
  }
  /* 堆叠后身份卡变宽，信息恢复双列 */
  .identity-info {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .profile-view {
    padding: var(--space-4);
  }
  .identity {
    flex-direction: column;
    gap: var(--space-5);
  }
  .identity-side {
    flex: 1;
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border-light);
    padding-right: 0;
    padding-bottom: var(--space-5);
  }
}

@media (max-width: 600px) {
  .identity-info {
    grid-template-columns: 1fr;
  }
  .profile-top-stats {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
}
</style>
