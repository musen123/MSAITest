<template>
  <div class="app-glow-bg" :class="`is-${variant}`">
    <div v-if="orbs" class="glow-orbs">
      <span class="orb orb-1" />
      <span class="orb orb-2" />
      <span class="orb orb-3" />
    </div>
    <div class="glow-content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AppGlowBg - 主色辉光背景
 *
 * 用法：
 *   <AppGlowBg variant="soft">  ← 内容外层
 *     ... 主体 ...
 *   </AppGlowBg>
 *
 * variant:
 *   - soft: 极淡（页面级默认）
 *   - strong: 较强（登录页风格）
 *   - card: 卡片内辉光
 */
withDefaults(
  defineProps<{
    variant?: 'soft' | 'strong' | 'card'
    orbs?: boolean
  }>(),
  {
    variant: 'soft',
    orbs: false,
  },
)
</script>

<style scoped lang="scss">
.app-glow-bg {
  position: relative;
  width: 100%;
  height: 100%;
  isolation: isolate;
}





.is-card {
  background: radial-gradient(
    circle at 30% 20%,
    var(--brand-glow-soft),
    transparent 60%
  ), var(--bg-card);
}

/* 深色模式辉光增强 */
:global([data-theme='dark']) .is-strong {
  background:
    radial-gradient(ellipse 600px 400px at 30% 30%, rgba(45, 212, 120, 0.15), transparent 60%),
    radial-gradient(ellipse 500px 300px at 70% 70%, rgba(45, 212, 120, 0.10), transparent 60%),
    var(--bg-card);
}

:global([data-theme='dark']) .is-card {
  background: radial-gradient(
    circle at 50% 60%,
    var(--brand-glow-soft),
    transparent 60%
  ), var(--bg-card);
}

.glow-orbs {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.6;
}

.orb-1 {
  top: -100px;
  left: -100px;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--brand-300), transparent 70%);
  animation: float-1 20s ease-in-out infinite;
}

.orb-2 {
  bottom: -150px;
  right: -100px;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--brand-200), transparent 70%);
  animation: float-2 25s ease-in-out infinite;
}

.orb-3 {
  top: 50%;
  left: 50%;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, var(--color-cyan-500), transparent 70%);
  opacity: 0.3;
  animation: float-3 30s ease-in-out infinite;
}

.glow-content {
  position: relative;
  z-index: 1;
}

@keyframes float-1 {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(80px, 60px); }
}
@keyframes float-2 {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-60px, -80px); }
}
@keyframes float-3 {
  0%, 100% { transform: translate(-50%, -50%); }
  50% { transform: translate(-30%, -70%); }
}
</style>
