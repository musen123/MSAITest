/**
 * RPC 分发表（契约 §2/§10/§3.1）—— 网关 rpc_request 的 Agent 侧执行入口。
 *
 * cmd：ping（连通性）、start_scrcpy / stop_scrcpy（投屏数据面，契约 §3.1）。
 * 未知 cmd 与未实现统一回 not_implemented；handler 内未捕获异常折叠为 internal，
 * ScrcpyError 折叠为对应协议错误码（busy → busy，其余 → internal）；超时由
 * dispatchRpcWithTimeout 竞速兜底——任何情况都必须给网关一个 rpc_response。
 *
 * 投屏 handler 需访问单例 ScrcpyManager（"一次一台"gate + data-WS 数据面），
 * 经 buildRpcDispatcher(manager) 注入，避免模块级全局单例（便于单测）。
 */

import fs from 'node:fs';

import { pressHome, type AppModelConfig } from './automation.js';
import { AutomationBusyError, type AutomationManager } from './automation_manager.js';
import type { RpcErrorCode } from './frames.js';
import type { ManualRecordManager } from './manual_record.js';
import { dedupeAdjacentSteps, stepsToYamlFlow } from './recover.js';
import { ScrcpyError } from './scrcpy.js';
import { WdaBusyError } from './wda.js';
import type { ScrcpyManager } from './scrcpy_manager.js';

export type RpcOutcome =
  | { ok: true; result: Record<string, unknown> }
  | { ok: false; error: { code: RpcErrorCode; message: string } };

/** handler 主动抛出的业务错误（带协议错误码）；其余异常一律折叠为 internal */
export class RpcError extends Error {
  constructor(
    readonly code: RpcErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'RpcError';
  }
}

type RpcHandler = (params: Record<string, unknown>) => Promise<Record<string, unknown>>;

export interface RpcDeps {
  scrcpy: ScrcpyManager;
  automation: AutomationManager;
  manualRecord: ManualRecordManager;
}

/** 取必填 string 参数，缺失/类型错抛 RpcError(internal)（网关侧参数错按内部处理） */
function requireStringParam(params: Record<string, unknown>, key: string): string {
  const value = params[key];
  if (typeof value !== 'string' || value.length === 0) {
    throw new RpcError('internal', `参数 ${key} 缺失或非法`);
  }
  return value;
}

/** 取可选正整数参数，缺失/非法返回 undefined（交给会话层用缺省值） */
function optionalPositiveInt(params: Record<string, unknown>, key: string): number | undefined {
  const value = params[key];
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return undefined;
  return Math.floor(value);
}

/** ScrcpyError → 协议错误码：'busy' 直通，其余折叠为 internal */
function scrcpyErrorCode(err: ScrcpyError): RpcErrorCode {
  return err.message === 'busy' ? 'busy' : 'internal';
}

/** 取 per-user 模型配置参数（缺任一件即 internal；FAMILY 必填，配错=坐标静默偏移） */
function requireModelConfig(params: Record<string, unknown>): AppModelConfig {
  const raw = params.model;
  if (!raw || typeof raw !== 'object') {
    throw new RpcError('internal', '参数 model 缺失或非法');
  }
  const m = raw as Record<string, unknown>;
  const pick = (key: string): string => {
    const v = m[key];
    if (typeof v !== 'string' || v.length === 0) {
      throw new RpcError('internal', `参数 model.${key} 缺失或非法`);
    }
    return v;
  };
  return { name: pick('name'), baseUrl: pick('base_url'), apiKey: pick('api_key'), family: pick('family') };
}

