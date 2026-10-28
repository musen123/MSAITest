/**
 * AutomationManager —— Midscene 自动化会话编排（“一台设备一路” gate + 生命周期 + 取消）。
 *
 * 与投屏（ScrcpyManager）同构但独立：按 serial 分桶，一台设备同时只跑一条录制/
 * 回放会话，不同设备并行互不可见。run_app_step 首次为某 session 建
 * AutomationSession（惰性连设备），同 session 复用；同设备别的 session 在跑步骤
 * 中 → busy（附 active_session_id）；同设备空闲旧会话 → 接管（跨设备绝不接管）。
 *
 * 取消闭环（S级铁律）：每步一个 AbortController，abort_app_flow / stopAll 都 abort
 * 当前在跑的 aiAct，让真机立即停、不空烧 token；结束/退出 dispose 清 modelConfig。
 *
 * sessionId 全局唯一（exec-{task}/explore-{task}/网关票据），按 sessionId 的
 * 查找（abort/end/progress/report）遍历各设备条目首个匹配即唯一——RPC 契约零变更。
 *
 * 依赖注入 createSession 工厂：便于单测用假会话验证 gate/取消/生命周期。
 */

import {
  AutomationSession,
  type AppModelConfig,
  type AutomationSessionParams,
  type StepProgressEntry,
  type StepResult,
} from './automation.js';
import type { DevicePlatform } from './frames.js';
import { log } from './log.js';
import type { WdaLike } from './wda.js';

/** gate 冲突：已有别的会话占用，附 active_session_id 供网关停孤儿重试 */
export class AutomationBusyError extends Error {
  constructor(readonly activeSessionId: string) {
    super('busy');
    this.name = 'AutomationBusyError';
  }
}

export interface RunStepParams {
  serial: string;
  sessionId: string;
  instruction: string;
  model: AppModelConfig;
  actContext?: string;
  replanningCycleLimit?: number;
}

export interface RunYamlParams {
  serial: string;
  sessionId: string;
  yaml: string;
  model: AppModelConfig;
  replanningCycleLimit?: number;
}

/** 会话最小契约（便于单测替身） */
export interface AutomationSessionLike {
  runStep(instruction: string, signal?: AbortSignal): Promise<StepResult>;
  runYaml(
    yaml: string,
  ): Promise<{ status: 'ok' | 'error'; result?: unknown; error?: string }>;
  reportHtml(): string | null;
  /** Midscene 落盘报告路径（可选：老替身缺省走内存串兜底） */
  reportFilePath?(): string;
  dispose(): Promise<void>;
  /** 执行进度增量读（可选：老替身/实现缺省视为无进度） */
  getProgress?(afterSeq: number): { seq: number; entries: StepProgressEntry[] };
}

interface ActiveAutomation {
  serial: string;
  sessionId: string;
  session: AutomationSessionLike;
  abort: AbortController | null; // 当前在跑 step 的取消器
  running: boolean;
  // 最近活动时刻（建会话 / 每次 runStep·runYaml 起止）——空闲自愈计时基准。
  // 图死了（worker 崩）而隧道没断时，会话没人来 end，靠它超时兜底 dispose。
  lastActivityAt: number;
}

export interface AutomationManagerDeps {
  /** 会话工厂（DI）；缺省用真 AutomationSession */
  createSession?: (params: AutomationSessionParams) => AutomationSessionLike;
  /** serial → 平台（index 注入合并快照查询）；缺省恒 android */
  resolvePlatform?: (serial: string) => DevicePlatform;
  /** 鸿蒙 hdc 路径（harmony 会话建 agentFromHdcDevice 用） */
  hdcPath?: string;
  /** WDA 存活管理（ios 会话建 agentFromWebDriverAgent 前自愈用；I2） */
  wda?: WdaLike;
}

export class AutomationManager {
  /** serial → 该设备的活跃会话（一台设备一路；不同设备并行） */
  private readonly sessions = new Map<string, ActiveAutomation>();
  private readonly createSession: (params: AutomationSessionParams) => AutomationSessionLike;
  private readonly resolvePlatform: (serial: string) => DevicePlatform;
  readonly hdcPath?: string;
  readonly wda?: WdaLike;

  constructor(deps: AutomationManagerDeps = {}) {
    this.createSession = deps.createSession ?? ((p) => new AutomationSession(p));
    this.resolvePlatform = deps.resolvePlatform ?? (() => 'android');
    this.hdcPath = deps.hdcPath;
    this.wda = deps.wda;
  }

