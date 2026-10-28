/** iOS 设备发现单测：idevice_id/ideviceinfo 纯解析函数 + pairing 错误判定 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  isPairingError,
  parseIdeviceIdOutput,
  parseIdeviceInfoOutput,
} from '../src/ios_devices.js';

describe('parseIdeviceIdOutput', () => {
  it('40 位 hex 与新式连字符 UDID 均接收，一行一个', () => {
    const out = [
      '6043dd6adc17c6556d212b8c3591fa8f7d243c96',
      '00008120-001A2B3C4D5E6F70',
      '',
    ].join('\n');
    assert.deepEqual(parseIdeviceIdOutput(out), [
      '6043dd6adc17c6556d212b8c3591fa8f7d243c96',
      '00008120-001A2B3C4D5E6F70',
    ]);
  });

  it('错误行/噪声行忽略；空输出回空表', () => {
    assert.deepEqual(parseIdeviceIdOutput('ERROR: Unable to retrieve device list!\n'), []);
    assert.deepEqual(parseIdeviceIdOutput(''), []);
    assert.deepEqual(parseIdeviceIdOutput('short\n'), []);
  });
});

describe('parseIdeviceInfoOutput', () => {
  it('全量 dump 提取 DeviceName/ProductVersion/ProductType（真机 iPad7,11 样例）', () => {
    const out = [
      'ActivationState: Activated',
      'DeviceClass: iPad',
      'DeviceName: iPad',
      'ProductType: iPad7,11',
      'ProductVersion: 18.7.9',
      'TimeZone: Asia/Shanghai',
    ].join('\n');
    assert.deepEqual(parseIdeviceInfoOutput(out), {
      device_name: 'iPad',
      os_version: '18.7.9',
      product_type: 'iPad7,11',
    });
  });

  it('键缺失回空串（未信任设备 dump 截断）', () => {
    assert.deepEqual(parseIdeviceInfoOutput('DeviceClass: iPhone\n'), {
      device_name: '',
      os_version: '',
      product_type: '',
    });
  });

  it('值含冒号不截断（DeviceName: iPad: work 之类）', () => {
    assert.equal(parseIdeviceInfoOutput('DeviceName: iPad: work\n').device_name, 'iPad: work');
  });
});

describe('isPairingError', () => {
  it('配对/信任类错误命中；普通超时不命中', () => {
    assert.ok(isPairingError('ERROR: Could not connect to lockdownd: Please trust this computer'));
    assert.ok(isPairingError('ERROR: pairing dialog response pending'));
    assert.ok(isPairingError('ERROR: device is password protected'));
    assert.ok(isPairingError('Invalid HostID (device not paired?)'));
    assert.equal(isPairingError('ETIMEDOUT: command timed out'), false);
  });
});
