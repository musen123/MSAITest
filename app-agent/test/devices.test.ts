/** 设备发现单测：喂固定 adb 输出验证解析 + 快照 diff（契约 §10） */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { diffDevices, parseAdbDevicesOutput, parseDeviceExtra } from '../src/devices.js';
import type { DeviceInfo } from '../src/frames.js';

const ADB_OUTPUT = [
  'List of devices attached',
  '0A1B2C3D               device usb:1-4 product:raven model:Pixel_6 device:raven transport_id:5',
  '192.168.1.20:5555      device product:sdk_gphone64 model:sdk_gphone64_arm64 device:emu64a transport_id:7',
  'FA7801A00279           unauthorized usb:1-2 transport_id:2',
  'emulator-5554          offline transport_id:9',
  '',
].join('\n');

function toMap(devices: readonly DeviceInfo[]): Map<string, DeviceInfo> {
  return new Map(devices.map((d) => [d.serial, d]));
}

describe('parseAdbDevicesOutput', () => {
  it('解析 usb/tcpip/unauthorized/offline 四种典型行', () => {
    const devices = parseAdbDevicesOutput(ADB_OUTPUT);
    assert.equal(devices.length, 4);

    assert.deepEqual(devices[0], {
      serial: '0A1B2C3D',
      state: 'device',
      model: 'Pixel_6',
      brand: '',
      android_version: '',
      resolution: '',
      connection: 'usb',
      platform: 'android',
    });
    // serial 带 host:port → tcpip
    assert.equal(devices[1]?.serial, '192.168.1.20:5555');
    assert.equal(devices[1]?.connection, 'tcpip');
    assert.equal(devices[1]?.model, 'sdk_gphone64_arm64');
    assert.equal(devices[2]?.state, 'unauthorized');
    // emulator serial 无冒号 → usb；offline 行无 model 键值 → 留空
    assert.deepEqual(devices[3], {
      serial: 'emulator-5554',
      state: 'offline',
      model: '',
      brand: '',
      android_version: '',
      resolution: '',
      connection: 'usb',
      platform: 'android',
    });
  });

  it('空输出/仅表头 → 空列表', () => {
    assert.deepEqual(parseAdbDevicesOutput(''), []);
    assert.deepEqual(parseAdbDevicesOutput('List of devices attached\n\n'), []);
  });

  it('跳过 adb daemon 噪声行', () => {
    const noisy = [
      '* daemon not running; starting now at tcp:5037',
      '* daemon started successfully',
      'List of devices attached',
      'ABC  device model:Foo transport_id:1',
      '',
    ].join('\n');
    const devices = parseAdbDevicesOutput(noisy);
    assert.equal(devices.length, 1);
    assert.equal(devices[0]?.serial, 'ABC');
  });

  it('冷门态（no permissions）折叠为 offline', () => {
    const output = 'List of devices attached\nXYZ  no permissions (user in plugdev group?) usb:1-2\n';
    assert.equal(parseAdbDevicesOutput(output)[0]?.state, 'offline');
  });
});

describe('diffDevices', () => {
  const initial = parseAdbDevicesOutput(ADB_OUTPUT);

  it('首轮（prev 为空）→ 全部 upsert', () => {
    const events = diffDevices(new Map(), initial);
    assert.equal(events.length, 4);
    assert.ok(events.every((e) => e.event === 'upsert'));
  });

  it('快照无变化 → 空事件', () => {
    assert.deepEqual(diffDevices(toMap(initial), initial), []);
  });

  it('state 变化（unauthorized → device）→ 该设备 upsert', () => {
    const next = initial.map((d) =>
      d.serial === 'FA7801A00279' ? { ...d, state: 'device' as const } : d,
    );
    const events = diffDevices(toMap(initial), next);
    assert.equal(events.length, 1);
    assert.equal(events[0]?.event, 'upsert');
    assert.equal(events[0]?.device.serial, 'FA7801A00279');
    assert.equal(events[0]?.device.state, 'device');
  });

  it('拔线（设备消失）→ remove 且携带旧信息', () => {
    const next = initial.filter((d) => d.serial !== '0A1B2C3D');
    const events = diffDevices(toMap(initial), next);
    assert.equal(events.length, 1);
    assert.equal(events[0]?.event, 'remove');
    assert.equal(events[0]?.device.model, 'Pixel_6');
  });

  it('adb 不可用（next 为空）→ 已知设备全部 remove', () => {
    const events = diffDevices(toMap(initial), []);
    assert.equal(events.length, 4);
    assert.ok(events.every((e) => e.event === 'remove'));
  });

  it('增删改混合一次 diff 全部产出', () => {
    const added: DeviceInfo = {
      serial: 'NEW999',
      state: 'device',
      model: 'Pixel_8',
      brand: '',
      android_version: '',
      resolution: '',
      connection: 'usb',
      platform: 'android',
    };
    const next = [
      ...initial
        .filter((d) => d.serial !== 'emulator-5554')
        .map((d) => (d.serial === '0A1B2C3D' ? { ...d, state: 'offline' as const } : d)),
      added,
    ];
    const events = diffDevices(toMap(initial), next);
    assert.equal(events.filter((e) => e.event === 'upsert').length, 2); // 状态变化 + 新增
    assert.equal(events.filter((e) => e.event === 'remove').length, 1); // emulator-5554
  });
});

// ==================== parseDeviceExtra（富化字段解析） ====================

void describe('parseDeviceExtra', () => {
  void it('标准三行输出', () => {
    const out = 'google\n15\nPhysical size: 1080x2400\n';
    assert.deepEqual(parseDeviceExtra(out), {
      brand: 'google',
      android_version: '15',
      resolution: '1080x2400',
    });
  });

  void it('Override 分辨率优先 + CRLF', () => {
    const out = 'Xiaomi\r\n14\r\nPhysical size: 1080x2400\r\nOverride size: 720x1600\r\n';
    assert.deepEqual(parseDeviceExtra(out), {
      brand: 'Xiaomi',
      android_version: '14',
      resolution: '720x1600',
    });
  });

  void it('异常/空输出不炸，字段留空', () => {
    assert.deepEqual(parseDeviceExtra(''), { brand: '', android_version: '', resolution: '' });
    assert.equal(parseDeviceExtra('error: device offline\n').resolution, '');
  });
});
