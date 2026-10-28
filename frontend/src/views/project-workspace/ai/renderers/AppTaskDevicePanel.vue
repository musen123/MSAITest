<script setup lang="ts">
/**
 * App 自动化任务详情 — 右侧常驻「手机设备」面板（run_app_script / run_app_suite /
 * explore_app_script）。
 *
 * 页面右栏用 CSS 手机框包住观战投屏 canvas：mode=observe 只读，不占设备锁，与正在
 * 驱动设备的 exec 会话零冲突（P4 观战通道，安卓/鸿蒙/iOS 平台透明）。运行中直播真机
 * 画面，任务进入终态断流上遮罩，不再占用隧道。模型逐轮日志由详情页左侧「运行日志」
 * 承担，此处只呈现设备画面。
 *
 * 平台解码器三级解析：input_params.platform（提交时落）→ 设备列表按 udid 反查
 * （老任务/定时套件缺省场景）→ android 兜底。解析完成后才开流，避免 M-JPEG 设备被
 * 按 H264 解码黑屏。平板设备走宽机身外形，手机走窄长外形。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { appDeviceApi } from '@/api/appDevice'
import { useDeviceScreencast, type DeviceCastPlatform } from '@/composables/useDeviceScreencast'
import type { AiTaskDetail } from '@/types/ai-task'

const props = defineProps<{
  active: boolean
  task?: AiTaskDetail | null
}>()

const params = computed(() => (props.task?.input_params || {}) as Record<string, unknown>)
const udid = computed(() => String(params.value.device_udid || ''))

const platform = ref<DeviceCastPlatform>('android')
const isTablet = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)
const sc = useDeviceScreencast({
  udid: () => udid.value,
  canvasRef,
  stageRef,
  platform: () => platform.value,
})

/** 结束态：不再开流；运行中断流后也置位（遮罩文案区分） */
const ended = ref(false)
const started = ref(false)

const PLATFORM_LABEL: Record<DeviceCastPlatform, string> = {
  android: 'Android',
  harmony: '鸿蒙',
  ios: 'iOS',
}

const deviceModel = ref('')
const isLive = computed(() => sc.viewState.value === 'streaming' && !ended.value)

async function resolvePlatformAndStart() {
  if (!udid.value || started.value) return
  const fromParams = params.value.platform
  if (fromParams === 'android' || fromParams === 'harmony' || fromParams === 'ios') {
    platform.value = fromParams
  }
  // 设备列表反查机型 / 平板外形 / 平台兜底（老任务或定时套件缺 platform）
  try {
    const devices = await appDeviceApi.listDevices()
    const hit = devices.find((d) => d.udid === udid.value)
    if (hit) {
      if (hit.platform) platform.value = hit.platform
      deviceModel.value = hit.model || ''
      const m = (hit.model || '').toLowerCase()
      isTablet.value = /ipad|pad|tablet/.test(m)
    }
  } catch {
    /* 兜底 android + 手机外形 */
  }
  if (!props.active) return // 解析期间任务已结束
  started.value = true
  void sc.startObserve()
}

onMounted(() => {
  if (props.active) void resolvePlatformAndStart()
  else ended.value = true
})

watch(
  () => props.active,
  (act) => {
    if (!act) {
      ended.value = true
      sc.cleanup()
    }
  },
)
// 详情页任务数据晚于渲染器挂载到位时补启（task 异步加载）
watch(udid, () => {
  if (props.active) void resolvePlatformAndStart()
})

onBeforeUnmount(() => sc.cleanup())
</script>

