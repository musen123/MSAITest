/** AutomationManager 单测：一台设备一路 gate + 多设备并行 + 取消闭环 + 生命周期（假会话 DI） */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import type { StepResult } from '../src/automation.js';
import {
  AutomationBusyError,
  AutomationManager,
  type AutomationSessionLike,
} from '../src/automation_manager.js';

const BASE = {
  serial: 'emulator-5554',
  model: { name: 'm', baseUrl: 'http://u', apiKey: 'k', family: 'doubao-seed' },
};
const SERIAL_B = 'RMX3617-device';

class FakeSession implements AutomationSessionLike {
  disposed = false;
  lastSignal?: AbortSignal;
  constructor(private readonly opt: { hang?: boolean; disposeError?: boolean } = {}) {}
  runStep(instruction: string, signal?: AbortSignal): Promise<StepResult> {
    this.lastSignal = signal;
    const result: StepResult = { status: 'ok', summary: instruction, steps: [], yamlFlow: '' };
    if (!this.opt.hang) return Promise.resolve(result);
    return new Promise((resolve) => {
      if (signal?.aborted) return resolve(result);
      signal?.addEventListener('abort', () => resolve(result), { once: true });
    });
  }
  runYaml(yaml: string): Promise<{ status: 'ok' | 'error'; result?: unknown; error?: string }> {
    return Promise.resolve({ status: 'ok', result: { yamlLength: yaml.length } });
  }
  reportHtml(): string | null {
    return '<html>';
  }
  async dispose(): Promise<void> {
    this.disposed = true;
    if (this.opt.disposeError) throw new Error('dispose boom');
  }
}

function makeManager(factory?: (serial: string) => FakeSession) {
  const created: FakeSession[] = [];
  const mgr = new AutomationManager({
    createSession: (p) => {
      const s = factory ? factory(p.serial) : new FakeSession();
      created.push(s);
      return s;
    },
  });
  return { mgr, created };
}

describe('AutomationManager', () => {
  it('首步建会话并回结果，activeSessionIds 落位', async () => {
    const { mgr, created } = makeManager();
    const res = await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'open settings' });
    assert.equal(res.status, 'ok');
    assert.equal(res.summary, 'open settings');
    assert.equal(created.length, 1);
    assert.deepEqual(mgr.activeSessionIds(), ['s1']);
    assert.equal(mgr.hasSessionForSerial(BASE.serial), true);
    assert.equal(mgr.hasSessionForSerial(SERIAL_B), false);
  });

  it('同会话复用同一 AutomationSession', async () => {
    const { mgr, created } = makeManager();
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'b' });
    assert.equal(created.length, 1);
  });

  it('同设备别的会话占用中 → AutomationBusyError 附 active_session_id', async () => {
    const { mgr } = makeManager(() => new FakeSession({ hang: true }));
    const p1 = mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    await assert.rejects(
      mgr.runStep({ ...BASE, sessionId: 's2', instruction: 'b' }),
      (err) => err instanceof AutomationBusyError && err.activeSessionId === 's1',
    );
    assert.deepEqual(mgr.abortFlow('s1'), { aborted: true }); // 放行挂起的 s1
    await p1;
  });

  it('两台设备并行执行互不阻塞（多设备核心）', async () => {
    const { mgr, created } = makeManager((serial) =>
      serial === BASE.serial ? new FakeSession({ hang: true }) : new FakeSession(),
    );
    // 设备 A 挂起在跑
    const pA = mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    await new Promise((r) => setTimeout(r, 5));
    // 设备 B 同时 runStep：不 busy、直接成功
    const resB = await mgr.runStep({
      ...BASE,
      serial: SERIAL_B,
      sessionId: 's2',
      instruction: 'b',
    });
    assert.equal(resB.status, 'ok');
    assert.equal(created.length, 2);
    assert.deepEqual(new Set(mgr.activeSessionIds()), new Set(['s1', 's2']));
    // abortFlow(s2 无在跑步骤) no-op；abort s1 放行
    assert.deepEqual(mgr.abortFlow('s2'), { aborted: false });
    assert.deepEqual(mgr.abortFlow('s1'), { aborted: true });
    await pA;
  });

  it('abortFlow 取消在跑的 step（signal.aborted 置真）', async () => {
    const fake = new FakeSession({ hang: true });
    const { mgr } = makeManager(() => fake);
    const p = mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    assert.deepEqual(mgr.abortFlow('s1'), { aborted: true });
    await p;
    assert.equal(fake.lastSignal?.aborted, true);
  });

  it('同设备旧会话空闲时，新 session_id 接管（dispose 旧、建新）', async () => {
    const { mgr, created } = makeManager(); // 非 hang：runStep 立即结束 → 旧会话空闲
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    // 投屏重连换了 session_id → 新 session 应接管而非 busy
    const res = await mgr.runStep({ ...BASE, sessionId: 's2', instruction: 'b' });
    assert.equal(res.status, 'ok');
    assert.equal(created.length, 2); // 建了两个会话
    assert.equal(created[0]!.disposed, true); // 旧会话被 dispose
    assert.deepEqual(mgr.activeSessionIds(), ['s2']);
  });

  it('跨设备绝不接管：A 空闲会话不因 B 的新会话被 dispose', async () => {
    const { mgr, created } = makeManager();
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' }); // A 空闲
    await mgr.runStep({ ...BASE, serial: SERIAL_B, sessionId: 's2', instruction: 'b' });
    assert.equal(created.length, 2);
    assert.equal(created[0]!.disposed, false); // A 的会话原样存活
    assert.deepEqual(new Set(mgr.activeSessionIds()), new Set(['s1', 's2']));
  });

  it('abortFlow 对不匹配会话是 no-op', async () => {
    const { mgr } = makeManager();
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    assert.deepEqual(mgr.abortFlow('other'), { aborted: false });
  });

  it('endSession dispose 并清对应设备槽（幂等；不影响另一台设备）', async () => {
    const { mgr, created } = makeManager();
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    await mgr.runStep({ ...BASE, serial: SERIAL_B, sessionId: 's2', instruction: 'b' });
    assert.deepEqual(await mgr.endSession('s1'), { ended: true });
    assert.equal(created[0]!.disposed, true);
    assert.equal(created[1]!.disposed, false); // B 不受影响
    assert.deepEqual(mgr.activeSessionIds(), ['s2']);
    assert.deepEqual(await mgr.endSession('s1'), { ended: false });
  });

  it('stepProgress/reportHtml 按 session 各自命中', async () => {
    class WithProgress extends FakeSession {
      constructor(private readonly tag: string) {
        super();
      }
      getProgress(afterSeq: number) {
        return { seq: afterSeq + 1, entries: [] };
      }
      override reportHtml(): string {
        return `<html>${this.tag}`;
      }
    }
    const { mgr } = makeManager((serial) => new WithProgress(serial));
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    await mgr.runStep({ ...BASE, serial: SERIAL_B, sessionId: 's2', instruction: 'b' });
    assert.equal(mgr.stepProgress('s1', 0).exists, true);
    assert.equal(mgr.stepProgress('s2', 0).exists, true);
    assert.equal(mgr.stepProgress('nope', 0).exists, false);
    assert.equal(mgr.reportHtml('s1'), `<html>${BASE.serial}`);
    assert.equal(mgr.reportHtml('s2'), `<html>${SERIAL_B}`);
  });

  it('stopAll 并行 dispose 全部会话，单条 dispose 抛错不阻其余', async () => {
    const { mgr, created } = makeManager((serial) =>
      serial === BASE.serial ? new FakeSession({ disposeError: true }) : new FakeSession(),
    );
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'a' });
    await mgr.runStep({ ...BASE, serial: SERIAL_B, sessionId: 's2', instruction: 'b' });
    await mgr.stopAll('test'); // 不应抛
    assert.equal(created[0]!.disposed, true);
    assert.equal(created[1]!.disposed, true);
    assert.deepEqual(mgr.activeSessionIds(), []);
  });
});

