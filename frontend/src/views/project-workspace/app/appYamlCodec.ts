/**
 * App 用例「可视化步骤 ↔ Midscene YAML」双向 codec。
 *
 * 唯一真相源是 Agent 侧 `app-agent/src/recover.ts` 的 stepsToYamlFlow —— 那是录制
 * 步骤落成 YAML、回放时真机实证跑通的序列化。本文件严格镜像它的动作→flow 映射,
 * 保证：① 块编辑产出的 YAML 与录制产出的同构、Midscene player 都吃；② 录制/手写的
 * YAML 能被解析回块。
 *
 * 设计铁律（与 recover.ts 对齐）：
 * - aiInput 的标量是「定位描述」,输入文本走同级 `value:`（recover.ts line 231-232）。
 * - 系统键 Android*Button 出 `{}`；Swipe/PullGesture/KeyboardPress 出参数 map；
 *   sleep 出 `sleep: 毫秒`；launch 标量是包名/URI；其余定位类标量是定位描述。
 * - 块是 WYSIWYG：**不**像 recover.ts 那样在每步后自动补 settle sleep —— 所见即所存,
 *   避免解析回块时凭空多出一堆 sleep。录制产出的 settle sleep 会如实显示为 sleep 块。
 * - 解析遇到编辑器不认识的构造（aiAssert/aiWaitFor/额外 key/未知动词…）→ 整体判不可
 *   可视化,返回 ok:false 让上层留在源码模式,**绝不静默丢字段**。
 */
// js-yaml v5 仅具名导出（无 default export），必须解构导入，否则运行时拿到 undefined
import { load as yamlLoad, dump as yamlDump } from 'js-yaml'

// ==================== 动作全集（镜像 recover.ts RecoveredAction） ====================

export type AppActionKind =
  | 'aiTap'
  | 'aiDoubleClick'
  | 'aiLongPress'
  | 'aiScroll'
  | 'aiKeyboardPress'
  | 'aiInput'
  | 'Swipe'
  | 'PullGesture'
  | 'KeyboardPress'
  | 'AndroidHomeButton'
  | 'AndroidBackButton'
  | 'AndroidRecentAppsButton'
  | 'IOSHomeButton'
  | 'sleep'
  | 'launch'

/** 单步字段表单形态（驱动块编辑器逐步渲染） */
export type StepForm = 'locate' | 'input' | 'swipe' | 'keyname' | 'sleep' | 'launch' | 'none'

export type AppPlatform = 'android' | 'harmony' | 'ios'

export interface ActionMeta {
  action: AppActionKind
  label: string
  group: string
  form: StepForm
  /** 该动作的一句话说明（块编辑器提示用） */
  hint: string
  /** 支持平台白名单；缺省=三平台通用。调色板按脚本 platform 过滤 */
  platforms?: AppPlatform[]
}

/** 动作元数据：调色板分组 + 逐步字段渲染的单一数据源（platforms 依据 @midscene 1.10.2 各端 actionSpace） */
export const ACTION_METAS: ActionMeta[] = [
  { action: 'aiTap', label: '点击', group: '点击', form: 'locate', hint: '点击目标元素' },
  { action: 'aiDoubleClick', label: '双击', group: '点击', form: 'locate', hint: '双击目标元素' },
  { action: 'aiLongPress', label: '长按', group: '点击', form: 'locate', hint: '长按目标元素' },
  { action: 'aiInput', label: '输入', group: '输入', form: 'input', hint: '在目标输入框填入文本' },
  { action: 'aiKeyboardPress', label: 'AI 按键', group: '输入', form: 'locate', hint: '聚焦目标后按键' },
  { action: 'KeyboardPress', label: '按键', group: '输入', form: 'keyname', hint: '按硬件/软键盘按键（如 Enter）' },
  { action: 'aiScroll', label: '滚动', group: '滚动 / 手势', form: 'locate', hint: '滚动到目标区域' },
  { action: 'Swipe', label: '滑动', group: '滚动 / 手势', form: 'swipe', hint: '从屏幕中心按方向滑动' },
  { action: 'PullGesture', label: '拉动', group: '滚动 / 手势', form: 'swipe', hint: '按方向拉动（下拉刷新等）', platforms: ['android'] },
  { action: 'AndroidHomeButton', label: 'Home 键', group: '系统键', form: 'none', hint: '回到桌面', platforms: ['android'] },
  { action: 'AndroidBackButton', label: '返回键', group: '系统键', form: 'none', hint: '系统返回', platforms: ['android'] },
  { action: 'AndroidRecentAppsButton', label: '多任务键', group: '系统键', form: 'none', hint: '最近任务', platforms: ['android'] },
  { action: 'IOSHomeButton', label: 'Home 键', group: '系统键', form: 'none', hint: '回到主屏幕', platforms: ['ios'] },
  { action: 'sleep', label: '等待', group: '控制', form: 'sleep', hint: '固定等待若干毫秒' },
  { action: 'launch', label: '启动应用', group: '控制', form: 'launch', hint: '按包名/URI 启动应用' },
]

