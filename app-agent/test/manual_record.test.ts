/** 手动录制单测：控制消息解析（锁 3.3.3 布局）+ 手势分类 + 录制器语义化（DI 假件） */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import * as jpeg from 'jpeg-js';
import { PNG } from 'pngjs';

import type { AppModelConfig } from '../src/automation.js';
import {
  classifyGesture,
  decodeToBitmap,
  KEYCODE_STEP,
  LONG_PRESS_MIN_MS,
  ManualRecorder,
  ManualRecordManager,
  markTapPoint,
  parseControlMessage,
  SWIPE_MIN_PX,
  type GestureEvent,
} from '../src/manual_record.js';

// ==================== 构造锁版本布局的控制消息（与前端序列化字节一致） ====================

function touchMsg(action: number, x: number, y: number): Buffer {
  const buf = Buffer.alloc(32);
  buf.writeUInt8(2, 0); // type=InjectTouch
  buf.writeUInt8(action, 1);
  buf.writeBigUInt64BE(0n, 2); // pointerId
  buf.writeUInt32BE(x, 10);
  buf.writeUInt32BE(y, 14);
  buf.writeUInt16BE(1080, 18); // videoW
  buf.writeUInt16BE(2400, 20); // videoH
  buf.writeUInt16BE(action === 1 ? 0 : 0xffff, 22); // pressure
  buf.writeUInt32BE(0, 24); // actionButton
  buf.writeUInt32BE(action === 1 ? 0 : 1, 28); // buttons
  return buf;
}

function keyMsg(action: number, keyCode: number): Buffer {
  const buf = Buffer.alloc(14);
  buf.writeUInt8(0, 0); // type=InjectKeyCode
  buf.writeUInt8(action, 1);
  buf.writeUInt32BE(keyCode, 2);
  buf.writeUInt32BE(0, 6); // repeat
  buf.writeUInt32BE(0, 10); // metaState
  return buf;
}

function clipboardMsg(text: string, paste = true): Buffer {
  const content = Buffer.from(text, 'utf8');
  const buf = Buffer.alloc(14 + content.length);
  buf.writeUInt8(9, 0); // type=SetClipboard
  buf.writeBigUInt64BE(1n, 1); // sequence
  buf.writeUInt8(paste ? 1 : 0, 9);
  buf.writeUInt32BE(content.length, 10);
  content.copy(buf, 14);
  return buf;
}

describe('parseControlMessage（锁 @yume-chan/scrcpy 3.3.3 布局）', () => {
  it('InjectTouch 32B → 坐标/动作/流坐标系尺寸', () => {
    assert.deepEqual(parseControlMessage(touchMsg(0, 540, 1200)), {
      kind: 'touch',
      action: 0,
      x: 540,
      y: 1200,
      videoW: 1080,
      videoH: 2400,
    });
  });

  it('InjectKeyCode 14B → keyCode；SetClipboard → paste+text', () => {
    assert.deepEqual(parseControlMessage(keyMsg(1, 3)), { kind: 'key', action: 1, keyCode: 3 });
    assert.deepEqual(parseControlMessage(clipboardMsg('你好 python')), {
      kind: 'clipboard',
      paste: true,
      text: '你好 python',
    });
  });

  it('未知 type / 长度不匹配一律忽略（防御式）', () => {
    assert.equal(parseControlMessage(Buffer.from([3, 0, 0])), null); // InjectScroll 非关注
    assert.equal(parseControlMessage(touchMsg(0, 1, 1).subarray(0, 30)), null); // 截断
    assert.equal(parseControlMessage(Buffer.alloc(0)), null);
  });
});

