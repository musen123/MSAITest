<script setup lang="ts">
/**
 * 功能测试模块占位组件
 *
 * 各路由暂用此组件占位，等待具体页面实现。
 */
defineProps<{
  pageName: string
  description?: string
  apiBindings?: string[]
}>()
</script>

<template>
  <div class="func-test-placeholder">
    <el-card shadow="never" class="placeholder-card">
      <template #header>
        <div class="placeholder-header">
          <el-icon :size="22"><Document /></el-icon>
          <span class="title">{{ pageName }}</span>
          <el-tag type="warning" size="small">骨架占位</el-tag>
        </div>
      </template>
      <el-empty :description="description || '页面待开发'">
        <template #image>
          <el-icon :size="64" color="#bbb"><DocumentAdd /></el-icon>
        </template>
      </el-empty>

      <div v-if="apiBindings && apiBindings.length" class="api-bindings">
        <div class="binding-title">已就绪的后端接口：</div>
        <ul>
          <li v-for="api in apiBindings" :key="api">
            <code>{{ api }}</code>
          </li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.func-test-placeholder {
  padding: 16px;
}
.placeholder-card {
  border-radius: 8px;
}
.placeholder-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.placeholder-header .title {
  font-size: 16px;
  font-weight: 600;
}
.api-bindings {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--theme-color-f7f8fa);
  border-radius: 6px;
  font-size: 13px;
  color: var(--theme-color-555555);
}
.binding-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.api-bindings ul {
  margin: 0;
  padding-left: 18px;
}
.api-bindings code {
  color: var(--theme-color-1677ff);
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
}
</style>
