#!/usr/bin/env node
/**
 * 填充 vendor/platform-tools/ 各平台 adb（安卓 SDK platform-tools）。
 *
 * 让「把 app-agent 拷到装了 Node 的任意电脑直接跑」成立：adb 随包带、免单独装 SDK。
 * config.ts 的 resolveVendoredTool 会按当前 OS+arch 选 `vendor/platform-tools/<平台>/adb`。
 *
 * 用法：node scripts/populate-sdks.mjs [darwin|win32-x64|linux-x64|all]
 * 不传参默认 all（三平台都填，供混合系统分发）。
 *
 * 数据源 = Google 官方 platform-tools（可再分发，scrcpy/Genymotion 等广泛打包）。
 * 依赖：curl + unzip（macOS/Linux 自带；Windows 用 Git-Bash 或 WSL，或手动解压见 README）。
 *
 * ⚠ 鸿蒙 hdc 不在此脚本内——HarmonyOS SDK 许可限制再分发，需手动把 hdc 放进
 *   vendor/hdc/<平台>/（见 vendor/hdc/README.md）。
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, copyFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VENDOR = fileURLToPath(new URL('../vendor/platform-tools', import.meta.url));
const BASE = 'https://dl.google.com/android/repository';

// slot → { zip 名, 从解压出的 platform-tools/ 里取哪些文件 }
const TARGETS = {
  darwin: { zip: 'platform-tools-latest-darwin.zip', files: ['adb'] }, // universal，覆盖 arm64+x64
  'win32-x64': {
    zip: 'platform-tools-latest-windows.zip',
    files: ['adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll'], // adb.exe 运行必需两个 DLL
  },
  'linux-x64': { zip: 'platform-tools-latest-linux.zip', files: ['adb'] },
};

const which = process.argv[2] || 'all';
const slots = which === 'all' ? Object.keys(TARGETS) : [which];

for (const slot of slots) {
  const t = TARGETS[slot];
  if (!t) {
    console.error(`未知平台槽: ${slot}（可选 ${Object.keys(TARGETS).join(' / ')} / all）`);
    process.exit(1);
  }
  const tmp = mkdtempSync(path.join(tmpdir(), 'pt-'));
  const zip = path.join(tmp, 'pt.zip');
  try {
    console.log(`[${slot}] 下载 ${t.zip} …`);
    execFileSync('curl', ['-fsSL', '--max-time', '120', '-o', zip, `${BASE}/${t.zip}`]);
    console.log(`[${slot}] 解压 …`);
    execFileSync('unzip', ['-q', '-o', zip, '-d', tmp]);
    const dst = path.join(VENDOR, slot);
    mkdirSync(dst, { recursive: true });
    for (const f of t.files) {
      const src = path.join(tmp, 'platform-tools', f);
      const out = path.join(dst, f);
      copyFileSync(src, out);
      if (!f.endsWith('.dll')) chmodSync(out, 0o755);
    }
    console.log(`[${slot}] ✓ → ${dst}（${t.files.join(', ')}）`);
  } catch (err) {
    console.error(`[${slot}] 失败: ${err.message}`);
    console.error('  手动方案：下载对应 platform-tools zip，把 adb[.exe]（Windows 另加两个 DLL）放进 vendor/platform-tools/<平台>/');
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}
