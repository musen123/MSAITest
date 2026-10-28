<script setup lang="ts">
/**
 * 智能操作台（App 自动化录制，P2 旗舰）
 *
 * 左＝设备实时投屏（复用 useDeviceScreencast），右＝自然语言指令流 + 步骤沉淀。
 * 流程：选在线设备 → 开始（申请票据+投屏，拿 session_id）→ 逐条输入自然语言
 * → Agent aiAct 执行（真机可见）→ 回收即时动作步骤累积成 YAML flow → 保存为
 * 可回放用例。录制会话与投屏同一锁 owner、同一 session_id（方案 §2.2）。
 *
 * 端到端需 Midscene 兼容 VL 模型（vision 配置的 model_family）；缺失时 step 端点
 * 回 400 引导去配置。
 */
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { appDeviceApi, type AppDevice } from '@/api/appDevice'
import {
  appTestApi,
  type ExploreResultSummary,
  type RecoveredStep,
  type StepProgressEntry,
} from '@/api/appTest'
import { aiTaskApi, streamAiTask } from '@/api/aiTask'
import { useDeviceScreencast } from '@/composables/useDeviceScreencast'
import AppPageHeader from '@/components/common/AppPageHeader.vue'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))

/** 操作台模式：逐步录制（P2，同步单步）| 探索生成（P3，任务化） */
const mode = ref<'record' | 'explore'>('record')

// ==================== 设备选择 ====================
const devices = ref<AppDevice[]>([])
const selectedUdid = ref('')
const loadingDevices = ref(false)

async function loadDevices() {
  loadingDevices.value = true
  try {
    const list = await appDeviceApi.listDevices()
    devices.value = list.filter((d) => d.online)
  } catch {
    /* 拦截器已提示 */
  } finally {
    loadingDevices.value = false
  }
}
loadDevices()

const selectedDevice = computed(() => devices.value.find((d) => d.udid === selectedUdid.value))

// ==================== 投屏（复用 composable） ====================
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)
const sc = useDeviceScreencast({
  udid: () => selectedUdid.value,
  canvasRef,
  stageRef,
  platform: () =>
    selectedDevice.value?.platform === 'harmony'
      ? 'harmony'
      : selectedDevice.value?.platform === 'ios'
        ? 'ios'
        : 'android',
})
// 平台能力（I4 起三平台等价）：投屏+触控+AI 单步/探索/手动录制全可用。
// 鸿蒙={t,x,y} 控制 tee + snapshot_display 语义化;iOS=同壳控制 tee(point 系)+
// WDA /screenshot 语义化——能力开关一律不看 platform。
// 安卓额外多一路（DT）:录制时 Agent 旁听 getevent,直接在手机上操作也入录,
// 提示文案按平台区分
const isAndroidDevice = computed(() => (selectedDevice.value?.platform ?? 'android') === 'android')

// 连接=可录制（控制模式）；观战（只读）不算——录制单步需要锁 owner 会话
const connected = computed(
  () =>
    sc.viewState.value === 'streaming' && !!sc.sessionId.value && sc.mode.value === 'control',
)

async function startSession() {
  if (!selectedUdid.value) {
    ElMessage.warning('请先选择一台在线设备')
    return
  }
  await sc.start()
}

async function stopSession() {
  if (manualRecording.value) await stopManualRecord()
  await endSessionRpc()
  sc.cleanup()
}

/** 结束 Agent 侧录制会话（dispose AndroidAgent）；投屏锁由 cleanup 释放 */
async function endSessionRpc() {
  if (selectedUdid.value && sc.sessionId.value) {
    try {
      await appTestApi.endSession(selectedUdid.value, sc.sessionId.value)
    } catch {
      /* best-effort */
    }
  }
}

// ==================== 指令流 + 步骤沉淀 ====================
interface StepCard {
  id: number
  instruction: string
  status: 'running' | 'ok' | 'error'
  summary?: string | null
  steps: RecoveredStep[]
  error?: string | null
  /** 执行进度直播行（大模型每轮规划原话+tokens/定位/动作），完成后保留 */
  logs: StepProgressEntry[]
}

const instruction = ref('')
const running = ref(false)
const cards = ref<StepCard[]>([])
/** 累积的 YAML flow 片段（每步回收拼接） */
const draftFlow = ref<string[]>([])
let seq = 0

const canRun = computed(
  () =>
    connected.value &&
    !running.value &&
    !manualRecording.value &&
    instruction.value.trim().length > 0,
)

/** 执行中进度直播：1.5s 增量拉 Agent 侧进度行喂给 running 卡片 */
const runningLogsEl = ref<HTMLDivElement | null>(null)
function setRunningLogsEl(el: unknown) {
  runningLogsEl.value = (el as HTMLDivElement) || null
}
let progressTimer: ReturnType<typeof setInterval> | null = null
let progressSeq = 0

