<template>
  <header class="app-page-header">
    <!-- 背景插画：放大置于右侧，溢出裁切只露局部，低透明度作氛围 -->
    <img
      v-if="illustration"
      :src="illustration"
      alt=""
      aria-hidden="true"
      class="header-bg-illust"
    />

    <div class="header-inner">
      <!-- 主区 -->
      <div class="page-main">
        <div v-if="icon" class="page-icon">
          <i :class="icon" />
        </div>
        <div class="page-info">
          <h1 class="page-title">
            <slot name="title">{{ title }}</slot>
          </h1>
          <p v-if="description || $slots.description" class="page-desc">
            <slot name="description">{{ description }}</slot>
          </p>
        </div>
        <div v-if="$slots.actions" class="page-actions">
          <slot name="actions" />
        </div>
      </div>
    </div>

    <!-- 品牌色渐隐分隔线 -->
    <div class="page-divider" />
  </header>
</template>

<script setup lang="ts">
/**
 * AppPageHeader - 通用页头（图标徽章式）
 *
 * 用法：
 *   <AppPageHeader
 *     title="用例库"
 *     description="管理所有测试用例..."
 *     :breadcrumbs="['测试管理', '用例库']"
 *     icon="i-solar-document-text-bold"
 *     :illustration="illustTestWeb"
 *   >
 *     <template #actions>
 *       <el-button>导入</el-button>
 *       <el-button type="primary">+ 新建用例</el-button>
 *     </template>
 *   </AppPageHeader>
 *
 * icon：可选，UnoCSS 图标 class，渲染为左侧软色图标块
 * illustration：可选，插画 URL（import 的 svg），
 *   作为背景放大置于右侧、裁切显示局部
 */
defineProps<{
  title?: string
  description?: string
  /** 已废弃：不再渲染面包屑，保留声明仅为吸收旧页面传参 */
  breadcrumbs?: string[]
  /** UnoCSS 图标 class（如 'i-solar-chart-square-bold'） */
  icon?: string
  /** 背景插画 URL，放大裁切显示 */
  illustration?: string
}>()
</script>

<style scoped lang="scss">
.app-page-header {
  position: relative;
  overflow: hidden;
  margin-bottom: var(--space-1);
}

.header-bg-illust {
  position: absolute;
  right: 2%;
  top: 50%;
  height: 220%;
  width: auto;
  transform: translateY(-46%);
  opacity: 0.2;
  pointer-events: none;
  user-select: none;
}

.header-inner {
  position: relative;
}

.page-main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.page-icon {
  width: 46px;
  height: 46px;
  border-radius: var(--radius-lg);
  background: var(--brand-50);
  color: var(--brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.page-info {
  flex: 1;
  min-width: 0;
}

.page-title {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: var(--line-height-tight);
  margin: 0;
}

.page-desc {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: var(--line-height-normal);
}

.page-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.page-divider {
  position: relative;
  height: 2px;
  margin-top: var(--space-3);
  background: linear-gradient(
    to right,
    var(--brand-200),
    transparent 70%
  );
}
</style>
