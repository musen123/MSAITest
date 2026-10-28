<template>
  <aside class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <!-- 折叠触发器 -->
    <div class="sb-collapse-trigger" @click="handleToggle">
      <i v-if="collapsed" class="i-solar-alt-arrow-right-linear" />
      <i v-else class="i-solar-alt-arrow-left-linear" />
    </div>

    <!-- 菜单 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      :unique-opened="true"
      router
      class="sb-menu"
    >
      <template v-for="item in visibleMenus" :key="item.path">
        <!-- 一级菜单（无子菜单） -->
        <el-menu-item v-if="!item.children" :index="item.path">
          <i :class="item.icon + ' sb-icon'" />
          <template #title>{{ item.name }}</template>
        </el-menu-item>

        <!-- 一级菜单（含子菜单） -->
        <el-sub-menu v-else :index="item.path">
          <template #title>
            <i :class="item.icon + ' sb-icon'" />
            <span>{{ item.name }}</span>
          </template>
          <el-menu-item
            v-for="child in item.children"
            :key="child.path"
            :index="child.path"
          >
            <span class="sb-child-dot" />
            <template #title>{{ child.name }}</template>
          </el-menu-item>
        </el-sub-menu>
      </template>
    </el-menu>

    <!-- 底部：版本号 / 帮助 -->
    <div class="sb-footer" v-if="!collapsed">
      <div class="sb-foot-row">
        <i class="i-solar-shield-check-bold-duotone foot-icon" />
        <div class="foot-text">
          <div class="foot-title">AutoTest Platform</div>
          <div class="foot-sub">v2.4.0</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

interface Props {
  collapsed?: boolean
}

interface MenuItem {
  name: string
  path: string
  icon: string  // unocss icon class
  children?: MenuItem[]
}

withDefaults(defineProps<Props>(), {
  collapsed: false,
})

const emit = defineEmits<{
  toggle: []
}>()

const route = useRoute()
const userStore = useUserStore()

const activeMenu = computed(() => {
  if (route.path.startsWith('/workspace/')) return route.path
  return ''
})

const allMenus: MenuItem[] = [
  { name: '我的项目',   path: '/workspace/projects',       icon: 'i-solar-folder-with-files-bold-duotone' },
  { name: '个人中心',   path: '/workspace/profile',        icon: 'i-solar-user-circle-bold-duotone' },
  { name: '大模型配置', path: '/workspace/llm-config',     icon: 'i-solar-cpu-bolt-bold-duotone' },
  { name: '用户管理',   path: '/workspace/users',          icon: 'i-solar-users-group-rounded-bold-duotone' },
  { name: '权限管理',   path: '/workspace/permissions',    icon: 'i-solar-key-square-2-bold-duotone' },
  { name: '操作日志',   path: '/workspace/operation-logs', icon: 'i-solar-clipboard-list-bold-duotone' },
  { name: '设计系统',   path: '/workspace/dev/design-system', icon: 'i-solar-palette-bold-duotone' },
]

function menuVisible(menu: MenuItem): boolean {
  if (menu.path === '/workspace/profile' || menu.path === '/workspace/llm-config') {
    return userStore.isLoggedIn
  }
  if (menu.path === '/workspace/users') return userStore.hasPermission('user:view')
  if (menu.path === '/workspace/permissions') return userStore.hasPermission('role:view')
  if (menu.path === '/workspace/projects') return userStore.hasPermission('project:view')
  if (menu.path === '/workspace/operation-logs') return userStore.hasPermission('system:log')
  return true
}

const visibleMenus = computed(() => {
  return allMenus
    .map((menu) => {
      if (!menu.children) return menuVisible(menu) ? menu : null
      // 分组：按子项权限过滤，全部不可见则整组隐藏
      const children = menu.children.filter(menuVisible)
      return children.length ? { ...menu, children } : null
    })
    .filter((m): m is MenuItem => m !== null)
})

const handleToggle = () => {
  emit('toggle')
}
</script>

<style lang="scss" scoped>
.app-sidebar {
  width: var(--layout-sidebar-w);
  height: 100%;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--duration-normal) var(--ease-out);
  position: relative;

  &.is-collapsed {
    width: var(--layout-sidebar-collapse);
  }
}

/* 折叠触发器 - 浮在右侧边缘的小圆按钮 */
.sb-collapse-trigger {
  position: absolute;
  top: 16px;
  right: -10px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  z-index: 2;
  transition: var(--transition-fast);

  i { font-size: 12px; }

  &:hover {
    background: var(--brand-500);
    border-color: var(--brand-500);
    color: #FFFFFF;
  }
}

/* 菜单 */
.sb-menu {
  flex: 1;
  border: none !important;
  background: transparent !important;
  padding: var(--space-3) 0;
  overflow-y: auto;
  overflow-x: hidden;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 2px;
  }
}

.sb-icon {
  font-size: 18px;
  margin-right: 10px;
  flex-shrink: 0;
  vertical-align: -3px;
}

/* 子菜单装饰点 */
.sb-child-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gray-300);
  margin-right: 10px;
  margin-left: 4px;
  flex-shrink: 0;
  transition: background var(--duration-fast);
}

/* ============ Menu 内部样式覆盖 ============ */
:deep(.el-menu) {
  background: transparent !important;
}

:deep(.el-menu-item),
:deep(.el-sub-menu__title) {
  height: 40px;
  line-height: 40px;
  margin: 2px var(--space-2);
  padding-left: var(--space-3) !important;
  padding-right: var(--space-3) !important;
  border-radius: var(--radius-md);
  color: var(--text-regular);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  transition: var(--transition-fast);

  &:hover {
    background: var(--bg-hover) !important;
    color: var(--text-primary);
  }
}

/* 激活状态：浅绿底 + 主色字 + 3px 左侧主色竖条 */
:deep(.el-menu-item.is-active) {
  background: var(--brand-50) !important;
  color: var(--brand-700) !important;
  font-weight: var(--font-weight-semibold);
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: -8px;
    top: 8px;
    bottom: 8px;
    width: 3px;
    border-radius: 0 2px 2px 0;
    background: var(--brand-500);
  }

  .sb-icon {
    color: var(--brand-600);
  }

  .sb-child-dot {
    background: var(--brand-500);
  }
}

/* 子菜单 */
:deep(.el-sub-menu) {
  .el-sub-menu__title {
    color: var(--text-regular);
  }

  &.is-active > .el-sub-menu__title {
    color: var(--brand-700);
    .sb-icon { color: var(--brand-600); }
  }

  &.is-opened > .el-sub-menu__title {
    color: var(--text-primary);
  }

  .el-menu-item {
    height: 36px;
    line-height: 36px;
    font-size: var(--font-size-sm);
    padding-left: var(--space-8) !important;
  }
}

/* 折叠态 */
.app-sidebar.is-collapsed {
  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    padding-left: 0 !important;
    padding-right: 0 !important;
    justify-content: center;

    .sb-icon { margin-right: 0; }
  }
}

/* 底部 */
.sb-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.sb-foot-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
}

.foot-icon {
  font-size: 22px;
  color: var(--brand-500);
  flex-shrink: 0;
}

.foot-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.foot-title {
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.foot-sub {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}
</style>