function startProgressPolling(card: StepCard) {
  progressSeq = 0
  stopProgressPolling()
  progressTimer = setInterval(() => void pumpProgress(card), 1500)
}
function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}
async function pumpProgress(card: StepCard) {
  const p = await appTestApi.stepProgress(selectedUdid.value, sc.sessionId.value, progressSeq)
  if (!p || !p.entries?.length) return
  card.logs.push(...p.entries)
  progressSeq = p.seq
  await nextTick()
  runningLogsEl.value?.scrollTo({ top: runningLogsEl.value.scrollHeight })
}

async function runInstruction() {
  const text = instruction.value.trim()
  if (!text || !canRun.value) return
  // reactive 包一层：轮询回调持有的是这个引用，直接 push raw 对象的话
  // 属性修改不过 proxy、Vue 侦测不到——直播日志会憋到步骤结束才一次性冒出
  const card = reactive<StepCard>({ id: ++seq, instruction: text, status: 'running', steps: [], logs: [] })
  cards.value.push(card)
  running.value = true
  instruction.value = ''
  startProgressPolling(card)
  try {
    const res = await appTestApi.runStep(selectedUdid.value, {
      session_id: sc.sessionId.value,
      instruction: text,
    })
    stopProgressPolling()
    await pumpProgress(card) // 尾拉一次：补"步骤完成，回收 N 个动作"等收尾行
    if (res.ok) {
      card.status = res.data.status === 'ok' ? 'ok' : 'error'
      card.summary = res.data.summary
      card.steps = res.data.steps
      card.error = friendlyStepError(res.data.error, res.data.steps.length)
      // 失败也累积已抢救的动作（Agent 只回收真正执行成功的步骤）
      if (res.data.yaml_flow) draftFlow.value.push(res.data.yaml_flow)
    } else {
      card.status = 'error'
      card.error = res.message
      if (res.code === 409) {
        ElMessage.warning('设备控制权已变更，请重新开始会话')
      } else {
        ElMessage.error(res.message)
      }
    }
  } catch (e) {
    card.status = 'error'
    card.error = (e as Error)?.message || '执行失败'
  } finally {
    stopProgressPolling()
    running.value = false
  }
}

async function abortRunning() {
  if (!running.value) return
  try {
    await appTestApi.abortStep(selectedUdid.value, sc.sessionId.value)
    ElMessage.info('已发送取消')
  } catch {
    /* ignore */
  }
}

// ==================== 手动操作录制（触控 → VL 语义化） ====================
const manualRecording = ref(false)
const manualPending = ref(0)
let manualCard: StepCard | null = null
let manualTimer: ReturnType<typeof setInterval> | null = null
let manualSeq = 0

/** 开始手动录制：投屏触控被 Agent 旁观，每次点击经 VL 识别为语义步骤 */
async function startManualRecord() {
  if (!connected.value || manualRecording.value) return
  try {
    await appTestApi.manualStart(selectedUdid.value, sc.sessionId.value)
  } catch {
    return /* 拦截器已提示（如未配 VISION 模型） */
  }
  manualRecording.value = true
  manualSeq = 0
  manualPending.value = 0
  manualCard = reactive<StepCard>({
    id: ++seq,
    instruction: '手动录制（直接操作左侧手机屏幕）',
    status: 'running',
    steps: [],
    logs: [],
  })
  cards.value.push(manualCard)
  manualTimer = setInterval(() => void pumpManualSteps(), 1500)
}

async function pumpManualSteps() {
  if (!manualCard) return
  const p = await appTestApi.manualSteps(selectedUdid.value, sc.sessionId.value, manualSeq)
  if (!p) return
  manualPending.value = p.pending || 0
  if (p.entries?.length) {
    manualCard.steps.push(...p.entries.map((e) => e.step))
    manualSeq = p.seq
  }
}

/** 停止：等在途识别落定 → YAML 并入草稿 */
async function stopManualRecord() {
  if (!manualRecording.value) return
  if (manualTimer) {
    clearInterval(manualTimer)
    manualTimer = null
  }
  manualRecording.value = false
  const card = manualCard
  manualCard = null
  try {
    const res = await appTestApi.manualStop(selectedUdid.value, sc.sessionId.value)
    if (card && res) {
      card.steps = res.steps
      card.status = 'ok'
      card.summary = `手动录制完成，共 ${res.steps.length} 步`
      if (res.yaml_flow) draftFlow.value.push(res.yaml_flow)
    } else if (card) {
      card.status = 'error'
      card.error = '结束录制失败'
    }
  } catch {
    if (card) {
      card.status = 'error'
      card.error = '结束录制失败'
    }
  } finally {
    manualPending.value = 0
  }
}

/** 常见执行错误翻译成可操作提示（原文保留在后） */
function friendlyStepError(error: string | null | undefined, salvaged: number): string | null | undefined {
  if (!error) return error
  if (/Replanned \d+ times/i.test(error)) {
    const head = salvaged > 0 ? `指令较复杂，规划轮数超限（已执行的 ${salvaged} 个动作已回收进草稿）。` : '指令较复杂，规划轮数超限。'
    return `${head}建议拆成多条短指令重试。\n${error}`
  }
  return error
}

