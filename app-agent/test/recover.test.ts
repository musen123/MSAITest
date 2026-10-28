/** 步骤回收单测：合成轨迹 + 合成 fixture 断言 + YAML 转义（P2 路线 A 适配层） */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  dedupeAdjacentSteps,
  recoverSteps,
  recoverStepsFromTasks,
  stepsToYamlFlow,
  type DumpTask,
} from '../src/recover.js';

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(here, 'fixtures', 'aiact-trace-11.execution.json');

describe('recoverStepsFromTasks', () => {
  it('配对 Planning/Locate → Action Space/Tap 成 aiTap', () => {
    const tasks: DumpTask[] = [
      { type: 'Planning', subType: 'Plan' },
      { type: 'Planning', subType: 'Locate', param: { prompt: '左上角的返回箭头' } },
      { type: 'Action Space', subType: 'Tap', status: 'finished', param: { locate: {} } },
    ];
    assert.deepEqual(recoverStepsFromTasks(tasks), [
      { action: 'aiTap', locate: '左上角的返回箭头' },
    ]);
  });

  it('Input 动作带 value', () => {
    const tasks: DumpTask[] = [
      { type: 'Planning', subType: 'Locate', param: { prompt: '搜索框' } },
      { type: 'Action Space', subType: 'Input', status: 'finished', param: { value: '蓝牙' } },
    ];
    assert.deepEqual(recoverStepsFromTasks(tasks), [
      { action: 'aiInput', locate: '搜索框', value: '蓝牙' },
    ]);
  });

  it('未 finished 的动作不回收', () => {
    const tasks: DumpTask[] = [
      { type: 'Planning', subType: 'Locate', param: { prompt: '按钮' } },
      { type: 'Action Space', subType: 'Tap', status: 'pending', param: {} },
    ];
    assert.deepEqual(recoverStepsFromTasks(tasks), []);
  });

  it('缺定位的配对动作 / 未知动作 subType 一律丢弃', () => {
    assert.deepEqual(
      recoverStepsFromTasks([
        { type: 'Action Space', subType: 'Tap', status: 'finished', param: {} },
      ]),
      [],
    );
    assert.deepEqual(
      recoverStepsFromTasks([
        { type: 'Action Space', subType: 'Pinch', status: 'finished', param: {} },
      ]),
      [],
    );
  });
});

describe('recoverStepsFromTasks（无定位动作直收）', () => {
  it('系统键动作直收（param=null）', () => {
    assert.deepEqual(
      recoverStepsFromTasks([
        { type: 'Action Space', subType: 'AndroidHomeButton', status: 'finished', param: null },
        { type: 'Action Space', subType: 'AndroidBackButton', status: 'finished', param: null },
      ]),
      [{ action: 'AndroidHomeButton' }, { action: 'AndroidBackButton' }],
    );
  });

  it('Swipe direction 模式直收（舍弃 start 定位仅作展示）；start+end 精确模式丢弃', () => {
    const steps = recoverStepsFromTasks([
      {
        type: 'Action Space',
        subType: 'Swipe',
        status: 'finished',
        param: { start: { prompt: '桌面底部区域' }, direction: 'up', distance: 800 },
      },
    ]);
    assert.deepEqual(steps, [
      { action: 'Swipe', params: { direction: 'up', distance: 800 }, locate: '桌面底部区域' },
    ]);
    // 无 direction（start+end 坐标模式）→ 设备相关，不回收
    assert.deepEqual(
      recoverStepsFromTasks([
        {
          type: 'Action Space',
          subType: 'Swipe',
          status: 'finished',
          param: { start: { prompt: 'a' }, end: { prompt: 'b' } },
        },
      ]),
      [],
    );
    // direction 模式缺 distance → 补默认 600（yaml player 回放路径必填，设备实证）
    assert.deepEqual(
      recoverStepsFromTasks([
        { type: 'Action Space', subType: 'Swipe', status: 'finished', param: { direction: 'up' } },
      ]),
      [{ action: 'Swipe', params: { direction: 'up', distance: 600 }, locate: undefined }],
    );
  });

  it('Sleep/KeyboardPress(keyName)/Launch 直收；KeyboardPress 无 keyName 丢弃', () => {
    assert.deepEqual(
      recoverStepsFromTasks([
        { type: 'Action Space', subType: 'Sleep', status: 'finished', param: { timeMs: 1500 } },
        { type: 'Action Space', subType: 'Sleep', status: 'finished', param: {} },
        { type: 'Action Space', subType: 'Launch', status: 'finished', param: { uri: 'com.android.settings' } },
      ]),
      [
        { action: 'sleep', params: { timeMs: 1500 } },
        { action: 'sleep', params: { timeMs: 1000 } },
        { action: 'launch', value: 'com.android.settings' },
      ],
    );
    // KeyboardPress：无配对定位时按 keyName 直收；连 keyName 都没有 → 丢弃
    assert.deepEqual(
      recoverStepsFromTasks([
        { type: 'Action Space', subType: 'KeyboardPress', status: 'finished', param: { keyName: 'Enter' } },
        { type: 'Action Space', subType: 'KeyboardPress', status: 'finished', param: {} },
      ]),
      [{ action: 'KeyboardPress', params: { keyName: 'Enter' } }],
    );
  });

  it('回收不自动去重（连按返回等必要重复原样保留）；dedupeAdjacentSteps 仅作自愈工具', () => {
    const tap = (prompt: string): DumpTask[] => [
      { type: 'Planning', subType: 'Locate', param: { prompt } },
      { type: 'Action Space', subType: 'Tap', status: 'finished', param: {} },
    ];
    // 必要重复（连按两次返回）与重规划冗余静态无法区分 → 回收原样保留
    const steps = recoverStepsFromTasks([...tap('返回箭头'), ...tap('返回箭头'), ...tap('闹钟标签')]);
    assert.deepEqual(
      steps.map((s) => s.locate),
      ['返回箭头', '返回箭头', '闹钟标签'],
    );
    // 自愈工具：折叠相邻全等；sleep 重复合法不折叠
    assert.deepEqual(
      dedupeAdjacentSteps(steps).map((s) => s.locate),
      ['返回箭头', '闹钟标签'],
    );
    assert.equal(
      dedupeAdjacentSteps([
        { action: 'sleep', params: { timeMs: 500 } },
        { action: 'sleep', params: { timeMs: 500 } },
      ]).length,
      2,
    );
  });

  it('任何动作处理后清 pendingLocate（防污染下一动作）', () => {
    const steps = recoverStepsFromTasks([
      { type: 'Planning', subType: 'Locate', param: { prompt: '底部区域' } },
      {
        type: 'Action Space',
        subType: 'Swipe',
        status: 'finished',
        param: { direction: 'up', distance: 500 },
      },
      // 下一个 Tap 没有自己的 Locate → 必须丢弃（不得吃到"底部区域"）
      { type: 'Action Space', subType: 'Tap', status: 'finished', param: {} },
    ]);
    assert.equal(steps.length, 1);
    assert.equal(steps[0]!.action, 'Swipe');
    assert.equal(steps[0]!.locate, '底部区域'); // 配对位转作展示
  });
});

