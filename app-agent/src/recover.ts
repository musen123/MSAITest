/**
 * 步骤回收（路线 A 适配层）—— Midscene aiAct 执行轨迹 → 即时动作步骤 / YAML flow。
 *
 * aiAct 每规划一步会在 executionDump.tasks 里留下成对：
 *   Planning/Locate（param.prompt = 定位描述原文）
 *   Action Space/<Tap|Input|Scroll|...>（status==='finished' 才算真执行）
 * 把「定位描述 + 动作」还原为可回放的即时动作步骤（aiTap/aiInput/...），回放
 * 便宜且稳定（S2 spike 实证：回收后回放比原始 aiAct 便宜约 4.5×）。
 *
 * 无定位动作（真机联调实证会被模型使用，丢弃=回收出的用例缺步骤没法冷回放）：
 *   AndroidHomeButton/BackButton/RecentAppsButton（param=null，系统键）
 *   Swipe/PullGesture（direction+distance 模式可移植——舍弃 start 定位=页面中心
 *   起滑，零 VL 调用；start+end 精确坐标模式设备相关，不回收）
 *   Sleep（模型显式等待）、KeyboardPress（无定位按键）、Launch（启动应用）
 * yaml player 对 action space 按 action.name / interfaceAlias 全量动态分发，
 * 以上动作名即合法 flow 动词（@midscene/core yaml/player 实证，锁版本结论）。
 *
 * 蓝本 spikes/s2-midscene/recover-to-yaml.mjs；坑：定位描述含英文引号必须 YAML 转义。
 * 纯函数、宽松结构入参，脱离 Midscene 依赖可单测。
 */

/** 回收动作全集：aiXxx=带定位即时动作；其余为无定位动作（动作名即 YAML 动词） */
export type RecoveredAction =
  | 'aiTap'
  | 'aiInput'
  | 'aiDoubleClick'
  | 'aiScroll'
  | 'aiKeyboardPress'
  | 'aiLongPress'
  | 'AndroidHomeButton'
  | 'AndroidBackButton'
  | 'AndroidRecentAppsButton'
  | 'IOSHomeButton'
  | 'Swipe'
  | 'PullGesture'
  | 'KeyboardPress'
  | 'sleep'
  | 'launch';

/** 即时动作步骤（回放用），对应 Midscene YAML flow 的一条动作 */
export interface RecoveredStep {
  /** Midscene YAML flow 动作键 */
  action: RecoveredAction;
  /** 定位描述（自然语言，回放时一次 VL 定位）；无定位动作缺省 */
  locate?: string;
  /** aiInput 的输入值 / launch 的包名或 uri */
  value?: string;
  /** 无定位动作的回放参数（Swipe 的 direction/distance、sleep 的 timeMs 等），原样进 YAML */
  params?: Record<string, string | number>;
}

/** executionDump 里的一条 task（只取回收需要的字段，宽松结构便于单测） */
export interface DumpTask {
  type?: string;
  subType?: string;
  status?: string;
  param?: {
    prompt?: string;
    value?: string | number;
    locate?: unknown;
    [key: string]: unknown;
  } | null;
}

/** executionDump：aiAct 单轮为 {tasks}，报告 dump 为 {executions:[{tasks}]} */
export interface DumpLike {
  tasks?: DumpTask[];
  executions?: Array<{ tasks?: DumpTask[] }>;
}

/** Action Space subType → YAML flow 动作键（带定位配对回收） */
const ACTION_MAP: Record<string, RecoveredStep['action']> = {
  Tap: 'aiTap',
  DoubleClick: 'aiDoubleClick',
  Input: 'aiInput',
  Scroll: 'aiScroll',
  KeyboardPress: 'aiKeyboardPress',
  LongPress: 'aiLongPress',
};

