<template>
  <header class="app-topbar">
    <!-- 左：Logo + 平台名 + 平台徽章 + 折叠按钮 -->
    <div class="tb-left">
      <router-link to="/workspace/projects" class="tb-brand">
        <img :src="logoSvg" alt="MSAITest" class="brand-logo" />
        <span class="brand-name">MSAITest</span>
        <span class="brand-badge">AI 测试平台</span>
      </router-link>
    </div>

    <!-- 中：全局搜索 -->
    <div class="tb-center">
      <div class="tb-search">
        <i class="i-solar-magnifer-linear search-icon" />
        <input
          v-model="searchKw"
          type="text"
          placeholder="搜索用例、模块、接口等..."
          class="search-input"
          @keyup.enter="onSearch"
        />
        <span v-if="!searchKw" class="search-shortcut">⌘ K</span>
      </div>
    </div>

    <!-- 右：帮助 / 主题 / 通知 / 头像 -->
    <div class="tb-right">

      <button class="tb-icon-btn" title="帮助文档" @click="onHelp">
        <i class="i-solar-question-circle-linear" />
      </button>

      <button
        class="tb-icon-btn"
        :title="themeStore.isDark ? '切换浅色' : '切换深色'"
        @click="themeStore.toggleTheme"
      >
        <i v-if="themeStore.isDark" class="i-solar-sun-linear" />
        <i v-else class="i-solar-moon-linear" />
      </button>

      <button class="tb-icon-btn" title="通知中心" @click="onNotice">
        <i class="i-solar-bell-linear" />
        <span v-if="noticeCount > 0" class="tb-badge">
          {{ noticeCount > 99 ? '99+' : noticeCount }}
        </span>
      </button>

      <div class="tb-divider" />

      <el-dropdown class="tb-user" @command="handleCommand" trigger="click">
        <div class="user-trigger">
          <el-avatar :size="32" :src="userStore.avatar" class="user-avatar">
            <i class="i-solar-user-bold" style="font-size: 18px" />
          </el-avatar>
          <div class="user-meta">
            <span class="user-name">{{ userStore.realName || userStore.username || '用户' }}</span>
            <span class="user-role">{{ userRoleLabel }}</span>
          </div>
          <i class="i-solar-alt-arrow-down-linear user-arrow" />
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <i class="i-solar-user-linear ds-menu-icon" />
              个人中心
            </el-dropdown-item>
            <el-dropdown-item command="password">
              <i class="i-solar-lock-linear ds-menu-icon" />
              修改密码
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <i class="i-solar-logout-2-linear ds-menu-icon" />
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 修改密码对话框 -->
    <ChangePasswordDialog v-model="showPasswordDialog" />
  </header>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import { ElMessageBox } from 'element-plus'
import ChangePasswordDialog from '@/components/user/ChangePasswordDialog.vue'
import logoSvg from '@/assets/brand/logo.svg'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const showPasswordDialog = ref(false)
const searchKw = ref('')
const noticeCount = ref(0) // 预留对接

const userRoleLabel = computed(() => {
  if (userStore.hasAnyRole?.('super_admin')) return '超级管理员'
  if (userStore.hasAnyRole?.('admin')) return '管理员'
  return '在线'
})

function onSearch() {
  if (!searchKw.value.trim()) return
  // TODO: 接入全局搜索
  console.log('search:', searchKw.value)
}

function onHelp() {
  window.open('/docs', '_blank')
}

function onNotice() {
  // TODO: 通知抽屉
}

async function handleCommand(command: string) {
  switch (command) {
    case 'profile':
      router.push('/workspace/profile')
      break
    case 'password':
      showPasswordDialog.value = true
      break
    case 'logout':
      await handleLogout()
      break
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await userStore.logout()
    router.push('/login')
  } catch {
    // 取消
  }
}
</script>

<style lang="scss" scoped>
.app-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--layout-header-h);
  padding: 0 var(--space-5);
  background: var(--bg-header);
  border-bottom: 1px solid var(--border-base);
  position: relative;
  z-index: var(--z-sticky);
}

/* ============ 左：品牌 ============ */
.tb-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.tb-brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
  color: var(--text-primary);
  height: 40px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-md);
  transition: var(--transition-fast);

  &:hover { background: var(--bg-hover); }
}

.brand-logo {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px var(--brand-glow-strong));
}

.brand-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--text-primary);
  white-space: nowrap;
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  background: var(--brand-50);
  color: var(--brand-700);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

/* ============ 中：搜索 ============ */
.tb-center {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 0 var(--space-6);
  max-width: 600px;
  margin: 0 auto;
}

.tb-search {
  position: relative;
  width: 100%;
  max-width: 420px;
  display: flex;
  align-items: center;
  height: 36px;
  padding: 0 var(--space-3) 0 var(--space-8);
  background: var(--gray-50);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  transition: var(--transition-fast);

  &:focus-within {
    background: var(--bg-card);
    border-color: var(--brand-400);
    box-shadow: 0 0 0 3px var(--brand-glow-soft);
  }
}

.search-icon {
  position: absolute;
  left: var(--space-3);
  font-size: 16px;
  color: var(--text-placeholder);
  pointer-events: none;
}

.search-input {
  flex: 1;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--font-size-sm);
  color: var(--text-primary);

  &::placeholder { color: var(--text-placeholder); }
}

.search-shortcut {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-placeholder);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-xs);
}

/* ============ 右：图标按钮组 + 用户 ============ */
.tb-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

.tb-course-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s ease;

  i { font-size: 16px; }
  &:hover { background: rgba(16, 185, 129, 0.18); }
}

.tb-icon-btn {
  position: relative;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-regular);
  cursor: pointer;
  transition: var(--transition-fast);

  i { font-size: 18px; }

  &:hover {
    background: var(--bg-hover);
    color: var(--brand-600);
  }
}

.tb-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  color: #FFFFFF;
  background: var(--color-danger-500);
  border: 2px solid var(--bg-header);
  border-radius: 8px;
  text-align: center;
}

.tb-divider {
  width: 1px;
  height: 20px;
  background: var(--border-base);
  margin: 0 var(--space-2);
}

/* ============ 用户区 ============ */
.tb-user {
  margin-left: var(--space-1);
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  height: 40px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-fast);

  &:hover { background: var(--bg-hover); }
}

.user-avatar {
  background: linear-gradient(135deg, var(--brand-300), var(--brand-600));
  color: #FFFFFF;
}

.user-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
  gap: 2px;
}

.user-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 11px;
  color: var(--text-secondary);

  &::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 4px;
    border-radius: 50%;
    background: var(--color-success-500);
    vertical-align: middle;
  }
}

.user-arrow {
  font-size: 14px;
  color: var(--text-placeholder);
}

.ds-menu-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -2px;
}

/* 响应式 - 窄屏隐藏徽章和用户名细节 */
@media (max-width: 1100px) {
  .brand-badge { display: none; }
  .user-meta .user-role { display: none; }
}
@media (max-width: 900px) {
  .brand-name { display: none; }
}
</style>
