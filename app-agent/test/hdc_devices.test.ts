/** 鸿蒙设备发现单测:list targets 解析 / 富化输出解析(真机 BLK-AL80 实测样本) */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { parseHdcDeviceExtra, parseHdcTargetsOutput } from '../src/hdc_devices.js';

describe('parseHdcTargetsOutput', () => {
  it('真机样本:USB Connected → device/usb/harmony', () => {
    const out = '4ACVB24929010894\t\tUSB\tConnected\tlocalhost\n';
    const devices = parseHdcTargetsOutput(out);
    assert.equal(devices.length, 1);
    assert.deepEqual(devices[0], {
      serial: '4ACVB24929010894',
      state: 'device',
      model: '',
      brand: '',
      android_version: '',
      resolution: '',
      connection: 'usb',
      platform: 'harmony',
    });
  });

  it('[Empty] / 空行 → 空列表', () => {
    assert.deepEqual(parseHdcTargetsOutput('[Empty]\n'), []);
    assert.deepEqual(parseHdcTargetsOutput('\n\n'), []);
  });

  it('非 Connected 状态折叠 offline;TCP 连接判 tcpip', () => {
    const out = 'AAA111\tUSB\tOffline\tlocalhost\n192.168.1.5:5555\tTCP\tConnected\tlocalhost\n';
    const devices = parseHdcTargetsOutput(out);
    assert.equal(devices[0]?.state, 'offline');
    assert.equal(devices[1]?.state, 'device');
    assert.equal(devices[1]?.connection, 'tcpip');
    assert.equal(devices[1]?.serial, '192.168.1.5:5555');
  });
});

describe('parseHdcDeviceExtra', () => {
  it('真机样本:brand/model/版本/分辨率全解析', () => {
    const out = [
      'HUAWEI',
      'BLK-AL80',
      '6.1.0',
      '',
      '-------------------------------[ability]-------------------------------',
      '----------------------------------RenderService----------------------------------',
      '-- ScreenInfo',
      'screen[0]: id=0, powerStatus=POWER_STATUS_OFF, backlight=2056, screenType=EXTERNAL_TYPE, render resolution=1084x2412, physical resolution=1084x2412, isVirtual=false',
      'supportedMode[0]: 1084x2412, refreshRate=60',
    ].join('\n');
    assert.deepEqual(parseHdcDeviceExtra(out), {
      brand: 'HUAWEI',
      model: 'BLK-AL80',
      os_version: '6.1.0',
      resolution: '1084x2412',
    });
  });

  it('param 失败行(fail!/errNum)置空,不当值', () => {
    const out = 'HUAWEI\nGet parameter "const.product.model" fail! errNum is:1002!\n6.1.0\n';
    const extra = parseHdcDeviceExtra(out);
    assert.equal(extra.brand, 'HUAWEI');
    assert.equal(extra.model, '');
    assert.equal(extra.os_version, '6.1.0');
    assert.equal(extra.resolution, '');
  });
});