describe('recoverSteps（合成 fixture aiact-trace-11）', () => {
  it('回收出 5 个 aiTap，均带非空定位原文', () => {
    const dump = JSON.parse(readFileSync(FIXTURE, 'utf8'));
    const steps = recoverSteps(dump);
    assert.equal(steps.length, 5); // fixture: 5×Planning/Locate + 5×Action Space/Tap finished
    assert.ok(steps.every((s) => s.action === 'aiTap'));
    assert.ok(steps.every((s) => (s.locate ?? '').length > 0));
    assert.ok(steps.some((s) => (s.locate ?? '').includes('返回箭头')));
  });
});

describe('recoverSteps（合成 fixture aiact-trace-clock，含无定位动作）', () => {
  const CLOCK_FIXTURE = join(here, 'fixtures', 'aiact-trace-clock.execution.json');

  it('完整回收 Home→Swipe→Tap→sleep 四步（旧实现只回收得到 1 步 Tap）', () => {
    const dump = JSON.parse(readFileSync(CLOCK_FIXTURE, 'utf8'));
    const steps = recoverSteps(dump);
    assert.deepEqual(
      steps.map((s) => s.action),
      ['AndroidHomeButton', 'Swipe', 'aiTap', 'sleep'],
    );
    assert.deepEqual(steps[1]!.params, { direction: 'up', distance: 800 });
    assert.equal(steps[2]!.locate, 'Clock应用图标');
    assert.deepEqual(steps[3]!.params, { timeMs: 1500 });

    const yaml = stepsToYamlFlow(steps);
    assert.equal(
      yaml,
      [
        '      - AndroidHomeButton: {}',
        '      - sleep: 800',
        '      - Swipe: { direction: "up", distance: 800 }',
        '      - sleep: 800',
        '      - aiTap: "Clock应用图标"',
        '      - sleep: 800',
        '      - sleep: 1500',
      ].join('\n'),
    );
  });
});

describe('stepsToYamlFlow', () => {
  it('aiTap 单行 / aiInput 带 value 两行，各补 settle sleep', () => {
    const yaml = stepsToYamlFlow(
      [
        { action: 'aiTap', locate: '登录按钮' },
        { action: 'aiInput', locate: '用户名', value: 'admin' },
      ],
      500,
    );
    assert.equal(
      yaml,
      [
        '      - aiTap: "登录按钮"',
        '      - sleep: 500',
        '      - aiInput: "用户名"',
        '        value: "admin"',
        '      - sleep: 500',
      ].join('\n'),
    );
  });

  it('定位描述含英文引号做 YAML 转义（spike 适配层必修坑）', () => {
    const yaml = stepsToYamlFlow([{ action: 'aiTap', locate: 'the "OK" button' }]);
    assert.ok(yaml.includes('- aiTap: "the \\"OK\\" button"'));
  });
});
