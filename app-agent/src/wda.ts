/**
 * WdaManager —— WebDriverAgent 存活管理（I2，iOS 执行的前置运维面）。
 *
 * 与安卓 adb 常驻 / 鸿蒙 hdc 常驻不同，WDA 是**会死的服务**：Mac 睡眠、设备重启、
 * xcodebuild test 会话被杀都会带走它（I0 残留风险清单）。执行前必须走 ensureAlive：
 *
 *   1. 探活 `GET http://127.0.0.1:{port}/status`——活着直接过；
 *   2. 死了先自拉 iproxy（libimobiledevice 端口转发，idevice_id 同目录兄弟；
 *      一个子进程同时转 8100 命令口 + 9100 MJPEG 口，I3 投屏共用）再探；
 *   3. 还死且配置了 WDA_PROJECT_PATH → 自启 `xcodebuild ... test`（盯输出
 *      `ServerURLHere->` 标志 + 轮询探活，冷启动 ~60-90s，回放 RPC 300s 上限内）；
 *   4. 都救不回来 → 抛带完整启动命令的人话错误（免费签名 7 天过期 / 首装信任
 *      开发者证书两大高频原因直接写进提示）。
 *
 * 单 iOS 设备假设（端口 8100/9100 写死贯穿执行/投屏/录制全链）：iproxy/xcodebuild
 * 子进程绑一个 udid。多设备并行改造后（Agent 其余管理器已按 serial 分桶），这里
 * 加**单 iOS 守卫**：已绑定设备的会话仍活跃（isUdidBusy 探针）时，另一台 iOS 的
 * ensureAlive 抛 WdaBusyError 明确拒绝——绝不像旧行为那样杀旧换绑打断正在跑的
 * 设备。绑定设备空闲时保留换机杀旧起新语义。多台 iOS 并行 = 端口池改造，后续任务。
 * stop() 只杀**本进程 spawn 的**子进程——用户手起的 xcodebuild 不归我们管。
 */

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

import { log } from './log.js';

/** WDA 命令端口（iproxy 本地口 = 设备口，与 I0 spike 一致） */
export const WDA_PORT = 8100;
/** WDA 内置 MJPEG 流端口（I3 投屏用，iproxy 顺带转好） */
export const WDA_MJPEG_PORT = 9100;
/** xcodebuild 日志里 WDA 就绪标志（I0 实证） */
export const WDA_SERVER_URL_MARKER = 'ServerURLHere->';

/**
 * 单 iOS 通道被占：已绑定设备的会话活跃时，另一台 iOS 请求被显式拒绝。
 * ⚠ RPC 层必须映射为 internal 码而非 busy——busy 会触发网关"停孤儿重试"，
 * 把正在干活的设备 A 的会话当孤儿杀掉。
 */
export class WdaBusyError extends Error {
  constructor(readonly boundUdid: string) {
    super(
      `iOS 通道被设备 ${boundUdid} 的活跃会话占用（当前仅支持单台 iOS 并行），` +
        '请先结束该设备的执行/投屏/录制会话',
    );
    this.name = 'WdaBusyError';
  }
}

/** 自动化会话侧最小契约（automation.ts 依赖此接口，便于单测替身） */
export interface WdaLike {
  readonly port: number;
  /** 确保 WDA 可达（探活→自愈→抛错），执行/建 Agent 前必调 */
  ensureAlive(udid: string): Promise<void>;
  /** 回主屏两连按（起点锚定；内部先 ensureAlive） */
  pressHome(udid: string): Promise<void>;
}

/** xcodebuild 自启配置（agent.config.json WDA_* 四键；不配则只探活不自启） */
export interface WdaXcodebuildConfig {
  /** WebDriverAgent.xcodeproj 路径或其所在目录（npm appium-webdriveragent 包根） */
  projectPath: string;
  /** 签名 Team ID（免费个人团队即可）；缺省用工程内既有签名设置 */
  teamId?: string;
  /** 唯一 bundle id（免费账号必须改，如 com.xxx.wdarunner） */
  bundleId?: string;
  /** DEVELOPER_DIR 覆盖（xcode-select 指向 CLT 时用，免 sudo） */
  developerDir?: string;
}

/** 探活/等待节奏（单测注入毫秒级跑完） */
export interface WdaTimings {
  /** 单次 /status 探活超时 */
  probeTimeoutMs: number;
  /** iproxy 起来后总等待窗口 */
  iproxyWaitMs: number;
  /** xcodebuild 冷启动总等待窗口 */
  bootTimeoutMs: number;
  /** 等待窗口内轮询间隔 */
  pollMs: number;
  /** pressHome 两按间隔（>双击手势窗口，防触发应用切换器） */
  homeGapMs: number;
  /** pressHome 后落定等待 */
  homeSettleMs: number;
}

