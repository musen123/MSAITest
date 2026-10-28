/**
 * scrcpy 会话（契约 §3 / §3.1）—— 以 S1 spike 的 relay.mjs 为蓝本产品化。
 *
 * 一路会话 = 一台设备的一次投屏：起 scrcpy-server 3.3.3（forward tunnel）、连
 * video + control 两个 socket、把 video 裸字节吐给上层（经 data-WS 推浏览器）、
 * 把上层收到的 control 裸字节写回设备。对外三个动作：onVideoBytes / writeControl /
 * stop。生命周期与"一次一台"gate 由 rpc.ts 的 ScrcpyManager 编排，本类只管单路。
 *
 * ── S1 运维铁律（违反=崩，逐条落地）───────────────────────────────────────
 *  1) 优雅退出：stop() 只关 socket 让 server 自己 release MediaCodec，绝不
 *     kill -9 app_process（信号不过 adb 线，编码器会被一直占，下次 SIGABRT）。
 *     关 socket 后轮询设备直到 server pid 消失，再撤 forward。
 *  2) adb forward premature-accept：`adb forward` 在设备端 server bind 前就
 *     accept 本地 TCP 并 0 字节关闭；不能拿它当就绪信号。等 server 打
 *     "INFO: Device"（bind 之前）+ settle 延时，listener 才真正就绪。
 *  3) handoff 丢字节：socket connect 瞬间就挂 data 监听 buffer 进队列，
 *     绝不等首次 pull 才挂（懒执行会丢握手字节）。
 *  4) video 首字节 dummy 0x00（forward tunnel）要 strip，库/浏览器不消费它。
 *  5) 编码器地雷：start 前检测残留 scrcpy 进程；server 启动 SIGABRT
 *     （"Aborted"/exit 134）→ 抛明确 error，绝不静默。
 *  6) 动态 forward 端口避冲突：一次一台 gate 已串行化，但动态端口 + 每次撤
 *     forward 消除残留 forward 导致的 premature-accept 误连。
 */

import { execFile, execFileSync, spawn } from 'node:child_process';
import type { ChildProcess } from 'node:child_process';
import net from 'node:net';

import { ScrcpyCodecOptions, ScrcpyOptions3_3_3 } from '@yume-chan/scrcpy';

import {
  SCRCPY_SERVER_JAR_PATH,
  SCRCPY_SERVER_VERSION,
} from './config.js';
import { log } from './log.js';

/** server 端固定的抽象 socket 名（tunnel_forward 无 scid 时即 localabstract:scrcpy） */
const REMOTE_ABSTRACT = 'localabstract:scrcpy';
/** server jar 在设备侧的推送落点 */
const REMOTE_JAR = '/data/local/tmp/scrcpy-server.jar';

/** 等 "INFO: Device" 行的上限（超时按已启动继续尝试连 socket 兜底） */
const INFO_WAIT_MS = 6_000;
/** INFO 之后的 settle 延时：listener 在此窗口内完成 bind（S1 铁律 #2） */
const SETTLE_MS = 1_500;
/** socket 连接重试：每 100ms 一次 */
const CONNECT_RETRY = 30;
const CONNECT_RETRY_INTERVAL_MS = 100;
/** 优雅关闭轮询：等设备侧 server pid 消失（30 × 200ms = 6s 上限） */
const SHUTDOWN_POLL_TIMES = 30;
const SHUTDOWN_POLL_INTERVAL_MS = 200;
/** 单次 adb 同步调用超时（ps/forward 等短命令） */
const ADB_SYNC_TIMEOUT_MS = 5_000;

export interface ScrcpySessionOptions {
  /** 设备 serial（adb -s 目标） */
  serial: string;
  /** adb 可执行路径 */
  adbPath: string;
  /** 帧率上限（缺省 30） */
  maxFps?: number;
  /** 视频码率 bps（缺省 4Mbps，真机 1080p 的合理起点） */
  bitRate?: number;
  /** 长边像素上限（缺省 1080） */
  maxSize?: number;
}

