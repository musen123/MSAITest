/**
 * 项目管理状态管理
 *
 * AI 智能测试平台 - 项目管理状态
 * 对应需求文档：02-项目管理模块.md
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { projectApi } from '@/api/projects'
import type {
  Project,
  ProjectListQuery,
  CreateProjectRequest,
  UpdateProjectRequest,
  ProjectsOverview,
} from '@/api/projects'
import { ElMessage } from 'element-plus'

/**
 * 项目管理状态 Store
 */
export const useProjectStore = defineStore(
  'projects',
  () => {
    // ==================== 状态 ====================

    /** 项目列表 */
    const projects: Ref<Project[]> = ref([])

    /** 当前选中的项目 */
    const currentProject: Ref<Project | null> = ref(null)

    /** 列表加载状态 */
    const loading: Ref<boolean> = ref(false)

    /** 列表总数 */
    const total: Ref<number> = ref(0)

    /** 当前页码 */
    const page: Ref<number> = ref(1)

    /** 每页数量 */
    const pageSize: Ref<number> = ref(20)

    /** 列表查询参数 */
    const queryParams: Ref<ProjectListQuery> = ref({})

    /** 工作台项目总览（5 张统计卡真实数据） */
    const overview: Ref<ProjectsOverview | null> = ref(null)

    /** 总览加载状态（与列表 loading 分离） */
    const overviewLoading: Ref<boolean> = ref(false)

    // ==================== 计算属性 ====================

    /**
     * 是否有项目数据
     */
    const hasProjects = computed(() => projects.value.length > 0)

    /**
     * 活跃项目列表
     */
    const activeProjects = computed(() => projects.value.filter((p) => p.status === 'active'))

    /**
     * 归档项目列表
     */
    const archivedProjects = computed(() => projects.value.filter((p) => p.status === 'archived'))

    // ==================== 方法 ====================

    /**
     * 获取项目列表
     */
    const fetchProjects = async (params?: ProjectListQuery) => {
      loading.value = true
      try {
        const mergedParams = { ...queryParams.value, ...params }
        const response = await projectApi.getProjectList(mergedParams)

        if (response.code === 200) {
          projects.value = response.data.items
          total.value = response.data.total
          page.value = response.data.page
          pageSize.value = response.data.page_size

          // 更新查询参数
          Object.assign(queryParams.value, mergedParams)
        }
      } catch (error: any) {
        console.error('获取项目列表失败:', error)
      } finally {
        loading.value = false
      }
    }

    /**
     * 刷新项目列表
     */
    const refreshProjects = async () => {
      await fetchProjects()
    }

    /**
     * 创建项目
     */
    const createProject = async (data: CreateProjectRequest): Promise<boolean> => {
      loading.value = true
      try {
        const response = await projectApi.createProject(data)

        if (response.code === 200) {
          ElMessage.success('项目创建成功')
          // 刷新项目列表
          await fetchProjects()
          return true
        } else {
          return false
        }
      } catch (error: any) {
        console.error('创建项目失败:', error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 更新项目
     */
    const updateProject = async (projectId: number, data: UpdateProjectRequest): Promise<boolean> => {
      loading.value = true
      try {
        const response = await projectApi.updateProject(projectId, data)

        if (response.code === 200) {
          ElMessage.success('项目更新成功')
          // 刷新项目列表
          await fetchProjects()
          return true
        } else {
          return false
        }
      } catch (error: any) {
        console.error('更新项目失败:', error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 归档项目
     */
    const archiveProject = async (projectId: number): Promise<boolean> => {
      loading.value = true
      try {
        const response = await projectApi.archiveProject(projectId)

        if (response.code === 200) {
          ElMessage.success('项目归档成功')
          // 刷新项目列表
          await fetchProjects()
          return true
        } else {
          return false
        }
      } catch (error: any) {
        console.error('归档项目失败:', error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 恢复项目
     */
    const restoreProject = async (projectId: number): Promise<boolean> => {
      loading.value = true
      try {
        const response = await projectApi.restoreProject(projectId)

        if (response.code === 200) {
          ElMessage.success('项目恢复成功')
          // 刷新项目列表
          await fetchProjects()
          return true
        } else {
          return false
        }
      } catch (error: any) {
        console.error('恢复项目失败:', error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 删除项目
     */
    const deleteProject = async (projectId: number): Promise<boolean> => {
      loading.value = true
      try {
        const response = await projectApi.deleteProject(projectId)

        if (response.code === 200) {
          ElMessage.success('项目删除成功')
          // 刷新项目列表
          await fetchProjects()
          return true
        } else {
          return false
        }
      } catch (error: any) {
        console.error('删除项目失败:', error)
        return false
      } finally {
        loading.value = false
      }
    }

    /**
     * 设置当前项目
     */
    const setCurrentProject = (project: Project | null) => {
      currentProject.value = project
    }

    /**
     * 清空项目列表
     */
    const clearProjects = () => {
      projects.value = []
      total.value = 0
      page.value = 1
    }

    /**
     * 重置查询参数
     */
    const resetQueryParams = () => {
      queryParams.value = {}
    }

    /**
     * 获取工作台项目总览（5 张统计卡真实数据）
     *
     * 策略：先调用后端 `/projects-overview`（如果实现）；
     *       失败/接口不存在时，降级为基于当前项目列表的本地聚合（trend=0）。
     */
    const fetchProjectsOverview = async (
      params?: { compare_window?: 'week' | 'month' },
    ) => {
      overviewLoading.value = true
      try {
        // 清理掉 undefined 字段，避免 axios 把 ?compare_window= 加到 URL
        const cleanParams = params?.compare_window
          ? { compare_window: params.compare_window }
          : undefined
        const response = await projectApi.getProjectsOverview(cleanParams)
        if (response.code === 200) {
          overview.value = response.data
          return
        }
        console.warn('[projects] 获取总览失败，使用本地降级:', response.message)
      } catch (error: any) {
        // 422 / 404 / 500 一律走本地降级，不阻塞页面
        const status = error?.response?.status
        const detail = error?.response?.data?.detail
        console.warn(
          `[projects] /projects-overview 接口不可用 (HTTP ${status})，使用本地降级聚合`,
          detail ? `detail=${JSON.stringify(detail)}` : '',
        )
      } finally {
        // 任何情况下都保证有兜底数据，UI 不会出现空卡
        if (!overview.value) {
          overview.value = buildLocalOverview()
        }
        overviewLoading.value = false
      }
    }

    /**
     * 基于当前 projects + total 构造本地降级 overview
     * （趋势全部为 0，等后端接口就绪后再覆盖）
     */
    function buildLocalOverview(): ProjectsOverview {
      const sum = (key: 'member_count' | 'module_count' | 'case_count' | 'bug_count') =>
        projects.value.reduce((s, p) => s + ((p as any)[key] || 0), 0)
      return {
        project_count: { value: total.value || projects.value.length, trend: 0, compare_window: 'week' },
        member_count:  { value: sum('member_count'),  trend: 0, compare_window: 'week' },
        module_count:  { value: sum('module_count'),  trend: 0, compare_window: 'week' },
        case_count:    { value: sum('case_count'),    trend: 0, compare_window: 'week' },
        bug_count:     { value: sum('bug_count'),     trend: 0, compare_window: 'week' },
        generated_at:  new Date().toISOString(),
      }
    }

    return {
      // 状态
      projects,
      currentProject,
      loading,
      total,
      page,
      pageSize,
      queryParams,
      overview,
      overviewLoading,

      // 计算属性
      hasProjects,
      activeProjects,
      archivedProjects,

      // 方法
      fetchProjects,
      refreshProjects,
      createProject,
      updateProject,
      archiveProject,
      restoreProject,
      deleteProject,
      setCurrentProject,
      clearProjects,
      resetQueryParams,
      fetchProjectsOverview,
    }
  },
  {
    // 持久化配置
    persist: {
      key: 'ai-test-platform-projects',
      storage: localStorage,
      // 只持久化当前选中的项目
      paths: ['currentProject'],
    },
  },
)