const META_BY_ACTION = new Map(ACTION_METAS.map((m) => [m.action, m]))
export const actionMeta = (a: AppActionKind): ActionMeta =>
  META_BY_ACTION.get(a) ?? ACTION_METAS[0]

/** 按平台过滤动作元数据（调色板/下拉用）；platform 缺省不过滤（源码模式仍是逃生口） */
export function metasForPlatform(platform?: string): ActionMeta[] {
  if (platform !== 'android' && platform !== 'harmony' && platform !== 'ios') return ACTION_METAS
  return ACTION_METAS.filter((m) => !m.platforms || m.platforms.includes(platform))
}

const ALL_ACTIONS = new Set<string>(ACTION_METAS.map((m) => m.action))
const LOCATE_ACTIONS = new Set<AppActionKind>([
  'aiTap',
  'aiDoubleClick',
  'aiLongPress',
  'aiScroll',
  'aiKeyboardPress',
])
const SYSTEM_KEYS = new Set<AppActionKind>([
  'AndroidHomeButton',
  'AndroidBackButton',
  'AndroidRecentAppsButton',
  'IOSHomeButton',
])
const PARAM_ACTIONS = new Set<AppActionKind>(['Swipe', 'PullGesture', 'KeyboardPress'])

// ==================== 内部模型 ====================

export interface AppStep {
  /** draggable 稳定 key（不进 YAML） */
  _uid: number
  action: AppActionKind
  /** 定位类动作 / aiInput 的定位描述（无关动作留空串，序列化时忽略） */
  locate: string
  /** aiInput 的输入值 / launch 的包名或 URI（无关动作留空串） */
  value: string
  /** Swipe/PullGesture/KeyboardPress/sleep 的参数（无关动作留 {}，序列化时忽略） */
  params: Record<string, string | number>
  // 三个字段非可选（默认空）——让块编辑器 v-model 绑定不必处理 undefined
}

export interface AppTask {
  _uid: number
  name: string
  flow: AppStep[]
}

let _uid = 1
export const nextUid = (): number => _uid++

// ==================== 新建步骤（调色板默认值） ====================

/** 空步骤骨架（三字段默认空，便于块编辑器 v-model 绑定） */
function blank(action: AppActionKind, over: Partial<AppStep> = {}): AppStep {
  return { _uid: nextUid(), action, locate: '', value: '', params: {}, ...over }
}

/** 按动作造一个带合理默认值的新步骤（调色板用） */
export function makeStep(action: AppActionKind): AppStep {
  switch (actionMeta(action).form) {
    case 'swipe':
      return blank(action, { params: { direction: 'up', distance: 600 } })
    case 'keyname':
      return blank(action, { params: { keyName: 'Enter' } })
    case 'sleep':
      return blank(action, { params: { timeMs: 800 } })
    default:
      return blank(action)
  }
}

export const makeTask = (name = '主流程'): AppTask => ({ _uid: nextUid(), name, flow: [] })

// ==================== 步骤 → YAML（镜像 recover.ts stepsToYamlFlow 的映射，无 settle） ====================

/** 单步 → Midscene flow 条目对象（js-yaml.dump 会转成合法 YAML，含引号转义） */
function stepToFlowItem(s: AppStep): Record<string, unknown> {
  if (s.action === 'sleep') return { sleep: numOr(s.params?.timeMs, 1000) }
  if (s.action === 'aiInput') return { aiInput: s.locate ?? '', value: s.value ?? '' }
  if (s.action === 'launch') return { launch: s.value ?? '' }
  if (SYSTEM_KEYS.has(s.action)) return { [s.action]: {} }
  if (PARAM_ACTIONS.has(s.action)) return { [s.action]: { ...(s.params ?? {}) } }
  // 定位类：标量即定位描述
  return { [s.action]: s.locate ?? '' }
}

function numOr(v: unknown, fallback: number): number {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : fallback
}