const DEFAULT_TIMINGS: WdaTimings = {
  probeTimeoutMs: 1_500,
  iproxyWaitMs: 4_000,
  bootTimeoutMs: 180_000,
  pollMs: 2_000,
  homeGapMs: 1_000,
  homeSettleMs: 800,
};

/** 最小 fetch 形状（避免依赖 DOM lib 类型；探活只看 ok） */
type FetchLike = (
  url: string,
  init?: { method?: string; signal?: AbortSignal },
) => Promise<{ ok: boolean; status: number }>;

/** 最小子进程形状（spawn 注入替身用） */
export interface ChildLike {
  stdout: { on(event: 'data', cb: (chunk: Buffer | string) => void): unknown } | null;
  stderr: { on(event: 'data', cb: (chunk: Buffer | string) => void): unknown } | null;
  on(event: 'exit', cb: (code: number | null) => void): unknown;
  on(event: 'error', cb: (err: Error) => void): unknown;
  kill(signal?: NodeJS.Signals): boolean;
  pid?: number;
}

type SpawnLike = (
  cmd: string,
  args: string[],
  opts: { env?: NodeJS.ProcessEnv; stdio?: unknown },
) => ChildLike;

export interface WdaManagerDeps {
  /** idevice_id 路径（iproxy 取同目录兄弟） */
  ideviceIdPath: string;
  port?: number;
  mjpegPort?: number;
  xcodebuild?: WdaXcodebuildConfig;
  fetchImpl?: FetchLike;
  spawnImpl?: SpawnLike;
  timings?: Partial<WdaTimings>;
}

/** xcodebuild 启动参数（纯函数，I0-RESULT.md 命令的参数化版） */
export function buildXcodebuildArgs(cfg: WdaXcodebuildConfig, udid: string): string[] {
  const proj = cfg.projectPath.endsWith('.xcodeproj')
    ? cfg.projectPath
    : path.join(cfg.projectPath, 'WebDriverAgent.xcodeproj');
  const args = [
    '-project',
    proj,
    '-scheme',
    'WebDriverAgentRunner',
    '-destination',
    `id=${udid}`,
    '-allowProvisioningUpdates',
  ];
  if (cfg.teamId) args.push(`DEVELOPMENT_TEAM=${cfg.teamId}`, 'CODE_SIGN_STYLE=Automatic');
  if (cfg.bundleId) args.push(`PRODUCT_BUNDLE_IDENTIFIER=${cfg.bundleId}`);
  args.push('test');
  return args;
}

/** WDA 不可达的人话报错（两大高频根因直接给出处置命令） */
export function wdaDeadMessage(port: number, udid: string, hasAutoStart: boolean): string {
  const cmd =
    `cd <appium-webdriveragent 工程目录> && xcodebuild -project WebDriverAgent.xcodeproj ` +
    `-scheme WebDriverAgentRunner -destination 'id=${udid}' -allowProvisioningUpdates ` +
    `DEVELOPMENT_TEAM=<TeamID> CODE_SIGN_STYLE=Automatic ` +
    `PRODUCT_BUNDLE_IDENTIFIER=<唯一bundleId> test`;
  return (
    `WDA(127.0.0.1:${port}) 不可达，iOS 执行需要设备上运行 WebDriverAgent。` +
    (hasAutoStart
      ? '自动拉起已尝试但未成功（见 Agent 日志）。'
      : '手动启动：' + cmd + '；或在 agent.config.json 配置 WDA_PROJECT_PATH/WDA_TEAM_ID/WDA_BUNDLE_ID 由 Agent 自动拉起。') +
    '常见原因：①免费签名 7 天过期——重跑 xcodebuild 重签；' +
    '②首次安装未信任证书——设备上 设置→通用→VPN与设备管理 信任开发者。'
  );
}

export class WdaManager implements WdaLike {
  readonly port: number;
  private readonly mjpegPort: number;
  private readonly iproxyPath: string;
  private readonly xcodebuild?: WdaXcodebuildConfig;
  private readonly fetchImpl: FetchLike;
  private readonly spawnImpl: SpawnLike;
  private readonly timings: WdaTimings;

