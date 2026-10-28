<template>
  <svg
    class="robot-avatar"
    :class="{ blink, sleeping, talking }"
    viewBox="0 0 64 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <!-- 阴影圆 -->
    <ellipse cx="32" cy="58" rx="14" ry="2" fill="rgba(0,0,0,0.15)" />

    <!-- 天线 -->
    <line
      x1="32"
      y1="4"
      x2="32"
      y2="10"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      opacity="0.85"
    />
    <circle
      cx="32"
      cy="4"
      r="2.4"
      fill="#ffcb6b"
      class="antenna-light"
    />

    <!-- 耳朵装饰 -->
    <rect
      x="4"
      y="24"
      width="4"
      height="12"
      rx="2"
      fill="currentColor"
      opacity="0.75"
    />
    <rect
      x="56"
      y="24"
      width="4"
      height="12"
      rx="2"
      fill="currentColor"
      opacity="0.75"
    />
    <!-- 耳朵内圈 -->
    <rect x="5" y="27" width="2" height="6" rx="1" fill="#ffcb6b" opacity="0.9" />
    <rect x="57" y="27" width="2" height="6" rx="1" fill="#ffcb6b" opacity="0.9" />

    <!-- 头部主体（圆角矩形） -->
    <rect
      x="10"
      y="11"
      width="44"
      height="38"
      rx="11"
      fill="currentColor"
    />
    <!-- 头部高光 -->
    <rect
      x="14"
      y="14"
      width="20"
      height="6"
      rx="3"
      fill="white"
      opacity="0.18"
    />

    <!-- 屏幕（深色面板） -->
    <rect
      x="15"
      y="19"
      width="34"
      height="22"
      rx="6"
      fill="rgba(0,0,0,0.35)"
    />

    <!-- 眼睛区域 -->
    <g class="eyes-group">
      <!-- 左眼 -->
      <g class="eye left-eye">
        <circle cx="24" cy="29" r="3.2" fill="white" />
        <circle cx="24.6" cy="28.4" r="0.9" fill="rgba(0,0,0,0.6)" />
      </g>
      <!-- 右眼 -->
      <g class="eye right-eye">
        <circle cx="40" cy="29" r="3.2" fill="white" />
        <circle cx="40.6" cy="28.4" r="0.9" fill="rgba(0,0,0,0.6)" />
      </g>
    </g>

    <!-- 嘴巴 -->
    <g class="mouth">
      <!-- 默认：微笑曲线 -->
      <path
        v-if="!talking"
        d="M 26 35 Q 32 39 38 35"
        stroke="white"
        stroke-width="1.8"
        stroke-linecap="round"
        fill="none"
        opacity="0.9"
      />
      <!-- talking：O 嘴 -->
      <ellipse
        v-else
        cx="32"
        cy="36"
        rx="3"
        ry="2"
        fill="white"
        opacity="0.9"
        class="talking-mouth"
      />
    </g>

    <!-- 腮红（淡淡的） -->
    <circle cx="18" cy="34" r="2" fill="#ff8a9a" opacity="0.45" />
    <circle cx="46" cy="34" r="2" fill="#ff8a9a" opacity="0.45" />
  </svg>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 说话动画（嘴巴变 O，配合脉动） */
    talking?: boolean
    /** 睡眠状态（眼睛闭着，z 标志） */
    sleeping?: boolean
  }>(),
  { talking: false, sleeping: false },
)

const blink = ref(false)
let blinkTimer: ReturnType<typeof setTimeout> | null = null

/** 随机间隔眨眼 */
function scheduleBlink() {
  const delay = 2500 + Math.random() * 3500
  blinkTimer = setTimeout(() => {
    blink.value = true
    setTimeout(() => {
      blink.value = false
      scheduleBlink()
    }, 180)
  }, delay)
}

onMounted(() => {
  if (!props.sleeping) scheduleBlink()
})

onBeforeUnmount(() => {
  if (blinkTimer) clearTimeout(blinkTimer)
})

watch(
  () => props.sleeping,
  (s) => {
    if (s) {
      if (blinkTimer) clearTimeout(blinkTimer)
    } else {
      scheduleBlink()
    }
  },
)
</script>

<style scoped>
.robot-avatar {
  width: 100%;
  height: 100%;
  color: currentColor; /* 主体色（继承父元素 color） */
}

/* 眨眼：眼睛 scale Y 缩到 0.1，配合 transform-origin 让眼睛闭起来像一条线 */
.robot-avatar .eye {
  transform-origin: center;
  transition: transform 0.08s ease;
}

.robot-avatar.blink .left-eye,
.robot-avatar.blink .right-eye {
  transform: scaleY(0.1);
}

/* 天线指示灯呼吸 */
.antenna-light {
  animation: antenna-pulse 1.8s ease-in-out infinite;
  transform-origin: center;
}

@keyframes antenna-pulse {
  0%,
  100% {
    opacity: 1;
    r: 2.4;
    filter: drop-shadow(0 0 2px color-mix(in srgb, var(--brand-500) 70%, transparent));
  }
  50% {
    opacity: 0.7;
    r: 2.8;
    filter: drop-shadow(0 0 5px color-mix(in srgb, var(--brand-500) 70%, transparent));
  }
}

/* 说话嘴巴：节奏开合 */
.talking-mouth {
  transform-origin: center;
  animation: mouth-talk 0.4s ease-in-out infinite;
}

@keyframes mouth-talk {
  0%,
  100% {
    transform: scaleY(1);
  }
  50% {
    transform: scaleY(0.4);
  }
}

/* 睡眠态：眼睛闭着 */
.robot-avatar.sleeping .left-eye,
.robot-avatar.sleeping .right-eye {
  transform: scaleY(0.1);
}
</style>