/** 会话状态机（生命周期由 ScrcpyManager 编排，本枚举供纯逻辑单测断言） */
export type ScrcpySessionState = 'idle' | 'starting' | 'running' | 'stopping' | 'stopped';

/** scrcpy 启动/运行期的明确错误（区别于隐性异常，rpc 层据此回具体 error） */
export class ScrcpyError extends Error {
  /** 附加信息，随 rpc_response.error 透传给网关（如 busy 时的 active_session_id） */
  readonly detail: Record<string, unknown> | undefined;

  constructor(message: string, detail?: Record<string, unknown>) {
    super(message);
    this.name = 'ScrcpyError';
    this.detail = detail;
  }
}

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

/**
 * setupForward 互斥链：pickFreePort 释放端口到 adb forward 真正占用之间有竞态
 * 窗口——多设备并行 start 时两路会话可能拿到同一端口，而 `adb forward` 允许
 * rebind，后果是第二台**静默偷走**第一台的转发（不报错）。把「挑端口→forward」
 * 整段串行化（仅安卓路径，毫秒级，不伤并行度）。
 */
let forwardChain: Promise<void> = Promise.resolve();

/**
 * 动态挑一个可用本地 TCP 端口：bind :0 让内核分配，取到端口号后立即释放。
 */
function pickFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const addr = srv.address();
      if (addr && typeof addr === 'object') {
        const port = addr.port;
        srv.close(() => resolve(port));
      } else {
        srv.close(() => reject(new ScrcpyError('无法分配本地端口')));
      }
    });
  });
}

/**
 * 单路 scrcpy 投屏会话。start() 成功后进入 running；video 字节经 onVideoBytes
 * 回调持续吐出，writeControl 把控制字节写回设备。stop() 优雅关闭（幂等）。
 */
export class ScrcpySession {
  private state: ScrcpySessionState = 'idle';
  private serverProc: ChildProcess | undefined;
  private videoSocket: net.Socket | undefined;
  private controlSocket: net.Socket | undefined;
  private forwardPort: number | undefined;
  private videoCb: ((bytes: Uint8Array) => void) | undefined;
  /** video 首字节 dummy 0x00 只 strip 一次（S1 铁律 #4） */
  private dummyStripped = false;
  /** onVideoBytes 尚未注册前先缓存 video 字节，注册后回放（避免丢首包） */
  private pendingVideo: Uint8Array[] = [];
  private readonly serverLog: string[] = [];
  /** 见过 server "INFO: Device" 行（就绪信号，S1 铁律 #2） */
  private sawInfo = false;
  /** 等 INFO 行就绪的 waiter 们（INFO 到达时一次性 resolve 并清空） */
  private infoWaiters: Array<() => void> = [];
  /** 会话自死（video socket 断/server 退出）通知，供编排层联动拆 data-WS + 释放 gate */
  private closedCb: (() => void) | undefined;

  constructor(private readonly opts: ScrcpySessionOptions) {}

  getState(): ScrcpySessionState {
    return this.state;
  }

  /** 注册 video 字节回调；注册前缓存的字节立即回放（幂等替换回调） */
  onVideoBytes(cb: (bytes: Uint8Array) => void): void {
    this.videoCb = cb;
    if (this.pendingVideo.length) {
      const buffered = this.pendingVideo;
      this.pendingVideo = [];
      for (const chunk of buffered) cb(chunk);
    }
  }

  /**
   * 注册会话自死回调：video socket 断开或 server 自行退出（非本方 stop 触发）时调用一次。
   * 编排层据此联动关 data-WS + 释放"一次一台"gate（不留僵尸会话占位）。
   */
  onClosed(cb: () => void): void {
    this.closedCb = cb;
  }

  /** 把控制裸字节写回设备（浏览器 → 设备方向）。socket 未就绪时静默丢弃 */
  writeControl(bytes: Uint8Array): void {
    const sock = this.controlSocket;
    if (!sock || sock.destroyed || !sock.writable) return;
    sock.write(bytes);
  }

