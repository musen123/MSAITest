<template>
  <section class="app-section-card" :class="{ 'is-padless': padless }">
    <header v-if="title || $slots.header || $slots.extra" class="section-header">
      <div class="section-title-row">
        <slot name="header">
          <h2 v-if="title" class="section-title">{{ title }}</h2>
        </slot>
        <p v-if="description" class="section-desc">{{ description }}</p>
      </div>
      <div v-if="$slots.extra" class="section-extra">
        <slot name="extra" />
      </div>
    </header>
    <div class="section-body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="section-footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup lang="ts">
/**
 * AppSectionCard - 通用内容卡（图表/列表/任意内容容器）
 *
 * 用法：
 *   <AppSectionCard title="测试执行趋势">
 *     <template #extra>
 *       <el-select>...</el-select>
 *     </template>
 *     <chart />
 *   </AppSectionCard>
 */
defineProps<{
  title?: string
  description?: string
  padless?: boolean
}>()
</script>

<style scoped lang="scss">
.app-section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6) 0;
}

.section-title-row {
  flex: 1;
  min-width: 0;
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.section-desc {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.section-extra {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.section-body {
  padding: var(--space-5) var(--space-6);
}

.app-section-card.is-padless .section-body {
  padding: 0;
}

.section-footer {
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-light);
  background: var(--gray-50);
}
</style>