describe('classifyGesture', () => {
  const ev = (action: number, x: number, y: number, t: number): GestureEvent => ({ action, x, y, t });

  it('短按小位移 = tap（按下坐标）', () => {
    assert.deepEqual(classifyGesture([ev(0, 100, 200, 0), ev(1, 105, 203, 120)]), {
      kind: 'tap',
      x: 100,
      y: 200,
    });
  });

  it('≥550ms 小位移 = longPress', () => {
    assert.deepEqual(classifyGesture([ev(0, 100, 200, 0), ev(1, 102, 200, LONG_PRESS_MIN_MS + 50)]), {
      kind: 'longPress',
      x: 100,
      y: 200,
    });
  });

  it('主轴位移 ≥40px = swipe，direction=手指方向', () => {
    assert.deepEqual(
      classifyGesture([ev(0, 500, 2000, 0), ev(2, 500, 1500, 80), ev(1, 505, 1200, 160)]),
      { kind: 'swipe', direction: 'up', distance: 800 },
    );
    assert.deepEqual(classifyGesture([ev(0, 100, 500, 0), ev(1, 100 + SWIPE_MIN_PX, 500, 90)]), {
      kind: 'swipe',
      direction: 'right',
      distance: SWIPE_MIN_PX,
    });
  });

  it('缺 down/up 返回 null', () => {
    assert.equal(classifyGesture([ev(2, 1, 1, 0)]), null);
  });
});

// ==================== 录制器（DI 假截图 + 假 VL） ====================

const MODEL: AppModelConfig = { name: 'm', baseUrl: 'http://x', apiKey: 'k', family: 'doubao-seed' };
const FAKE_PNG = Buffer.from('89504e470d0a1a0a', 'hex');

function makeRecorder(describeText = (x: number, y: number) => `坐标${x},${y}的按钮`) {
  const calls: Array<{ x: number; y: number }> = [];
  const recorder = new ManualRecorder('emulator-5554', 's1', MODEL, {
    adbPath: 'adb',
    screencap: async () => FAKE_PNG,
    describe: async (_png, x, y) => {
      calls.push({ x, y });
      return describeText(x, y);
    },
  });
  return { recorder, calls };
}

describe('ManualRecorder', () => {
  it('tap → VL 语义化 aiTap；文本粘贴配对上一次点击描述', async () => {
    const { recorder, calls } = makeRecorder(() => '搜索输入框');
    recorder.onControl(touchMsg(0, 300, 400));
    recorder.onControl(touchMsg(1, 300, 400));
    recorder.onControl(clipboardMsg('python'));
    const { steps, yamlFlow } = await recorder.stop();
    // 注意：clipboard 步骤先入（VL 识别异步在后），顺序按事件落定
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], { x: 300, y: 400 });
    const actions = steps.map((s) => s.action);
    assert.ok(actions.includes('aiTap'));
    assert.ok(actions.includes('aiInput'));
    const tap = steps.find((s) => s.action === 'aiTap')!;
    assert.equal(tap.locate, '搜索输入框');
    assert.ok(yamlFlow.includes('- aiTap: "搜索输入框"'));
  });

  it('swipe 零 VL 直收 direction+distance；系统键按 UP 记一次', async () => {
    const { recorder, calls } = makeRecorder();
    recorder.onControl(touchMsg(0, 540, 2000));
    recorder.onControl(touchMsg(2, 540, 1500));
    recorder.onControl(touchMsg(1, 540, 1100));
    recorder.onControl(keyMsg(0, 3)); // down 不记
    recorder.onControl(keyMsg(1, 3)); // up 记 Home
    const { steps } = await recorder.stop();
    assert.equal(calls.length, 0); // 全程零 VL
    assert.deepEqual(steps[0], { action: 'Swipe', params: { direction: 'up', distance: 900 } });
    assert.deepEqual(steps[1], { action: 'AndroidHomeButton' });
  });

  it('VL 失败用坐标兜底描述（诚实保留步骤）', async () => {
    const recorder = new ManualRecorder('emulator-5554', 's1', MODEL, {
      adbPath: 'adb',
      screencap: async () => FAKE_PNG,
      describe: async () => {
        throw new Error('VL down');
      },
    });
    recorder.onControl(touchMsg(0, 111, 222));
    recorder.onControl(touchMsg(1, 111, 222));
    const { steps } = await recorder.stop();
    assert.equal(steps.length, 1);
    assert.match(steps[0]!.locate!, /坐标\(111, 222\)/);
  });

  it('keycode 表覆盖 Home/Back/最近任务', () => {
    assert.equal(KEYCODE_STEP[3], 'AndroidHomeButton');
    assert.equal(KEYCODE_STEP[4], 'AndroidBackButton');
    assert.equal(KEYCODE_STEP[187], 'AndroidRecentAppsButton');
  });

  it('流坐标系 → 设备坐标系换算（真机实证 488×1080 流 vs 1080×2400 设备）', async () => {
    // 构造 videoW/H=488×1080 的触控消息（缩放流坐标系）
    const streamTouch = (action: number, x: number, y: number): Buffer => {
      const buf = touchMsg(action, x, y);
      buf.writeUInt16BE(488, 18);
      buf.writeUInt16BE(1080, 20);
      return buf;
    };
    const calls: Array<{ x: number; y: number }> = [];
    const recorder = new ManualRecorder(
      'emulator-5554',
      's1',
      MODEL,
      {
        adbPath: 'adb',
        screencap: async () => FAKE_PNG,
        describe: async (_png, x, y) => {
          calls.push({ x, y });
          return 'el';
        },
      },
      '1080x2400', // 设备物理分辨率
    );
    recorder.onControl(streamTouch(0, 327, 670));
    recorder.onControl(streamTouch(1, 327, 670));
    // 滑动：流坐标系 450px → 设备系应 ×(2400/1080)=1000px
    recorder.onControl(streamTouch(0, 244, 900));
    recorder.onControl(streamTouch(1, 244, 450));
    const { steps } = await recorder.stop();
    // tap 描述坐标换算到设备系：327×(1080/488)=724，670×(2400/1080)=1489
    assert.deepEqual(calls[0], { x: 724, y: 1489 });
    const swipe = steps.find((s) => s.action === 'Swipe')!;
    assert.deepEqual(swipe.params, { direction: 'up', distance: 1000 });
  });
});