  private iproxyChild: ChildLike | null = null;
  private xcbChild: ChildLike | null = null;
  /** 子进程当前绑定的设备（换机杀旧起新） */
  private boundUdid: string | null = null;
  /** xcodebuild 输出尾环（报错时带出最后一段，签名类错误都在末尾） */
  private xcbTail = '';
  /** 并发 ensureAlive 合流（同 udid 共享；异 udid 排队，见 ensureAlive） */
  private pending: { udid: string; promise: Promise<void> } | null = null;
  /** 单 iOS 守卫探针：已绑定 udid 是否有活跃会话（index 后绑三管理器 Map 查询） */
  private isUdidBusy: ((udid: string) => boolean) | undefined;
  private stopped = false;

  constructor(deps: WdaManagerDeps) {
    this.port = deps.port ?? WDA_PORT;
    this.mjpegPort = deps.mjpegPort ?? WDA_MJPEG_PORT;
    this.iproxyPath = path.join(path.dirname(deps.ideviceIdPath), 'iproxy');
    this.xcodebuild = deps.xcodebuild;
    this.fetchImpl = deps.fetchImpl ?? (fetch as unknown as FetchLike);
    this.spawnImpl = deps.spawnImpl ?? (spawn as unknown as SpawnLike);
    this.timings = { ...DEFAULT_TIMINGS, ...deps.timings };
  }

  /**
   * 后绑单 iOS 守卫探针（wda 在三个管理器之前构造，构造参数给不了）。
   * 探针回答"该 udid 当前是否有活跃执行/投屏/录制会话"。
   */
  setBusyProbe(probe: (udid: string) => boolean): void {
    this.isUdidBusy = probe;
  }

