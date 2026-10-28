<template>
  <div class="history-tabs-wrapper">
    <div class="tabs-container">
      <!-- 左侧滚动按钮 -->
      <button
        v-if="showScrollLeft"
        class="scroll-button scroll-left"
        @click="scrollTabs('left')"
        aria-label="向左滚动"
      >
        <el-icon><ArrowLeft /></el-icon>
      </button>

      <!-- Tabs 滚动容器 -->
      <div ref="tabsScrollRef" class="tabs-scroll-container" @wheel.prevent="handleWheel">
        <div class="tabs-list">
          <button
            v-for="tab in historyTabs"
            :key="tab.fullPath"
            :class="['tab-item', {
              'is-active': tab.fullPath === activeTab,
              'is-pinned': tab.pinned
            }]"
            :aria-current="tab.fullPath === activeTab ? 'page' : undefined"
            :aria-label="`${tab.title}${tab.pinned ? '（已固定）' : ''}`"
            @click="handleTabClick(tab)"
          >
            <span class="tab-icon-wrapper">
              <el-icon v-if="tab.pinned" class="pin-icon" size="12">
                <Paperclip />
              </el-icon>
            </span>
            <span class="tab-title" :title="tab.title">{{ tab.title }}</span>
            <button
              v-if="!tab.pinned"
              class="tab-close"
              :aria-label="`关闭 ${tab.title}`"
              @click.stop="handleTabRemove(tab.fullPath)"
            >
              <el-icon size="12"><Close /></el-icon>
            </button>
          </button>
        </div>
      </div>

      <!-- 右侧滚动按钮 -->
      <button
        v-if="showScrollRight"
        class="scroll-button scroll-right"
        @click="scrollTabs('right')"
        aria-label="向右滚动"
      >
        <el-icon><ArrowRight /></el-icon>
      </button>

      <!-- 操作按钮 -->
      <div class="tabs-actions">
        <el-dropdown trigger="click" @command="handleAction" placement="bottom-end">
          <button class="action-button" aria-label="标签操作">
            <el-icon size="14"><MoreFilled /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="closeOthers" :disabled="historyTabs.length <= 1">
                <el-icon><Close /></el-icon>
                <span>关闭其他</span>
              </el-dropdown-item>
              <el-dropdown-item command="closeLeft" :disabled="currentTabIndex <= 0">
                <el-icon><Back /></el-icon>
                <span>关闭左侧</span>
              </el-dropdown-item>
              <el-dropdown-item command="closeRight" :disabled="currentTabIndex >= historyTabs.length - 1">
                <el-icon><Right /></el-icon>
                <span>关闭右侧</span>
              </el-dropdown-item>
              <el-dropdown-item divided command="closeAll" :disabled="historyTabs.length === 0">
                <el-icon><Delete /></el-icon>
                <span>关闭所有</span>
              </el-dropdown-item>
              <el-dropdown-item divided command="togglePin" :disabled="!currentTab">
                <el-icon>
                  <component :is="currentTab?.pinned ? 'Unlock' : 'Lock'" />
                </el-icon>
                <span>{{ currentTab?.pinned ? '取消固定' : '固定' }}</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Paperclip,
  Close,
  ArrowLeft,
  ArrowRight,
  MoreFilled,
  Back,
  Right,
  Delete,
  Lock,
  Unlock
} from '@element-plus/icons-vue'
import { useProjectWorkspaceStore, type HistoryTab } from '@/stores/projectWorkspace'

const route = useRoute()
const router = useRouter()
const workspaceStore = useProjectWorkspaceStore()

// 当前激活的标签
const activeTab = ref(route.fullPath)

// 历史记录
const historyTabs = computed(() => workspaceStore.historyTabs)

// 当前标签
const currentTab = computed(() => {
  return historyTabs.value.find((t) => t.fullPath === activeTab.value)
})

// 当前标签索引
const currentTabIndex = computed(() => {
  return historyTabs.value.findIndex((t) => t.fullPath === activeTab.value)
})

// 滚动相关
const tabsScrollRef = ref<HTMLElement>()
const showScrollLeft = ref(false)
const showScrollRight = ref(false)

// 检查滚动状态
const checkScroll = () => {
  if (!tabsScrollRef.value) return
  const { scrollLeft, scrollWidth, clientWidth } = tabsScrollRef.value
  showScrollLeft.value = scrollLeft > 0
  showScrollRight.value = scrollLeft + clientWidth < scrollWidth
}