/** 构建 cmd → handler 分发表（注入投屏 manager） */
function buildHandlers(deps: RpcDeps): Record<string, RpcHandler> {
  return {
    ping: async () => ({ pong: true }),

    // 投屏数据面（契约 §3.1）：一次一台 gate + data-WS 出站 + video 推流 / control 回写
    start_scrcpy: async (params) => {
      const serial = requireStringParam(params, 'serial');
      const sessionId = requireStringParam(params, 'session_id');
      return deps.scrcpy.startScrcpy({
        serial,
        sessionId,
        maxFps: optionalPositiveInt(params, 'max_fps'),
        bitRate: optionalPositiveInt(params, 'bit_rate'),
      });
    },

    stop_scrcpy: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      return deps.scrcpy.stopScrcpy(sessionId);
    },

    // 自动化执行内核（P2）：单步自然语言 aiAct → 回收即时动作步骤；取消/结束。
    // 一句 aiAct 内部多轮规划都算“一步”，耗时较长 → 网关须给较宽超时档。
    run_app_step: async (params) => {
      const serial = requireStringParam(params, 'serial');
      const sessionId = requireStringParam(params, 'session_id');
      const instruction = requireStringParam(params, 'instruction');
      const model = requireModelConfig(params);
      const actContext =
        typeof params.act_context === 'string' ? params.act_context : undefined;
      if (params.press_home === true)
        await pressHome(serial, {
          platform: deps.automation.platformOf(serial),
          hdcPath: deps.automation.hdcPath,
          wda: deps.automation.wda,
        }); // 起点锚定（探索用）
      const result = await deps.automation.runStep({
        serial,
        sessionId,
        instruction,
        model,
        actContext,
        replanningCycleLimit: optionalPositiveInt(params, 'replanning_cycle_limit'),
      });
      // 疑似重规划冗余的自愈候选：相邻全等折叠后若步骤数变少，附带去重版
      // （必要重复与冗余静态无法区分——只供平台在**回放验证失败后**重验用）
      const deduped = dedupeAdjacentSteps(result.steps);
      const hasDedup = result.status === 'ok' && deduped.length < result.steps.length;
      // 契约 §3.2 回包用 snake_case（yaml_flow）；StepResult 是内部 camelCase，显式映射
      return {
        session_id: sessionId,
        status: result.status,
        summary: result.summary,
        steps: result.steps,
        yaml_flow: result.yamlFlow,
        ...(hasDedup
          ? { steps_deduped: deduped, yaml_flow_deduped: stepsToYamlFlow(deduped) }
          : {}),
        error: result.error ?? null,
      };
    },

    // 回放：跑整段 Midscene YAML（tasks 段）。取消 = end_app_session（dispose）。
    run_app_yaml: async (params) => {
      const serial = requireStringParam(params, 'serial');
      const sessionId = requireStringParam(params, 'session_id');
      const yaml = requireStringParam(params, 'yaml');
      const model = requireModelConfig(params);
      if (params.press_home === true)
        await pressHome(serial, {
          platform: deps.automation.platformOf(serial),
          hdcPath: deps.automation.hdcPath,
          wda: deps.automation.wda,
        }); // 起点锚定（回放确定性）
      const result = await deps.automation.runYaml({
        serial,
        sessionId,
        yaml,
        model,
        replanningCycleLimit: optionalPositiveInt(params, 'replanning_cycle_limit'),
      });
      return { session_id: sessionId, ...result };
    },

    // 手动录制（操作台）：投屏触控流 tee → VL 语义化步骤。录制必须挂在
    // 活跃投屏会话上（触控从那来）；stop 回步骤+YAML flow 供并入草稿。
    start_manual_record: async (params) => {
      const serial = requireStringParam(params, 'serial');
      const sessionId = requireStringParam(params, 'session_id');
      const model = requireModelConfig(params);
      // 设备物理分辨率（触控消息坐标在缩放流坐标系，语义化前须换算到设备系）
      const resolution =
        typeof params.resolution === 'string' ? params.resolution : undefined;
      if (!deps.scrcpy.isSessionActive(sessionId)) {
        throw new RpcError('internal', '投屏会话不存在或不匹配，请先连接投屏再开始手动录制');
      }
      return deps.manualRecord.start(serial, sessionId, model, resolution) as unknown as Record<
        string,
        unknown
      >;
    },

    get_manual_steps: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      const afterSeq = optionalPositiveInt(params, 'after_seq') ?? 0;
      return deps.manualRecord.pull(sessionId, afterSeq) as unknown as Record<string, unknown>;
    },

    stop_manual_record: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      const result = await deps.manualRecord.stop(sessionId);
      if (result === null) return { recording: false, steps: [], yaml_flow: '' };
      return { recording: false, ...result } as unknown as Record<string, unknown>;
    },

    // 执行进度增量读（只读旁路，runStep/runYaml in-flight 期间轮询用）。
    // after_seq=0 起始拉全量；会话不匹配回 exists=false（轮询端安静停表）。
    get_app_step_progress: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      const afterSeq = optionalPositiveInt(params, 'after_seq') ?? 0;
      return deps.automation.stepProgress(sessionId, afterSeq) as unknown as Record<
        string,
        unknown
      >;
    },

    // 分块取当前会话报告 HTML（base64；避免整份数 MB 撑爆 WS 帧上限）。
    // 正路读 Midscene 落盘文件——reportHTMLString() **不含**真执行的
    // midscene-image 截图仓块（截图按 data-id 存独立 script 块只写盘），
    // 用内存串上传的报告播放器全黑（2026-07-03 实证）；内存串仅作兜底。
    get_app_report: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      const offset = optionalPositiveInt(params, 'offset') ?? 0;
      const maxBytes = Math.min(optionalPositiveInt(params, 'max_bytes') ?? 262_144, 1_048_576);

      const filePath = deps.automation.reportFilePath(sessionId);
      if (filePath !== null) {
        try {
          const fh = await fs.promises.open(filePath, 'r');
          try {
            const { size } = await fh.stat();
            const len = Math.max(0, Math.min(maxBytes, size - offset));
            const buf = Buffer.alloc(len);
            if (len > 0) await fh.read(buf, 0, len, offset);
            return {
              data_b64: buf.toString('base64'),
              offset,
              total: size,
              eof: offset + len >= size,
            };
          } finally {
            await fh.close();
          }
        } catch {
          // 文件缺失/读失败（如 Midscene 改命名）→ 走内存串兜底
        }
      }

      const html = deps.automation.reportHtml(sessionId);
      if (html === null) {
        throw new RpcError('internal', '当前会话无报告（会话不存在或未生成）');
      }
      const buf = Buffer.from(html, 'utf8');
      const slice = buf.subarray(offset, offset + maxBytes);
      return {
        data_b64: slice.toString('base64'),
        offset,
        total: buf.byteLength,
        eof: offset + slice.byteLength >= buf.byteLength,
      };
    },

    // 取消闭环入口：abort 当前在跑的 aiAct（真机立即停，不空烧 token）
    abort_app_flow: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      return deps.automation.abortFlow(sessionId);
    },

    // 结束会话：dispose AndroidAgent + 清内存 modelConfig（不漏 key）
    end_app_session: async (params) => {
      const sessionId = requireStringParam(params, 'session_id');
      return deps.automation.endSession(sessionId);
    },
  };
}

