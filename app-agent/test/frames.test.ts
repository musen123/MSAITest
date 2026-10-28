/** frames 编解码单测：合法帧回环 + 脏帧拒收（契约 §2） */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  FrameDecodeError,
  decodeAgentFrame,
  decodeGatewayFrame,
  encodeAgentFrame,
  type AgentFrame,
  type DeviceInfo,
} from '../src/frames.js';

const DEVICE: DeviceInfo = {
  serial: 'ABC123',
  state: 'device',
  model: 'Pixel_6',
  brand: 'Google',
  android_version: '14',
  resolution: '1080x2400',
  connection: 'usb',
  platform: 'android',
};

describe('encodeAgentFrame / decodeAgentFrame 回环', () => {
  const frames: AgentFrame[] = [
    {
      v: 1,
      type: 'register',
      agent_version: '0.1.0',
      capabilities: ['scrcpy'],
      protocol_version: 1,
    },
    { v: 1, type: 'heartbeat', ts: 1_700_000_000, devices: [DEVICE] },
    { v: 1, type: 'heartbeat', ts: 1_700_000_010, devices: [] },
    { v: 1, type: 'device_event', event: 'upsert', device: DEVICE },
    { v: 1, type: 'device_event', event: 'remove', device: DEVICE },
    { v: 1, type: 'rpc_response', id: 'r-1', ok: true, result: { pong: true } },
    {
      v: 1,
      type: 'rpc_response',
      id: 'r-2',
      ok: false,
      error: { code: 'not_implemented', message: 'start_scrcpy 未实现' },
    },
  ];

  for (const frame of frames) {
    it(`${frame.type}${'event' in frame ? `/${frame.event}` : ''}${'ok' in frame ? `/ok=${frame.ok}` : ''}`, () => {
      assert.deepEqual(decodeAgentFrame(encodeAgentFrame(frame)), frame);
    });
  }
});

describe('decodeGatewayFrame 合法帧', () => {
  it('registered', () => {
    const frame = decodeGatewayFrame(
      JSON.stringify({ v: 1, type: 'registered', agent_id: 3, heartbeat_interval_s: 10 }),
    );
    assert.deepEqual(frame, { v: 1, type: 'registered', agent_id: 3, heartbeat_interval_s: 10 });
  });

  it('rpc_request（未知 cmd 也是合法帧，由分发表处理）', () => {
    const frame = decodeGatewayFrame(
      JSON.stringify({
        v: 1,
        type: 'rpc_request',
        id: 'r-uuid',
        cmd: 'whatever',
        params: { serial: 'ABC123' },
        timeout_ms: 15_000,
      }),
    );
    assert.equal(frame.type, 'rpc_request');
    assert.equal(frame.type === 'rpc_request' && frame.cmd, 'whatever');
  });

  it('error', () => {
    const frame = decodeGatewayFrame(
      JSON.stringify({ v: 1, type: 'error', code: 'internal', message: 'boom' }),
    );
    assert.deepEqual(frame, { v: 1, type: 'error', code: 'internal', message: 'boom' });
  });
});

describe('脏帧拒收', () => {
  const bad: Array<[string, string]> = [
    ['非法 JSON', 'not-json{{'],
    ['非对象', '[1,2,3]'],
    ['协议版本不符', JSON.stringify({ v: 2, type: 'registered', agent_id: 1, heartbeat_interval_s: 10 })],
    ['缺 type', JSON.stringify({ v: 1, agent_id: 1 })],
    ['未知 type', JSON.stringify({ v: 1, type: 'nope' })],
    ['registered 缺 agent_id', JSON.stringify({ v: 1, type: 'registered', heartbeat_interval_s: 10 })],
    [
      'rpc_request 缺 id',
      JSON.stringify({ v: 1, type: 'rpc_request', cmd: 'ping', params: {}, timeout_ms: 1000 }),
    ],
    [
      'rpc_request params 非对象',
      JSON.stringify({ v: 1, type: 'rpc_request', id: 'r-1', cmd: 'ping', params: 'x', timeout_ms: 1000 }),
    ],
  ];

  for (const [name, raw] of bad) {
    it(`decodeGatewayFrame 拒收: ${name}`, () => {
      assert.throws(() => decodeGatewayFrame(raw), FrameDecodeError);
    });
  }

  it('decodeAgentFrame 拒收 device state 非法', () => {
    const raw = JSON.stringify({
      v: 1,
      type: 'device_event',
      event: 'upsert',
      device: { ...DEVICE, state: 'rebooting' },
    });
    assert.throws(() => decodeAgentFrame(raw), FrameDecodeError);
  });

  it('decodeAgentFrame 拒收 rpc_response error.code 非法', () => {
    const raw = JSON.stringify({
      v: 1,
      type: 'rpc_response',
      id: 'r-1',
      ok: false,
      error: { code: 'weird', message: 'x' },
    });
    assert.throws(() => decodeAgentFrame(raw), FrameDecodeError);
  });
});
