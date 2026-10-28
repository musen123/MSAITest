<script setup lang="ts">
/**
 * 设备投屏控制弹框（scrcpy 播放器）—— 替代原独立路由页 DeviceControlView。
 *
 * 由设备列表「控制」按钮唤起，左右布局：
 *   左＝手机投屏舞台（canvas 上屏 + 指针注入），右＝控制面板（导航键 / 文本注入 /
 *   会话信息 / 调试日志）。
 *
 * 生命周期绑定弹框开合：@open → 申请票据+连接；@closed → dispose + 释放锁 + 通知父刷新。
 * destroy-on-close 保证每次打开都是全新 canvas（贴近原路由页 remount 语义）。
 * 其余投屏 / 坐标映射 / 断线重连逻辑与原页一致（契约《APP自动化-P1接口契约.md》§3/§5）。
 *
 * WebCodecs 需 secure context：生产 https / localhost 满足，普通 http 内网 IP 不满足
 *   → 弹框顶部给出明确告警，不静默黑屏。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useDeviceScreencast } from '@/composables/useDeviceScreencast'

const props = defineProps<{
  visible: boolean
  udid: string
  deviceName?: string
  /** 设备平台（H3/I3）：harmony/ios 走 M-JPEG 投屏 + 触控（无导航键/文本注入） */
  platform?: 'android' | 'harmony' | 'ios'
}>()
const emit = defineEmits<{
  'update:visible': [boolean]
  released: []
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

// ==================== DOM refs ====================
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)

// 投屏会话编排（票据→WS→scrcpy/harmony→坐标映射→重连→释放锁）复用 composable
const sc = useDeviceScreencast({
  udid: () => props.udid,
  canvasRef,
  stageRef,
  platform: () => props.platform ?? 'android',
})
// 鸿蒙 v1：hdckit 单连接只支持触控,无导航键/文本注入（走 uitest 会冲突）；
// iOS v1 同样只支持触控（WDA actions 手势注入）——导航/文本面板仅安卓可见
const isHarmony = computed(() => props.platform === 'harmony')
const isIos = computed(() => props.platform === 'ios')
const isAndroid = computed(() => (props.platform ?? 'android') === 'android')
const {
  viewState,
  errorMsg,
  conflict,
  sessionId,
  mode,
  meta,
  logs,
  canInteract,
  screenAspect,
  stateLabel,
  stateType,
  manualReconnect,
  requestTakeover,
  startObserve,
  onPointerDown,
  onPointerMove,
  onPointerUp,
} = sc

// 宽屏设备（平板/横屏）：投屏容器按画面比例加宽 + 去手机外壳（改平板细边框）。
// 用真实画面宽高比判定（横竖屏都准），meta 未到时按平台兜底（iOS 当前=iPad）。
const isWideScreen = computed(() => {
  if (meta.width && meta.height) return meta.width / meta.height >= 0.62
  return (props.platform ?? 'android') === 'ios'
})
// 弹框宽度：手机 740px；平板竖屏 780px（比手机略宽容纳 3:4，不占满屏）；
// 平板横屏画面很宽 → 按需放大但克制封顶。
const dialogWidth = computed(() => {
  if (!isWideScreen.value) return '740px'
  const a = meta.width && meta.height ? meta.width / meta.height : 0.75
  return a >= 1 ? 'min(1040px, 90vw)' : '780px'
})

// 弹框专属状态
const clipboardText = ref('')
const showLog = ref(false)

// 标题：优先设备上报名，其次列表传入名，最后 udid
const titleName = computed(() => meta.deviceName || props.deviceName || props.udid)

function closeDialog() {
  dialogVisible.value = false
}
function handleReleaseAndClose() {
  dialogVisible.value = false
}

// 导航键 / 文本注入 → composable
const onHome = () => sc.pressHome()
const onBack = () => sc.pressBack()
const onAppSwitch = () => sc.pressAppSwitch()
function sendClipboard() {
  if (!clipboardText.value) {
    ElMessage.warning('请输入要注入的文本')
    return
  }
  if (sc.injectText(clipboardText.value)) {
    ElMessage.success('已注入（设备端粘贴）')
  }
}

