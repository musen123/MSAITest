/**
 * ScrcpySession 生命周期状态机单测（契约 §3.1）—— 纯逻辑，不起真 scrcpy / adb。
 *
 * 只覆盖不触发 IO 的状态守卫与安全 no-op：
 *  - 初始 idle
 *  - stop() 从 idle → stopped（纯 no-op，不碰 adb）
 *  - start() 仅允许从 idle 启动（非 idle 抛 ScrcpyError）
 *  - writeControl 在 socket 未就绪时安全丢弃（不抛）
 *  - onVideoBytes 注册可幂等替换回调
 * 真起 server / 连 socket / dummy-strip 端到端留给 Verify（真机/模拟器）。
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { ScrcpyError, ScrcpySession } from '../src/scrcpy.js';
import type { ScrcpySessionOptions } from '../src/scrcpy.js';

const OPTS: ScrcpySessionOptions = { serial: 'TEST-SERIAL', adbPath: 'adb' };

describe('ScrcpySession 状态机', () => {
  it('初始状态为 idle', () => {
    const s = new ScrcpySession(OPTS);
    assert.equal(s.getState(), 'idle');
  });

  it('stop() 从 idle → stopped（纯 no-op，不触发 adb IO）', async () => {
    const s = new ScrcpySession(OPTS);
    await s.stop();
    assert.equal(s.getState(), 'stopped');
  });

  it('stop() 幂等：重复调用停在 stopped', async () => {
    const s = new ScrcpySession(OPTS);
    await s.stop();
    await s.stop();
    assert.equal(s.getState(), 'stopped');
  });

  it('start() 仅允许从 idle 启动：stopped 后再 start 抛 ScrcpyError', async () => {
    const s = new ScrcpySession(OPTS);
    await s.stop(); // → stopped
    await assert.rejects(
      () => s.start(),
      (err: unknown) => err instanceof ScrcpyError && /只能从 idle/.test(err.message),
    );
    // 状态未被 start 破坏
    assert.equal(s.getState(), 'stopped');
  });
});

describe('ScrcpySession · socket 未就绪时的安全行为', () => {
  it('writeControl 在 start 前调用不抛（control socket 未就绪，静默丢弃）', () => {
    const s = new ScrcpySession(OPTS);
    assert.doesNotThrow(() => s.writeControl(new Uint8Array([1, 2, 3])));
  });

  it('onVideoBytes 注册前无缓存时不回放；可幂等替换回调', () => {
    const s = new ScrcpySession(OPTS);
    const received: Uint8Array[] = [];
    s.onVideoBytes((b) => received.push(b));
    // 尚无 video 字节流入，回调不应被调用
    assert.equal(received.length, 0);
    // 替换回调也不应抛
    assert.doesNotThrow(() => s.onVideoBytes(() => {}));
  });

  it('onClosed 注册安全（会话未运行时不触发）', () => {
    const s = new ScrcpySession(OPTS);
    let closed = false;
    assert.doesNotThrow(() => s.onClosed(() => (closed = true)));
    assert.equal(closed, false);
  });
});
