/**
 * 投屏编排单测（契约 §3.1）—— 纯逻辑，不起真 scrcpy / 真 WS：
 *  - 一次一台 gate（已有活跃 → busy）
 *  - bounded-queue 丢帧决策（WS bufferedAmount 超阈值丢视频帧，计数）
 *  - 会话生命周期状态机（start→running→stop 释放 gate；start 失败释放 gate；
 *    data-WS 关闭联动停会话；隧道断开 stopAll 清所有）
 *
 * 用 fake ScrcpySession + fake DataWs（依赖注入），断言 gate/丢帧/生命周期，
 * 真 adb/scrcpy/网络留给 Verify。
 */

import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';

import type { AgentConfig } from '../src/config.js';
import { ScrcpyError } from '../src/scrcpy.js';
import { ScrcpyManager } from '../src/scrcpy_manager.js';
import type {
  DataWs,
  ScrcpySessionLike,
} from '../src/scrcpy_manager.js';
import type { ScrcpySessionOptions } from '../src/scrcpy.js';

const WS_OPEN = 1;
const WS_CONNECTING = 0;

const CFG: AgentConfig = {
  platformWsUrl: 'wss://platform.example.com/api/v1/app/agents/ws',
  agentToken: 'tok-123',
  hostFingerprint: 'fp',
  adbPath: 'adb',
};

/** 可控 fake data-WS：手动调 bufferedAmount / readyState / 触发事件 */
class FakeDataWs implements DataWs {
  bufferedAmount = 0;
  readyState = WS_OPEN;
  sent: Uint8Array[] = [];
  closed = false;
  closeCode: number | undefined;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private handlers: Record<string, Array<(...args: any[]) => void>> = {};

  send(data: Uint8Array): void {
    if (this.readyState !== WS_OPEN) throw new Error('WS not open');
    this.sent.push(data);
  }
  close(code?: number): void {
    this.closed = true;
    this.closeCode = code;
    this.readyState = 3;
  }
  on(event: 'open', cb: () => void): void;
  on(event: 'message', cb: (data: Buffer, isBinary: boolean) => void): void;
  on(event: 'close', cb: (code: number, reason: Buffer) => void): void;
  on(event: 'error', cb: (err: Error) => void): void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  on(event: string, cb: (...args: any[]) => void): void {
    (this.handlers[event] ??= []).push(cb);
  }
  emit(event: 'open'): void;
  emit(event: 'message', data: Buffer, isBinary: boolean): void;
  emit(event: 'close', code: number, reason: Buffer): void;
  emit(event: 'error', err: Error): void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  emit(event: string, ...args: any[]): void {
    for (const cb of this.handlers[event] ?? []) cb(...args);
  }
}

/** 可控 fake ScrcpySession：捕获 video 回调，记录 start/stop/writeControl */
class FakeSession implements ScrcpySessionLike {
  started = false;
  stopped = false;
  startError: Error | undefined;
  videoCb: ((bytes: Uint8Array) => void) | undefined;
  closedCb: (() => void) | undefined;
  controlWrites: Uint8Array[] = [];

  async start(): Promise<void> {
    if (this.startError) throw this.startError;
    this.started = true;
  }
  async stop(): Promise<void> {
    this.stopped = true;
  }
  onVideoBytes(cb: (bytes: Uint8Array) => void): void {
    this.videoCb = cb;
  }
  onClosed(cb: () => void): void {
    this.closedCb = cb;
  }
  writeControl(bytes: Uint8Array): void {
    this.controlWrites.push(bytes);
  }
  /** 模拟设备吐一帧视频 */
  pushVideo(bytes: Uint8Array): void {
    this.videoCb?.(bytes);
  }
  /** 模拟会话自死（video socket 断/server 退出） */
  die(): void {
    this.closedCb?.();
  }
}