// ==================== 用例草稿（YAML）+ 保存 ====================
// 数动作行：排除 settle/显式 sleep（Swipe/AndroidHomeButton 等无 ai 前缀动作也要计入）
const stepCount = computed(() =>
  draftFlow.value.reduce(
    (n, blk) => n + blk.split('\n').filter((l) => /^\s*- (?!sleep:)/.test(l)).length,
    0,
  ),
)

const draftYaml = computed(() => {
  if (!draftFlow.value.length) return ''
  return ['tasks:', '  - name: 录制用例', '    flow:', ...draftFlow.value].join('\n')
})

function clearDraft() {
  if (manualRecording.value) {
    ElMessage.warning('手动录制进行中，请先停止录制再清空')
    return
  }
  draftFlow.value = []
  cards.value = []
  seq = 0
}

async function saveAsCase() {
  if (!draftFlow.value.length) {
    ElMessage.warning('还没有可保存的步骤，先录制几条指令')
    return
  }
  try {
    const { value: name } = await ElMessageBox.prompt('给这条用例起个名字', '保存为用例', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: `录制用例 ${new Date().toLocaleString()}`,
      inputValidator: (v) => (v && v.trim().length > 0 ? true : '请输入用例名称'),
    })
    const yaml = ['tasks:', `  - name: ${name.trim()}`, '    flow:', ...draftFlow.value].join('\n')
    await appTestApi.createScript(projectId.value, {
      name: name.trim(),
      yaml_content: yaml,
      platform:
        selectedDevice.value?.platform === 'harmony'
          ? 'harmony'
          : selectedDevice.value?.platform === 'ios'
            ? 'ios'
            : 'android',
      target_app: selectedDevice.value?.model || undefined,
      status: 'active',
    })
    ElMessage.success('用例已保存')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('保存失败')
  }
}

// ==================== 探索式生成（P3） ====================
type ExploreStatus = 'idle' | 'running' | 'succeeded' | 'failed' | 'canceled'

const goal = ref('')
const exploreName = ref('')
const appHint = ref('')
const optVerify = ref(true)
const optAsserts = ref(true)
const exploreStatus = ref<ExploreStatus>('idle')
const exploreTaskId = ref<number | null>(null)
const exploreStage = ref('')
const exploreProgress = ref(0)
const exploreLogs = ref<string[]>([])
const exploreResult = ref<ExploreResultSummary | null>(null)
const exploreError = ref('')
const logsRef = ref<HTMLDivElement | null>(null)
let stopStream: (() => void) | null = null

const exploring = computed(() => exploreStatus.value === 'running')
const canExplore = computed(
  () => !!selectedUdid.value && goal.value.trim().length >= 4 && !exploring.value,
)