  /** 查设备平台（rpc pressHome 分派用） */
  platformOf(serial: string): DevicePlatform {
    return this.resolvePlatform(serial);
  }

  /**
   * 一台设备一路 gate + 同设备空闲接管（**同步**：不 await，避免让出微任务导致
   * 并发 runStep 穿透占位）：
   * - 本设备无会话 → null 走新建；
   * - 本设备同 session → 返回复用；
   * - 本设备别的会话在**跑步骤中** → busy（附 active_session_id，真并发冲突）；
   * - 本设备别的会话**空闲**（多因投屏重连换了 session_id，同用户）→ 同步清占位、
   *   后台 dispose 旧（fire-and-forget），返回 null 走新建。
   * 接管只在同 serial 内发生——跨设备接管是旧单槽实现的副作用，并行下会误杀
   * 另一台设备仍在用的会话。
   */
  private gateOrTakeoverSync(serial: string, sessionId: string): ActiveAutomation | null {
    const active = this.sessions.get(serial);
    if (!active || active.sessionId === sessionId) return active ?? null;
    if (active.running) throw new AutomationBusyError(active.sessionId);
    log('info', '自动化会话接管（同设备旧会话空闲）', {
      serial,
      old: active.sessionId,
      next: sessionId,
    });
    this.sessions.delete(serial);
    void active.session.dispose().catch(() => {});
    return null;
  }

  /** 按 sessionId 找条目（sessionId 全局唯一，首个匹配即唯一） */
  private findBySessionId(sessionId: string): ActiveAutomation | undefined {
    for (const entry of this.sessions.values()) {
      if (entry.sessionId === sessionId) return entry;
    }
    return undefined;
  }

  /** 单步自然语言执行：gate → 建/复用会话 → aiAct（可 abort）→ 回收步骤。 */
  async runStep(params: RunStepParams): Promise<StepResult> {
    const { serial, sessionId } = params;
    let entry = this.gateOrTakeoverSync(serial, sessionId);
    if (!entry) {
      const session = this.createSession({
        serial,
        sessionId,
        model: params.model,
        actContext: params.actContext,
        replanningCycleLimit: params.replanningCycleLimit,
        platform: this.resolvePlatform(serial),
        hdcPath: this.hdcPath,
        wda: this.wda,
      });
      entry = {
        serial,
        sessionId,
        session,
        abort: null,
        running: false,
        lastActivityAt: Date.now(),
      };
      this.sessions.set(serial, entry);
      log('info', '自动化会话建立', { serial, session: sessionId });
    }
    // 同会话上一步未结束（后端应串行下发，防御性拒绝）
    if (entry.running) throw new Error('该会话有步骤正在执行');

    const controller = new AbortController();
    entry.abort = controller;
    entry.running = true;
    entry.lastActivityAt = Date.now();
    try {
      return await entry.session.runStep(params.instruction, controller.signal);
    } finally {
      entry.running = false;
      entry.abort = null;
      entry.lastActivityAt = Date.now(); // 跑完重置空闲计时
    }
  }

  /**
   * 回放：跑整段 YAML（gate/复用语义同 runStep）。runYaml 无 abort 原语，
   * 取消 = endSession（dispose 销毁 AndroidAgent → runYaml 报错返回）。
   */
  async runYaml(
    params: RunYamlParams,
  ): Promise<{ status: 'ok' | 'error'; result?: unknown; error?: string }> {
    const { serial, sessionId } = params;
    let entry = this.gateOrTakeoverSync(serial, sessionId);
    if (!entry) {
      const session = this.createSession({
        serial,
        sessionId,
        model: params.model,
        replanningCycleLimit: params.replanningCycleLimit,
        platform: this.resolvePlatform(serial),
        hdcPath: this.hdcPath,
        wda: this.wda,
      });
      entry = {
        serial,
        sessionId,
        session,
        abort: null,
        running: false,
        lastActivityAt: Date.now(),
      };
      this.sessions.set(serial, entry);
      log('info', '自动化会话建立（回放）', { serial, session: sessionId });
    }
    if (entry.running) throw new Error('该会话有步骤正在执行');
    entry.running = true;
    entry.lastActivityAt = Date.now();
    try {
      return await entry.session.runYaml(params.yaml);
    } finally {
      entry.running = false;
      entry.lastActivityAt = Date.now(); // 跑完重置空闲计时
    }
  }

