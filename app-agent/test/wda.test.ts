/** WdaManager 单测：探活/自愈链（iproxy→xcodebuild）/合流/换机/报错文案。
 *  fetch/spawn 全替身，timings 毫秒级；不碰真网络真进程。
 *  iproxy 路径按 idevice_id 同目录兄弟解析且 existsSync 硬检查——
 *  在临时目录造一对壳文件充当真实安装位。 */

import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { mkdtempSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  buildXcodebuildArgs,
  WdaBusyError,
  WdaManager,
  wdaDeadMessage,
  type ChildLike,
  type WdaManagerDeps,
} from '../src/wda.js';

const FAKE_BIN_DIR = mkdtempSync(path.join(os.tmpdir(), 'wda-test-bin-'));
writeFileSync(path.join(FAKE_BIN_DIR, 'idevice_id'), '#!/bin/sh\n');
writeFileSync(path.join(FAKE_BIN_DIR, 'iproxy'), '#!/bin/sh\n');
const IDEVICE_ID = path.join(FAKE_BIN_DIR, 'idevice_id');
const IPROXY = path.join(FAKE_BIN_DIR, 'iproxy');

const TINY = {
  probeTimeoutMs: 30,
  iproxyWaitMs: 60,
  bootTimeoutMs: 200,
  pollMs: 10,
  homeGapMs: 10,
  homeSettleMs: 5,
};
const UDID = '6043dd6adc17c6556d212b8c3591fa8f7d243c96';

/** 假子进程：stdout/stderr 可发数据，kill 同步触发 exit */
class FakeChild extends EventEmitter implements ChildLike {
  stdout = new EventEmitter();
  stderr = new EventEmitter();
  pid = 4321;
  killed: NodeJS.Signals | undefined;
  kill(signal?: NodeJS.Signals): boolean {
    this.killed = signal ?? 'SIGTERM';
    this.emit('exit', null);
    return true;
  }
}

interface Harness {
  mgr: WdaManager;
  spawns: Array<{ cmd: string; args: string[]; env?: NodeJS.ProcessEnv }>;
  children: FakeChild[];
  posts: string[];
  setAlive(v: boolean): void;
}

function makeHarness(extra: Partial<WdaManagerDeps> = {}): Harness {
  let alive = false;
  const spawns: Harness['spawns'] = [];
  const children: FakeChild[] = [];
  const posts: string[] = [];
  const mgr = new WdaManager({
    ideviceIdPath: IDEVICE_ID,
    timings: TINY,
    fetchImpl: async (url, init) => {
      if (init?.method === 'POST') {
        posts.push(url);
        return { ok: true, status: 200 };
      }
      if (!alive) throw new Error('ECONNREFUSED');
      return { ok: true, status: 200 };
    },
    spawnImpl: (cmd, args, opts) => {
      spawns.push({ cmd, args, env: opts.env });
      const child = new FakeChild();
      children.push(child);
      return child;
    },
    ...extra,
  });
  return { mgr, spawns, children, posts, setAlive: (v) => (alive = v) };
}

describe('buildXcodebuildArgs', () => {
  it('目录路径自动拼 WebDriverAgent.xcodeproj；全参齐活以 test 收尾', () => {
    const args = buildXcodebuildArgs(
      { projectPath: '/x/wda', teamId: 'TEAM1', bundleId: 'com.a.b' },
      UDID,
    );
    assert.equal(args[1], '/x/wda/WebDriverAgent.xcodeproj');
    assert.ok(args.includes(`id=${UDID}`));
    assert.ok(args.includes('DEVELOPMENT_TEAM=TEAM1'));
    assert.ok(args.includes('CODE_SIGN_STYLE=Automatic'));
    assert.ok(args.includes('PRODUCT_BUNDLE_IDENTIFIER=com.a.b'));
    assert.equal(args[args.length - 1], 'test');
  });

  it('.xcodeproj 结尾不重复拼；无 teamId 不带签名覆盖', () => {
    const args = buildXcodebuildArgs({ projectPath: '/x/WebDriverAgent.xcodeproj' }, UDID);
    assert.equal(args[1], '/x/WebDriverAgent.xcodeproj');
    assert.ok(!args.some((a) => a.startsWith('DEVELOPMENT_TEAM=')));
    assert.ok(!args.includes('CODE_SIGN_STYLE=Automatic'));
  });
});