/** 无参系统键动作（param=null，动作名即 YAML 动词）；IOSHomeButton=@midscene/ios 同款语义 */
const SYSTEM_KEY_ACTIONS = new Set<RecoveredAction>([
  'AndroidHomeButton',
  'AndroidBackButton',
  'AndroidRecentAppsButton',
  'IOSHomeButton',
]);

/** 数值参数提取（缺失/非法返回 undefined） */
function num(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined;
}

/** Swipe/PullGesture direction 模式缺省滑动距离（px，中型滑动，覆盖开抽屉/翻页） */
const DEFAULT_SWIPE_DISTANCE = 600;

/** Swipe/PullGesture 的 start 定位描述（仅供展示，不进 YAML） */
function startDesc(param: DumpTask['param']): string | undefined {
  const start = param?.start as Record<string, unknown> | undefined;
  const d = start?.prompt ?? start?.description;
  return typeof d === 'string' && d ? d : undefined;
}

/** 无定位动作直收：还原为可回放步骤；不可移植/信息不足返回 null（丢弃） */
function recoverStandalone(t: DumpTask): RecoveredStep | null {
  const sub = t.subType ?? '';
  if (SYSTEM_KEY_ACTIONS.has(sub as RecoveredAction)) {
    return { action: sub as RecoveredAction };
  }
  if (sub === 'Swipe' || sub === 'PullGesture') {
    // 只回收 direction 相对模式（可移植）；start+end 精确坐标设备相关，不回收。
    // distance 缺省必补：yaml player 的 normalize 要求 direction 模式必须带
    // distance/end（真机联调实证——aiAct 内部执行路径宽容，回放路径会拒）。
    const direction = t.param?.direction;
    if (typeof direction !== 'string' || !direction) return null;
    const params: Record<string, string | number> = { direction };
    params.distance = num(t.param?.distance) ?? DEFAULT_SWIPE_DISTANCE;
    const duration = num(t.param?.duration);
    if (duration !== undefined) params.duration = duration;
    return { action: sub as RecoveredAction, params, locate: startDesc(t.param) };
  }
  if (sub === 'Sleep') {
    return { action: 'sleep', params: { timeMs: num(t.param?.timeMs) ?? 1000 } };
  }
  if (sub === 'KeyboardPress') {
    const keyName = t.param?.keyName;
    if (typeof keyName !== 'string' || !keyName) return null;
    return { action: 'KeyboardPress', params: { keyName } };
  }
  if (sub === 'Launch') {
    const uri = t.param?.uri ?? t.param?.value;
    if (typeof uri !== 'string' || !uri) return null;
    return { action: 'launch', value: uri };
  }
  return null;
}

/** 步骤等价判定（相邻冗余清洗用） */
function sameStep(a: RecoveredStep, b: RecoveredStep): boolean {
  return (
    a.action === b.action &&
    a.locate === b.locate &&
    a.value === b.value &&
    JSON.stringify(a.params ?? null) === JSON.stringify(b.params ?? null)
  );
}

/**
 * 相邻全等步骤折叠（重规划冗余清洗，S2 spike 遗留课题）。
 *
 * **不做自动清洗**（裁决记录）：模型重规划确实会把已完成动作再执行一遍
 * （真机实证：两个一模一样的 aiTap，第二次回放定位必失败）——但"连按
 * 多次返回箭头"这类必要重复的定位描述同样完全相同（trace-11 fixture
 * 实证：5 步去重剩 2 步，误伤），静态判据无法区分两者。
 * 本函数只作为**验证失败自愈**的工具：探索图在回放验证失败后用去重版
 * 重验一次——冗余场景重验通过（转正），误伤场景重验仍失败（保草稿），
 * 以真实回放结果为判据，零误伤。sleep 除外（显式等待重复合法）。
 */
export function dedupeAdjacentSteps(steps: RecoveredStep[]): RecoveredStep[] {
  const out: RecoveredStep[] = [];
  for (const s of steps) {
    const prev = out[out.length - 1];
    if (prev && s.action !== 'sleep' && sameStep(prev, s)) continue;
    out.push(s);
  }
  return out;
}