  /** 取消当前在跑的 aiAct（取消闭环入口之一）。 */
  abortFlow(sessionId: string): { aborted: boolean } {
    const entry = this.findBySessionId(sessionId);
    if (entry?.abort) {
      entry.abort.abort();
      return { aborted: true };
    }
    return { aborted: false };
  }

  /** 取当前会话报告 HTML（供上传平台鉴权端点）。 */
  /** 落盘报告路径（会话不匹配/替身未实现 → null，调用方走内存串兜底） */
  reportFilePath(sessionId: string): string | null {
    return this.findBySessionId(sessionId)?.session.reportFilePath?.() ?? null;
  }

  reportHtml(sessionId: string): string | null {
    return this.findBySessionId(sessionId)?.session.reportHtml() ?? null;
  }

  /**
   * 执行进度增量读（只读旁路：**不过 busy gate**——必须在 runStep/runYaml
   * in-flight 期间可用，这正是它存在的意义）。会话不匹配回 exists=false，
   * 轮询端安静停表，不当错误。
   */
  stepProgress(
    sessionId: string,
    afterSeq: number,
  ): { exists: boolean; running: boolean; seq: number; entries: StepProgressEntry[] } {
    const entry = this.findBySessionId(sessionId);
    if (!entry?.session.getProgress) {
      return { exists: false, running: false, seq: afterSeq, entries: [] };
    }
    const p = entry.session.getProgress(afterSeq);
    return { exists: true, running: entry.running, seq: p.seq, entries: p.entries };
  }

  /** 结束会话：abort 在跑步骤 + dispose（清 modelConfig）。幂等。 */
  async endSession(sessionId: string): Promise<{ ended: boolean }> {
    const entry = this.findBySessionId(sessionId);
    if (!entry) return { ended: false };
    this.sessions.delete(entry.serial);
    entry.abort?.abort();
    await entry.session.dispose();
    log('info', '自动化会话结束', { serial: entry.serial, session: sessionId });
    return { ended: true };
  }

  /**
   * 空闲自愈：**空闲**（!running）且超 maxIdleMs 无活动的会话自动 dispose
   * （释放设备 + 清 modelConfig）。终极兜底——图死了（worker 崩溃/重启）而
   * 隧道没断时，会话没人来 endSession，靠它避免永久占设备烧锁。
   *
   * 只碰 !running 的：in-flight 会话（正跑 aiAct/runYaml）绝不动——单用例受
   * 300s RPC 上限约束不会无限跑，跑完 finally 会重置 lastActivityAt。
   * now 可注入（单测控时）。返回本轮清理的会话数（多设备逐个扫）。
   */
  reapIdle(maxIdleMs: number, now: number = Date.now()): number {
    let reaped = 0;
    for (const entry of [...this.sessions.values()]) {
      if (entry.running) continue;
      const idle = now - entry.lastActivityAt;
      if (idle <= maxIdleMs) continue;
      if (this.sessions.get(entry.serial) === entry) this.sessions.delete(entry.serial);
      log('warn', '自动化会话空闲超时自愈', {
        serial: entry.serial,
        session: entry.sessionId,
        idleMs: idle,
      });
      entry.abort?.abort();
      void entry.session.dispose().catch(() => {});
      reaped += 1;
    }
    return reaped;
  }

  /** 兜底清理（隧道断开 / 进程退出）：并行 abort + dispose 全部活跃会话。 */
  async stopAll(reason: string): Promise<void> {
    const entries = [...this.sessions.values()];
    if (entries.length === 0) return;
    this.sessions.clear();
    await Promise.allSettled(
      entries.map(async (entry) => {
        log('info', 'AutomationManager.stopAll', {
          serial: entry.serial,
          session: entry.sessionId,
          reason,
        });
        entry.abort?.abort();
        try {
          await entry.session.dispose();
        } catch (err) {
          log('warn', '自动化会话 dispose 异常', {
            session: entry.sessionId,
            error: String(err),
          });
        }
      }),
    );
  }

  /** 当前全部占用会话 id（观测/单测）。 */
  activeSessionIds(): string[] {
    return [...this.sessions.values()].map((e) => e.sessionId);
  }

  /** 某设备是否有活跃自动化会话（WDA 单 iOS 守卫探针用）。 */
  hasSessionForSerial(serial: string): boolean {
    return this.sessions.has(serial);
  }
}