describe('WdaManager.ensureAlive', () => {
  it('探活即通 → 不 spawn 任何子进程', async () => {
    const h = makeHarness();
    h.setAlive(true);
    await h.mgr.ensureAlive(UDID);
    assert.equal(h.spawns.length, 0);
  });

  it('死 → 拉 iproxy（双口+绑 udid）→ 探活恢复即通；二次调用不重复 spawn', async () => {
    const h = makeHarness();
    setTimeout(() => h.setAlive(true), 20); // 模拟 iproxy 起后转发恢复
    await h.mgr.ensureAlive(UDID);
    assert.equal(h.spawns.length, 1);
    assert.equal(h.spawns[0]!.cmd, IPROXY);
    assert.deepEqual(h.spawns[0]!.args, ['8100:8100', '9100:9100', '-u', UDID]);
    await h.mgr.ensureAlive(UDID); // 已活：不再 spawn
    assert.equal(h.spawns.length, 1);
  });

  it('死透且未配 xcodebuild → 报错含启动命令与配置键提示', async () => {
    const h = makeHarness();
    await assert.rejects(
      () => h.mgr.ensureAlive(UDID),
      (err: Error) => {
        assert.match(err.message, /xcodebuild/);
        assert.match(err.message, /WDA_PROJECT_PATH/);
        assert.match(err.message, /7 天过期/);
        return true;
      },
    );
  });

  it('配 xcodebuild → 自启并等到探活恢复；spawn 环境带 DEVELOPER_DIR', async () => {
    const h = makeHarness({
      xcodebuild: { projectPath: '/x/wda', teamId: 'T', developerDir: '/Apps/Xcode' },
    });
    // iproxy 拉起后仍死；xcodebuild 拉起 30ms 后 WDA 冷启动完成
    const tick = setInterval(() => {
      if (h.spawns.some((s) => s.cmd === 'xcodebuild')) {
        setTimeout(() => h.setAlive(true), 30);
        clearInterval(tick);
      }
    }, 5);
    try {
      await h.mgr.ensureAlive(UDID);
    } finally {
      clearInterval(tick);
    }
    assert.deepEqual(
      h.spawns.map((s) => s.cmd),
      [IPROXY, 'xcodebuild'],
    );
    const xcb = h.spawns[1]!;
    assert.equal(xcb.env?.DEVELOPER_DIR, '/Apps/Xcode');
    assert.ok(xcb.args.includes('DEVELOPMENT_TEAM=T'));
  });

  it('xcodebuild 起后即退（签名失败类）→ 报错带输出尾', async () => {
    const h = makeHarness({ xcodebuild: { projectPath: '/x/wda' } });
    const tick = setInterval(() => {
      const idx = h.spawns.findIndex((s) => s.cmd === 'xcodebuild');
      if (idx >= 0) {
        clearInterval(tick);
        const xcb = h.children[idx]!;
        xcb.stderr.emit('data', 'error: Signing certificate is invalid (expired)\n');
        xcb.emit('exit', 65);
      }
    }, 5);
    try {
      await assert.rejects(
        () => h.mgr.ensureAlive(UDID),
        (err: Error) => {
          assert.match(err.message, /Signing certificate is invalid/);
          return true;
        },
      );
    } finally {
      clearInterval(tick);
    }
  });

  it('并发 ensureAlive 合流：只走一遍自愈（iproxy 只 spawn 一次）', async () => {
    const h = makeHarness();
    setTimeout(() => h.setAlive(true), 25);
    await Promise.all([h.mgr.ensureAlive(UDID), h.mgr.ensureAlive(UDID)]);
    assert.equal(h.spawns.filter((s) => s.cmd === IPROXY).length, 1);
  });

  it('换 udid（绑定设备空闲）→ 杀旧 iproxy 重拉（-u 绑新设备）', async () => {
    const h = makeHarness();
    h.mgr.setBusyProbe(() => false); // 绑定设备空闲 → 放行换绑
    setTimeout(() => h.setAlive(true), 20);
    await h.mgr.ensureAlive(UDID);
    const first = h.children[0]!;
    h.setAlive(false);
    setTimeout(() => h.setAlive(true), 20);
    await h.mgr.ensureAlive('00008120-001A2B3C4D5E6F70');
    assert.equal(first.killed, 'SIGTERM');
    const last = h.spawns[h.spawns.length - 1]!;
    assert.ok(last.args.includes('00008120-001A2B3C4D5E6F70'));
  });

  it('单 iOS 守卫：绑定设备会话活跃 → 另一台被 WdaBusyError 拒绝且不杀 A 的 iproxy', async () => {
    const h = makeHarness();
    h.mgr.setBusyProbe((udid) => udid === UDID); // A 活跃
    setTimeout(() => h.setAlive(true), 20);
    await h.mgr.ensureAlive(UDID); // A 绑定成功（拉起 iproxy）
    const first = h.children[0]!;
    await assert.rejects(
      () => h.mgr.ensureAlive('00008120-001A2B3C4D5E6F70'),
      (err: unknown) => err instanceof WdaBusyError && err.boundUdid === UDID,
    );
    assert.equal(first.killed, undefined); // A 的 iproxy 毫发无损
    // A 自己再来照常通过
    await h.mgr.ensureAlive(UDID);
  });

  it('不同 udid 不合流：B 排队等 A 的在飞自愈,再按守卫判定（不共享假成功）', async () => {
    const h = makeHarness();
    h.mgr.setBusyProbe((udid) => udid === UDID);
    setTimeout(() => h.setAlive(true), 25);
    const pA = h.mgr.ensureAlive(UDID); // A 自愈在飞
    const pB = h.mgr.ensureAlive('00008120-001A2B3C4D5E6F70'); // B 背靠背进入
    await pA; // A 成功
    await assert.rejects(
      () => pB,
      (err: unknown) => err instanceof WdaBusyError && err.boundUdid === UDID,
    ); // B 没有搭上 A 的假成功，排队后被守卫明确拒绝
    assert.equal(h.spawns.filter((s) => s.cmd === IPROXY).length, 1); // 只为 A 拉过 iproxy
  });

  it('pressHome 被守卫覆盖：A 活跃时 B 的 pressHome 拒绝', async () => {
    const h = makeHarness();
    h.mgr.setBusyProbe((udid) => udid === UDID);
    h.setAlive(true);
    await h.mgr.ensureAlive(UDID);
    await assert.rejects(
      () => h.mgr.pressHome('00008120-001A2B3C4D5E6F70'),
      (err: unknown) => err instanceof WdaBusyError,
    );
    assert.equal(h.posts.length, 0); // 没打到 A 的 homescreen 上
  });

  it('stop 后 ensureAlive 拒绝；已 spawn 的子进程被 SIGTERM', async () => {
    const h = makeHarness();
    setTimeout(() => h.setAlive(true), 20);
    await h.mgr.ensureAlive(UDID);
    h.mgr.stop();
    assert.equal(h.children[0]!.killed, 'SIGTERM');
    await assert.rejects(() => h.mgr.ensureAlive(UDID), /已停止/);
  });
});

describe('WdaManager.pressHome', () => {
  it('两连 POST /wda/homescreen（起点锚定双按语义）', async () => {
    const h = makeHarness();
    h.setAlive(true);
    await h.mgr.pressHome(UDID);
    assert.equal(h.posts.length, 2);
    assert.ok(h.posts.every((u) => u.endsWith('/wda/homescreen')));
  });
});

describe('wdaDeadMessage', () => {
  it('无自启配置给完整命令；有自启配置说尝试过', () => {
    assert.match(wdaDeadMessage(8100, UDID, false), /xcodebuild -project/);
    assert.match(wdaDeadMessage(8100, UDID, true), /自动拉起已尝试/);
  });
});