  private adbArgs(args: string[]): string[] {
    return ['-s', this.opts.serial, ...args];
  }

  private adbSync(args: string[]): string {
    return execFileSync(this.opts.adbPath, this.adbArgs(args), {
      encoding: 'utf-8',
      timeout: ADB_SYNC_TIMEOUT_MS,
    });
  }

  /** 设备侧是否还有本 serial 的 scrcpy Server 进程存活 */
  private serverIsRunning(): boolean {
    try {
      const out = this.adbSync([
        'shell',
        'ps -A -o PID,ARGS | grep com.genymobile.scrcpy.Server | grep -v grep',
      ]);
      return out.trim().length > 0;
    } catch {
      return false; // grep 无匹配 exit 1，execFileSync 抛错 = 无残留
    }
  }

  /**
   * 起会话：检测残留 → 动态 forward → 推 jar 起 server → 等就绪 →
   * 连 video/control（handoff 立即挂监听）→ 进入 running。
   * 任一步失败：清理已占资源并抛 ScrcpyError。
   */
  async start(): Promise<void> {
    if (this.state !== 'idle') {
      throw new ScrcpyError(`会话状态非法: ${this.state}（只能从 idle 启动）`);
    }
    this.state = 'starting';
    try {
      await this.ensureNoResidualServer();
      await this.setupForward();
      this.spawnServer();
      await this.waitServerReady();
      await this.connectSockets();
      this.state = 'running';
      log('info', 'scrcpy 会话就绪', { serial: this.opts.serial, port: this.forwardPort });
    } catch (err) {
      // 启动失败也要优雅清理，绝不留半开 socket / 残留 forward / 烧编码器的 server
      await this.cleanup();
      this.state = 'stopped';
      if (err instanceof ScrcpyError) throw err;
      const message = err instanceof Error ? err.message : String(err);
      throw new ScrcpyError(`scrcpy 启动失败: ${message}`);
    }
  }

  /**
   * start 前的残留检测（S1 铁律 #5）：设备上还有 server 说明上次没优雅退出。
   * 接管场景（stop 旧 → 立即 start 新）下旧 server 优雅退出需要 1-2s——先给
   * 一个等待窗口轮询到退干净，仍存活才判"真残留"报错。
   */
  private async ensureNoResidualServer(): Promise<void> {
    const RESIDUAL_WAIT_MS = 4_000;
    const POLL_MS = 250;
    const deadline = Date.now() + RESIDUAL_WAIT_MS;
    while (this.serverIsRunning()) {
      if (Date.now() >= deadline) {
        throw new ScrcpyError(
          `设备 ${this.opts.serial} 上残留 scrcpy-server 进程（上次未优雅退出，编码器可能被占）——` +
            `请断开该设备所有投屏或重启设备后重试`,
        );
      }
      await sleep(POLL_MS);
    }
  }

  private async setupForward(): Promise<void> {
    // 「挑端口→forward」全段挂互斥链：防并行 start 撞端口被 adb rebind 偷流
    const run = forwardChain.then(async () => {
      const port = await pickFreePort();
      this.forwardPort = port;
      // 幂等清一次同端口的残留 forward（动态端口下极少命中，防御性）
      try {
        this.adbSync(['forward', '--remove', `tcp:${port}`]);
      } catch {
        /* 无残留 forward 时报错，忽略 */
      }
      this.adbSync(['forward', `tcp:${port}`, REMOTE_ABSTRACT]);
    });
    forwardChain = run.catch(() => {}); // 链只传播时序，不传播失败
    await run;
  }