describe('markTapPoint（set-of-marks 红圈标记）', () => {
  it('中心点与圆环像素变红；边缘坐标不越界', () => {
    const img = new PNG({ width: 200, height: 200 });
    img.data.fill(255); // 全白
    const marked = PNG.sync.read(markTapPoint(PNG.sync.write(img), 100, 100));
    const px = (x: number, y: number) => {
      const i = (marked.width * y + x) << 2;
      return [marked.data[i], marked.data[i + 1], marked.data[i + 2]];
    };
    assert.deepEqual(px(100, 100), [255, 0, 0]); // 中心红点
    assert.deepEqual(px(100 + 90, 100), [255, 0, 0]); // 圆环上（R=90）
    assert.deepEqual(px(100 + 40, 100), [255, 255, 255]); // 环内空白仍白
    // 靠边点击不越界（防溃）
    const edge = PNG.sync.read(markTapPoint(PNG.sync.write(img), 1, 1));
    assert.equal(edge.width, 200);
  });
});

// ==================== 鸿蒙（{t,x,y} JSON 控制 + JPEG 截图） ====================

/** 浏览器下发的鸿蒙控制帧（二进制 JSON，坐标=设备物理像素） */
function harmonyMsg(t: 'down' | 'move' | 'up', x: number, y: number): Buffer {
  return Buffer.from(JSON.stringify({ t, x, y }), 'utf-8');
}

/** 极小合法 JPEG（jpeg-js 编码 4×4 白图） */
function tinyJpeg(width = 4, height = 4): Buffer {
  const data = Buffer.alloc(width * height * 4, 255);
  return jpeg.encode({ width, height, data }, 90).data;
}

