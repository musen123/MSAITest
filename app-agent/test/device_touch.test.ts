/** 设备端触控源单测:getevent -p 探测 / -lt 流解析(真实模拟器 fixture)/ 量程标定 / 进程编排 */

import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { describe, it } from 'node:test';

import {
  DeviceTouchSource,
  GeteventParser,
  parseGeteventDevices,
  parseWmSize,
  type DeviceTouchEvent,
} from '../src/device_touch.js';

// ==================== 真实 fixture（emulator-5554 API34 实抓） ====================

const GETEVENT_P = `add device 1: /dev/input/event0
  name:     "gpio-keys"
  events:
    KEY (0001): 0074
  input props:
    <none>
add device 2: /dev/input/event1
  name:     "virtio_input_multi_touch_1"
  events:
    KEY (0001): 0141  014b
    ABS (0003): 0000  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0
                0001  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0
                0035  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0
                0036  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0
                0039  : value 0, min 0, max 65535, fuzz 0, flat 0, resolution 0
    SW  (0005): 0000
  input props:
    <none>
add device 3: /dev/input/event2
  name:     "virtio_input_multi_touch_2"
  events:
    KEY (0001): 0141  014b
    ABS (0003): 0035  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0
                0036  : value 0, min 0, max 32767, fuzz 0, flat 0, resolution 0
    ABS (0003): 0039  : value 0, min 0, max 65535, fuzz 0, flat 0, resolution 0
  input props:
    <none>
`;

/** 实抓 tap 轨迹（sendevent raw 16383,16383;此虚拟面板不回显 BTN_TOUCH,靠 TRACKING_ID） */
const TRACE_TAP = `[     150.269811] EV_ABS       ABS_MT_TRACKING_ID   00000001
[     150.269811] EV_ABS       ABS_MT_POSITION_X    00003fff
[     150.269811] EV_ABS       ABS_MT_POSITION_Y    00003fff
[     150.269811] EV_SYN       SYN_REPORT           00000000
[     150.557701] EV_ABS       ABS_MT_TRACKING_ID   ffffffff
[     150.557701] EV_SYN       SYN_REPORT           00000000
`;

const PANEL = { xMin: 0, xMax: 32767, yMin: 0, yMax: 32767 };
const SCREEN = { w: 1080, h: 2400 };

describe('parseGeteventDevices', () => {
  it('跳过非 MT 设备(gpio-keys)，选出触摸屏并读量程/TRACKING_ID', () => {
    const p = parseGeteventDevices(GETEVENT_P);
    assert.ok(p);
    assert.equal(p.path, '/dev/input/event1'); // 并列量程取首个（模拟器主显）
    assert.equal(p.xMax, 32767);
    assert.equal(p.yMax, 32767);
    assert.equal(p.hasTrackingId, true);
  });

  it('无 MT 设备回 null', () => {
    assert.equal(parseGeteventDevices('add device 1: /dev/input/event0\n  name: "keys"\n'), null);
  });
});

describe('parseWmSize', () => {
  it('Physical/Override 解析,Override 优先', () => {
    assert.deepEqual(parseWmSize('Physical size: 1080x2400\n'), { w: 1080, h: 2400 });
    assert.deepEqual(
      parseWmSize('Physical size: 1080x2400\nOverride size: 720x1600\n'),
      { w: 720, h: 1600 },
    );
    assert.equal(parseWmSize('garbage'), null);
  });
});