<template>
  <div class="app-device-panel">
    <div class="adp-head">
      <span class="adp-title">
        <i class="i-solar-smartphone-2-bold" />
        设备实时画面
      </span>
      <span v-if="isLive" class="adp-live"><span class="adp-dot" />直播</span>
      <span v-else class="adp-off">{{ ended ? '已结束' : '未连接' }}</span>
    </div>

    <!-- CSS 手机框：深色机身 + 灵动岛 + 屏幕区嵌观战 canvas -->
    <div ref="stageRef" class="adp-frame" :class="{ tablet: isTablet }">
      <span v-if="!isTablet" class="adp-island" />
      <div
        class="adp-screen"
        :style="sc.meta.width ? { aspectRatio: sc.screenAspect.value } : undefined"
      >
        <canvas ref="canvasRef" class="adp-canvas" :class="{ 'is-live': isLive }" />
        <div v-if="!isLive" class="adp-overlay">
          <template v-if="ended">
            <i class="i-solar-monitor-smartphone-bold adp-icon" />
            <span class="adp-msg">任务已结束</span>
            <span class="adp-hint">直播仅任务运行期间提供，回放录像见执行报告</span>
          </template>
          <template v-else-if="!udid">
            <i class="i-solar-smartphone-2-bold adp-icon" />
            <span class="adp-msg">未绑定具体设备</span>
            <span class="adp-hint">套件默认设备，执行开始后可实时查看</span>
          </template>
          <template v-else>
            <i class="i-solar-eye-bold adp-icon" />
            <span class="adp-msg">{{ sc.stateLabel.value }}</span>
          </template>
        </div>
      </div>
      <span v-if="!isTablet" class="adp-home" />
    </div>

    <div class="adp-foot">
      <span class="adp-plat">{{ PLATFORM_LABEL[platform] }}</span>
      <span v-if="deviceModel" class="adp-model" :title="deviceModel">{{ deviceModel }}</span>
      <span v-if="sc.meta.width" class="adp-res">{{ sc.meta.width }}×{{ sc.meta.height }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-device-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.adp-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
}
.adp-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.adp-live {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--success-600);
  background: var(--success-50);
  border: 1px solid var(--success-200);
  border-radius: var(--radius-full);
  padding: 2px 9px;
}
.adp-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success-500);
  animation: adp-pulse 1.2s ease-in-out infinite;
}
@keyframes adp-pulse {
  50% { opacity: 0.35; }
}
.adp-off {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--gray-100);
  border-radius: var(--radius-full);
  padding: 2px 9px;
}

/* 手机机身：深色边框 + 圆角，屏幕区居中 */
.adp-frame {
  position: relative;
  width: 100%;
  max-width: 260px;
  background: #12161c;
  border: 1px solid #2b323c;
  border-radius: 34px;
  padding: 12px;
  box-shadow:
    0 10px 30px rgba(0, 0, 0, 0.22),
    inset 0 0 0 2px #0a0d12;

  &.tablet {
    max-width: 300px;
    border-radius: 22px;
    padding: 14px;
  }
}
/* 灵动岛 */
.adp-island {
  position: absolute;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  width: 68px;
  height: 18px;
  border-radius: 10px;
  background: #05070a;
  z-index: 2;
}
/* Home 指示条 */
.adp-home {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: 84px;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.28);
  z-index: 2;
}
.adp-screen {
  position: relative;
  width: 100%;
  aspect-ratio: 9 / 19.5;
  background: #0b0f14;
  border-radius: 24px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;

  .tablet & {
    aspect-ratio: 3 / 4;
    border-radius: 12px;
  }
}
.adp-canvas {
  max-width: 100%;
  max-height: 100%;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  &:not(.is-live) { opacity: 0; }
}
.adp-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #9ca3af;
  text-align: center;
  padding: 0 20px;
}
.adp-icon {
  font-size: 34px;
  color: var(--brand-400, #4ade80);
}
.adp-msg {
  font-size: var(--font-size-sm);
}
.adp-hint {
  font-size: var(--font-size-xs);
  color: #6b7280;
  line-height: 1.4;
}
.adp-foot {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.adp-plat {
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.adp-model {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.adp-res {
  font-family: var(--font-mono);
  color: var(--text-placeholder);
}
</style>
