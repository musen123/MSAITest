/** trimErrorMessage 单测：剥掉 Midscene 错误里的调用栈帧，只留人话 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { trimErrorMessage } from '../src/automation.js';

describe('trimErrorMessage', () => {
  it('剥掉 " at fn (file://...)" 栈帧（实测重规划超限错误串）', () => {
    const raw =
      'Replanned 8 times, exceeding the limit. Please configure a larger value for ' +
      'replanningCycleLimit (or use MIDSCENE_REPLANNING_CYCLE_LIMIT) to handle more complex tasks.' +
      '\n    at Object.executor (file:///x/@midscene/core/src/task-runner.ts:467:15)' +
      '\n    at TaskRunner.flush (file:///x/task-runner.ts:342:36)';
    const out = trimErrorMessage(raw);
    assert.ok(out.startsWith('Replanned 8 times'));
    assert.ok(!out.includes('file://'));
    assert.ok(!out.includes(' at '));
  });

  it('无栈帧原样返回', () => {
    assert.equal(trimErrorMessage('设备离线'), '设备离线');
  });
});
