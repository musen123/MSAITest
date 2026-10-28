<template>
  <div class="app-update-notice" :class="`tone-${tone}`">
    <!-- 装饰光晕 -->
    <div class="bg-glow"></div>

    <!-- 左侧插画 -->
    <div class="notice-illu" aria-hidden="true">
      <svg viewBox="0 0 80 80" width="80" height="80">
        <!-- 火箭主体 -->
        <defs>
          <linearGradient id="rocketGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="currentColor" stop-opacity="0.95" />
            <stop offset="100%" stop-color="currentColor" stop-opacity="0.6" />
          </linearGradient>
        </defs>
        <!-- 火焰 -->
        <path
          d="M30 60 Q33 70 36 64 L34 58 Z M40 64 Q44 78 48 64 L44 58 Z M48 60 Q52 70 54 64 L50 58 Z"
          fill="#f59e0b"
          opacity="0.85"
        />
        <path
          d="M34 58 Q38 68 42 58 Z M44 58 Q48 66 50 58 Z"
          fill="#fbbf24"
        />
        <!-- 火箭身 -->
        <path
          d="M40 12 C 28 26 28 44 32 58 L48 58 C 52 44 52 26 40 12 Z"
          fill="url(#rocketGrad)"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
        <!-- 火箭窗 -->
        <circle cx="40" cy="32" r="5" fill="#fff" opacity="0.9" />
        <circle cx="40" cy="32" r="3" fill="currentColor" opacity="0.4" />
        <!-- 侧翼 -->
        <path d="M28 50 L24 58 L32 58 Z" fill="currentColor" opacity="0.7" />
        <path d="M52 50 L56 58 L48 58 Z" fill="currentColor" opacity="0.7" />
        <!-- 装饰星 -->
        <g class="star star-1">
          <path d="M14 18 L15.5 21 L18.5 21.5 L15.5 22 L14 25 L12.5 22 L9.5 21.5 L12.5 21 Z" fill="currentColor" opacity="0.5" />
        </g>
        <g class="star star-2">
          <path d="M64 16 L65 18 L67 18.5 L65 19 L64 21 L63 19 L61 18.5 L63 18 Z" fill="currentColor" opacity="0.6" />
        </g>
        <g class="star star-3">
          <path d="M66 46 L67 48 L69 48.5 L67 49 L66 51 L65 49 L63 48.5 L65 48 Z" fill="currentColor" opacity="0.5" />
        </g>
      </svg>
    </div>

    <!-- 文字内容 -->
    <div class="notice-body">
      <div class="notice-title-row">
        <h3 class="notice-title">{{ title }}</h3>
        <span v-if="badge" class="notice-badge">{{ badge }}</span>
      </div>
      <p class="notice-desc">{{ description }}</p>
      <div v-if="meta || cta" class="notice-meta-row">
        <span v-if="meta" class="notice-meta">
          <i class="i-solar-calendar-date-bold" />
          {{ meta }}
        </span>
        <span v-if="cta" class="notice-cta">
          {{ cta }}
          <i class="i-solar-arrow-right-bold" />
        </span>
      </div>
    </div>

    <!-- 关闭按钮 -->
    <button v-if="closable" class="notice-close" aria-label="关闭" @click="onClose">
      <i class="i-solar-close-circle-linear" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

/**
 * AppUpdateNotice - 功能上线公告插画
 *
 * 用法：
 *   <AppUpdateNotice
 *     title="性能测试模块"
 *     description="该功能于 7 月新班级开班更新上线"
 *     meta="预计 2026-07 上线"
 *     cta="敬请期待"
 *   />
 */
withDefaults(
  defineProps<{
    title?: string
    description?: string
    meta?: string
    cta?: string
    badge?: string
    tone?: 'brand' | 'warning' | 'info' | 'purple'
    closable?: boolean
  }>(),
  {
    title: '该功能即将上线',
    description: '本功能正在紧张开发中，新班级开班后即可体验完整能力。',
    meta: '预计 2026 年 7 月上线',
    cta: '敬请期待',
    badge: '即将上新',
    tone: 'brand',
    closable: false,
  }
)