/** 提交探索：已连投屏先干净断开（探索任务独占设备，否则会被网关踢出产生噪音） */
async function submitExplore() {
  if (!canExplore.value) return
  if (connected.value) {
    try {
      await ElMessageBox.confirm(
        '探索期间设备由任务独占，当前控制会话将转为观战直播（只读实时画面）。继续？',
        '开始探索',
        { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
    await stopSession()
  }
  exploreStatus.value = 'running'
  exploreStage.value = '提交任务…'
  exploreProgress.value = 0
  exploreLogs.value = []
  exploreResult.value = null
  exploreError.value = ''
  try {
    const { task_id } = await appTestApi.explore(projectId.value, {
      device_udid: selectedUdid.value,
      goal: goal.value.trim(),
      script_name: exploreName.value.trim() || undefined,
      app_hint: appHint.value.trim() || undefined,
      verify: optVerify.value,
      suggest_asserts: optAsserts.value,
    })
    exploreTaskId.value = task_id
    watchExplore(task_id)
    // 自动转观战直播（P4）：观战不占锁，与 exec 抢锁零冲突，全程实时画面
    void sc.startObserve()
  } catch (e) {
    exploreStatus.value = 'failed'
    exploreError.value = (e as Error)?.message || '提交失败'
  }
}

/** 订阅任务 SSE：stage/progress/log 驱动进度区，result/task_end 收尾 */
function watchExplore(taskId: number) {
  stopStream?.()
  stopStream = streamAiTask(projectId.value, taskId, {
    onEvent: (ev) => {
      const p = ev.payload || {}
      if (ev.type === 'stage') {
        exploreStage.value = String(p.name || '')
      } else if (ev.type === 'progress') {
        exploreProgress.value = Number(p.percent) || exploreProgress.value
      } else if (ev.type === 'log') {
        exploreLogs.value.push(String(p.message || ''))
      } else if (ev.type === 'result') {
        exploreResult.value = (p.summary as ExploreResultSummary) || null
      } else if (ev.type === 'error') {
        exploreError.value = String(p.message || '任务失败')
      } else if (ev.type === 'task_end') {
        const st = String(p.status || '')
        exploreStatus.value =
          st === 'succeeded' ? 'succeeded' : st === 'canceled' || st === 'cancelled' ? 'canceled' : 'failed'
        if (st === 'succeeded') exploreProgress.value = 100
        stopStream?.()
        stopStream = null
        // 兜底：result 事件缺失/迟到时，从任务详情读 result_summary
        if (st === 'succeeded' && !exploreResult.value && exploreTaskId.value) {
          aiTaskApi
            .detail(projectId.value, exploreTaskId.value)
            .then((res) => {
              const s = (res.data as any)?.result_summary
              if (!exploreResult.value && s) {
                exploreResult.value = (typeof s === 'string' ? JSON.parse(s) : s) as ExploreResultSummary
              }
            })
            .catch(() => {})
        }
      }
    },
    onError: () => {
      if (exploring.value) {
        exploreLogs.value.push('（事件流断开，任务仍在后台执行，可到「AI 任务中心」查看进度）')
      }
    },
  })
}

async function cancelExplore() {
  if (!exploreTaskId.value) return
  try {
    await aiTaskApi.cancel(projectId.value, exploreTaskId.value)
    ElMessage.info('已发送取消（等待设备侧停止）')
  } catch {
    /* 拦截器已提示 */
  }
}

function resetExplore() {
  exploreStatus.value = 'idle'
  exploreTaskId.value = null
  exploreStage.value = ''
  exploreProgress.value = 0
  exploreLogs.value = []
  exploreResult.value = null
  exploreError.value = ''
}

// 日志自动滚底
watch(
  () => exploreLogs.value.length,
  () => nextTick(() => logsRef.value?.scrollTo({ top: logsRef.value.scrollHeight })),
)

const VERIFY_META: Record<string, { label: string; type: 'success' | 'danger' | 'info' | 'warning' }> = {
  success: { label: '验证通过', type: 'success' },
  failed: { label: '验证失败（草稿）', type: 'danger' },
  skipped: { label: '未验证（草稿）', type: 'info' },
  cancelled: { label: '验证被取消', type: 'warning' },
}

function goCases() {
  router.push({ name: 'AppCases', params: { id: projectId.value } })
}
function goExecutions() {
  router.push({ name: 'AppExecutions', params: { id: projectId.value } })
}

onBeforeUnmount(() => {
  stopStream?.()
  stopProgressPolling()
  if (manualTimer) clearInterval(manualTimer)
  if (manualRecording.value) void appTestApi.manualStop(selectedUdid.value, sc.sessionId.value)
  void endSessionRpc()
  // sc 自带 onBeforeUnmount cleanup（释放锁）
})

/** 进度行 kind → 图标/配色（设计系统 i-solar-*，不用 emoji） */
const LOG_META: Record<string, { icon: string }> = {
  plan: { icon: 'i-solar-lightbulb-bolt-bold' },
  locate: { icon: 'i-solar-magnifer-linear' },
  action: { icon: 'i-solar-cursor-bold' },
  info: { icon: 'i-solar-info-circle-linear' },
  error: { icon: 'i-solar-danger-circle-bold' },
}

const actionLabel: Record<string, string> = {
  aiTap: '点击',
  aiInput: '输入',
  aiDoubleClick: '双击',
  aiScroll: '滚动',
  aiKeyboardPress: '按键',
  aiLongPress: '长按',
  // 无定位动作（回收完整度增补）
  AndroidHomeButton: '按 Home 键',
  AndroidBackButton: '按返回键',
  AndroidRecentAppsButton: '最近任务键',
  Swipe: '滑动',
  PullGesture: '拉动',
  KeyboardPress: '按键',
  sleep: '等待',
  launch: '启动应用',
}

/** 回收步骤 chip 文本（locate/value/params 均可缺省） */
function stepChipText(s: RecoveredStep): string {
  let text = actionLabel[s.action] || s.action
  if (s.locate) text += `「${s.locate}」`
  if (s.value) text += `：${s.value}`
  const p = s.params || {}
  if (p.direction) text += `（${p.direction}${p.distance ? `，${p.distance}px` : ''}）`
  else if (p.timeMs) text += ` ${p.timeMs}ms`
  else if (p.keyName) text += `：${p.keyName}`
  return text
}
</script>

<template>
  <div class="console-page">
    <AppPageHeader
      title="智能操作台"
      description="输入自然语言操作 App，实时执行并沉淀为可回放用例"
      icon="i-solar-cpu-bolt-bold-duotone"
    >
      <template #actions>
        <el-radio-group v-model="mode" :disabled="running || exploring" class="mode-switch">
          <el-radio-button value="record">逐步录制</el-radio-button>
          <el-radio-button value="explore">探索生成</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="selectedUdid"
          placeholder="选择在线设备"
          :loading="loadingDevices"
          :disabled="connected || exploring"
          class="dev-select"
          filterable
          @visible-change="(open: boolean) => open && loadDevices()"
        >
          <el-option
            v-for="d in devices"
            :key="d.udid"
            :label="`${d.model || d.serial}（${d.udid}）`"
            :value="d.udid"
          />
        </el-select>
        <template v-if="mode === 'record'">
          <el-button v-if="!connected" type="primary" :disabled="!selectedUdid" @click="startSession">
            <i class="i-solar-play-bold btn-icon" />开始
          </el-button>
          <el-button v-else @click="stopSession">
            <i class="i-solar-stop-bold btn-icon" />结束会话
          </el-button>
        </template>
      </template>
    </AppPageHeader>

    <div class="console-body">
      <!-- 左：投屏舞台 -->
      <div class="stage-col">
        <div class="phone-shell">
          <span class="phone-key phone-key--power" />
          <span class="phone-key phone-key--volume" />
          <div class="phone-notch"><span class="notch-cam" /><span class="notch-speaker" /></div>
          <div ref="stageRef" class="stage" :style="{ aspectRatio: sc.screenAspect.value }">
            <canvas
              ref="canvasRef"
              class="screen-canvas"
              :class="{ 'is-live': sc.viewState.value === 'streaming' }"
              @pointerdown="sc.onPointerDown"
              @pointermove="sc.onPointerMove"
              @pointerup="sc.onPointerUp"
              @pointercancel="sc.onPointerUp"
              @contextmenu.prevent
            />
            <div v-if="sc.viewState.value !== 'streaming'" class="stage-overlay">
              <!-- 探索模式：设备由任务独占驱动，无实时画面（围观语义 P4），过程看右侧进度 + 事后报告 -->
              <template v-if="mode === 'explore'">
                <i
                  :class="[
                    exploring ? 'i-solar-radar-2-bold-duotone spinning'
                    : exploreStatus === 'succeeded' ? 'i-solar-check-circle-bold'
                    : exploreStatus === 'failed' ? 'i-solar-close-circle-bold'
                    : 'i-solar-compass-big-bold-duotone',
                    'overlay-icon',
                    exploreStatus === 'failed' ? 'danger' : '',
                  ]"
                />
                <div class="overlay-title">
                  {{ exploring ? (exploreStage || '探索执行中…')
                    : exploreStatus === 'succeeded' ? '探索完成'
                    : exploreStatus === 'failed' ? '探索失败'
                    : '探索生成模式' }}
                </div>
                <div class="overlay-sub">
                  {{ exploring ? '任务已独占设备自动执行，进度见右侧；可开观战直播实时看真机画面'
                    : '输入一句目标，AI 将在真机上自动探索并沉淀为可回放用例；过程可在完成后的报告中逐步回看' }}
                </div>
                <el-button
                  v-if="exploring"
                  type="primary"
                  size="small"
                  @click="sc.startObserve"
                >
                  <i class="i-solar-eye-bold btn-icon-sm" />观战直播（只读）
                </el-button>
              </template>
              <template v-else-if="sc.viewState.value === 'init'">
                <i class="i-solar-smartphone-2-bold-duotone overlay-icon" />
                <div class="overlay-title">选择设备后点「开始」</div>
                <div class="overlay-sub">连接后即可用自然语言操作</div>
              </template>
              <template v-else-if="sc.viewState.value === 'conflict'">
                <i class="i-solar-lock-keyhole-bold overlay-icon warn" />
                <div class="overlay-title">设备已被占用</div>
                <div class="overlay-sub">
                  当前占用者：{{ sc.conflict.owner_name || '用户 #' + sc.conflict.owner_user_id }}
                </div>
                <el-button type="primary" size="small" @click="sc.requestTakeover">重试 / 接管</el-button>
              </template>
              <template v-else-if="sc.viewState.value === 'error' || sc.viewState.value === 'expired'">
                <i class="i-solar-danger-triangle-bold overlay-icon danger" />
                <div class="overlay-title">{{ sc.stateLabel.value }}</div>
                <div class="overlay-sub">{{ sc.errorMsg.value }}</div>
                <el-button type="primary" size="small" @click="sc.manualReconnect">重试</el-button>
              </template>
              <template v-else>
                <i class="i-solar-refresh-bold overlay-icon spinning" />
                <div class="overlay-title">{{ sc.stateLabel.value }}</div>
              </template>
            </div>
          </div>
          <div class="phone-home" />
        </div>
      </div>

      <!-- 右（探索生成 P3）：目标输入 + 任务进度 + 结果 -->
      <div v-if="mode === 'explore'" class="panel-col">
        <div class="cmd-box">
          <el-input
            v-model="goal"
            type="textarea"
            :rows="3"
            :disabled="exploring"
            resize="none"
            placeholder="一句话描述探索目标，如「打开设置，进入显示设置，开启深色模式」"
          />
          <div class="explore-opts">
            <el-input
              v-model="exploreName"
              :disabled="exploring"
              placeholder="用例名（可选，默认按目标生成）"
              clearable
            />
            <el-input
              v-model="appHint"
              :disabled="exploring"
              placeholder="应用上下文提示（可选，如「权限弹窗一律允许」）"
              clearable
            />
          </div>
          <div class="cmd-actions">
            <div class="opt-switches">
              <el-checkbox v-model="optVerify" :disabled="exploring">回放验证</el-checkbox>
              <el-checkbox v-model="optAsserts" :disabled="exploring">断言建议</el-checkbox>
            </div>
            <div class="cmd-btns">
              <el-button v-if="exploring" size="small" @click="cancelExplore">
                <i class="i-solar-stop-circle-bold btn-icon" />取消任务
              </el-button>
              <el-button
                v-else-if="exploreStatus !== 'idle'"
                size="small"
                @click="resetExplore"
              >
                <i class="i-solar-restart-bold btn-icon" />再来一次
              </el-button>
              <el-button type="primary" :loading="exploring" :disabled="!canExplore" @click="submitExplore">
                <i class="i-solar-compass-big-bold btn-icon" />开始探索
              </el-button>
            </div>
          </div>
        </div>

        <!-- 任务进度 + 日志 -->
        <div class="stream">
          <div v-if="exploreStatus === 'idle'" class="stream-empty">
            <i class="i-solar-compass-big-linear" />
            <span>选择设备、输入一句目标，AI 会自动探索 App 并沉淀为可回放用例。</span>
            <span class="empty-sub">生成后自动回放验证，并由文本模型追加断言建议（可关）。</span>
          </div>
          <template v-else>
            <div class="explore-head">
              <el-progress
                :percentage="exploreProgress"
                :status="exploreStatus === 'failed' ? 'exception' : exploreStatus === 'succeeded' ? 'success' : undefined"
                :stroke-width="8"
              />
              <div class="explore-stage">
                <i
                  :class="exploring ? 'i-solar-refresh-bold spinning' : exploreStatus === 'succeeded' ? 'i-solar-check-circle-bold ok' : 'i-solar-info-circle-bold'"
                />
                <span>{{ exploreStage || '—' }}</span>
              </div>
            </div>
            <div ref="logsRef" class="explore-logs">
              <div v-for="(l, i) in exploreLogs" :key="i" class="explore-log">{{ l }}</div>
            </div>

            <!-- 结果卡 -->
            <div
              v-if="!exploring"
              class="result-card"
              :class="exploreStatus === 'succeeded' ? 'is-ok' : exploreStatus === 'canceled' ? 'is-cancel' : 'is-fail'"
            >
              <template v-if="exploreStatus === 'succeeded' && exploreResult">
                <div class="rc-head">
                  <i class="i-solar-check-circle-bold rc-icon" />
                  <span class="rc-title">
                    用例 #{{ exploreResult.script_id }} 已生成 · {{ exploreResult.steps_count }} 步
                  </span>
                  <el-tag
                    v-if="exploreResult.verify_status"
                    :type="VERIFY_META[exploreResult.verify_status]?.type || 'info'"
                    size="small"
                    effect="light"
                  >
                    {{ VERIFY_META[exploreResult.verify_status]?.label || exploreResult.verify_status }}
                  </el-tag>
                </div>
                <div v-if="exploreResult.asserts?.length" class="rc-asserts">
                  <div class="rc-asserts-title">AI 建议断言（已作为注释写入用例，确认后启用）：</div>
                  <div v-for="(a, i) in exploreResult.asserts" :key="i" class="rc-assert">{{ a }}</div>
                </div>
                <div v-if="exploreResult.error" class="rc-error">{{ exploreResult.error }}</div>
                <div class="rc-btns">
                  <el-button size="small" type="primary" @click="goCases">
                    <i class="i-solar-clipboard-list-bold btn-icon" />查看用例
                  </el-button>
                  <el-button size="small" @click="goExecutions">
                    <i class="i-solar-document-text-bold btn-icon" />查看报告
                  </el-button>
                </div>
              </template>
              <template v-else>
                <div class="rc-head">
                  <i
                    :class="exploreStatus === 'canceled' ? 'i-solar-minus-circle-bold' : 'i-solar-close-circle-bold'"
                    class="rc-icon"
                  />
                  <span class="rc-title">{{ exploreStatus === 'canceled' ? '任务已取消' : '探索失败' }}</span>
                </div>
                <div v-if="exploreError" class="rc-error">{{ exploreError }}</div>
                <div v-if="exploreStatus !== 'canceled' && exploreResult?.script_id" class="rc-btns">
                  <el-button size="small" @click="goCases">查看已生成的草稿用例</el-button>
                </div>
              </template>
            </div>
          </template>
        </div>
      </div>

      <!-- 右（逐步录制 P2）：指令流 + 沉淀 -->
      <div v-else class="panel-col">
        <!-- 指令输入 -->
        <div class="cmd-box">
          <el-input
            v-model="instruction"
            type="textarea"
            :rows="2"
            :disabled="!connected || running || manualRecording"
            resize="none"
            :placeholder="manualRecording
              ? (isAndroidDevice
                  ? '手动录制中：操作左侧投屏或直接在手机上点按，每步自动识别为语义步骤'
                  : '手动录制中：直接操作左侧手机屏幕，每步点击将自动识别为语义步骤')
              : '用一句话描述要做的操作，如「点击搜索框，输入蓝牙，点第一个结果」'"
            @keydown.enter.exact.prevent="runInstruction"
          />
          <div class="cmd-actions">
            <span class="cmd-hint">
              <template v-if="manualRecording">
                <span class="rec-dot" />录制中
                {{ manualPending > 0
                  ? `· 识别中 ${manualPending} 步…`
                  : isAndroidDevice ? '· 点/滑投屏或直接操作手机' : '· 直接点/滑左侧屏幕' }}
              </template>
              <template v-else>
                {{ connected ? 'Enter 执行 · Shift+Enter 换行' : '连接设备后可输入' }}
              </template>
            </span>
            <div class="cmd-btns">
              <!-- key 防 v-if/v-else 复用同一元素（程序化 click 后 patch 期串 handler） -->
              <el-button
                v-if="!manualRecording"
                key="manual-rec-start"
                :disabled="!connected || running"
                @click="startManualRecord"
              >
                <i class="i-solar-record-circle-bold btn-icon rec-icon" />手动录制
              </el-button>
              <el-button
                v-else-if="manualRecording"
                key="manual-rec-stop"
                type="danger"
                plain
                @click="stopManualRecord"
              >
                <i class="i-solar-stop-bold btn-icon" />停止录制
              </el-button>
              <el-button v-if="running" @click="abortRunning">
                <i class="i-solar-stop-circle-bold btn-icon" />取消
              </el-button>
              <el-button type="primary" :loading="running" :disabled="!canRun" @click="runInstruction">
                <i class="i-solar-play-circle-bold btn-icon" />执行
              </el-button>
            </div>
          </div>
        </div>

        <!-- 步骤流 -->
        <div class="stream">
          <div v-if="!cards.length" class="stream-empty">
            <i class="i-solar-chat-round-line-linear" />
            <span>还没有指令。连接设备后，输入一句自然语言开始。</span>
          </div>
          <div v-for="c in cards" :key="c.id" class="step-card" :class="`is-${c.status}`">
            <div class="sc-head">
              <i
                :class="[
                  c.status === 'running' ? 'i-solar-refresh-bold spinning'
                  : c.status === 'ok' ? 'i-solar-check-circle-bold'
                  : 'i-solar-close-circle-bold',
                  'sc-icon',
                ]"
              />
              <span class="sc-instr">{{ c.instruction }}</span>
            </div>
            <!-- 执行进度直播：大模型每轮规划原话（含 tokens/耗时）+ 定位 + 动作 -->
            <div
              v-if="c.logs.length"
              :ref="c.status === 'running' ? setRunningLogsEl : undefined"
              class="sc-logs"
            >
              <div v-for="l in c.logs" :key="l.seq" class="sc-log" :class="`is-${l.kind}`">
                <i :class="LOG_META[l.kind]?.icon || LOG_META.info.icon" class="sc-log-icon" />
                <span>{{ l.text }}</span>
              </div>
            </div>
            <div v-if="c.summary" class="sc-summary">
              <i class="i-solar-chat-square-like-linear sc-summary-icon" />{{ c.summary }}
            </div>
            <div v-if="c.steps.length" class="sc-steps">
              <span v-for="(s, i) in c.steps" :key="i" class="sc-step">{{ stepChipText(s) }}</span>
            </div>
            <div v-if="c.error" class="sc-error">{{ c.error }}</div>
          </div>
        </div>

        <!-- 用例草稿 -->
        <div class="draft-bar">
          <div class="draft-info">
            <i class="i-solar-clipboard-list-bold" />
            <span>已沉淀 <b>{{ stepCount }}</b> 个动作</span>
          </div>
          <div class="draft-btns">
            <el-button size="small" :disabled="!draftFlow.length" @click="clearDraft">清空</el-button>
            <el-button size="small" type="primary" :disabled="!draftFlow.length" @click="saveAsCase">
              <i class="i-solar-diskette-bold btn-icon" />保存为用例
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.console-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
}
.btn-icon {
  margin-right: 4px;
}
.dev-select {
  width: 280px;
}