/** 装配一个用 fake 工厂的 manager，返回 manager 与最近一次工厂产出的句柄 */
function makeManager(backpressureBytes = 4 * 1024 * 1024): {
  manager: ScrcpyManager;
  sessions: FakeSession[];
  wsList: FakeDataWs[];
  lastSessionOpts: () => ScrcpySessionOptions | undefined;
} {
  const sessions: FakeSession[] = [];
  const wsList: FakeDataWs[] = [];
  let lastOpts: ScrcpySessionOptions | undefined;
  const manager = new ScrcpyManager(CFG, {
    backpressureBytes,
    createSession: (opts) => {
      lastOpts = opts;
      const s = new FakeSession();
      sessions.push(s);
      return s;
    },
    createDataWs: () => {
      const ws = new FakeDataWs();
      wsList.push(ws);
      return ws;
    },
  });
  return { manager, sessions, wsList, lastSessionOpts: () => lastOpts };
}

describe('ScrcpyManager · 一台设备一路 gate（契约 §3.1）', () => {
  it('无活跃会话时 start 成功，进入活跃态', async () => {
    const { manager, sessions } = makeManager();
    const res = await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    assert.deepEqual(res, { started: true });
    assert.equal(manager.hasActiveSession(), true);
    assert.equal(manager.isSessionActive('sess-1'), true);
    assert.equal(manager.hasSessionForSerial('S1'), true);
    assert.equal(sessions[0]?.started, true);
  });

  it('同设备第 2 路 start 抛 ScrcpyError("busy") 附旧会话 id', async () => {
    const { manager } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    await assert.rejects(
      () => manager.startScrcpy({ serial: 'S1', sessionId: 'sess-2' }),
      (err: unknown) =>
        err instanceof ScrcpyError &&
        err.message === 'busy' &&
        (err.detail as { active_session_id?: string } | undefined)?.active_session_id ===
          'sess-1',
    );
    // 第 2 个被拒后原会话仍活跃、未被顶替
    assert.equal(manager.isSessionActive('sess-1'), true);
  });

  it('不同设备并行 start 全成功，数据面各走各（多设备核心）', async () => {
    const { manager, sessions, wsList } = makeManager(1000);
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    await manager.startScrcpy({ serial: 'S2', sessionId: 'sess-2' });
    assert.equal(sessions.length, 2);
    assert.equal(manager.isSessionActive('sess-1'), true);
    assert.equal(manager.isSessionActive('sess-2'), true);
    // 各自 video 走各自 WS
    sessions[0]!.pushVideo(new Uint8Array([1]));
    sessions[1]!.pushVideo(new Uint8Array([2, 2]));
    assert.equal(wsList[0]!.sent.length, 1);
    assert.equal(wsList[1]!.sent.length, 1);
    assert.equal(manager.statsOf('sess-1')?.videoBytesForwarded, 1);
    assert.equal(manager.statsOf('sess-2')?.videoBytesForwarded, 2);
    // 各自控制字节回各自设备
    wsList[1]!.emit('message', Buffer.from([7]), true);
    assert.equal(sessions[0]!.controlWrites.length, 0);
    assert.equal(sessions[1]!.controlWrites.length, 1);
  });

  it('同一 tick 同设备并发两个 start：先落骨架，第 2 个立即 busy（gate 无穿透）', async () => {
    const { manager, sessions } = makeManager();
    const p1 = manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    const p2 = manager.startScrcpy({ serial: 'S1', sessionId: 'sess-2' });
    const results = await Promise.allSettled([p1, p2]);
    const rejected = results.filter((r) => r.status === 'rejected');
    assert.equal(rejected.length, 1);
    assert.ok(
      rejected[0]?.status === 'rejected' &&
        rejected[0].reason instanceof ScrcpyError &&
        rejected[0].reason.message === 'busy',
    );
    // 只起了一路真会话
    assert.equal(sessions.length, 1);
  });

  it('控制字节旁观者按 sessionId 路由（双会话 tee 不串台）', async () => {
    const { manager, wsList } = makeManager();
    const seen: Array<{ sessionId: string; byte: number }> = [];
    manager.setControlObserver((sessionId, data) => {
      seen.push({ sessionId, byte: data[0]! });
    });
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    await manager.startScrcpy({ serial: 'S2', sessionId: 'sess-2' });
    wsList[0]!.emit('message', Buffer.from([11]), true);
    wsList[1]!.emit('message', Buffer.from([22]), true);
    assert.deepEqual(seen, [
      { sessionId: 'sess-1', byte: 11 },
      { sessionId: 'sess-2', byte: 22 },
    ]);
  });

  it('start 传入的会话参数透传（serial/adbPath/maxFps/bitRate）', async () => {
    const { manager, lastSessionOpts } = makeManager();
    await manager.startScrcpy({
      serial: 'DEV9',
      sessionId: 's',
      maxFps: 24,
      bitRate: 2_000_000,
    });
    const opts = lastSessionOpts();
    assert.equal(opts?.serial, 'DEV9');
    assert.equal(opts?.adbPath, 'adb');
    assert.equal(opts?.maxFps, 24);
    assert.equal(opts?.bitRate, 2_000_000);
  });
});

