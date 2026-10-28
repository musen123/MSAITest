<template>
  <div class="project-switcher">
    <el-button
      :icon="FolderOpened"
      class="switch-btn"
      @click="handleSwitch"
    >
      切换项目
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { FolderOpened } from '@element-plus/icons-vue'
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace'

const router = useRouter()
const workspaceStore = useProjectWorkspaceStore()

// 切换项目：清除当前项目并返回项目列表
const handleSwitch = () => {
  // 清除当前项目信息
  workspaceStore.clearCurrentProject()

  // 返回项目列表
  router.push('/workspace/projects')
}
</script>

<style scoped lang="scss">
.project-switcher {
  .switch-btn {
    color: var(--workspace-text-regular);
    font-size: 14px;
    transition: color 0.2s;

    &:hover {
      color: var(--workspace-color-primary);
    }
  }
}
</style>