.console-body {
  display: flex;
  gap: 18px;
  flex: 1;
  min-height: 0;
}

/* 左：投屏（沿用设备控制弹框的手机外壳风格） */
.stage-col {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}
.phone-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--gray-900);
  border-radius: 34px;
  padding: 20px 10px 10px;
  box-shadow: var(--shadow-xl);
}
.phone-key {
  position: absolute;
  right: -3px;
  width: 3px;
  border-radius: 2px;
  background: var(--gray-700);
  &--power { top: 120px; height: 52px; }
  &--volume { top: 188px; height: 80px; }
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
  .notch-cam { width: 8px; height: 8px; border-radius: 50%; background: var(--gray-700); }
  .notch-speaker { width: 46px; height: 5px; border-radius: 3px; background: var(--gray-700); }
}
.phone-home {
  width: 70px;
  height: 4px;
  border-radius: 2px;
  background: var(--gray-600);
  margin: 7px auto 0;
  flex-shrink: 0;
}
.stage {
  position: relative;
  flex: 0 0 auto;
  height: clamp(380px, 62vh, 560px);
  background: #0b0f14;
  border-radius: 24px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.screen-canvas {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: 100%;
  object-fit: contain;
  touch-action: none;
  display: block;
  cursor: pointer;
  &:not(.is-live) { opacity: 0; }
}
.stage-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #e5e7eb;
  background: rgba(11, 15, 20, 0.86);
  text-align: center;
  padding: 24px;
}
.overlay-icon {
  font-size: 48px;
  color: var(--brand-400, #4ade80);
  &.warn { color: #fbbf24; }
  &.danger { color: #f87171; }
  &.spinning { animation: spin 1s linear infinite; }
}
@keyframes spin { to { transform: rotate(360deg); } }
.overlay-title { font-size: 16px; font-weight: 600; }
.overlay-sub { font-size: 12px; color: #9ca3af; max-width: 300px; }

/* 右：指令流 */
.panel-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cmd-box {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 12px;
  box-shadow: var(--shadow-card);
}
.cmd-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.cmd-hint {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.cmd-btns {
  display: flex;
  gap: 8px;
}

.stream {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 2px;
}
.stream-empty {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-placeholder);
  font-size: var(--font-size-sm);
  i { font-size: 32px; }
}
.step-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-left-width: 3px;
  border-radius: 10px;
  padding: 10px 12px;
  &.is-running { border-left-color: var(--color-warning-500); }
  &.is-ok { border-left-color: var(--brand-500); }
  &.is-error { border-left-color: var(--color-danger-500); }
}
.sc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  .sc-icon { font-size: 16px; flex-shrink: 0; }
  .is-running & .sc-icon { color: var(--color-warning-500); }
  .is-ok & .sc-icon { color: var(--brand-500); }
  .is-error & .sc-icon { color: var(--color-danger-500); }
}
.sc-instr {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.sc-summary {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: 1.5;
  .sc-summary-icon {
    margin-right: 4px;
    vertical-align: -2px;
    color: var(--brand-500);
  }
}

/* 执行进度直播（大模型规划原话/定位/动作） */
.sc-logs {
  margin-top: 8px;
  max-height: 190px;
  overflow-y: auto;
  background: var(--bg-page, var(--gray-50));
  border: 1px solid var(--border-lighter, var(--border-light));
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sc-log {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-secondary);
  word-break: break-all;
  &.is-plan {
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
  }
  &.is-error { color: var(--color-danger-600); }
  &.is-locate, &.is-info { color: var(--text-placeholder); }
}
.sc-log-icon {
  flex-shrink: 0;
  font-size: 12px;
  margin-top: 3px;
  .is-plan & { color: var(--color-warning-500); }
  .is-action & { color: var(--brand-500); }
  .is-error & { color: var(--color-danger-500); }
}
.sc-steps {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sc-step {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
}
.sc-error {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-danger-600);
  word-break: break-all;
}
.spinning { animation: spin 1s linear infinite; }

.draft-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
}
.draft-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  b { color: var(--brand-600); margin: 0 2px; }
}
.draft-btns {
  display: flex;
  gap: 8px;
}

/* 手动录制状态点 */
.rec-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger-500);
  margin-right: 5px;
  animation: rec-blink 1.2s ease-in-out infinite;
}
@keyframes rec-blink {
  50% { opacity: 0.25; }
}
.rec-icon { color: var(--color-danger-500); }