describe('GeteventParser', () => {
  it('实抓 tap 轨迹 → down+up,raw 16383 标定到屏幕中心', () => {
    const p = new GeteventParser(PANEL, SCREEN);
    const evs = p.feed(TRACE_TAP);
    assert.equal(evs.length, 2);
    assert.equal(evs[0]!.action, 0);
    // 16383*(1080-1)/32767≈539.5;up 帧无坐标沿用最后值
    assert.ok(Math.abs(evs[0]!.x - 540) <= 1, `x=${evs[0]!.x}`);
    assert.ok(Math.abs(evs[0]!.y - 1200) <= 1, `y=${evs[0]!.y}`);
    assert.equal(evs[1]!.action, 1);
    assert.equal(evs[1]!.x, evs[0]!.x);
  });

  it('半行分块喂入不丢事件（跨 chunk 缓冲）', () => {
    const p = new GeteventParser(PANEL, SCREEN);
    const mid = Math.floor(TRACE_TAP.length / 2);
    const evs = [...p.feed(TRACE_TAP.slice(0, mid)), ...p.feed(TRACE_TAP.slice(mid))];
    assert.deepEqual(
      evs.map((e) => e.action),
      [0, 1],
    );
  });

  it('touching 中坐标变化 → move;BTN_TOUCH 面板(无 TRACKING_ID)同样落抬', () => {
    const p = new GeteventParser(PANEL, SCREEN);
    const evs = p.feed(
      [
        '[1.0] EV_KEY BTN_TOUCH DOWN',
        '[1.0] EV_ABS ABS_MT_POSITION_X 00001000',
        '[1.0] EV_ABS ABS_MT_POSITION_Y 00001000',
        '[1.0] EV_SYN SYN_REPORT 00000000',
        '[1.1] EV_ABS ABS_MT_POSITION_Y 00003000',
        '[1.1] EV_SYN SYN_REPORT 00000000',
        '[1.2] EV_KEY BTN_TOUCH UP',
        '[1.2] EV_SYN SYN_REPORT 00000000',
        '',
      ].join('\n'),
    );
    assert.deepEqual(
      evs.map((e) => e.action),
      [0, 2, 1],
    );
    assert.ok(evs[1]!.y > evs[0]!.y);
  });

  it('非 0 slot（第二根手指）事件忽略,主指手势不受污染', () => {
    const p = new GeteventParser(PANEL, SCREEN);
    const evs = p.feed(
      [
        '[1.0] EV_ABS ABS_MT_TRACKING_ID 00000001',
        '[1.0] EV_ABS ABS_MT_POSITION_X 00001000',
        '[1.0] EV_ABS ABS_MT_POSITION_Y 00001000',
        '[1.0] EV_SYN SYN_REPORT 00000000',
        '[1.1] EV_ABS ABS_MT_SLOT 00000001', // 第二指落下
        '[1.1] EV_ABS ABS_MT_POSITION_X 00007000',
        '[1.1] EV_SYN SYN_REPORT 00000000',
        '[1.2] EV_ABS ABS_MT_SLOT 00000000', // 回主指
        '[1.2] EV_ABS ABS_MT_TRACKING_ID ffffffff',
        '[1.2] EV_SYN SYN_REPORT 00000000',
        '',
      ].join('\n'),
    );
    assert.deepEqual(
      evs.map((e) => e.action),
      [0, 1],
    );
    // 第二指的 X 没污染主指坐标
    assert.ok(Math.abs(evs[1]!.x - evs[0]!.x) <= 1);
  });
});

describe('DeviceTouchSource', () => {
  function makeFakeChild() {
    const child = new EventEmitter() as any;
    child.stdout = new EventEmitter();
    child.stdout.setEncoding = () => {};
    child.kill = () => {
      child.killed = true;
    };
    return child;
  }

  it('探测→拉流→事件回调（真实 fixture 全链）;stop 杀进程', async () => {
    const child = makeFakeChild();
    const got: DeviceTouchEvent[] = [];
    const spawnArgs: string[][] = [];
    const src = new DeviceTouchSource({
      adbPath: 'adb',
      serial: 'emulator-5554',
      resolution: '1080x2400',
      onEvent: (ev) => got.push(ev),
      probeImpl: async (_a, _s, args) => {
        assert.deepEqual(args, ['shell', 'getevent', '-p']);
        return GETEVENT_P;
      },
      spawnImpl: ((_cmd: string, args: string[]) => {
        spawnArgs.push(args);
        return child;
      }) as any,
    });
    await src.start();
    assert.deepEqual(spawnArgs[0], ['-s', 'emulator-5554', 'shell', 'getevent', '-lt', '/dev/input/event1']);
    child.stdout.emit('data', TRACE_TAP);
    assert.deepEqual(
      got.map((e) => e.action),
      [0, 1],
    );
    src.stop();
    assert.equal(child.killed, true);
  });

  it('resolution 缺省走 wm size 兜底;无 MT 设备明确报错', async () => {
    const probes: string[][] = [];
    const child = makeFakeChild();
    const src = new DeviceTouchSource({
      adbPath: 'adb',
      serial: 'X',
      onEvent: () => {},
      probeImpl: async (_a, _s, args) => {
        probes.push(args);
        return args[1] === 'getevent' ? GETEVENT_P : 'Physical size: 720x1600\n';
      },
      spawnImpl: (() => child) as any,
    });
    await src.start();
    assert.deepEqual(probes[1], ['shell', 'wm', 'size']);
    src.stop();

    const bad = new DeviceTouchSource({
      adbPath: 'adb',
      serial: 'X',
      onEvent: () => {},
      probeImpl: async () => 'add device 1: /dev/input/event0\n  name: "keys"\n',
    });
    await assert.rejects(() => bad.start(), /ABS_MT/);
  });
});