  private buildServerArgs(): string[] {
    const { maxFps = 30, bitRate = 4_000_000, maxSize = 1080 } = this.opts;
    // 用 @yume-chan/scrcpy 的 3.3.3 选项序列化 server 参数：与浏览器侧解码用的
    // ScrcpyOptions3_3_3 同源，保证 server 参数 ↔ 客户端解析假设一致（S1 核心赌注前提），
    // 版本升级时二者一起动，不会漂。control 默认 true、tunnel_forward 显式开。
    //
    // 强制 H264 Baseline + 无 B 帧（profile=1,max-bframes=0）：非安全上下文（内网
    // http 访问）浏览器无 WebCodecs，前端回退 TinyH264 纯软解，而 TinyH264 只吃
    // Baseline（无 B 帧/CABAC）。设备默认常编 Main/High → 软解黑屏；钉 Baseline
    // 让软解在任何设备上都能解，WebCodecs 硬解同样兼容，代价仅极小压缩率损失。
    return new ScrcpyOptions3_3_3({
      audio: false,
      control: true,
      tunnelForward: true,
      maxSize,
      videoBitRate: bitRate,
      maxFps,
      videoCodecOptions: new ScrcpyCodecOptions({ profile: 1, maxBframes: 0 }),
    }).serialize();
  }

