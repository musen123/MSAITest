<template>
  <div class="pws-layout">
    <!-- 顶部导航栏 -->
    <WorkspaceHeader />

    <!-- 主体 -->
    <div class="pws-body">
      <WorkspaceSidebar v-if="currentProject" />

      <main class="pws-main">
        <!-- 历史记录标签 -->
        <HistoryTabs />

        <!-- 路由视图 -->
        <div class="pws-content">
          <RouterView />
        </div>
      </main>
    </div>

    <!-- 全局浮窗智能体 -->
    <FloatingChat />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace'
import { projectApi } from '@/api/projects'
import { ElMessage } from 'element-plus'
import WorkspaceHeader from '@/components/workspace/WorkspaceHeader.vue'
import WorkspaceSidebar from '@/components/workspace/WorkspaceSidebar.vue'
import HistoryTabs from '@/components/workspace/HistoryTabs.vue'
import FloatingChat from '@/components/chat/FloatingChat.vue'

const route = useRoute()
const router = useRouter()
const workspaceStore = useProjectWorkspaceStore()

const currentProject = computed(() => workspaceStore.currentProject)

let restoreVersion = 0
watch(
  () => route.params.id,
  async (rawId) => {
    const version = ++restoreVersion
    const projectId = Number(rawId)
    if (!Number.isInteger(projectId) || projectId <= 0) {
      workspaceStore.clearCurrentProject()
      await router.replace('/workspace/projects')
      return
    }
    try {
      const [projectRes, permissionRes] = await Promise.all([
        projectApi.getProjectDetail(projectId),
        projectApi.getMemberPermissions(projectId),
      ])
      if (version !== restoreVersion) return
      workspaceStore.setCurrentProject(projectRes.data)
      workspaceStore.setUserRole(permissionRes.data.project_role)
      workspaceStore.setPermissions(permissionRes.data.permissions)
      // 成员页按需加载；恢复工作空间不应额外依赖 member:view 权限。
      workspaceStore.setMembers([])
    } catch (error) {
      if (version !== restoreVersion) return
      workspaceStore.clearCurrentProject()
      ElMessage.error('项目不存在或已无权访问')
      await router.replace('/workspace/projects')
    }
  },
  { immediate: true },
)
</script>

<style scoped lang="scss">
.pws-layout {
  width: 100%;
  height: 100vh;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.pws-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
  z-index: 1;
}

.pws-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* 极淡主色辉光 - 与 Workspace 一致 */
  background:
    radial-gradient(circle at 0% 0%,    rgba(0, 185, 107, 0.04), transparent 50%),
    radial-gradient(circle at 100% 100%, rgba(0, 185, 107, 0.03), transparent 50%),
    var(--bg-page);
}

.pws-content {
  flex: 1;
  padding: var(--layout-content-pad);
  overflow-y: auto;
  overflow-x: hidden;
}

.pws-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.pws-content::-webkit-scrollbar-thumb {
  background: var(--gray-300);
  border-radius: 3px;
  &:hover { background: var(--gray-400); }
}
</style>