describe('ManualRecorder（harmony）', () => {
  function makeHarmonyRecorder(resolution?: string) {
    const calls: Array<{ x: number; y: number; osName?: string }> = [];
    let snapshots = 0;
    const recorder = new ManualRecorder(
      '4ACVB2XXXX',
      's1',
      MODEL,
      {
        adbPath: 'adb',
        hdcPath: 'hdc',
        snapshotHdc: async () => {
          snapshots += 1;
          return tinyJpeg();
        },
        // 安卓截图通道给个必炸假件：走错通道立刻暴露
        screencap: async () => {
          throw new Error('鸿蒙不应走 adb screencap');
        },
        describe: async (_png, x, y, _model, osName) => {
          calls.push({ x, y, osName });
          return `鸿蒙元素${x},${y}`;
        },
      },
      resolution,
      'harmony',
    );
    return { recorder, calls, snapshots: () => snapshots };
  }

  it('JSON 控制 → tap 语义化；坐标已是设备像素，配了 resolution 也不换算', async () => {
    const { recorder, calls, snapshots } = makeHarmonyRecorder('1084x2412');
    recorder.onControl(harmonyMsg('down', 542, 1200));
    recorder.onControl(harmonyMsg('up', 545, 1203));
    const { steps, yamlFlow } = await recorder.stop();
    assert.equal(snapshots(), 1); // 截图走 hdc 通道
    assert.deepEqual(calls[0], { x: 542, y: 1200, osName: 'HarmonyOS（鸿蒙）' });
    assert.equal(steps[0]!.action, 'aiTap');
    assert.equal(steps[0]!.locate, '鸿蒙元素542,1200');
    assert.ok(yamlFlow.includes('aiTap'));
  });

  it('down/move/up 滑动 → Swipe（零 VL）；scrcpy 二进制帧误投安静忽略', async () => {
    const { recorder, calls } = makeHarmonyRecorder();
    recorder.onControl(harmonyMsg('down', 540, 2000));
    recorder.onControl(harmonyMsg('move', 540, 1500));
    recorder.onControl(harmonyMsg('up', 540, 1100));
    recorder.onControl(touchMsg(0, 1, 1)); // scrcpy 二进制：首字节非 0x7B，忽略
    const { steps } = await recorder.stop();
    assert.equal(calls.length, 0);
    assert.deepEqual(steps, [{ action: 'Swipe', params: { direction: 'up', distance: 900 } }]);
  });
});

// ==================== iOS（{t,x,y} JSON 控制=point 系 + WDA PNG 截图=@2x 像素） ====================

/** pngjs 合成指定尺寸 PNG（WDA /screenshot 假件） */
function tinyPng(width: number, height: number): Buffer {
  return PNG.sync.write(new PNG({ width, height }));
}

describe('ManualRecorder（ios）', () => {
  function makeIosRecorder(opts: {
    shotW: number;
    shotH: number;
    pointSize?: { width: number; height: number } | 'reject';
  }) {
    const calls: Array<{ x: number; y: number; osName?: string }> = [];
    let shots = 0;
    const recorder = new ManualRecorder(
      '6043ddXXXX',
      's1',
      MODEL,
      {
        adbPath: 'adb',
        wda: { port: 8100, ensureAlive: async () => {} },
        wdaShot: async () => {
          shots += 1;
          return tinyPng(opts.shotW, opts.shotH);
        },
        wdaPointSizeFn: async () => {
          const ps = opts.pointSize;
          if (ps === 'reject') throw new Error('rect 不可得');
          return ps ?? { width: 810, height: 1080 };
        },
        // 走错通道立刻暴露
        screencap: async () => {
          throw new Error('iOS 不应走 adb screencap');
        },
        snapshotHdc: async () => {
          throw new Error('iOS 不应走 hdc snapshot');
        },
        describe: async (_png, x, y, _model, osName) => {
          calls.push({ x, y, osName });
          return `iOS元素${x},${y}`;
        },
      },
      undefined,
      'ios',
    );
    return { recorder, calls, shots: () => shots };
  }

  it('JSON 控制(point 系) → tap；红圈坐标按 截图宽/point宽 放大（@3x 也对）', async () => {
    const { recorder, calls, shots } = makeIosRecorder({
      shotW: 300,
      shotH: 600,
      pointSize: { width: 100, height: 200 }, // scale=3
    });
    recorder.onControl(harmonyMsg('down', 50, 60));
    recorder.onControl(harmonyMsg('up', 51, 61));
    const { steps } = await recorder.stop();
    assert.equal(shots(), 1); // 截图走 WDA 通道
    assert.deepEqual(calls[0], { x: 150, y: 180, osName: 'iOS/iPadOS' });
    assert.equal(steps[0]!.action, 'aiTap');
    assert.equal(steps[0]!.locate, 'iOS元素150,180');
  });

  it('point 尺寸不可得 → 红圈按 @2x 兜底；步骤照常产出', async () => {
    const { recorder, calls } = makeIosRecorder({ shotW: 300, shotH: 600, pointSize: 'reject' });
    recorder.onControl(harmonyMsg('down', 50, 60));
    recorder.onControl(harmonyMsg('up', 50, 60));
    const { steps } = await recorder.stop();
    assert.deepEqual(calls[0], { x: 100, y: 120, osName: 'iOS/iPadOS' });
    assert.equal(steps.length, 1);
  });

  it('滑动 → Swipe 零 VL，distance 保持 point 系（WDA 回放同系零换算）', async () => {
    const { recorder, calls } = makeIosRecorder({ shotW: 300, shotH: 600 });
    recorder.onControl(harmonyMsg('down', 405, 900));
    recorder.onControl(harmonyMsg('move', 405, 600));
    recorder.onControl(harmonyMsg('up', 405, 300));
    const { steps } = await recorder.stop();
    assert.equal(calls.length, 0);
    assert.deepEqual(steps, [{ action: 'Swipe', params: { direction: 'up', distance: 600 } }]);
  });
});

