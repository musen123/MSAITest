import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Project, ProjectMember, ProjectRole } from '@/api/projects'

/**
 * 历史记录项
 */
export interface HistoryTab {
  /** 路由名称 */
  name: string
  /** 页面标题 */
  title: string
  /** 完整路径 */
  fullPath: string
  /** 路由参数 */
  params: Record<string, any>
  /** 查询参数 */
  query: Record<string, any>
  /** 是否固定 */
  pinned?: boolean
}

/**
 * 项目工作空间状态管理
 */
export const useProjectWorkspaceStore = defineStore(
  'projectWorkspace',
  () => {
    // ==================== 状态 ====================

    /** 当前项目信息 */
    const currentProject = ref<Project | null>(null)

    /** 项目成员列表 */
    const members = ref<ProjectMember[]>([])

    /** 用户在项目中的角色 */
    const userRole = ref<ProjectRole | null>(null)

    /** 权限集合 */
    const permissions = ref<string[]>([])

    /** 侧边栏折叠状态 */
    const sidebarCollapsed = ref(false)

    /** 历史访问记录 */
    const historyTabs = ref<HistoryTab[]>([])

    // ==================== 计算属性 ====================

    /** 是否有项目 */
    const hasProject = computed(() => currentProject.value !== null)

    /** 是否为项目负责人 */
    const isOwner = computed(() => userRole.value === 'owner')

    /** 是否为测试负责人 */
    const isTestLead = computed(
      () => userRole.value === 'owner' || userRole.value === 'test_lead'
    )

    /** 是否为测试人员 */
    const isTester = computed(
      () =>
        userRole.value === 'owner' ||
        userRole.value === 'test_lead' ||
        userRole.value === 'tester'
    )

    /** 是否为只读成员 */
    const isViewer = computed(() => userRole.value === 'viewer')

    // ==================== 方法 ====================

    /**
     * 设置当前项目
     */
    const setCurrentProject = (project: Project | null) => {
      currentProject.value = project
    }

    /**
     * 设置项目成员列表
     */
    const setMembers = (memberList: ProjectMember[]) => {
      members.value = memberList
    }

    /**
     * 设置用户在项目中的角色
     */
    const setUserRole = (role: ProjectRole | null) => {
      userRole.value = role
    }

    /**
     * 设置权限集合
     */
    const setPermissions = (perms: string[]) => {
      permissions.value = perms
    }

    /**
     * 切换侧边栏折叠状态
     */
    const toggleSidebar = () => {
      sidebarCollapsed.value = !sidebarCollapsed.value
    }

    /**
     * 清空当前项目数据
     */
    const clearCurrentProject = () => {
      currentProject.value = null
      members.value = []
      userRole.value = null
      permissions.value = []
    }

    /**
     * 检查是否有指定权限
     */
    const hasPermission = (perm: string): boolean => {
      return permissions.value.includes(perm)
    }

    // ==================== 历史记录管理 ====================

    /**
     * 添加历史记录
     */
    const addHistoryTab = (tab: HistoryTab) => {
      const existingIndex = historyTabs.value.findIndex((t) => t.fullPath === tab.fullPath)
      if (existingIndex !== -1) {
        historyTabs.value.splice(existingIndex, 1)
      }

      historyTabs.value.push(tab)

      const MAX_TABS = 7
      const unpinned = historyTabs.value.filter((t) => !t.pinned)
      if (unpinned.length > MAX_TABS) {
        const toRemove = unpinned.slice(0, unpinned.length - MAX_TABS)
        historyTabs.value = historyTabs.value.filter((t) => t.pinned || !toRemove.includes(t))
      }
    }

    /**
     * 移除历史记录
     */
    const removeHistoryTab = (fullPath: string) => {
      const index = historyTabs.value.findIndex((t) => t.fullPath === fullPath)
      if (index !== -1) {
        historyTabs.value.splice(index, 1)
      }
    }

    /**
     * 移除其他历史记录（保留指定的）
     */
    const removeOtherTabs = (fullPath: string) => {
      historyTabs.value = historyTabs.value.filter((t) => t.fullPath === fullPath)
    }

    /**
     * 移除左侧历史记录
     */
    const removeLeftTabs = (fullPath: string) => {
      const index = historyTabs.value.findIndex((t) => t.fullPath === fullPath)
      if (index > 0) {
        historyTabs.value = historyTabs.value.slice(index)
      }
    }

    /**
     * 移除右侧历史记录
     */
    const removeRightTabs = (fullPath: string) => {
      const index = historyTabs.value.findIndex((t) => t.fullPath === fullPath)
      if (index !== -1 && index < historyTabs.value.length - 1) {
        historyTabs.value = historyTabs.value.slice(0, index + 1)
      }
    }

    /**
     * 清空所有历史记录
     */
    const clearHistoryTabs = () => {
      historyTabs.value = []
    }

    /**
     * 固定/取消固定历史记录
     */
    const toggleTabPin = (fullPath: string) => {
      const tab = historyTabs.value.find((t) => t.fullPath === fullPath)
      if (tab) {
        tab.pinned = !tab.pinned
      }
    }

    // ==================== 返回 ====================

    return {
      // 状态
      currentProject,
      members,
      userRole,
      permissions,
      sidebarCollapsed,
      historyTabs,

      // 计算属性
      hasProject,
      isOwner,
      isTestLead,
      isTester,
      isViewer,

      // 方法
      setCurrentProject,
      setMembers,
      setUserRole,
      setPermissions,
      toggleSidebar,
      clearCurrentProject,
      hasPermission,

      // 历史记录管理
      addHistoryTab,
      removeHistoryTab,
      removeOtherTabs,
      removeLeftTabs,
      removeRightTabs,
      clearHistoryTabs,
      toggleTabPin,
    }
  },
  {
    persist: {
      key: 'project-workspace',
      storage: sessionStorage,
      paths: ['currentProject', 'userRole', 'historyTabs'],
    },
  }
)
