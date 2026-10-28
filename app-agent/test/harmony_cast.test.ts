/** 鸿蒙投屏会话单测:控制帧解析 / 手势分类 / meta 帧 / 假 driver 生命周期与语义注入 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  HarmonyCastSession,
  buildMetaFrame,
  classifyGesture,
  parseControlMessage,
  type HmGesturePoint,
  type HarmonyDriverLike,
} from '../src/harmony_cast.js';

describe('parseControlMessage', () => {
  it('合法 down/move/up 解析,坐标取整', () => {
    const buf = Buffer.from(JSON.stringify({ t: 'down', x: 100.6, y: 200.2 }));
    assert.deepEqual(parseControlMessage(buf), { t: 'down', x: 101, y: 200 });
  });

  it('scrcpy 二进制控制字节(非 0x7B 开头)安静丢弃', () => {
    // scrcpy injectTouch 首字节是消息类型枚举(2),绝不能被误解析
    assert.equal(parseControlMessage(new Uint8Array([2, 0, 0, 1, 4])), null);
  });

  it('坏 JSON / 缺字段 / 非法 t → null', () => {
    assert.equal(parseControlMessage(Buffer.from('{bad json')), null);
    assert.equal(parseControlMessage(Buffer.from('{"t":"down"}')), null);
    assert.equal(parseControlMessage(Buffer.from('{"t":"fly","x":1,"y":2}')), null);
  });
});

describe('classifyGesture', () => {
  const P = (t: 'down' | 'move' | 'up', x: number, y: number, ts: number): HmGesturePoint => ({
    t,
    x,
    y,
    ts,
  });

  it('位移小=点按（保真实按住时长,长按语义天然保留,上限钳 1500）', () => {
    assert.deepEqual(classifyGesture([P('down', 100, 200, 0), P('up', 105, 210, 90)]), {
      kind: 'tap',
      x: 100,
      y: 200,
      heldMs: 90,
    });
    const long = classifyGesture([P('down', 5, 5, 0), P('up', 5, 5, 9_000)]);
    assert.equal((long as { heldMs: number }).heldMs, 1_500);
  });

  it('位移大=swipe:首尾点+按真实手速换算 speed（钳 600~15000 px/s）', () => {
    // 500px / 0.25s = 2000 px/s
    const op = classifyGesture([
      P('down', 500, 1500, 0),
      P('move', 500, 1200, 100),
      P('up', 500, 1000, 250),
    ]);
    assert.deepEqual(op, { kind: 'swipe', x1: 500, y1: 1500, x2: 500, y2: 1000, speed: 2000 });
    // 慢速长拖:速度托底 600
    const slow = classifyGesture([P('down', 0, 800, 0), P('up', 0, 100, 8_000)]);
    assert.equal((slow as { speed: number }).speed, 600);
    // 极速轻扫:封顶 15000
    const fast = classifyGesture([P('down', 0, 900, 0), P('up', 0, 0, 10)]);
    assert.equal((fast as { speed: number }).speed, 15_000);
  });

  it('残缺（无 down/无 up/单点）回 null', () => {
    assert.equal(classifyGesture([P('move', 1, 1, 0), P('up', 1, 1, 5)]), null);
    assert.equal(classifyGesture([P('down', 1, 1, 0)]), null);
  });
});

describe('buildMetaFrame', () => {
  it('首字节 0x7B(与 JPEG 0xFFD8 区分),内容含宽高', () => {
    const frame = buildMetaFrame(1084, 2412);
    assert.equal(frame[0], 0x7b);
    const parsed = JSON.parse(Buffer.from(frame).toString('utf-8'));
    assert.deepEqual(parsed, { type: 'harmony_meta', width: 1084, height: 2412 });
  });
});

/** 假 driver:记录调用序,帧回调可手动触发 */
function makeFakeDriver() {
  const calls: string[] = [];
  let frameCb: ((f: Buffer) => void) | undefined;
  const driver: HarmonyDriverLike = {
    start: async () => {
      calls.push('start');
    },
    stop: async () => {
      calls.push('stop');
    },
    getDisplaySize: async () => ({ width: 1084, height: 2412 }),
    startCaptureScreen: async (cb) => {
      frameCb = cb;
      calls.push('capture');
    },
    stopCaptureScreen: async () => {
      calls.push('stopCapture');
    },
    touchDown: async (x, y) => {
      calls.push(`down:${x},${y}`);
    },
    touchMove: async (x, y) => {
      calls.push(`move:${x},${y}`);
    },
    touchUp: async (x, y) => {
      calls.push(`up:${x},${y}`);
    },
    swipe: async (x1, y1, x2, y2, speed) => {
      calls.push(`swipe:${x1},${y1}->${x2},${y2}@${speed}`);
    },
    click: async (x, y) => {
      calls.push(`click:${x},${y}`);
    },
  };
  return { driver, calls, emitFrame: (f: Buffer) => frameCb?.(f) };
}