// 滚动标签
const scrollTabs = (direction: 'left' | 'right') => {
  if (!tabsScrollRef.value) return
  const scrollAmount = 200
  const newScrollLeft =
    direction === 'left'
      ? tabsScrollRef.value.scrollLeft - scrollAmount
      : tabsScrollRef.value.scrollLeft + scrollAmount

  tabsScrollRef.value.scrollTo({
    left: newScrollLeft,
    behavior: 'smooth'
  })
}

// 鼠标滚轮滚动
const handleWheel = (e: WheelEvent) => {
  if (!tabsScrollRef.value) return
  const scrollAmount = 100
  const newScrollLeft = tabsScrollRef.value.scrollLeft + (e.deltaY > 0 ? scrollAmount : -scrollAmount)
  tabsScrollRef.value.scrollTo({
    left: newScrollLeft,
    behavior: 'smooth'
  })
}

// 监听路由变化，更新激活标签
watch(
  () => route.fullPath,
  (newPath) => {
    activeTab.value = newPath
    // 滚动到当前标签
    nextTick(() => {
      const activeTabEl = tabsScrollRef.value?.querySelector('.tab-item.is-active') as HTMLElement
      if (activeTabEl && tabsScrollRef.value) {
        const containerRect = tabsScrollRef.value.getBoundingClientRect()
        const tabRect = activeTabEl.getBoundingClientRect()
        if (tabRect.left < containerRect.left || tabRect.right > containerRect.right) {
          activeTabEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
        }
      }
    })
  }
)

// 监听路由变化，添加到历史记录
watch(
  () => route,
  (newRoute) => {
    // 只处理项目工作空间内的路由
    if (newRoute.path.startsWith('/project-workspace/')) {
      const meta = newRoute.meta as { title?: string; hidden?: boolean }

      // 即使是隐藏的路由也记录到历史 tabs 中（子页面需要记录）
      // 只有明确不记录的路由才跳过
      const skipRecord = (meta as any).skipHistoryRecord === true
      if (skipRecord) {
        return
      }

      const tab: HistoryTab = {
        name: newRoute.name as string,
        title: meta.title || '未命名页面',
        fullPath: newRoute.fullPath,
        params: newRoute.params,
        query: newRoute.query,
        pinned: false,
      }

      workspaceStore.addHistoryTab(tab)

      // 更新滚动状态
      nextTick(() => checkScroll())
    }
  },
  { immediate: true, deep: true }
)

// 点击标签
const handleTabClick = (tab: HistoryTab) => {
  if (tab.fullPath !== route.fullPath) {
    router.push(tab.fullPath)
  }
}

// 移除标签
const handleTabRemove = (fullPath: string) => {
  workspaceStore.removeHistoryTab(fullPath)

  // 如果移除的是当前激活的标签，跳转到最后一个标签
  if (fullPath === activeTab.value && historyTabs.value.length > 0) {
    const lastTab = historyTabs.value[historyTabs.value.length - 1]
    router.push(lastTab.fullPath)
  } else if (historyTabs.value.length === 0) {
    // 如果没有标签了，返回概览页
    router.replace({ name: 'ProjectOverview' })
  }

  nextTick(() => checkScroll())
}

// 操作命令处理
const handleAction = (command: string) => {
  const fullPath = activeTab.value

  switch (command) {
    case 'closeOthers':
      workspaceStore.removeOtherTabs(fullPath)
      ElMessage.success('已关闭其他标签')
      break
    case 'closeLeft':
      workspaceStore.removeLeftTabs(fullPath)
      ElMessage.success('已关闭左侧标签')
      break
    case 'closeRight':
      workspaceStore.removeRightTabs(fullPath)
      ElMessage.success('已关闭右侧标签')
      break
    case 'closeAll':
      workspaceStore.clearHistoryTabs()
      router.replace({ name: 'ProjectOverview' })
      ElMessage.success('已关闭所有标签')
      break
    case 'togglePin':
      workspaceStore.toggleTabPin(fullPath)
      ElMessage.success(currentTab.value?.pinned ? '已取消固定' : '已固定')
      break
  }

  nextTick(() => checkScroll())
}