/** 多任务 → 完整 Midscene YAML 文档字符串 */
export function tasksToYaml(tasks: AppTask[]): string {
  const doc = {
    tasks: tasks.map((t) => ({
      name: t.name?.trim() || '任务',
      flow: t.flow.map(stepToFlowItem),
    })),
  }
  // lineWidth:-1 不折行（定位描述可能很长）；noRefs 不生成锚点引用
  return yamlDump(doc, { lineWidth: -1, noRefs: true })
}

// ==================== YAML → 步骤（不可表达即整体判不支持） ====================

export type ParseResult =
  | { ok: true; tasks: AppTask[] }
  | { ok: false; reason: string }

/** 解析整份 YAML 为可视化任务；任一步骤/结构不可表达 → ok:false（上层留源码模式） */
export function parseYamlToTasks(text: string): ParseResult {
  if (!text.trim()) return { ok: true, tasks: [] }
  let doc: unknown
  try {
    doc = yamlLoad(text)
  } catch (e) {
    return { ok: false, reason: `YAML 语法错误：${(e as Error).message}` }
  }
  if (!isObject(doc) || !Array.isArray((doc as Record<string, unknown>).tasks)) {
    return { ok: false, reason: '顶层不是 tasks 列表结构' }
  }
  const rawTasks = (doc as Record<string, unknown>).tasks as unknown[]
  const tasks: AppTask[] = []
  for (const rawTask of rawTasks) {
    if (!isObject(rawTask)) return { ok: false, reason: '任务项结构非法' }
    const rt = rawTask as Record<string, unknown>
    if (!Array.isArray(rt.flow)) return { ok: false, reason: '任务缺少 flow 步骤列表' }
    const flow: AppStep[] = []
    for (const item of rt.flow as unknown[]) {
      const step = flowItemToStep(item)
      if (!step) {
        return {
          ok: false,
          reason: `含可视化编辑器暂不支持的步骤：${briefly(item)}`,
        }
      }
      flow.push(step)
    }
    tasks.push({ _uid: nextUid(), name: typeof rt.name === 'string' ? rt.name : '任务', flow })
  }
  return { ok: true, tasks }
}

/** 单条 flow 条目 → 步骤；不可表达返回 null */
function flowItemToStep(item: unknown): AppStep | null {
  if (!isObject(item)) return null
  const rec = item as Record<string, unknown>
  const keys = Object.keys(rec)
  const actionKey = keys.find((k) => ALL_ACTIONS.has(k)) as AppActionKind | undefined
  if (!actionKey) return null
  const val = rec[actionKey]

  // aiInput 是唯一允许同级 value 的动作
  if (actionKey === 'aiInput') {
    if (keys.some((k) => k !== 'aiInput' && k !== 'value')) return null
    return blank('aiInput', { locate: scalarStr(val), value: scalarStr(rec.value) })
  }
  // 其余动作只允许单键（额外 key = 可能是不认识的修饰,不静默吞）
  if (keys.length !== 1) return null

  if (actionKey === 'sleep') {
    const ms = typeof val === 'number' ? val : Number(val)
    if (!Number.isFinite(ms)) return null
    return blank('sleep', { params: { timeMs: ms } })
  }
  if (actionKey === 'launch') return blank('launch', { value: scalarStr(val) })
  if (SYSTEM_KEYS.has(actionKey)) {
    // {} / null 均视为系统键；非空对象参数不表达 → 不支持
    if (val != null && !(isObject(val) && Object.keys(val as object).length === 0)) return null
    return blank(actionKey)
  }
  if (PARAM_ACTIONS.has(actionKey)) {
    if (!isObject(val)) return null
    const params: Record<string, string | number> = {}
    for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
      if (typeof v === 'number' || typeof v === 'string') params[k] = v
      else return null
    }
    return blank(actionKey, { params })
  }
  if (LOCATE_ACTIONS.has(actionKey)) {
    if (typeof val !== 'string') return null
    return blank(actionKey, { locate: val })
  }
  return null
}

// ==================== 小工具 ====================

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** 标量→字符串（数字/布尔也容忍,统一成串给输入框） */
function scalarStr(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  return ''
}

/** 不支持步骤的简短摘要（提示用，避免整段 dump） */
function briefly(item: unknown): string {
  if (isObject(item)) {
    const k = Object.keys(item as object)[0]
    return k ? `${k} …` : '{}'
  }
  return String(item).slice(0, 40)
}