describe('decodeToBitmap / markTapPoint（JPEG 入 PNG 出）', () => {
  it('JPEG 解码成位图；红圈标记后输出恒为 PNG', () => {
    const bmp = decodeToBitmap(tinyJpeg(8, 8));
    assert.equal(bmp.width, 8);
    assert.equal(bmp.height, 8);
    const marked = markTapPoint(tinyJpeg(200, 200), 100, 100);
    assert.equal(marked[0], 0x89); // PNG 魔数
    const img = PNG.sync.read(marked);
    const i = (img.width * 100 + 100) << 2;
    assert.deepEqual([img.data[i], img.data[i + 1], img.data[i + 2]], [255, 0, 0]); // 中心红点
  });
});

describe('ManualRecordManager', () => {
  it('start/pull/stop 生命周期；session 不匹配 pull 回 recording=false', async () => {
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      screencap: async () => FAKE_PNG,
      describe: async () => '设置图标',
    });
    mgr.start('emulator-5554', 's1', MODEL);
    mgr.onControl('s1', touchMsg(0, 10, 20));
    mgr.onControl('s1', touchMsg(1, 10, 20));
    mgr.onControl('other', touchMsg(0, 99, 99)); // 不匹配的会话忽略
    // 等语义化链落定
    await new Promise((r) => setTimeout(r, 20));
    const pulled = mgr.pull('s1', 0);
    assert.equal(pulled.recording, true);
    assert.equal(pulled.entries.length, 1);
    assert.equal(pulled.entries[0]!.step.locate, '设置图标');
    assert.deepEqual(mgr.pull('nope', 0), { recording: false, seq: 0, pending: 0, entries: [] });
    const stopped = await mgr.stop('s1');
    assert.equal(stopped!.steps.length, 1);
    assert.ok(stopped!.yaml_flow.includes('aiTap'));
    assert.equal(await mgr.stop('s1'), null); // 幂等
  });

  it('android：开录同时旁听设备端触控源,设备事件与浏览器 tee 汇流;stop 收源', async () => {
    const fake = { started: 0, stopped: 0, emit: null as ((ev: any) => void) | null };
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      screencap: async () => FAKE_PNG,
      describe: async (_p, x, y) => `设备上(${x},${y})的图标`,
      deviceTouchFactory: (o) => {
        fake.emit = o.onEvent;
        return {
          start: async () => {
            fake.started += 1;
          },
          stop: () => {
            fake.stopped += 1;
          },
        };
      },
    });
    mgr.start('emulator-5554', 's1', MODEL, '1080x2400');
    assert.ok(fake.emit, '设备源应被创建并注册回调');
    // 设备端物理点按（getevent 解析后的屏幕像素事件）
    fake.emit!({ action: 0, x: 540, y: 1200, t: Date.now() });
    fake.emit!({ action: 1, x: 540, y: 1200, t: Date.now() + 60 });
    // 浏览器 tee 事件照常并行可用（混合录制）
    mgr.onControl('s1', touchMsg(0, 100, 100));
    mgr.onControl('s1', touchMsg(1, 100, 100));
    await new Promise((r) => setTimeout(r, 30));
    const pulled = mgr.pull('s1', 0);
    assert.equal(pulled.entries.length, 2);
    assert.equal(pulled.entries[0]!.step.locate, '设备上(540,1200)的图标');
    await mgr.stop('s1');
    assert.equal(fake.started, 1);
    assert.ok(fake.stopped >= 1, 'stop 必须回收设备源');
  });

  it('两台设备并行录制：控制字节按 sessionId 各归各,双 getevent 源并存', async () => {
    const sources: Array<{ serial: string; started: number; stopped: number }> = [];
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      screencap: async () => FAKE_PNG,
      describe: async (_p, x, y) => `(${x},${y})`,
      deviceTouchFactory: (o) => {
        const rec = { serial: o.serial, started: 0, stopped: 0 };
        sources.push(rec);
        return {
          start: async () => {
            rec.started += 1;
          },
          stop: () => {
            rec.stopped += 1;
          },
        };
      },
    });
    mgr.start('devA', 's1', MODEL);
    mgr.start('devB', 's2', MODEL);
    assert.equal(sources.length, 2); // 两路设备源并存
    assert.equal(mgr.hasSessionForSerial('devA'), true);
    assert.equal(mgr.hasSessionForSerial('devB'), true);
    // 各自控制流各归各
    mgr.onControl('s1', touchMsg(0, 10, 10));
    mgr.onControl('s1', touchMsg(1, 10, 10));
    mgr.onControl('s2', touchMsg(0, 20, 20));
    mgr.onControl('s2', touchMsg(1, 20, 20));
    await new Promise((r) => setTimeout(r, 30));
    assert.equal(mgr.pull('s1', 0).entries.length, 1);
    assert.equal(mgr.pull('s2', 0).entries.length, 1);
    assert.equal(mgr.pull('s1', 0).entries[0]!.step.locate, '(10,10)');
    assert.equal(mgr.pull('s2', 0).entries[0]!.step.locate, '(20,20)');
    // stop(s1) 只收 devA 的源，devB 照常
    await mgr.stop('s1');
    assert.equal(sources[0]!.stopped, 1);
    assert.equal(sources[1]!.stopped, 0);
    assert.equal(mgr.pull('s2', 0).recording, true);
    await mgr.stop('s2');
    assert.equal(sources[1]!.stopped, 1);
  });

  it('同设备换 session 替换旧录制;异设备绝不替换', async () => {
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      screencap: async () => FAKE_PNG,
      describe: async () => 'x',
      deviceTouchFactory: () => ({ start: async () => {}, stop: () => {} }),
    });
    mgr.start('devA', 's1', MODEL);
    mgr.start('devB', 's2', MODEL);
    // devA 换会话（投屏重连换票据）→ s1 被替换,s2（devB）不动
    mgr.start('devA', 's3', MODEL);
    assert.deepEqual(mgr.pull('s1', 0).recording, false); // 旧的没了
    assert.equal(mgr.pull('s3', 0).recording, true);
    assert.equal(mgr.pull('s2', 0).recording, true); // devB 原样
    // 同 session 重复 start 幂等
    mgr.start('devA', 's3', MODEL);
    assert.equal(mgr.pull('s3', 0).recording, true);
    await mgr.stop('s2');
    await mgr.stop('s3');
  });

  it('stopAll 并行收全部录制与设备源', async () => {
    let stops = 0;
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      screencap: async () => FAKE_PNG,
      describe: async () => 'x',
      deviceTouchFactory: () => ({
        start: async () => {},
        stop: () => {
          stops += 1;
        },
      }),
    });
    mgr.start('devA', 's1', MODEL);
    mgr.start('devB', 's2', MODEL);
    await mgr.stopAll('tunnel down');
    assert.equal(stops, 2);
    assert.equal(mgr.pull('s1', 0).recording, false);
    assert.equal(mgr.pull('s2', 0).recording, false);
  });

  it('harmony/ios 不开设备源（getevent 是安卓专属通道）', async () => {
    let made = 0;
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      hdcPath: 'hdc',
      resolvePlatform: () => 'harmony',
      snapshotHdc: async () => tinyJpeg(),
      describe: async () => 'x',
      deviceTouchFactory: () => {
        made += 1;
        return { start: async () => {}, stop: () => {} };
      },
    });
    mgr.start('h1', 's1', MODEL);
    assert.equal(made, 0);
    await mgr.stop('s1');
  });

  it('ios：wda 是类实例（方法依赖 this）也能开录——防解构裸调回归', async () => {
    // 复刻 WdaManager 形态：ensureAlive 首行同步读 this 上的字段
    class FakeWda {
      port = 8100;
      private pending: Promise<void> | null = null;
      ensureAlive(_udid: string): Promise<void> {
        if (this.pending) return this.pending;
        this.pending = Promise.resolve();
        return this.pending;
      }
    }
    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      wda: new FakeWda(),
      resolvePlatform: () => 'ios',
      wdaShot: async () => tinyPng(200, 400),
      wdaPointSizeFn: async () => ({ width: 100, height: 200 }),
      describe: async () => '类实例元素',
    });
    mgr.start('i2', 's9', MODEL); // 曾在此炸 reading 'pending'
    mgr.onControl('s9', harmonyMsg('down', 10, 20));
    mgr.onControl('s9', harmonyMsg('up', 10, 20));
    await new Promise((r) => setTimeout(r, 20));
    assert.equal(mgr.pull('s9', 0).entries.length, 1);
    await mgr.stop('s9');
  });

  it('ios：未配 wda 拒开录（明确报错）；配了则正常建录制器', async () => {
    const noWda = new ManualRecordManager({
      adbPath: 'adb',
      resolvePlatform: () => 'ios',
    });
    assert.throws(() => noWda.start('i1', 's1', MODEL), /idevice|WDA/);

    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      wda: { port: 8100, ensureAlive: async () => {} },
      resolvePlatform: () => 'ios',
      wdaShot: async () => tinyPng(200, 400),
      wdaPointSizeFn: async () => ({ width: 100, height: 200 }),
      describe: async () => 'iPad 设置图标',
    });
    mgr.start('i1', 's1', MODEL);
    mgr.onControl('s1', harmonyMsg('down', 10, 20));
    mgr.onControl('s1', harmonyMsg('up', 10, 20));
    await new Promise((r) => setTimeout(r, 20));
    const pulled = mgr.pull('s1', 0);
    assert.equal(pulled.entries.length, 1);
    assert.equal(pulled.entries[0]!.step.locate, 'iPad 设置图标');
    await mgr.stop('s1');
  });

  it('harmony：未配 hdcPath 拒开录；配了则按平台建录制器', async () => {
    const noHdc = new ManualRecordManager({
      adbPath: 'adb',
      resolvePlatform: () => 'harmony',
    });
    assert.throws(() => noHdc.start('h1', 's1', MODEL), /HDC_PATH/);

    const mgr = new ManualRecordManager({
      adbPath: 'adb',
      hdcPath: 'hdc',
      resolvePlatform: () => 'harmony',
      snapshotHdc: async () => tinyJpeg(),
      describe: async () => '鸿蒙设置图标',
    });
    mgr.start('h1', 's1', MODEL);
    mgr.onControl('s1', harmonyMsg('down', 10, 20));
    mgr.onControl('s1', harmonyMsg('up', 10, 20));
    await new Promise((r) => setTimeout(r, 20));
    const pulled = mgr.pull('s1', 0);
    assert.equal(pulled.entries.length, 1);
    assert.equal(pulled.entries[0]!.step.locate, '鸿蒙设置图标');
    await mgr.stop('s1');
  });
});