// 窗口大小变化时检查滚动状态
const handleResize = () => {
  checkScroll()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  nextTick(() => checkScroll())
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped lang="scss">
.history-tabs-wrapper {
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 2px;
  flex-shrink: 0;

  .tabs-container {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  // 滚动按钮
  .scroll-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    background: var(--theme-transparent);
    color: var(--el-text-color-secondary);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    flex-shrink: 0;

    &:hover {
      background: var(--el-fill-color-light);
      color: var(--el-text-color-regular);
    }

    &:active {
      transform: scale(0.95);
    }
  }

  // Tabs 滚动容器
  .tabs-scroll-container {
    flex: 1;
    overflow: hidden;
    position: relative;

    &::-webkit-scrollbar {
      display: none;
    }
  }

  // Tabs 列表
  .tabs-list {
    display: flex;
    align-items: center;
    gap: 4px;
    user-select: none;
  }

  // Tab 项目
  .tab-item {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 10px;
    border: 1px solid var(--el-border-color-light);
    border-radius: 6px;
    background: var(--el-fill-color-lighter);
    color: var(--el-text-color-regular);
    font-size: 13px;
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;

    // 悬停状态
    &:hover {
      background: var(--el-fill-color-light);
      border-color: var(--el-text-color-disabled);
      color: var(--theme-text-strong);

      .tab-close {
        opacity: 1;
      }
    }

    // 激活状态
    &.is-active {
      background: var(--el-bg-color);
      border-color: var(--el-color-primary, var(--el-color-info));
      color: var(--el-color-primary, var(--el-color-info));
      box-shadow: 0 1px 2px rgba(var(--theme-rgb-black), 0.05);

      .tab-close {
        opacity: 0.7;
      }

      &:hover .tab-close {
        opacity: 1;
      }
    }

    // 固定状态
    &.is-pinned {
      border-color: var(--el-color-warning);
      background: var(--el-color-warning-light-9);

      .pin-icon {
        color: var(--el-color-warning);
      }

      &:hover {
        background: var(--el-color-warning-light-7);
      }

      &.is-active {
        background: var(--el-bg-color);
        border-color: var(--el-color-primary, var(--el-color-info));
        box-shadow: 0 1px 2px rgba(var(--theme-rgb-black), 0.05);
      }
    }

    // 标签图标包装
    .tab-icon-wrapper {
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }

    // 标签标题
    .tab-title {
      max-width: 140px;
      overflow: hidden;
      text-overflow: ellipsis;
      flex: 1;
      min-width: 0;
    }

    // 关闭按钮
    .tab-close {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border: none;
      background: var(--theme-transparent);
      color: inherit;
      border-radius: 3px;
      cursor: pointer;
      opacity: 0;
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
      flex-shrink: 0;
      margin-left: 2px;

      &:hover {
        background: rgba(var(--theme-rgb-black), 0.08);
        transform: scale(1.1);
      }

      &:active {
        transform: scale(0.95);
      }
    }

    // 固定标签始终显示关闭按钮
    &.is-pinned .tab-close,
    &.is-active .tab-close {
      opacity: 0.5;
    }

    &:hover.is-pinned .tab-close,
    &:hover.is-active .tab-close {
      opacity: 1;
    }
  }

  // 操作按钮区域
  .tabs-actions {
    flex-shrink: 0;

    .action-button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border: none;
      background: var(--theme-transparent);
      color: var(--el-text-color-secondary);
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);

      &:hover {
        background: var(--el-fill-color-light);
        color: var(--el-text-color-regular);
      }

      &:active {
        transform: scale(0.95);
      }
    }
  }
}

// 下拉菜单样式优化
:deep(.el-dropdown-menu) {
  .el-dropdown-menu__item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    font-size: 13px;

    .el-icon {
      font-size: 14px;
      color: var(--el-text-color-secondary);
    }

    &:hover {
      .el-icon {
        color: var(--el-color-primary, var(--el-color-info));
      }
    }

    &.is-disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .history-tabs-wrapper {
    padding: 6px 12px 0;

    .tab-item {
      height: 30px;
      padding: 0 8px;
      font-size: 12px;

      .tab-title {
        max-width: 100px;
      }
    }

    .scroll-button,
    .action-button {
      width: 26px;
      height: 26px;
    }
  }
}

// 减少动画（无障碍）
@media (prefers-reduced-motion: reduce) {
  .history-tabs-wrapper {
    .tab-item,
    .scroll-button,
    .action-button,
    .tab-close {
      transition: none;
    }
  }
}
</style>