describe('reportFilePath（落盘报告路径透传）', () => {
  it('替身未实现 → null（RPC 走内存串兜底）；会话不匹配 → null', async () => {
    const { mgr } = makeManager();
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'x' });
    assert.equal(mgr.reportFilePath('s1'), null); // FakeSession 无 reportFilePath
    assert.equal(mgr.reportFilePath('nope'), null);
  });

  it('会话实现即透传路径', async () => {
    class WithPath extends FakeSession {
      reportFilePath(): string {
        return '/tmp/midscene_run/report/app-s1.html';
      }
    }
    const { mgr } = makeManager(() => new WithPath());
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'x' });
    assert.equal(mgr.reportFilePath('s1'), '/tmp/midscene_run/report/app-s1.html');
  });
});

describe('reapIdle（会话空闲 TTL 自愈）', () => {
  it('空闲超时的会话被 dispose（now 注入控时）', async () => {
    const { mgr, created } = makeManager();
    await mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'x' });
    assert.deepEqual(mgr.activeSessionIds(), ['s1']);
    // 未超时 → 不清
    assert.equal(mgr.reapIdle(600_000, Date.now()), 0);
    assert.deepEqual(mgr.activeSessionIds(), ['s1']);
    // 注入未来时刻使空闲 > TTL → 清 + dispose
    assert.equal(mgr.reapIdle(600_000, Date.now() + 601_000), 1);
    assert.deepEqual(mgr.activeSessionIds(), []);
    assert.equal(created[0]!.disposed, true);
  });

  it('多设备：running 的不动，空闲超时的清（一轮清一批）', async () => {
    const { mgr, created } = makeManager((serial) =>
      serial === BASE.serial ? new FakeSession({ hang: true }) : new FakeSession(),
    );
    const p = mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'x' }); // A running
    await new Promise((r) => setTimeout(r, 5));
    await mgr.runStep({ ...BASE, serial: SERIAL_B, sessionId: 's2', instruction: 'y' }); // B 空闲
    assert.equal(mgr.reapIdle(0, Date.now() + 999_999), 1); // 只清 B
    assert.deepEqual(mgr.activeSessionIds(), ['s1']);
    assert.equal(created[1]!.disposed, true);
    assert.deepEqual(mgr.abortFlow('s1'), { aborted: true });
    await p;
  });

  it('in-flight（running）会话绝不被 reap', async () => {
    const { mgr } = makeManager(() => new FakeSession({ hang: true }));
    const p = mgr.runStep({ ...BASE, sessionId: 's1', instruction: 'x' }); // 挂起
    await new Promise((r) => setTimeout(r, 5));
    // 即便远超 TTL，running 中不动
    assert.equal(mgr.reapIdle(0, Date.now() + 999_999), 0);
    assert.deepEqual(mgr.activeSessionIds(), ['s1']);
    void p; // 挂起的 promise 不 await（FakeSession hang）
  });

  it('无活跃会话 → 0', () => {
    const { mgr } = makeManager();
    assert.equal(mgr.reapIdle(0), 0);
  });
});