// ==================== 生命周期（绑定弹框开合） ====================
async function onOpen() {
  await sc.start()
}
function onClosed() {
  sc.cleanup() // dispose + 释放锁 + 复位（幂等）
  clipboardText.value = ''
  showLog.value = false
  emit('released') // 关闭即释放了锁，通知父列表刷新
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :width="dialogWidth"
    top="5vh"
    destroy-on-close
    :close-on-click-modal="false"
    append-to-body
    class="device-control-dialog"
    @open="onOpen"
    @closed="onClosed"
  >
    <template #header>
      <div class="dlg-head">
        <div class="dlg-title">
          <i class="i-solar-monitor-smartphone-bold-duotone dlg-title-icon" />
          <span class="dlg-title-text" :title="titleName">{{ titleName }}</span>
          <el-tag :type="stateType" effect="light" size="small">
            <i class="i-solar-record-circle-bold state-dot" />{{ stateLabel }}
          </el-tag>
          <span v-if="meta.width" class="dlg-title-meta">
            {{ meta.codecName }} · {{ meta.width }}×{{ meta.height }}
          </span>
        </div>
        <div class="dlg-head-actions">
          <el-button text size="small" @click="showLog = !showLog">
            <i class="i-solar-bug-bold btn-icon" />日志
          </el-button>
          <el-button size="small" @click="handleReleaseAndClose">
            <i class="i-solar-exit-bold btn-icon" />释放并关闭
          </el-button>
        </div>
      </div>
    </template>

    <div class="control-body">
      <!-- 左：投屏舞台（手机外观 / 平板宽外形） -->
      <div class="stage-col">
        <div class="phone-shell" :class="{ 'is-tablet': isWideScreen }">
          <!-- 手机装饰（刘海/侧键）：平板不显示（iPad 无刘海） -->
          <template v-if="!isWideScreen">
            <span class="phone-key phone-key--power" />
            <span class="phone-key phone-key--volume" />
            <div class="phone-notch">
              <span class="notch-cam" />
              <span class="notch-speaker" />
            </div>
          </template>
          <div
            ref="stageRef"
            class="stage"
            :class="{ 'is-wide': isWideScreen }"
            :style="{ aspectRatio: screenAspect }"
          >
            <!-- canvas 上屏 -->
            <canvas
              ref="canvasRef"
              class="screen-canvas"
              :class="{ 'is-live': viewState === 'streaming' }"
              @pointerdown="onPointerDown"
              @pointermove="onPointerMove"
              @pointerup="onPointerUp"
              @pointercancel="onPointerUp"
              @contextmenu.prevent
            />

            <!-- 遮罩：非 streaming 态 -->
            <div v-if="viewState !== 'streaming'" class="stage-overlay">
              <!-- 占用冲突 -->
              <template v-if="viewState === 'conflict'">
                <i class="i-solar-lock-keyhole-bold overlay-icon warn" />
                <div class="overlay-title">设备已被占用</div>
                <div class="overlay-sub">
                  当前占用者：{{ conflict.owner_name || '用户 #' + conflict.owner_user_id }}
                  ·自动化执行/他人操控期间可选择只读观战
                </div>
                <div class="overlay-actions">
                  <el-button type="primary" @click="requestTakeover">重试 / 申请接管</el-button>
                  <el-button @click="startObserve">
                    <i class="i-solar-eye-bold btn-icon" />只读观战
                  </el-button>
                  <el-button @click="closeDialog">关闭</el-button>
                </div>
              </template>

              <!-- 会话失效 -->
              <template v-else-if="viewState === 'expired'">
                <i class="i-solar-shield-cross-bold overlay-icon danger" />
                <div class="overlay-title">会话已失效</div>
                <div class="overlay-sub">{{ errorMsg || '控制会话已结束，请重新申请' }}</div>
                <div class="overlay-actions">
                  <el-button type="primary" @click="manualReconnect">重新申请控制</el-button>
                  <el-button @click="startObserve">
                    <i class="i-solar-eye-bold btn-icon" />只读观战
                  </el-button>
                  <el-button @click="closeDialog">关闭</el-button>
                </div>
              </template>

              <!-- 错误 -->
              <template v-else-if="viewState === 'error'">
                <i class="i-solar-danger-triangle-bold overlay-icon danger" />
                <div class="overlay-title">连接异常</div>
                <div class="overlay-sub">{{ errorMsg || '发生未知错误' }}</div>
                <div class="overlay-actions">
                  <el-button type="primary" @click="manualReconnect">重试</el-button>
                  <el-button @click="closeDialog">关闭</el-button>
                </div>
              </template>

              <!-- 连接 / 重连 / 申请中 -->
              <template v-else>
                <i class="i-solar-refresh-bold overlay-icon spinning" />
                <div class="overlay-title">{{ stateLabel }}</div>
                <div class="overlay-sub">
                  {{
                    viewState === 'reconnecting'
                      ? '网络中断，正在尝试恢复连接…'
                      : '正在建立投屏连接，请稍候…'
                  }}
                </div>
              </template>
            </div>
          </div>
          <div v-if="!isWideScreen" class="phone-home" />
        </div>
      </div>

      <!-- 右：控制面板 -->
      <div class="panel-col">
        <!-- 观战态提示（只读；接管转控制） -->
        <div v-if="mode === 'observe'" class="panel-card observe-card">
          <div class="panel-title">
            <i class="i-solar-eye-bold observe-icon" />观战模式（只读）
          </div>
          <div class="panel-hint">
            当前仅观看画面，触控/导航/文本注入均不可用；自动化执行期间观战不影响执行。
          </div>
          <el-button
            type="primary"
            class="inject-btn"
            :disabled="viewState !== 'streaming'"
            @click="requestTakeover"
          >
            <i class="i-solar-hand-shake-bold btn-icon" />申请接管控制
          </el-button>
        </div>

        <!-- 导航键（鸿蒙/iOS v1 不支持:鸿蒙无 keyEvent、iOS 走 WDA 手势注入） -->
        <div v-if="isAndroid" class="panel-card">
          <div class="panel-title">导航</div>
          <div class="nav-keys">
            <el-button :disabled="!canInteract" @click="onBack">
              <i class="i-solar-arrow-left-bold" />
              <span>返回</span>
            </el-button>
            <el-button :disabled="!canInteract" @click="onHome">
              <i class="i-solar-home-2-bold" />
              <span>主页</span>
            </el-button>
            <el-button :disabled="!canInteract" @click="onAppSwitch">
              <i class="i-solar-widget-bold" />
              <span>多任务</span>
            </el-button>
          </div>
        </div>

        <!-- 文本注入（鸿蒙/iOS v1 不支持） -->
        <div v-if="isAndroid" class="panel-card">
          <div class="panel-title">文本注入（支持中文）</div>
          <el-input
            v-model="clipboardText"
            type="textarea"
            :rows="3"
            :disabled="!canInteract"
            placeholder="输入文本，点击注入后在设备当前输入框自动粘贴"
            resize="none"
          />
          <el-button
            type="primary"
            class="inject-btn"
            :disabled="!canInteract || !clipboardText"
            @click="sendClipboard"
          >
            <i class="i-solar-clipboard-text-bold btn-icon" />
            注入到设备
          </el-button>
          <div class="panel-hint">
            经 SET_CLIPBOARD(paste=true) 写入设备剪贴板并粘贴，需设备当前有输入焦点。
          </div>
        </div>

        <!-- 鸿蒙能力说明 -->
        <div v-if="isHarmony" class="panel-card">
          <div class="panel-title">鸿蒙投屏</div>
          <div class="panel-hint">
            鸿蒙 NEXT 经 uitest 帧流投屏，支持<b>点击 / 滑动</b>触控。受平台能力限制，
            画面为变化驱动的 JPEG 流（非 H.264），暂不支持导航键与文本注入。
          </div>
        </div>

        <!-- iOS 能力说明 -->
        <div v-if="isIos" class="panel-card">
          <div class="panel-title">iOS 投屏</div>
          <div class="panel-hint">
            iOS 经 WebDriverAgent MJPEG 帧流投屏，支持<b>点击 / 滑动</b>触控——
            手势在<b>抬手后</b>整段注入到设备（约 0.5-1s 延迟，非实时拖动）。
            暂不支持导航键与文本注入。
          </div>
        </div>

        <!-- 会话信息 -->
        <div class="panel-card">
          <div class="panel-title">会话</div>
          <div class="info-row">
            <span class="info-k">设备</span>
            <span class="info-v mono">{{ props.udid }}</span>
          </div>
          <div class="info-row">
            <span class="info-k">Session</span>
            <span class="info-v mono">{{ sessionId || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-k">编码</span>
            <span class="info-v">{{ meta.codecName || '—' }}</span>
          </div>
        </div>

        <!-- 调试日志 -->
        <div v-if="showLog" class="panel-card log-card">
          <div class="panel-title">调试日志</div>
          <div class="log-box">
            <div v-for="(l, i) in logs" :key="i" class="log-line">{{ l }}</div>
            <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped lang="scss">
.btn-icon {
  margin-right: 4px;
}
.state-dot {
  margin-right: 4px;
  vertical-align: -1px;
}

/* ── 弹框头部 ─────────────────────────────────────── */
.dlg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-right: 28px; // 避开右上角关闭 X

  .dlg-title {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .dlg-title-icon {
    font-size: 20px;
    color: var(--brand-500);
    flex-shrink: 0;
  }
  .dlg-title-text {
    font-size: var(--font-size-md);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
  }
  .dlg-title-meta {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .dlg-head-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }
}

/* ── 主体：左右布局 ────────────────────────────────── */
.control-body {
  display: flex;
  gap: 18px;
}

.stage-col {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 手机外壳 */
.phone-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--gray-900);
  border-radius: 34px;
  padding: 20px 10px 10px;
  box-shadow: var(--shadow-xl);
  max-width: 100%;

  /* 平板外壳：无刘海，均匀细边框 + 小圆角（贴近 iPad 观感） */
  &.is-tablet {
    border-radius: 20px;
    padding: 12px;
  }
}

.phone-key {
  position: absolute;
  right: -3px;
  width: 3px;
  border-radius: 2px;
  background: var(--gray-700);

  &--power {
    top: 120px;
    height: 52px;
  }
  &--volume {
    top: 188px;
    height: 80px;
  }
}

.phone-notch {
  position: absolute;
  top: 9px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 2;

  .notch-cam {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--gray-700);
    box-shadow: inset 0 0 2px var(--gray-500);
  }
  .notch-speaker {
    width: 46px;
    height: 5px;
    border-radius: 3px;
    background: var(--gray-700);
  }
}

.phone-home {
  width: 70px;
  height: 4px;
  border-radius: 2px;
  background: var(--gray-600);
  margin: 7px auto 0;
  flex-shrink: 0;
}

/* 屏幕（坐标映射基于 canvas 自身 rect）；aspect-ratio 由内联样式按真实
   设备分辨率驱动，canvas 铺满无黑边、圆角裁切干净 */
.stage {
  position: relative;
  flex: 0 0 auto;
  height: clamp(360px, 56vh, 520px);
  max-width: 100%;
  background: #0b0f14;
  border-radius: 24px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 平板屏幕圆角更小（贴近 iPad） */
.stage.is-wide {
  border-radius: 14px;
}

.screen-canvas {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: 100%;
  object-fit: contain;
  touch-action: none; // 关键：禁用浏览器手势，全部交给 injectTouch
  display: block;
  cursor: pointer; // 手指：提示屏幕内可直接点按（模拟触屏）

  &:not(.is-live) {
    opacity: 0;
  }
}

.stage-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #e5e7eb;
  background: rgba(11, 15, 20, 0.86);
  text-align: center;
  padding: 24px;
}

.overlay-icon {
  font-size: 52px;
  color: var(--brand-400, #4ade80);

  &.warn {
    color: #fbbf24;
  }
  &.danger {
    color: #f87171;
  }
  &.spinning {
    animation: spin 1s linear infinite;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.overlay-title {
  font-size: 18px;
  font-weight: 600;
}
.overlay-sub {
  font-size: 13px;
  color: #9ca3af;
  max-width: 360px;
}
.overlay-actions {
  margin-top: 10px;
  display: flex;
  gap: 10px;
}

/* ── 右侧面板 ─────────────────────────────────────── */
.panel-col {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: clamp(360px, 56vh, 520px);
  overflow-y: auto;
}

.panel-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 14px;
}

.panel-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 10px;
}

.observe-card {
  border-color: var(--brand-300, #86efac);
  .observe-icon {
    margin-right: 5px;
    color: var(--brand-500);
    vertical-align: -2px;
  }
}

.nav-keys {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;

  :deep(.el-button) {
    display: flex;
    flex-direction: column;
    gap: 4px;
    height: auto;
    padding: 10px 4px;
    margin: 0;

    i {
      font-size: 20px;
    }
    span {
      font-size: 11px;
    }
  }
}

.inject-btn {
  width: 100%;
  margin-top: 10px;
}

.panel-hint {
  margin-top: 8px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: 1.5;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: var(--font-size-sm);

  .info-k {
    color: var(--text-secondary);
  }
  .info-v {
    color: var(--text-regular);
    max-width: 62%;
    text-align: right;
    word-break: break-all;
  }
}

.mono {
  font-family: var(--font-mono);
  font-size: 12px;
}

.log-card {
  display: flex;
  flex-direction: column;
}

.log-box {
  overflow-y: auto;
  background: var(--bg-page);
  border-radius: 8px;
  padding: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-secondary);
  max-height: 180px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-empty {
  color: var(--text-placeholder);
  text-align: center;
  padding: 12px;
}
</style>