const emit = defineEmits<{ (e: 'close'): void }>()
const visible = ref(true)
function onClose() {
  visible.value = false
  emit('close')
}
</script>

<style scoped lang="scss">
.app-update-notice {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-5) var(--space-6);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  isolation: isolate;
  transition: transform 0.3s, box-shadow 0.3s;

  &:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-card-hover);
  }
}

/* 背景光晕 */
.bg-glow {
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  opacity: 0.4;

  &::before,
  &::after {
    content: '';
    position: absolute;
    border-radius: 50%;
    filter: blur(40px);
  }
  &::before {
    top: -60px;
    left: -40px;
    width: 220px;
    height: 220px;
  }
  &::after {
    bottom: -80px;
    right: 20%;
    width: 280px;
    height: 280px;
    opacity: 0.7;
  }
}

/* 左侧插画 */
.notice-illu {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  position: relative;

  svg {
    animation: rocket-float 3.6s ease-in-out infinite;
  }

  .star {
    transform-origin: center;
    animation: star-twinkle 2.4s ease-in-out infinite;
  }
  .star-1 { animation-delay: 0s; }
  .star-2 { animation-delay: 0.8s; }
  .star-3 { animation-delay: 1.6s; }
}

/* 主体内容 */
.notice-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.notice-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.notice-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  letter-spacing: 0.2px;
}
.notice-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.5px;
}
.notice-desc {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}
.notice-meta-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: 4px;
  flex-wrap: wrap;
}
.notice-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);

  > i { font-size: 14px; }
}
.notice-cta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: gap 0.2s;

  &:hover { gap: 8px; }
  > i { font-size: 12px; }
}

/* 关闭 */
.notice-close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: background 0.15s, color 0.15s;

  &:hover {
    background: var(--gray-100);
    color: var(--text-primary);
  }
}

/* ============ 主题色 ============ */
.tone-brand {
  color: var(--brand-500);

  .bg-glow::before { background: var(--brand-100); }
  .bg-glow::after  { background: var(--brand-50); }
  .notice-illu {
    background: var(--brand-50);
  }
  .notice-badge {
    background: var(--brand-50);
    color: var(--brand-600);
  }
  .notice-meta   { color: var(--brand-600); }
  .notice-cta    { color: var(--brand-500); }
}

.tone-info {
  color: var(--color-info-500);

  .bg-glow::before { background: var(--color-info-100); }
  .bg-glow::after  { background: var(--color-info-50); }
  .notice-illu {
    background: var(--color-info-50);
  }
  .notice-badge {
    background: var(--color-info-50);
    color: var(--color-info-600);
  }
  .notice-meta   { color: var(--color-info-600); }
  .notice-cta    { color: var(--color-info-500); }
}

.tone-warning {
  color: #f59e0b;

  .bg-glow::before { background: #fef3c7; }
  .bg-glow::after  { background: #fffbeb; }
  .notice-illu {
    background: #fff7ed;
  }
  .notice-badge {
    background: #fff7ed;
    color: #d97706;
  }
  .notice-meta   { color: #d97706; }
  .notice-cta    { color: #f59e0b; }
}

.tone-purple {
  color: var(--color-purple-500);

  .bg-glow::before { background: var(--color-purple-100); }
  .bg-glow::after  { background: var(--color-purple-50); }
  .notice-illu {
    background: var(--color-purple-50);
  }
  .notice-badge {
    background: var(--color-purple-50);
    color: var(--color-purple-600);
  }
  .notice-meta   { color: var(--color-purple-600); }
  .notice-cta    { color: var(--color-purple-500); }
}

/* ============ 动画 ============ */
@keyframes rocket-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-6px); }
}
@keyframes star-twinkle {
  0%, 100% { opacity: 0.3; transform: scale(0.85); }
  50%      { opacity: 0.9; transform: scale(1.15); }
}

/* ============ 响应式 ============ */
@media (max-width: 640px) {
  .app-update-notice {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-4);
  }
  .notice-illu {
    width: 64px;
    height: 64px;
    svg { width: 64px; height: 64px; }
  }
}
</style>