  /** 单次探活：/status 200 即视为活（不看 body，WDA 就绪必 200） */
  async probe(): Promise<boolean> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), this.timings.probeTimeoutMs);
    try {
      const resp = await this.fetchImpl(`http://127.0.0.1:${this.port}/status`, {
        signal: ctrl.signal,
      });
      return resp.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  ensureAlive(udid: string): Promise<void> {
    // 合流按 udid：同 udid 并发共享同一次自愈（避免双拉 iproxy/xcodebuild）；
    // 不同 udid **排队**而非合流——旧实现里 B 会搭上 A 的 pending 拿到"假成功"，
    // 然后打到 A 的转发口上。排到后再走单 iOS 守卫判定。
    if (this.pending) {
      if (this.pending.udid === udid) return this.pending.promise;
      const queued = this.pending.promise.catch(() => {}).then(() => this.ensureAlive(udid));
      return queued;
    }
    const entry = {
      udid,
      promise: this.ensureAliveInner(udid).finally(() => {
        if (this.pending === entry) this.pending = null;
      }),
    };
    this.pending = entry;
    return entry.promise;
  }

  private async ensureAliveInner(udid: string): Promise<void> {
    if (this.stopped) throw new Error('WdaManager 已停止');
    if (this.boundUdid && this.boundUdid !== udid) {
      // 单 iOS 守卫：已绑定设备的会话仍活跃 → 显式拒绝，绝不杀旧打断它
      if (this.isUdidBusy?.(this.boundUdid)) throw new WdaBusyError(this.boundUdid);
      // 绑定设备空闲 → 换设备：旧子进程全下线（iproxy -u 绑死 udid，不换必转错设备）
      this.killChildren('切换 iOS 设备');
    }
    this.boundUdid = udid;

    if (await this.probe()) return;

    // ── 自愈 1：iproxy 转发不在 → 拉起再等一小窗 ──
    if (!this.iproxyChild) {
      this.startIproxy(udid);
      if (await this.waitAlive(this.timings.iproxyWaitMs)) return;
    }

    // ── 自愈 2：WDA 本体死了 → 配置允许则 xcodebuild 自启 ──
    if (this.xcodebuild) {
      if (!this.xcbChild) {
        this.startXcodebuild(udid);
      }
      if (await this.waitAlive(this.timings.bootTimeoutMs, () => this.xcbChild === null)) return;
      const tail = this.xcbTail.slice(-400).trim();
      throw new Error(
        wdaDeadMessage(this.port, udid, true) + (tail ? `xcodebuild 末尾输出：${tail}` : ''),
      );
    }

    throw new Error(wdaDeadMessage(this.port, udid, false));
  }

  /** 回主屏（起点锚定）：两次 /wda/homescreen，间隔 1s（避开双击手势窗口）——
   *  第一次离开当前应用，第二次把多页主屏钉回第一页，与安卓 pressHome 同语义。 */
  async pressHome(udid: string): Promise<void> {
    await this.ensureAlive(udid);
    const post = async (): Promise<void> => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 5_000);
      try {
        await this.fetchImpl(`http://127.0.0.1:${this.port}/wda/homescreen`, {
          method: 'POST',
          signal: ctrl.signal,
        });
      } finally {
        clearTimeout(timer);
      }
    };
    await post();
    await sleep(this.timings.homeGapMs);
    await post();
    await sleep(this.timings.homeSettleMs);
  }

  /** 在窗口内轮询探活；bail() 为真（如 xcodebuild 已退出）提前放弃 */
  private async waitAlive(totalMs: number, bail?: () => boolean): Promise<boolean> {
    const deadline = Date.now() + totalMs;
    for (;;) {
      if (await this.probe()) return true;
      if (this.stopped || (bail && bail())) return false;
      if (Date.now() >= deadline) return false;
      await sleep(this.timings.pollMs);
    }
  }

  private startIproxy(udid: string): void {
    if (!existsSync(this.iproxyPath)) {
      log('warn', 'iproxy 不存在，跳过端口转发自启（依赖外部转发）', { path: this.iproxyPath });
      return;
    }
    // 一个 iproxy 同时转命令口+MJPEG 口；-u 绑 udid（多设备插着也转对台）
    const args = [`${this.port}:${this.port}`, `${this.mjpegPort}:${this.mjpegPort}`, '-u', udid];
    try {
      const child = this.spawnImpl(this.iproxyPath, args, { stdio: ['ignore', 'pipe', 'pipe'] });
      // exit/error 异步到达：只清"仍是自己"的句柄，防换机后误清新拉起的子进程
      child.on('error', (err) => {
        log('warn', 'iproxy 启动失败', { error: err.message });
        if (this.iproxyChild === child) this.iproxyChild = null;
      });
      child.on('exit', (code) => {
        log('info', 'iproxy 退出', { code });
        if (this.iproxyChild === child) this.iproxyChild = null;
      });
      this.iproxyChild = child;
      log('info', 'iproxy 已拉起', { udid, ports: `${this.port},${this.mjpegPort}` });
    } catch (err) {
      log('warn', 'iproxy spawn 异常', { error: err instanceof Error ? err.message : String(err) });
    }
  }

  private startXcodebuild(udid: string): void {
    const cfg = this.xcodebuild as WdaXcodebuildConfig;
    const args = buildXcodebuildArgs(cfg, udid);
    const env = { ...process.env, ...(cfg.developerDir ? { DEVELOPER_DIR: cfg.developerDir } : {}) };
    this.xcbTail = '';
    let child: ChildLike;
    try {
      child = this.spawnImpl('xcodebuild', args, { env, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (err) {
      log('warn', 'xcodebuild spawn 异常', {
        error: err instanceof Error ? err.message : String(err),
      });
      return;
    }
    const onChunk = (chunk: Buffer | string): void => {
      const text = chunk.toString();
      this.xcbTail = (this.xcbTail + text).slice(-4_000);
      if (text.includes(WDA_SERVER_URL_MARKER)) {
        log('info', 'WDA 就绪标志出现（ServerURLHere）', { udid });
      }
    };
    child.stdout?.on('data', onChunk);
    child.stderr?.on('data', onChunk);
    child.on('error', (err) => {
      log('warn', 'xcodebuild 启动失败', { error: err.message });
      if (this.xcbChild === child) this.xcbChild = null;
    });
    child.on('exit', (code) => {
      // 正常路径下 test 会话常驻不退；退出即 WDA 一起没了
      log('warn', 'xcodebuild 退出（WDA 随之下线）', { code });
      if (this.xcbChild === child) this.xcbChild = null;
    });
    this.xcbChild = child;
    log('info', 'xcodebuild 自启中（WDA 冷启动约 60-90s）', { udid, project: cfg.projectPath });
  }

  private killChildren(reason: string): void {
    if (this.iproxyChild || this.xcbChild) {
      log('info', 'WDA 子进程下线', { reason });
    }
    try {
      this.iproxyChild?.kill('SIGTERM');
    } catch {
      /* 已退无妨 */
    }
    try {
      this.xcbChild?.kill('SIGTERM');
    } catch {
      /* 已退无妨 */
    }
    this.iproxyChild = null;
    this.xcbChild = null;
  }

  /** 进程退出清理：只杀本进程 spawn 的子进程（用户手起的 xcodebuild 不动） */
  stop(): void {
    this.stopped = true;
    this.killChildren('agent 停止');
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