describe('ScrcpyManager · bounded-queue 丢帧（契约 §3.1 / S1 backpressure）', () => {
  it('WS 缓冲低于阈值 → 视频帧经 WS 推出', async () => {
    const { manager, sessions, wsList } = makeManager(1000);
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    wsList[0]!.bufferedAmount = 500;
    sessions[0]!.pushVideo(new Uint8Array([1, 2, 3]));
    assert.equal(wsList[0]!.sent.length, 1);
    const stats = manager.statsOf('sess-1');
    assert.equal(stats?.videoFramesForwarded, 1);
    assert.equal(stats?.videoBytesForwarded, 3);
    assert.equal(stats?.videoFramesDropped, 0);
  });

  it('WS 缓冲超阈值 → 丢该帧并计数（不 send）', async () => {
    const { manager, sessions, wsList } = makeManager(1000);
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    wsList[0]!.bufferedAmount = 1001; // 超阈值
    sessions[0]!.pushVideo(new Uint8Array([1, 2, 3, 4]));
    assert.equal(wsList[0]!.sent.length, 0);
    const stats = manager.statsOf('sess-1');
    assert.equal(stats?.videoFramesDropped, 1);
    assert.equal(stats?.videoFramesForwarded, 0);
  });

  it('缓冲回落到阈值内 → 恢复推流（丢帧是瞬时决策不是永久停）', async () => {
    const { manager, sessions, wsList } = makeManager(1000);
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    wsList[0]!.bufferedAmount = 2000;
    sessions[0]!.pushVideo(new Uint8Array([9])); // 丢
    wsList[0]!.bufferedAmount = 100;
    sessions[0]!.pushVideo(new Uint8Array([8])); // 推
    const stats = manager.statsOf('sess-1');
    assert.equal(stats?.videoFramesDropped, 1);
    assert.equal(stats?.videoFramesForwarded, 1);
    assert.equal(wsList[0]!.sent.length, 1);
  });

  it('WS 未 OPEN（握手中）→ 丢帧不 send', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    wsList[0]!.readyState = WS_CONNECTING;
    sessions[0]!.pushVideo(new Uint8Array([1]));
    assert.equal(wsList[0]!.sent.length, 0);
    assert.equal(manager.statsOf('sess-1')?.videoFramesDropped, 1);
  });
});

describe('ScrcpyManager · 控制字节回写（WS → 设备）', () => {
  it('data-WS 二进制帧 → writeControl 到设备并计数', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    wsList[0]!.emit('message', Buffer.from([10, 20, 30]), true);
    assert.equal(sessions[0]!.controlWrites.length, 1);
    assert.deepEqual([...sessions[0]!.controlWrites[0]!], [10, 20, 30]);
    assert.equal(manager.statsOf('sess-1')?.controlBytesReceived, 3);
  });

  it('data-WS 文本帧（isBinary=false）→ 忽略，不写设备', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    wsList[0]!.emit('message', Buffer.from('hello'), false);
    assert.equal(sessions[0]!.controlWrites.length, 0);
  });
});

