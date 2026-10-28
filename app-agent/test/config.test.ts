/** config 单测：vendored 工具解析的回退契约（未命中必须返回 undefined，不破坏 PATH 兜底） */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { resolveVendoredTool } from '../src/config.js';

describe('resolveVendoredTool', () => {
  it('未 vendored 的子目录 → undefined（回退 PATH / 未配置，零回归）', () => {
    // 该子目录 vendor/ 下不存在 → 无论当前平台都取不到，必须返回 undefined
    assert.equal(resolveVendoredTool('no-such-tool-dir', 'nope'), undefined);
  });

  it('存在的工具名但目录空 → undefined（不误命中）', () => {
    assert.equal(resolveVendoredTool('platform-tools', '不存在的二进制名'), undefined);
  });
});