describe('HarmonyCastSession(假 driver)', () => {
  it('start → meta 帧先行,早到帧缓冲在 onVideoBytes 注册后补发', async () => {
    const fake = makeFakeDriver();
    const s = new HarmonyCastSession({
      serial: 'X',
      hdcPath: 'hdc',
      createDriver: async () => fake.driver,
    });
    await s.start();
    fake.emitFrame(Buffer.from([0xff, 0xd8, 1, 2, 0xff, 0xd9])); // start 后、注册前到达
    const got: Uint8Array[] = [];
    s.onVideoBytes((b) => got.push(b));
    assert.equal(got.length, 2, 'meta + 1 早到帧都应补发');
    assert.equal(got[0]?.[0], 0x7b, '第一帧必须是 meta');
    assert.equal(got[1]?.[0], 0xff, '第二帧是 JPEG');
    // 注册后帧直通
    fake.emitFrame(Buffer.from([0xff, 0xd8, 9, 0xff, 0xd9]));
    assert.equal(got.length, 3);
    await s.stop();
  });

  it('writeControl:短点按抬手后注入单 RPC click,scrcpy 字节丢弃', async () => {
    const fake = makeFakeDriver();
    const s = new HarmonyCastSession({
      serial: 'X',
      hdcPath: 'hdc',
      createDriver: async () => fake.driver,
    });
    await s.start();
    s.writeControl(Buffer.from(JSON.stringify({ t: 'down', x: 10, y: 20 })));
    s.writeControl(new Uint8Array([2, 0, 0])); // scrcpy 字节 → 丢
    await new Promise((r) => setTimeout(r, 10));
    assert.equal(fake.calls.filter((c) => c.startsWith('click')).length, 0, '抬手前不注入');
    s.writeControl(Buffer.from(JSON.stringify({ t: 'up', x: 10, y: 20 })));
    await new Promise((r) => setTimeout(r, 20)); // 等串行泵排空
    assert.deepEqual(
      fake.calls.filter((c) => /^(click|down|up)/.test(c)),
      ['click:10,20'], // 单 RPC,无 down/up
    );
    await s.stop();
  });

  it('writeControl:大位移手势编成一次系统级 swipe（不逐事件流式）', async () => {
    const fake = makeFakeDriver();
    const s = new HarmonyCastSession({
      serial: 'X',
      hdcPath: 'hdc',
      createDriver: async () => fake.driver,
    });
    await s.start();
    s.writeControl(Buffer.from(JSON.stringify({ t: 'down', x: 500, y: 1800 })));
    for (let i = 1; i <= 5; i++) {
      s.writeControl(Buffer.from(JSON.stringify({ t: 'move', x: 500, y: 1800 - i * 200 })));
    }
    s.writeControl(Buffer.from(JSON.stringify({ t: 'up', x: 500, y: 800 })));
    await new Promise((r) => setTimeout(r, 20));
    const swipes = fake.calls.filter((c) => c.startsWith('swipe:'));
    assert.equal(swipes.length, 1);
    assert.match(swipes[0]!, /^swipe:500,1800->500,800@\d+$/);
    // 逐事件通道不再被滑动占用
    assert.equal(fake.calls.filter((c) => c.startsWith('move')).length, 0);
    await s.stop();
  });

  it('stop 幂等:停帧流+断连接,后续 writeControl 静默', async () => {
    const fake = makeFakeDriver();
    const s = new HarmonyCastSession({
      serial: 'X',
      hdcPath: 'hdc',
      createDriver: async () => fake.driver,
    });
    await s.start();
    let closed = 0;
    s.onClosed(() => closed++);
    await s.stop();
    await s.stop();
    assert.equal(closed, 1, 'onClosed 只触发一次');
    assert.ok(fake.calls.includes('stopCapture') && fake.calls.includes('stop'));
    s.writeControl(Buffer.from(JSON.stringify({ t: 'down', x: 1, y: 1 })));
    await new Promise((r) => setTimeout(r, 10));
    assert.ok(!fake.calls.some((c) => c === 'down:1,1'), 'stop 后不再注入');
  });
});