describe('ScrcpyManager · 会话生命周期状态机（契约 §3.1）', () => {
  it('stop_scrcpy 优雅停对应会话 + 关 WS + 释放 gate', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    const res = await manager.stopScrcpy('sess-1');
    assert.deepEqual(res, { stopped: true });
    assert.equal(sessions[0]!.stopped, true);
    assert.equal(wsList[0]!.closed, true);
    assert.equal(manager.hasActiveSession(), false);
    // gate 已释放：同设备可再起新会话
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-2' });
    assert.equal(manager.isSessionActive('sess-2'), true);
  });

  it('stop_scrcpy 目标会话不存在 → 幂等回 stopped，不误停当前会话', async () => {
    const { manager, sessions } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    const res = await manager.stopScrcpy('sess-OTHER');
    assert.deepEqual(res, { stopped: true });
    // 当前会话未被误停
    assert.equal(sessions[0]!.stopped, false);
    assert.equal(manager.hasActiveSession(), true);
  });

  it('start 失败（scrcpy 起不来）→ 清理并释放 gate，异常上抛', async () => {
    const sessions: FakeSession[] = [];
    const wsList: FakeDataWs[] = [];
    const manager = new ScrcpyManager(CFG, {
      createSession: () => {
        const s = new FakeSession();
        s.startError = new ScrcpyError('scrcpy-server 启动 SIGABRT');
        sessions.push(s);
        return s;
      },
      createDataWs: () => {
        const ws = new FakeDataWs();
        wsList.push(ws);
        return ws;
      },
    });
    await assert.rejects(
      () => manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' }),
      (err: unknown) => err instanceof ScrcpyError && err.message.includes('SIGABRT'),
    );
    // gate 释放，WS 已关，可重试
    assert.equal(manager.hasActiveSession(), false);
    assert.equal(wsList[0]!.closed, true);
  });

  it('data-WS 关闭（浏览器断开）→ 只联动停自己的会话，另一台不受影响', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    await manager.startScrcpy({ serial: 'S2', sessionId: 'sess-2' });
    wsList[0]!.emit('close', 1006, Buffer.from(''));
    // teardown 是 async，让微任务跑完
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(sessions[0]!.stopped, true);
    assert.equal(sessions[1]!.stopped, false); // S2 原样活跃
    assert.equal(manager.isSessionActive('sess-2'), true);
    assert.equal(manager.isSessionActive('sess-1'), false);
  });

  it('会话自死（video socket 断/server 退出）→ 联动拆：关 WS + 释放 gate', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    sessions[0]!.die();
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(sessions[0]!.stopped, true);
    assert.equal(wsList[0]!.closed, true);
    assert.equal(manager.hasActiveSession(), false);
  });

  it('stopAll（隧道断开/进程退出）→ 并行清全部会话，单条 stop 抛错不阻其余', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    await manager.startScrcpy({ serial: 'S2', sessionId: 'sess-2' });
    sessions[0]!.stop = async () => {
      sessions[0]!.stopped = true;
      throw new Error('stop boom');
    };
    await manager.stopAll('tunnel_close_1006'); // 不应抛
    assert.equal(sessions[0]!.stopped, true);
    assert.equal(sessions[1]!.stopped, true);
    assert.equal(wsList[0]!.closed, true);
    assert.equal(wsList[1]!.closed, true);
    assert.equal(manager.hasActiveSession(), false);
  });

  it('stopAll 无活跃会话时安全 no-op', async () => {
    const { manager } = makeManager();
    await manager.stopAll('shutdown');
    assert.equal(manager.hasActiveSession(), false);
  });

  it('teardown 幂等：WS close 与显式 stop 双触发只停一次', async () => {
    const { manager, sessions, wsList } = makeManager();
    await manager.startScrcpy({ serial: 'S1', sessionId: 'sess-1' });
    // 先 WS close 触发 teardown，再显式 stopScrcpy
    wsList[0]!.emit('close', 1000, Buffer.from(''));
    await Promise.resolve();
    let stopCalls = 0;
    const orig = sessions[0]!.stop.bind(sessions[0]!);
    sessions[0]!.stop = async () => {
      stopCalls += 1;
      return orig();
    };
    await manager.stopScrcpy('sess-1');
    // WS close 已 teardown 并释放 gate，stopScrcpy 走幂等分支不再停第二次
    assert.equal(stopCalls, 0);
  });
});
