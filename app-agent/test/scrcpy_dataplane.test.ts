/** 投屏数据面纯逻辑单测：data-WS URL 推导 + bounded-queue 丢帧决策（契约 §3.1） */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  VIDEO_BACKPRESSURE_BYTES,
  deriveDataWsUrl,
  emptyStats,
  shouldDropVideoFrame,
} from '../src/scrcpy_dataplane.js';

describe('deriveDataWsUrl', () => {
  it('生产 wss 控制隧道 → data-ws + session_id（契约 §3.1）', () => {
    const out = deriveDataWsUrl(
      'wss://platform.example.com/api/v1/app/agents/ws',
      's-abc-123',
    );
    assert.equal(
      out,
      'wss://platform.example.com/api/v1/app/agents/data-ws?session_id=s-abc-123',
    );
  });

  it('本地直连网关 ws://127.0.0.1:8889 同样适用', () => {
    const out = deriveDataWsUrl('ws://127.0.0.1:8889/api/v1/app/agents/ws', 's-1');
    assert.equal(out, 'ws://127.0.0.1:8889/api/v1/app/agents/data-ws?session_id=s-1');
  });

  it('session_id 含特殊字符时正确 URL 编码', () => {
    const out = deriveDataWsUrl('wss://p.example.com/api/v1/app/agents/ws', 's/with space');
    // URLSearchParams 编码：/ → %2F，空格 → + 或 %20
    assert.ok(out.includes('session_id='));
    assert.ok(!out.includes('s/with space'));
    // 回环解析拿回原值
    const parsed = new URL(out);
    assert.equal(parsed.searchParams.get('session_id'), 's/with space');
  });

  it('保留控制隧道的协议与 host（仅换末段路径）', () => {
    const out = deriveDataWsUrl('wss://gw.internal:9999/api/v1/app/agents/ws', 'x');
    const parsed = new URL(out);
    assert.equal(parsed.protocol, 'wss:');
    assert.equal(parsed.host, 'gw.internal:9999');
    assert.equal(parsed.pathname, '/api/v1/app/agents/data-ws');
  });
});

describe('shouldDropVideoFrame（bounded queue 丢帧决策）', () => {
  it('缓冲低于阈值 → 不丢', () => {
    assert.equal(shouldDropVideoFrame(0), false);
    assert.equal(shouldDropVideoFrame(VIDEO_BACKPRESSURE_BYTES - 1), false);
  });

  it('缓冲等于阈值 → 不丢（严格大于才丢）', () => {
    assert.equal(shouldDropVideoFrame(VIDEO_BACKPRESSURE_BYTES), false);
  });

  it('缓冲超过阈值 → 丢（慢消费者不堆积，S1 结论）', () => {
    assert.equal(shouldDropVideoFrame(VIDEO_BACKPRESSURE_BYTES + 1), true);
  });

  it('自定义阈值生效', () => {
    assert.equal(shouldDropVideoFrame(100, 50), true);
    assert.equal(shouldDropVideoFrame(40, 50), false);
  });
});

describe('emptyStats', () => {
  it('初始计数全零', () => {
    assert.deepEqual(emptyStats(), {
      videoBytesForwarded: 0,
      videoFramesForwarded: 0,
      videoFramesDropped: 0,
      controlBytesReceived: 0,
    });
  });
});