  private spawnServer(): void {
    // jar 已在 config 启动校验过 sha256；此处推到设备再起。
    this.adbSync(['push', SCRCPY_SERVER_JAR_PATH, REMOTE_JAR]);
    const args = this.adbArgs([
      'shell',
      `CLASSPATH=${REMOTE_JAR}`,
      'app_process',
      '/',
      'com.genymobile.scrcpy.Server',
      SCRCPY_SERVER_VERSION,
      ...this.buildServerArgs(),
    ]);
    const proc = spawn(this.opts.adbPath, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    this.serverProc = proc;
    proc.stdout?.on('data', (d: Buffer) => {
      const s = d.toString();
      this.serverLog.push(s);
      if (!this.sawInfo && s.includes('INFO: Device')) {
        this.sawInfo = true;
        for (const r of this.infoWaiters) r();
        this.infoWaiters = [];
      }
    });
    proc.stderr?.on('data', (d: Buffer) => this.serverLog.push(d.toString()));
    proc.on('exit', (code, sig) => this.serverLog.push(`[exit] code=${code} sig=${sig}`));
  }

  /** 等 "INFO: Device" + settle（S1 铁律 #2），并检测启动即 SIGABRT（铁律 #5） */
  private async waitServerReady(): Promise<void> {
    await Promise.race([
      new Promise<void>((r) => {
        if (this.sawInfo) r();
        else this.infoWaiters.push(r);
      }),
      sleep(INFO_WAIT_MS),
    ]);
    await sleep(SETTLE_MS);
    // SIGABRT（模拟器软编重入必崩，真机待复验）→ 明确报错不静默
    if (this.serverLog.some((s) => s.includes('Aborted'))) {
      throw new ScrcpyError(
        'scrcpy-server 启动 SIGABRT（编码器被占/软编重入）——' +
          '真机重试或重启设备；模拟器需 adb emu kill 重启后重推 jar',
      );
    }
    // server 进程已退出（非 SIGABRT 的其它启动失败）也要明确报错
    if (this.serverProc && this.serverProc.exitCode !== null) {
      throw new ScrcpyError(
        `scrcpy-server 启动即退出（exit=${this.serverProc.exitCode}）: ${this.tailLog()}`,
      );
    }
  }

  private tailLog(): string {
    return this.serverLog.slice(-4).join(' ').replace(/\s+/g, ' ').slice(0, 300);
  }

  private connect(label: 'video' | 'control'): Promise<net.Socket> {
    const port = this.forwardPort;
    if (port === undefined) return Promise.reject(new ScrcpyError('forward 端口未就绪'));
    return new Promise((resolve, reject) => {
      const attempt = (left: number): void => {
        const sock = net.connect({ host: '127.0.0.1', port }, () => {
          sock.setNoDelay(true);
          resolve(sock);
        });
        sock.once('error', (err: Error) => {
          if (left <= 0) reject(new ScrcpyError(`[${label}] 连接失败: ${err.message}`));
          else setTimeout(() => attempt(left - 1), CONNECT_RETRY_INTERVAL_MS);
        });
      };
      attempt(CONNECT_RETRY);
    });
  }

  /**
   * 连 video（先）+ control（后），顺序与 server 端 accept 顺序一致。
   * video socket connect 瞬间即挂 data 监听（handoff 铁律 #3），strip 首字节 dummy。
   */
  private async connectSockets(): Promise<void> {
    const video = await this.connect('video');
    this.videoSocket = video;
    // 立即挂监听：绝不等回调注册/首次 pull（懒执行会丢握手字节）
    video.on('data', (chunk: Buffer) => this.handleVideoChunk(chunk));
    video.on('error', (e: Error) =>
      log('warn', 'video socket 错误', { serial: this.opts.serial, error: e.message }),
    );
    video.on('close', () => {
      // 会话自死（server 退出/设备断开）：只在运行态通知编排层，由其联动拆
      // data-WS + 释放 gate（编排层的 teardown 会回调本会话 stop()，此处不自 stop
      // 避免与 teardown 的 stop 竞争，也不让 running→stopped 绕过编排层）。
      if (this.state === 'running') {
        log('info', 'video socket 关闭，会话自死', { serial: this.opts.serial });
        this.closedCb?.();
      }
    });

    const control = await this.connect('control');
    this.controlSocket = control;
    control.on('error', (e: Error) =>
      log('warn', 'control socket 错误', { serial: this.opts.serial, error: e.message }),
    );
  }

  /** 处理一块 video 字节：首块 strip dummy 0x00，然后吐给回调（或先缓存） */
  private handleVideoChunk(chunk: Buffer): void {
    let out: Uint8Array = chunk;
    if (!this.dummyStripped) {
      this.dummyStripped = true;
      out = chunk.subarray(1); // forward tunnel dummy byte
      if (out.length === 0) return;
    }
    if (this.videoCb) {
      this.videoCb(out);
    } else {
      // 回调尚未注册：缓存，onVideoBytes 注册时回放（避免丢 metadata 头字节）
      this.pendingVideo.push(new Uint8Array(out));
    }
  }

  /**
   * 优雅停止（幂等）：关 socket 让 server release 编码器 → 轮询设备直到 pid 消失
   * → SIGTERM 兜底 adb 子进程 → 撤 forward。S1 铁律 #1。
   */
  async stop(): Promise<void> {
    // idle（从未 start）无资源可释放，直接置 stopped——纯 no-op，不碰 adb
    if (this.state === 'idle') {
      this.state = 'stopped';
      return;
    }
    if (this.state === 'stopping' || this.state === 'stopped') return;
    this.state = 'stopping';
    await this.cleanup();
    this.state = 'stopped';
    log('info', 'scrcpy 会话已优雅停止', { serial: this.opts.serial });
  }

  /** 释放所有资源；start 失败与 stop 共用，必须对半开状态健壮 */
  private async cleanup(): Promise<void> {
    // 1) 关 socket → server 见 broken pipe 自己 release MediaCodec（绝不 kill app_process）
    try {
      this.controlSocket?.destroy();
    } catch {
      /* ignore */
    }
    try {
      this.videoSocket?.destroy();
    } catch {
      /* ignore */
    }
    // 2) 轮询设备侧 server pid 消失（确认编码器已 release）
    for (let i = 0; i < SHUTDOWN_POLL_TIMES; i++) {
      if (!this.serverIsRunning()) break;
      await sleep(SHUTDOWN_POLL_INTERVAL_MS);
    }
    // 3) SIGTERM 兜底本地 adb 子进程（不影响设备侧，仅清进程句柄）
    try {
      this.serverProc?.kill('SIGTERM');
    } catch {
      /* ignore */
    }
    // 4) 撤 forward（异步，不阻塞停止路径）
    if (this.forwardPort !== undefined) {
      const port = this.forwardPort;
      execFile(this.opts.adbPath, this.adbArgs(['forward', '--remove', `tcp:${port}`]), () => {
        /* best-effort */
      });
    }
    this.videoSocket = undefined;
    this.controlSocket = undefined;
    this.serverProc = undefined;
    this.videoCb = undefined;
    this.pendingVideo = [];
  }
}