/** 从一组 tasks 回收即时动作步骤（配对 Planning/Locate → Action Space/*；无定位动作直收） */
export function recoverStepsFromTasks(tasks: DumpTask[]): RecoveredStep[] {
  const steps: RecoveredStep[] = [];
  let pendingLocate: string | null = null;
  for (const t of tasks) {
    if (t.type === 'Planning' && t.subType === 'Locate') {
      pendingLocate = typeof t.param?.prompt === 'string' ? t.param.prompt : null;
      continue;
    }
    if (t.type === 'Action Space' && t.status === 'finished') {
      const paired = t.subType ? ACTION_MAP[t.subType] : undefined;
      if (paired && pendingLocate) {
        const step: RecoveredStep = { action: paired, locate: pendingLocate };
        if (paired === 'aiInput') step.value = String(t.param?.value ?? '');
        steps.push(step);
      } else {
        // 无定位路径（系统键/滑动/等待/…）；回收不了的动作诚实丢弃
        const standalone = recoverStandalone(t);
        if (standalone) {
          if (pendingLocate && !standalone.locate) standalone.locate = pendingLocate;
          steps.push(standalone);
        }
      }
      pendingLocate = null; // 任何动作处理后清配对位，防污染下一动作
    }
  }
  return steps; // 相邻重复原样保留（必要重复无法与冗余静态区分，见 dedupeAdjacentSteps）
}

/** 从 executionDump（{tasks} 或 {executions:[{tasks}]}）回收即时动作步骤 */
export function recoverSteps(dump: DumpLike | null | undefined): RecoveredStep[] {
  if (!dump) return [];
  const groups: DumpTask[][] = Array.isArray(dump.executions)
    ? dump.executions.map((e) => e.tasks ?? [])
    : [dump.tasks ?? []];
  return groups.flatMap(recoverStepsFromTasks);
}

/** YAML 双引号字符串转义（反斜杠/英文引号；spike 适配层必修坑） */
function yamlDq(s: string): string {
  return '"' + s.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
}

/** params → YAML 内联映射（flow mapping；字符串转义、数值原样） */
function yamlInlineParams(params: Record<string, string | number>): string {
  const parts = Object.entries(params).map(
    ([k, v]) => `${k}: ${typeof v === 'number' ? v : yamlDq(v)}`,
  );
  return `{ ${parts.join(', ')} }`;
}

/**
 * 即时动作步骤 → Midscene YAML flow 片段（tasks[].flow 下的条目，6 空格缩进）。
 * 每步后补一条 settle sleep 兜 UI 稳定（sleep 步自身除外）；外层 name/tasks
 * 由调用方拼装。无定位动作出动作名动词（player 按 action.name 动态匹配）。
 */
export function stepsToYamlFlow(steps: RecoveredStep[], settleMs = 800): string {
  const lines: string[] = [];
  for (const s of steps) {
    if (s.action === 'sleep') {
      lines.push(`      - sleep: ${s.params?.timeMs ?? 1000}`);
      continue; // 等待步不再叠 settle
    }
    if (s.action === 'aiInput') {
      lines.push(`      - aiInput: ${yamlDq(s.locate ?? '')}`);
      lines.push(`        value: ${yamlDq(s.value ?? '')}`);
    } else if (s.action === 'launch') {
      lines.push(`      - launch: ${yamlDq(s.value ?? '')}`);
    } else if (SYSTEM_KEY_ACTIONS.has(s.action)) {
      lines.push(`      - ${s.action}: {}`);
    } else if (s.params) {
      // Swipe/PullGesture/KeyboardPress：内联参数映射
      lines.push(`      - ${s.action}: ${yamlInlineParams(s.params)}`);
    } else {
      lines.push(`      - ${s.action}: ${yamlDq(s.locate ?? '')}`);
    }
    lines.push(`      - sleep: ${settleMs}`);
  }
  return lines.join('\n');
}
