/**
 * AutomationSession —— 单设备 Midscene 自动化会话（录制/回放执行内核）。
 *
 * 封装 @midscene/android 的 AndroidAgent：
 *  - per-user modelConfig（内存态、dispose 时清空，不落盘不漏 key —— G9/S级铁律）；
 *  - 单步 aiAct（带 abortSignal 取消，取消闭环必到设备否则烧 token 占锁）；
 *  - 执行轨迹回收成即时动作步骤（recover.ts）供沉淀用例；
 *  - HTML 报告取用（供分块上传平台鉴权端点，绝不落 /uploads）。
 * “一次一台”编排在 AutomationManager，本类只管单会话。
 *
 * 关键坑（S2 spike）：FAMILY 配错=坐标静默偏移（非报错）；Android 无定位缓存，
 * 每步 aiAct 一次 VL 调用非零 token；一句 aiAct 可跑多轮规划（贵），回放走回收后
 * 的即时动作（便宜约 4.5×）。
 */

import { execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import { agentFromAdbDevice, type AndroidAgent } from '@midscene/android';
import { agentFromHdcDevice, type HarmonyAgent } from '@midscene/harmony';
import { agentFromWebDriverAgent, type IOSAgent } from '@midscene/ios';

import type { DevicePlatform } from './frames.js';
import { hdcEnv } from './hdc_devices.js';
import { log } from './log.js';
import type { WdaLike } from './wda.js';

/** 安卓 / 鸿蒙 / iOS Midscene Agent 公共类型（都继承 @midscene/core 的 Agent 基类，
 *  aiAct/runYaml/onDumpUpdate/dumpDataString/reportHTMLString/destroy 全共享） */
type AnyAgent = AndroidAgent | HarmonyAgent | IOSAgent;
import {
  recoverSteps,
  stepsToYamlFlow,
  type DumpLike,
  type RecoveredStep,
} from './recover.js';

/** 每用户 VL 模型配置（后端下发，映射 MIDSCENE_MODEL_* 四件套） */
export interface AppModelConfig {
  name: string;
  baseUrl: string;
  apiKey: string;
  /** 模型家族：配错=坐标静默偏移（非报错），必填（S2 spike 铁律） */
  family: string;
}

/** 单步执行结果 */
export interface StepResult {
  status: 'ok' | 'error';
  /** aiAct 返回的文字总结（若有） */
  summary: string | null;
  /** 本步回收到的即时动作步骤（沉淀用例用） */
  steps: RecoveredStep[];
  /** 拼好的 YAML flow 片段（可直接进用例草稿） */
  yamlFlow: string;
  error?: string;
}

// ==================== 执行进度直播 ====================

/** 执行进度行（操作台实时日志 / 探索 SSE 转发用） */
export interface StepProgressEntry {
  seq: number;
  ts: number;
  kind: 'plan' | 'locate' | 'action' | 'info' | 'error';
  text: string;
}

/** 进度收集器状态（ingestProgress 的可变上下文；每个 runStep/runYaml 重置） */
export interface ProgressState {
  /** taskId → 已上报 status（同任务状态跃迁才再发行） */
  seen: Map<string, string>;
  planRound: number;
  seq: number;
  entries: StepProgressEntry[];
}

export function newProgressState(): ProgressState {
  return { seen: new Map(), planRound: 0, seq: 0, entries: [] };
}

const PROGRESS_ACTION_LABEL: Record<string, string> = {
  Tap: '点击',
  DoubleClick: '双击',
  Input: '输入',
  Scroll: '滚动',
  Swipe: '滑动',
  KeyboardPress: '按键',
  LongPress: '长按',
  // Android 设备键动作（真机直播实测出现，无定位描述）
  AndroidHomeButton: '按 Home 键',
  AndroidBackButton: '按返回键',
  AndroidRecentAppsButton: '按最近任务键',
  // iOS 设备动作（I2；IOSAgent actionSpace）
  IOSHomeButton: '按 Home 键',
  IOSAppSwitcher: '打开应用切换器',
  RunWdaRequest: 'WDA 请求',
  Launch: '启动应用',
  Sleep: '等待',
};
/** 进度缓冲上限（防病态长循环撑爆内存；消费端按 seq 增量拉，掐头无碍） */
const MAX_PROGRESS_ENTRIES = 500;

export function pushProgress(
  state: ProgressState,
  kind: StepProgressEntry['kind'],
  text: string,
): StepProgressEntry {
  state.seq += 1;
  const entry: StepProgressEntry = { seq: state.seq, ts: Date.now(), kind, text };
  state.entries.push(entry);
  if (state.entries.length > MAX_PROGRESS_ENTRIES) state.entries.shift();
  return entry;
}

/**
 * dump 快照 → 新增进度行（纯函数，onDumpUpdate 每次全量喂入，按 taskId+status
 * 去重只发状态跃迁）。素材（S2 fixture 实证字段）：
 *   Planning/Plan.output.log = 大模型该轮规划原话；usage = tokens/耗时
 *   Planning/Locate.param.prompt = 定位描述；Action Space/<Tap|...> = 动作+状态
 */
export function ingestProgress(
  state: ProgressState,
  dump: DumpLike | null | undefined,
): StepProgressEntry[] {
  if (!dump) return [];
  const groups = Array.isArray(dump.executions)
    ? dump.executions.map((e) => e.tasks ?? [])
    : [dump.tasks ?? []];
  const fresh: StepProgressEntry[] = [];
  let idx = 0;
  for (const tasks of groups) {
    for (const t of tasks) {
      const anyT = t as Record<string, any>;
      const id = String(anyT.taskId ?? `idx:${idx}`);
      idx += 1;
      const status = String(t.status ?? '');
      if (status !== 'finished' && status !== 'failed') continue; // 只报终态，运行中不刷屏
      if (state.seen.get(id) === status) continue;
      state.seen.set(id, status);

      if (t.type === 'Planning' && t.subType === 'Plan') {
        if (status === 'failed') {
          fresh.push(pushProgress(state, 'error', '规划失败'));
          continue;
        }
        state.planRound += 1;
        const out = anyT.output ?? {};
        const usage = anyT.usage ?? {};
        const cost =
          typeof usage.total_tokens === 'number'
            ? `（${usage.total_tokens.toLocaleString()} tokens${
                typeof usage.time_cost === 'number' ? ` · ${(usage.time_cost / 1000).toFixed(1)}s` : ''
              }）`
            : '';
        const said = typeof out.log === 'string' && out.log ? out.log : '（模型未给说明）';
        fresh.push(pushProgress(state, 'plan', `第${state.planRound}轮规划：${said}${cost}`));
        if (out.shouldContinuePlanning === false) {
          fresh.push(pushProgress(state, 'info', '规划判定目标已完成'));
        }
      } else if (t.type === 'Planning' && t.subType === 'Locate') {
        const prompt = typeof t.param?.prompt === 'string' ? t.param.prompt : '';
        fresh.push(
          pushProgress(
            state,
            status === 'failed' ? 'error' : 'locate',
            status === 'failed' ? `定位失败「${prompt}」` : `定位到「${prompt}」`,
          ),
        );
      } else if (t.type === 'Action Space' && t.subType) {
        const label = PROGRESS_ACTION_LABEL[t.subType] ?? t.subType;
        const desc =
          typeof (anyT.param?.locate as Record<string, unknown> | undefined)?.description === 'string'
            ? String((anyT.param.locate as Record<string, unknown>).description)
            : '';
        const value = t.param?.value != null && t.param.value !== '' ? `：${t.param.value}` : '';
        fresh.push(
          pushProgress(
            state,
            status === 'failed' ? 'error' : 'action',
            `${label}${desc ? `「${desc}」` : ''}${value}${status === 'failed' ? ' 失败' : ' ✓'}`,
          ),
        );
      }
      // 其余任务类型（Insight/Assert 等）暂不上报
    }
  }
  return fresh;
}

export interface AutomationSessionParams {
  serial: string;
  sessionId: string;
  model: AppModelConfig;
  /** aiAct 全局上下文提示（如“设置类应用，权限弹窗一律允许”） */
  actContext?: string;
  /** 单句 aiAct 最大重规划轮数（成本闸门，缺省 8） */
  replanningCycleLimit?: number;
  /** 设备平台（H2/I2 多平台）：harmony 走 agentFromHdcDevice、ios 走
   *  agentFromWebDriverAgent，缺省 android */
  platform?: DevicePlatform;
  /** 鸿蒙 hdc 路径（platform=harmony 时必需） */
  hdcPath?: string;
  /** WDA 存活管理（platform=ios 时必需；探活/自愈在建 Agent 前完成） */
  wda?: WdaLike;
}

/**
 * 错误信息瘦身：Midscene 抛错的 message 常内嵌整条调用栈
 * （"... at Object.executor (file://...)"），原样回传前端没法读。
 * 砍掉首个栈帧起的全部内容，只留人话部分。
 */
export function trimErrorMessage(raw: string): string {
  return raw.split(/\n?\s+at\s+\S+\s*\(/)[0]!.trim();
}

/**
 * 回 Home 锚定起点（探索/回放前，best-effort）。
 *
 * 联调实证之一：探索把设备停在目标页，回放验证从"当前屏"起跑首步定位必失败。
 * 联调实证之二：Android 桌面多页——只按一次 Home 落在上次停留页，探索与验证
 * 落页可能不同（一页有设置图标一页没有）→ 首步定位失败。**按两次**：第一次
 * 离开当前应用回桌面，第二次把多页桌面钉回默认页，起点强一致。
 * 失败不抛（无 Home 概念的设备直接跑）。
 */
export function pressHome(
  serial: string,
  opts: { platform?: DevicePlatform; hdcPath?: string; wda?: WdaLike } = {},
): Promise<void> {
  if (opts.platform === 'ios') {
    // iOS 无 adb/hdc：WDA /wda/homescreen 双按（WdaManager 内含 ensureAlive——
    // 顺带把 WDA 自愈前置到回放最开头）。best-effort：失败不抛，交给后续
    // ensureAgent 的 ensureAlive 给出真报错。
    if (!opts.wda) return Promise.resolve();
    return opts.wda.pressHome(serial).catch(() => {});
  }
  if (opts.platform === 'harmony') {
    // 鸿蒙无 adb：hdc + uitest keyEvent Home（S1 实证）。桌面单页，按一次即可。
    const hdc = opts.hdcPath || 'hdc';
    return new Promise<void>((resolve) => {
      execFile(
        hdc,
        ['-t', serial, 'shell', 'uitest uiInput keyEvent Home'],
        { timeout: 5_000, env: hdcEnv() },
        () => resolve(),
      );
    }).then(() => new Promise<void>((r) => setTimeout(r, 800)));
  }
  const adb = process.env.MIDSCENE_ADB_PATH || 'adb';
  const key = () =>
    new Promise<void>((resolve) => {
      execFile(adb, ['-s', serial, 'shell', 'input', 'keyevent', '3'], { timeout: 5_000 }, () =>
        resolve(),
      );
    });
  return key()
    .then(() => new Promise<void>((r) => setTimeout(r, 400)))
    .then(key)
    .then(() => new Promise<void>((r) => setTimeout(r, 800))); // 桌面动画/焦点稳定
}

/** AppModelConfig → Midscene TModelConfig（env-key 映射，Record<string,string>） */
function toModelConfig(m: AppModelConfig): Record<string, string> {
  return {
    MIDSCENE_MODEL_NAME: m.name,
    MIDSCENE_MODEL_BASE_URL: m.baseUrl,
    MIDSCENE_MODEL_API_KEY: m.apiKey,
    MIDSCENE_MODEL_FAMILY: m.family,
  };
}

export class AutomationSession {
  readonly serial: string;
  readonly sessionId: string;
  private agent: AnyAgent | null = null;
  private modelConfig: Record<string, string> | null;
  private readonly actContext?: string;
  private readonly replanningCycleLimit: number;
  private readonly platform: DevicePlatform;
  private readonly hdcPath?: string;
  private readonly wda?: WdaLike;
  private lastDump: DumpLike | null = null;
  private stepSeq = 0;
  private disposed = false;
  /** 执行进度缓冲（每个 runStep/runYaml 重置；轮询侧按 seq 增量拉） */
  private progress: ProgressState = newProgressState();

  constructor(params: AutomationSessionParams) {
    this.serial = params.serial;
    this.sessionId = params.sessionId;
    this.modelConfig = toModelConfig(params.model);
    this.actContext = params.actContext;
    this.replanningCycleLimit = params.replanningCycleLimit ?? 8;
    this.platform = params.platform ?? 'android';
    this.hdcPath = params.hdcPath;
    this.wda = params.wda;
  }

  /** 惰性建 Midscene Agent（首次 runStep 才连设备，占位不连）；按平台选 adb/hdc */
  private async ensureAgent(): Promise<AnyAgent> {
    if (this.agent) return this.agent;
    if (this.disposed || !this.modelConfig) throw new Error('会话已释放');
    // AgentOpt 字段三平台同构（都继承 core AgentOpt）；鸿蒙额外传 hdcPath，
    // iOS 走 WDA HTTP（先 ensureAlive 自愈：探活→iproxy→可选 xcodebuild）
    const commonOpt = {
      modelConfig: this.modelConfig,
      aiActContext: this.actContext,
      generateReport: true,
      replanningCycleLimit: this.replanningCycleLimit,
      reportFileName: `app-${this.sessionId}`,
    };
    let agent: AnyAgent;
    if (this.platform === 'ios') {
      if (!this.wda) {
        throw new Error('iOS 执行需要 WDA 管理（未检测到 libimobiledevice/IDEVICE_PATH，iOS 能力未开启）');
      }
      await this.wda.ensureAlive(this.serial);
      agent = await agentFromWebDriverAgent({
        ...commonOpt,
        wdaHost: '127.0.0.1',
        wdaPort: this.wda.port,
      });
    } else if (this.platform === 'harmony') {
      agent = await agentFromHdcDevice(this.serial, { ...commonOpt, hdcPath: this.hdcPath });
    } else {
      agent = await agentFromAdbDevice(this.serial, commonOpt);
    }
    // 捕获每次 aiAct 的结构化执行轨迹（executionDump）：供步骤回收 + 进度直播
    agent.onDumpUpdate = (_dumpStr: string, executionDump?: unknown) => {
      if (executionDump) {
        this.lastDump = executionDump as unknown as DumpLike;
        ingestProgress(this.progress, this.lastDump);
      }
    };
    this.agent = agent;
    log('info', 'Midscene Agent 已建立', {
      serial: this.serial,
      session: this.sessionId,
      platform: this.platform,
      replanningCycleLimit: this.replanningCycleLimit,
    });
    return agent;
  }

  /**
   * 回放：跑整段 Midscene YAML（tasks 段）。runYaml 无 abortSignal —— 取消
   * 语义 = endSession/dispose 销毁 AndroidAgent，runYaml 随之报错返回。
   */
  async runYaml(yaml: string): Promise<{ status: 'ok' | 'error'; result?: unknown; error?: string }> {
    this.progress = newProgressState();
    pushProgress(this.progress, 'info', '开始回放 YAML…');
    const agent = await this.ensureAgent();
    try {
      const { result } = await agent.runYaml(yaml);
      return { status: 'ok', result };
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);
      log('warn', 'runYaml 失败/被终止', { session: this.sessionId, error });
      return { status: 'error', error };
    }
  }

  /**
   * 单步：跑一句自然语言 aiAct（可 abort），回收本步即时动作。
   * aiAct 内部多轮规划都算“这一步”（录制一条指令 = 用户一句话）。
   */
  async runStep(instruction: string, signal?: AbortSignal): Promise<StepResult> {
    this.progress = newProgressState();
    pushProgress(this.progress, 'info', '已提交大模型规划…');
    const agent = await this.ensureAgent();
    this.lastDump = null;
    this.stepSeq += 1;
    try {
      const summary = await agent.aiAct(instruction, { abortSignal: signal });
      const steps = recoverSteps(this.lastDump ?? this.readDumpFallback(agent));
      pushProgress(this.progress, 'info', `步骤完成，回收 ${steps.length} 个动作`);
      return { status: 'ok', summary: summary ?? null, steps, yamlFlow: stepsToYamlFlow(steps) };
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err);
      const aborted = signal?.aborted || /abort/i.test(raw);
      log(aborted ? 'info' : 'warn', `aiAct ${aborted ? '已取消' : '失败'}`, {
        session: this.sessionId,
        error: raw,
      });
      // 失败也抢救已执行动作（如"重规划超限"时设备上多步早已成功——丢弃=白烧 token）。
      // 只认本步 lastDump，不走 dumpDataString 兜底：失败发生在任何动作前时，
      // 兜底会捞到上一步的轨迹造成草稿重复。recoverSteps 只配对 finished 动作，
      // 失败/中断的尾动作天然被排除。
      const steps = aborted ? [] : recoverSteps(this.lastDump);
      const error = trimErrorMessage(raw);
      pushProgress(this.progress, aborted ? 'info' : 'error', aborted ? '已取消' : error);
      return {
        status: 'error',
        summary: null,
        steps,
        yamlFlow: stepsToYamlFlow(steps),
        error,
      };
    }
  }

  /** 增量读执行进度（seq > afterSeq 的行）；轮询侧驱动，不阻塞执行。 */
  getProgress(afterSeq: number): { seq: number; entries: StepProgressEntry[] } {
    return {
      seq: this.progress.seq,
      entries: this.progress.entries.filter((e) => e.seq > afterSeq),
    };
  }

  /** 兜底：onDumpUpdate 没给结构化 dump 时，从 dumpDataString 取最后一条执行 */
  private readDumpFallback(agent: AnyAgent): DumpLike | null {
    try {
      const parsed = JSON.parse(agent.dumpDataString()) as DumpLike;
      const execs = parsed.executions;
      const last = Array.isArray(execs) ? execs[execs.length - 1] : undefined;
      if (last) return { executions: [last] };
      return parsed;
    } catch {
      return null;
    }
  }

  /** 当前报告 HTML（内存串）。⚠ reportHTMLString() **不含**真执行的
   *  midscene-image 截图仓块（截图按 data-id 引用存独立 script 块，只写进
   *  落盘文件）——播放器会黑屏。仅作落盘文件缺失时的兜底，正路走
   *  reportFilePath() 读文件版。 */
  reportHtml(): string | null {
    if (!this.agent) return null;
    try {
      return this.agent.reportHTMLString();
    } catch {
      return null;
    }
  }

  /** Midscene 落盘报告路径（generateReport 每次 dump 更新即写盘，含
   *  midscene-image 截图仓——上传平台走这份）。文件由 dispose 清理。 */
  reportFilePath(): string {
    return path.join(process.cwd(), 'midscene_run', 'report', `app-${this.sessionId}.html`);
  }

  /** 释放：销毁 agent + 清空内存 modelConfig（不漏 key，S级铁律） */
  async dispose(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    this.modelConfig = null; // 先抹 key，再拆 agent
    const agent = this.agent;
    this.agent = null;
    this.lastDump = null;
    if (agent) {
      try {
        await agent.destroy();
      } catch (err) {
        log('warn', 'AndroidAgent destroy 异常', {
          session: this.sessionId,
          error: String(err),
        });
      }
      // 落盘报告清理（平台在 end_app_session 前已分块拉走；单份可达 19MB，
      // 不清会把宿主机磁盘吃穿）。best-effort：删失败不影响会话收尾。
      fs.promises.unlink(this.reportFilePath()).catch(() => {});
    }
  }
}