/* ==================== 探索生成（P3） ==================== */
.mode-switch {
  margin-right: 4px;
}
.explore-opts {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  > * { flex: 1; min-width: 0; }
}
.opt-switches {
  display: flex;
  align-items: center;
  gap: 12px;
}
.empty-sub {
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
}
.explore-head {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 12px 14px;
}
.explore-stage {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--text-regular);
  i { font-size: 15px; color: var(--color-warning-500); }
  i.ok { color: var(--brand-500); }
}
.explore-logs {
  flex: 1;
  min-height: 80px;
  overflow-y: auto;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.explore-log {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: 1.6;
  word-break: break-all;
  white-space: pre-wrap;
}
.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-left-width: 3px;
  border-radius: 10px;
  padding: 12px 14px;
  &.is-ok { border-left-color: var(--brand-500); }
  &.is-fail { border-left-color: var(--color-danger-500); }
  &.is-cancel { border-left-color: var(--color-warning-500); }
}
.rc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  .rc-icon { font-size: 17px; flex-shrink: 0; }
  .is-ok & .rc-icon { color: var(--brand-500); }
  .is-fail & .rc-icon { color: var(--color-danger-500); }
  .is-cancel & .rc-icon { color: var(--color-warning-500); }
}
.rc-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.rc-asserts {
  margin-top: 8px;
}
.rc-asserts-title {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.rc-assert {
  font-size: var(--font-size-xs);
  color: var(--brand-700);
  background: var(--brand-50);
  border-radius: 6px;
  padding: 4px 8px;
  margin-top: 4px;
  line-height: 1.5;
}
.rc-error {
  margin-top: 8px;
  font-size: var(--font-size-xs);
  color: var(--color-danger-600);
  word-break: break-all;
}
.rc-btns {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}
</style>