/**
 * 构建 dispatcher：cmd → RpcOutcome。未知 cmd 回 not_implemented；
 * RpcError 保码；ScrcpyError 映射（busy/internal）；其余异常折叠 internal。
 */
export function buildRpcDispatcher(
  deps: RpcDeps,
): (cmd: string, params: Record<string, unknown>) => Promise<RpcOutcome> {
  const handlers = buildHandlers(deps);
  return async (cmd, params) => {
    const handler = handlers[cmd];
    if (!handler) {
      return { ok: false, error: { code: 'not_implemented', message: `未知 cmd: ${cmd}` } };
    }
    try {
      return { ok: true, result: await handler(params) };
    } catch (err) {
      if (err instanceof RpcError) {
        return { ok: false, error: { code: err.code, message: err.message } };
      }
      if (err instanceof ScrcpyError) {
        return {
          ok: false,
          error: { code: scrcpyErrorCode(err), message: err.message, ...(err.detail ?? {}) },
        };
      }
      if (err instanceof AutomationBusyError) {
        // 网关据 active_session_id 停孤儿会话后重试（同 scrcpy busy 语义）
        return {
          ok: false,
          error: { code: 'busy', message: 'busy', ...{ active_session_id: err.activeSessionId } },
        };
      }
      if (err instanceof WdaBusyError) {
        // ⚠ 必须 internal 而非 busy：busy 会触发网关"停孤儿重试"，把正在
        // 干活的 iOS 设备 A 的会话当孤儿杀掉（单 iOS 守卫的意义就在于不打断 A）
        return { ok: false, error: { code: 'internal', message: err.message } };
      }
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, error: { code: 'internal', message } };
    }
  };
}

/**
 * 按 rpc_request.timeout_ms 本地兜底：超时先回 timeout，晚到的 handler 结果丢弃。
 * 传入 dispatcher（buildRpcDispatcher 产出），保持"必给网关一个 rpc_response"不变量。
 */
export function dispatchRpcWithTimeout(
  dispatch: (cmd: string, params: Record<string, unknown>) => Promise<RpcOutcome>,
  cmd: string,
  params: Record<string, unknown>,
  timeoutMs: number,
): Promise<RpcOutcome> {
  const effective = timeoutMs > 0 ? timeoutMs : 15_000;
  let timer: NodeJS.Timeout | undefined;
  const timeout = new Promise<RpcOutcome>((resolve) => {
    timer = setTimeout(
      () =>
        resolve({
          ok: false,
          error: { code: 'timeout', message: `cmd ${cmd} 执行超过 ${effective}ms` },
        }),
      effective,
    );
  });
  return Promise.race([dispatch(cmd, params), timeout]).finally(() => clearTimeout(timer));
}
