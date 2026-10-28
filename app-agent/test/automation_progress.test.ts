/** 执行进度收集单测：dump 快照 → 增量行（去重/轮次/tokens/终态措辞），fixture 形状对齐 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { ingestProgress, newProgressState, pushProgress } from '../src/automation.js';

/** 造一条 fixture 形状的 Plan task（S2 aiact-trace-11 字段） */
function planTask(id: string, log: string, opts: { done?: boolean; tokens?: number; ms?: number } = {}) {
  return {
    taskId: id,
    type: 'Planning',
    subType: 'Plan',
    status: 'finished',
    param: { userInstruction: 'x' },
    output: { log, shouldContinuePlanning: !(opts.done ?? false) },
    usage: opts.tokens ? { total_tokens: opts.tokens, time_cost: opts.ms ?? 5000 } : undefined,
  };
}

describe('ingestProgress', () => {
  it('Plan/Locate/Action 各出一行，含轮次与 tokens；重复喂入不重发', () => {
    const state = newProgressState();
    const dump = {
      tasks: [
        planTask('t1', '点击左上角的返回箭头，回到上一级设置页面', { tokens: 9819, ms: 5649 }),
        {
          taskId: 't2',
          type: 'Planning',
          subType: 'Locate',
          status: 'finished',
          param: { prompt: '左上角的返回箭头按钮' },
        },
        {
          taskId: 't3',
          type: 'Action Space',
          subType: 'Tap',
          status: 'finished',
          param: { locate: { description: '左上角的返回箭头按钮' } },
        },
      ],
    };
    const fresh = ingestProgress(state, dump as never);
    assert.equal(fresh.length, 3);
    assert.equal(fresh[0]!.kind, 'plan');
    assert.match(fresh[0]!.text, /^第1轮规划：点击左上角的返回箭头/);
    assert.match(fresh[0]!.text, /9,819 tokens · 5\.6s/);
    assert.equal(fresh[1]!.kind, 'locate');
    assert.match(fresh[1]!.text, /定位到「左上角的返回箭头按钮」/);
    assert.equal(fresh[2]!.kind, 'action');
    assert.match(fresh[2]!.text, /点击「左上角的返回箭头按钮」 ✓/);
    // 同一快照再喂：全部已见，零新行
    assert.equal(ingestProgress(state, dump as never).length, 0);
  });

  it('状态跃迁才发行：pending 不报，转 finished 时报；轮次跨快照累计', () => {
    const state = newProgressState();
    const t = planTask('p1', '打开设置');
    const pending = { ...t, status: 'pending', output: undefined };
    assert.equal(ingestProgress(state, { tasks: [pending] } as never).length, 0);
    const fresh = ingestProgress(state, { tasks: [t, planTask('p2', '进入网络页', { done: true })] } as never);
    // p1 一行 + p2 一行 + p2 的"判定完成"信息行
    assert.equal(fresh.length, 3);
    assert.match(fresh[0]!.text, /^第1轮规划：打开设置/);
    assert.match(fresh[1]!.text, /^第2轮规划：进入网络页/);
    assert.equal(fresh[2]!.kind, 'info');
    assert.match(fresh[2]!.text, /目标已完成/);
  });

  it('failed 动作/定位报 error 行；Input 带值', () => {
    const state = newProgressState();
    const fresh = ingestProgress(state, {
      tasks: [
        { taskId: 'l1', type: 'Planning', subType: 'Locate', status: 'failed', param: { prompt: '搜索框' } },
        {
          taskId: 'a1',
          type: 'Action Space',
          subType: 'Input',
          status: 'finished',
          param: { value: 'python', locate: { description: '搜索输入框' } },
        },
      ],
    } as never);
    assert.equal(fresh[0]!.kind, 'error');
    assert.match(fresh[0]!.text, /定位失败「搜索框」/);
    assert.match(fresh[1]!.text, /输入「搜索输入框」：python ✓/);
  });

  it('getProgress 语义：seq 单调，按 afterSeq 增量切片', () => {
    const state = newProgressState();
    pushProgress(state, 'info', 'a');
    pushProgress(state, 'info', 'b');
    pushProgress(state, 'info', 'c');
    const after1 = state.entries.filter((e) => e.seq > 1);
    assert.deepEqual(after1.map((e) => e.text), ['b', 'c']);
    assert.equal(state.seq, 3);
  });
});
