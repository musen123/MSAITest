<script setup lang="ts">
/**
 * 执行实时查看（P4）：左＝观战直播（只读投屏，不占锁与 exec 零冲突），
 * 右＝任务事件直播（SSE：阶段/进度/模型逐轮日志）。回放/套件执行提交后
 * 自动打开，跑完就地收尾（状态+报告入口由父层刷新提供）。
 *
 * 自包含：挂载即开观战+订阅 SSE，卸载即断流+清理（放在 destroy-on-close
 * 的抽屉里用）。观战对锁零接触——执行结束后画面仍在，随时关。
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { streamAiTask } from '@/api/aiTask'
import { appDeviceApi } from '@/api/appDevice'
import { useDeviceScreencast, type DeviceCastPlatform } from '@/composables/useDeviceScreencast'

const props = defineProps<{
  projectId: number
  udid: string
  taskId: number
  title?: string
}>()
const emit = defineEmits<{
  /** 任务终态（succeeded/failed/canceled）——父层刷新列表/详情 */
  finished: [status: string]
}>()

// ── 观战投屏 ──
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)
// 平台决定解码器（harmony/ios=M-JPEG，android=scrcpy H264）：开流前按 udid 反查，不能默认 android
const platform = ref<DeviceCastPlatform>('android')
const sc = useDeviceScreencast({
  udid: () => props.udid,
  canvasRef,
  stageRef,
  platform: () => platform.value,
})

// ── 任务事件流 ──
const stageText = ref('')
const percent = ref(0)
const logs = ref<string[]>([])
const taskStatus = ref<'running' | 'succeeded' | 'failed' | 'canceled'>('running')
const logsEl = ref<HTMLDivElement | null>(null)
let stopStream: (() => void) | null = null

const STATUS_META: Record<string, { label: string; type: string }> = {
  running: { label: '执行中', type: 'warning' },
  succeeded: { label: '执行成功', type: 'success' },
  failed: { label: '执行失败', type: 'danger' },
  canceled: { label: '已取消', type: 'info' },
}

function pushLog(line: string) {
  logs.value.push(line)
  if (logs.value.length > 500) logs.value.splice(0, logs.value.length - 500)
  void nextTick(() => {
    logsEl.value?.scrollTo({ top: logsEl.value.scrollHeight })
  })
}

onMounted(async () => {
  await nextTick()
  // 观战直播（只读，不占锁）：exec 正驱动设备也照看。先解析平台再开流，避免解码器走错
  try {
    const devices = await appDeviceApi.listDevices()
    const hit = devices.find((d) => d.udid === props.udid)
    if (hit?.platform) platform.value = hit.platform
  } catch {
    /* 查不到按 android 兜底 */
  }
  void sc.startObserve()
  stopStream = streamAiTask(props.projectId, props.taskId, {
    onEvent: (ev) => {
      const p = (ev.payload || {}) as Record<string, unknown>
      if (ev.type === 'stage') {
        stageText.value = String(p.name || '')
      } else if (ev.type === 'progress') {
        percent.value = Number(p.percent) || percent.value
      } else if (ev.type === 'log') {
        pushLog(String(p.message || ''))
      } else if (ev.type === 'error') {
        pushLog(`✗ ${String(p.message || '任务失败')}`)
      } else if (ev.type === 'task_end') {
        const st = String(p.status || '')
        taskStatus.value =
          st === 'succeeded' ? 'succeeded'
          : st === 'canceled' || st === 'cancelled' ? 'canceled'
          : 'failed'
        if (st === 'succeeded') percent.value = 100
        stopStream?.()
        stopStream = null
        emit('finished', taskStatus.value)
      }
    },
    onError: () => {
      pushLog('（事件流断开，任务仍在后台执行，可刷新列表看结果）')
    },
  })
})

onBeforeUnmount(() => {
  stopStream?.()
  stopStream = null
  sc.cleanup()
})
</script>

<template>
  <div class="live-view">
    <!-- 左：观战直播 -->
    <div class="lv-stage-col">
      <div ref="stageRef" class="lv-stage" :style="{ aspectRatio: sc.screenAspect.value }">
        <canvas
          ref="canvasRef"
          class="lv-canvas"
          :class="{ 'is-live': sc.viewState.value === 'streaming' }"
        />
        <div v-if="sc.viewState.value !== 'streaming'" class="lv-overlay">
          <i class="i-solar-eye-bold lv-overlay-icon" />
          <span>{{ sc.stateLabel.value }}</span>
        </div>
      </div>
      <div class="lv-stage-foot">
        <el-tag size="small" effect="light" type="success">
          <i class="i-solar-eye-bold tag-icon" />观战直播（只读）
        </el-tag>
        <span v-if="sc.meta.width" class="lv-meta">
          {{ sc.meta.codecName }} · {{ sc.meta.width }}×{{ sc.meta.height }}
        </span>
      </div>
    </div>

    <!-- 右：任务事件直播 -->
    <div class="lv-log-col">
      <div class="lv-head">
        <el-tag :type="STATUS_META[taskStatus].type" effect="light" size="small">
          {{ STATUS_META[taskStatus].label }}
        </el-tag>
        <span class="lv-stage-text">{{ stageText || '—' }}</span>
      </div>
      <el-progress
        :percentage="percent"
        :status="taskStatus === 'failed' ? 'exception' : taskStatus === 'succeeded' ? 'success' : undefined"
        :stroke-width="8"
      />
      <div ref="logsEl" class="lv-logs">
        <div v-for="(l, i) in logs" :key="i" class="lv-log-line">{{ l }}</div>
        <div v-if="!logs.length" class="lv-log-empty">等待执行日志…</div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.live-view {
  display: flex;
  gap: 16px;
  height: 100%;
  min-height: 460px;
}
.lv-stage-col {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.lv-stage {
  position: relative;
  height: clamp(360px, 52vh, 520px);
  background: #0b0f14;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.lv-canvas {
  max-width: 100%;
  max-height: 100%;
  height: 100%;
  width: auto;
  object-fit: contain;
  display: block;
  &:not(.is-live) { opacity: 0; }
}
.lv-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
  font-size: var(--font-size-sm);
  .lv-overlay-icon { font-size: 40px; color: var(--brand-400, #4ade80); }
}
.lv-stage-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  .tag-icon { margin-right: 3px; vertical-align: -1px; }
  .lv-meta { font-size: var(--font-size-xs); color: var(--text-secondary); }
}
.lv-log-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lv-head {
  display: flex;
  align-items: center;
  gap: 10px;
  .lv-stage-text {
    font-size: var(--font-size-sm);
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
.lv-logs {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-page);
  border: 1px solid var(--border-lighter);
  border-radius: 10px;
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-regular);
}
.lv-log-line { white-space: pre-wrap; word-break: break-all; }
.lv-log-empty { color: var(--text-placeholder); text-align: center; padding: 24px 0; }
</style>
