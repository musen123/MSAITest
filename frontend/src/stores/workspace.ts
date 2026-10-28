/**
 * 工作台状态管理
 *
 * AI 智能测试平台 - 工作台状态管理
 * 负责管理当前项目上下文、用户项目列表、菜单状态等
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'

/**
 * 项目信息接口
 */
export interface Project {
  id: number
  name: string
  code: string
  description?: string
  avatar?: string
  status: 'active' | 'archived' | 'deleted'
  is_public: boolean
  member_role?: 'owner' | 'test_lead' | 'tester' | 'viewer'
  created_at: string
  updated_at: string
}

/**
 * 模块信息接口
 */
export interface Module {
  id: number
  name: string
  parent_id: number | null
  sort_order: number
  description?: string
  children?: Module[]
}

/**
 * 工作台状态 Store
 */
export const useWorkspaceStore = defineStore(
  'workspace',
  () => {
    // ==================== 状态 ====================

    /** 当前选中的项目 */
    const currentProject: Ref<Project | null> = ref(null)
    /** 用户可访问的项目列表 */
    const userProjects: Ref<Project[]> = ref([])
    /** 菜单折叠状态 */
    const menuCollapsed: Ref<boolean> = ref(false)
    /** 当前项目的模块树 */
    const moduleTree: Ref<Module[]> = ref([])

    // ==================== 计算属性 ====================

    /** 是否有当前项目 */
    const hasCurrentProject = computed(() => currentProject.value !== null)

    // ==================== 方法 ====================

    /**
     * 设置当前项目
     */
    const setCurrentProject = (project: Project) => {
      currentProject.value = project
      // 保存到 localStorage，刷新后恢复
      localStorage.setItem('currentProjectId', String(project.id))
    }

    /**
     * 清除当前项目
     */
    const clearCurrentProject = () => {
      currentProject.value = null
      localStorage.removeItem('currentProjectId')
    }

    /**
     * 设置用户项目列表
     */
    const setUserProjects = (projects: Project[]) => {
      userProjects.value = projects
    }

    /**
     * 根据ID获取用户可访问的项目
     */
    const getUserProject = (projectId: string): Project | undefined => {
      return userProjects.value.find((p) => String(p.id) === projectId)
    }

    /**
     * 设置模块树
     */
    const setModuleTree = (modules: Module[]) => {
      moduleTree.value = modules
    }

    /**
     * 切换菜单折叠状态
     */
    const toggleMenu = () => {
      menuCollapsed.value = !menuCollapsed.value
    }

    /**
     * 设置菜单折叠状态
     */
    const setMenuCollapsed = (collapsed: boolean) => {
      menuCollapsed.value = collapsed
    }

    /**
     * 从 localStorage 恢复当前项目
     */
    const restoreCurrentProject = (): boolean => {
      const projectId = localStorage.getItem('currentProjectId')
      if (projectId) {
        const project = getUserProject(projectId)
        if (project) {
          currentProject.value = project
          return true
        }
      }
      return false
    }

    return {
      // 状态
      currentProject,
      userProjects,
      menuCollapsed,
      moduleTree,
      // 计算属性
      hasCurrentProject,
      // 方法
      setCurrentProject,
      clearCurrentProject,
      setUserProjects,
      getUserProject,
      setModuleTree,
      toggleMenu,
      setMenuCollapsed,
      restoreCurrentProject,
    }
  },
  {
    // 持久化配置
    persist: {
      key: 'ai-test-platform-workspace',
      storage: localStorage,
      paths: ['menuCollapsed'],
    },
  },
)
