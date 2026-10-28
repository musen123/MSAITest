/**
 * Agent 配置装载 —— env 优先，agent.config.json 兜底（契约 §10）。
 *
 * 四个配置项（逐 key 取优先级：环境变量 > 配置文件 > 缺省值）：
 * - PLATFORM_WS_URL   平台控制隧道地址（wss://<平台>/api/v1/app/agents/ws），必填
 * - AGENT_TOKEN       平台签发的明文 token（POST /api/v1/app/agents 响应仅返回一次），必填
 * - HOST_FINGERPRINT  宿主机指纹；缺省 = 机器标识哈希（首连即被平台绑定，之后不符拒连）
 * - ADB_PATH          adb 可执行路径；缺省 `adb`（依赖 PATH）
 * - HDC_PATH          鸿蒙 hdc 可执行路径；可选——配了才启用鸿蒙 NEXT 设备发现（H1）
 * - IDEVICE_PATH      iOS idevice_id 可执行路径；可选——未配则自动探测 brew 常见
 *                     安装位（I1；ideviceinfo/idevicescreenshot 取同目录兄弟）
 * - WDA_PROJECT_PATH  WebDriverAgent.xcodeproj 路径或所在目录；可选——配了 WDA
 *                     死时 Agent 自动 xcodebuild 拉起（I2 存活管理），不配只探活报错
 * - WDA_TEAM_ID       xcodebuild 签名 Team ID（免费个人团队即可）
 * - WDA_BUNDLE_ID     WDA runner 唯一 bundle id（免费账号必须自定义）
 * - WDA_DEVELOPER_DIR DEVELOPER_DIR 覆盖（xcode-select 指向 CLT 时用，免 sudo）
 */

import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { WdaXcodebuildConfig } from './wda.js';

export const AGENT_VERSION = '0.1.0';
/** P1 能力声明：scrcpy 投屏数据面已接通（S1 spike 落地，见 src/scrcpy.ts） */
export const CAPABILITIES = ['scrcpy'];

// ---------------------------------------------------------------------------
// scrcpy-server 钉版（S1 裁决 §产物 + 契约 §3.1）
// ---------------------------------------------------------------------------

/** scrcpy-server 协议版本；@yume-chan/scrcpy 的 ScrcpyOptions3_3_3 与之对齐 */
export const SCRCPY_SERVER_VERSION = '3.3.3';

/**
 * 钉版 jar 期望 sha256（S1-RESULT.md 产物清单）。启动时强校验：不符即拒启，
 * 绝不用未知 jar 起 scrcpy-server（官方 client 会覆盖同路径 jar 成 4.0，见 S1 地雷 #6）。
 */
export const SCRCPY_SERVER_SHA256 =
  '7e70323ba7f259649dd4acce97ac4fefbae8102b2c6d91e2e7be613fd5354be0';

/** 钉版 jar 落点：随工程分发的 vendor/（相对本模块解析，不受 cwd 影响） */
export const SCRCPY_SERVER_JAR_PATH = fileURLToPath(
  new URL(`../vendor/scrcpy-server-v${SCRCPY_SERVER_VERSION}`, import.meta.url),
);

export interface AgentConfig {
  platformWsUrl: string;
  agentToken: string;
  hostFingerprint: string;
  adbPath: string;
  /** 鸿蒙 hdc 路径；undefined = 未配置，鸿蒙设备发现关闭 */
  hdcPath?: string;
  /** iOS idevice_id 路径；undefined = 未配置且未探测到，iOS 设备发现关闭 */
  ideviceIdPath?: string;
  /** WDA xcodebuild 自启配置；undefined = 只探活不自启（I2） */
  wdaXcodebuild?: WdaXcodebuildConfig;
}

const CONFIG_KEYS = [
  'PLATFORM_WS_URL',
  'AGENT_TOKEN',
  'HOST_FINGERPRINT',
  'ADB_PATH',
  'HDC_PATH',
  'IDEVICE_PATH',
  'WDA_PROJECT_PATH',
  'WDA_TEAM_ID',
  'WDA_BUNDLE_ID',
  'WDA_DEVELOPER_DIR',
] as const;
type ConfigKey = (typeof CONFIG_KEYS)[number];

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

/**
 * 机器标识哈希：hostname + platform/arch + 非回环网卡 MAC（排序去重）做 sha256。
 * 重启/换 IP 稳定，换网卡或改主机名才变——变了等价于换宿主机，平台侧拒连是预期行为，
 * 此时应显式配置 HOST_FINGERPRINT 或走平台重新绑定。
 */
export function machineFingerprint(): string {
  const macs = new Set<string>();
  for (const nics of Object.values(os.networkInterfaces())) {
    for (const nic of nics ?? []) {
      if (!nic.internal && nic.mac && nic.mac !== '00:00:00:00:00:00') macs.add(nic.mac);
    }
  }
  const material = [os.hostname(), os.platform(), os.arch(), ...[...macs].sort()].join('|');
  return createHash('sha256').update(material).digest('hex');
}

function readConfigFile(filePath: string): Partial<Record<ConfigKey, string>> {
  let raw: string;
  try {
    raw = readFileSync(filePath, 'utf-8');
  } catch {
    return {}; // 文件不存在 = 纯 env 配置，合法
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new ConfigError(`${filePath} 不是合法 JSON`);
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new ConfigError(`${filePath} 应为 JSON 对象`);
  }
  const result: Partial<Record<ConfigKey, string>> = {};
  for (const key of CONFIG_KEYS) {
    const value = (parsed as Record<string, unknown>)[key];
    if (typeof value === 'string') result[key] = value;
  }
  return result;
}

/**
 * 校验钉版 scrcpy-server jar 的 sha256（契约 §3.1 编码器地雷防护的第 0 道闸）。
 * jar 缺失或哈希不符时抛 ConfigError——启动即失败，不带病起投屏。
 */
export function verifyScrcpyServerJar(
  jarPath: string = SCRCPY_SERVER_JAR_PATH,
  expectedSha256: string = SCRCPY_SERVER_SHA256,
): void {
  let bytes: Buffer;
  try {
    bytes = readFileSync(jarPath);
  } catch {
    throw new ConfigError(
      `scrcpy-server jar 缺失: ${jarPath}（应随工程分发在 vendor/，检查是否漏拉大文件）`,
    );
  }
  const actual = createHash('sha256').update(bytes).digest('hex');
  if (actual !== expectedSha256) {
    throw new ConfigError(
      `scrcpy-server jar 校验失败: 期望 ${expectedSha256} 实得 ${actual}（jar 可能被官方 client 覆盖为其它版本，S1 地雷 #6）`,
    );
  }
}

/**
 * 探测 adb 可用性：`adb version` 能跑通即可用（不校验设备）。
 * 不可用时抛 ConfigError——投屏靠 adb forward + app_process，adb 缺席时启动即无意义。
 */
export function checkAdbAvailable(adbPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    execFile(adbPath, ['version'], { timeout: 5_000 }, (err) => {
      if (err) {
        reject(
          new ConfigError(
            `adb 不可用（path=${adbPath}）: ${err.message}（安装 platform-tools 或设置 ADB_PATH）`,
          ),
        );
      } else {
        resolve();
      }
    });
  });
}

/**
 * vendor/ 下随工程分发的平台工具解析：按当前 OS+arch 找 vendored 二进制，
 * 找到返回绝对路径、否则 undefined（回退 PATH / 未配置）。让「拷到装了 Node 的任意
 * 电脑直接跑」成立——adb/hdc 随包带、免单独装 SDK。与 scrcpy jar 同款 module-relative
 * 解析（不看 cwd）。
 *
 * 目录约定：`vendor/<subdir>/<platform-key>/<name>[.exe]`，platform-key 依次尝试
 * `<platform>-<arch>` → `<platform>`（darwin 的 adb 是 universal 二进制、单 darwin 槽即可；
 * win/linux 按 arch 分）。混合系统把各平台二进制填进对应槽即可（见 scripts/populate-sdks.mjs）。
 */
export function resolveVendoredTool(subdir: string, name: string): string | undefined {
  const plat = os.platform();
  const exe = plat === 'win32' ? `${name}.exe` : name;
  for (const key of [`${plat}-${os.arch()}`, plat]) {
    const candidate = fileURLToPath(
      new URL(`../vendor/${subdir}/${key}/${exe}`, import.meta.url),
    );
    if (existsSync(candidate)) return candidate;
  }
  return undefined;
}

export function loadConfig(
  configPath: string = path.resolve(process.cwd(), 'agent.config.json'),
): AgentConfig {
  const file = readConfigFile(configPath);
  // 空串视同未配置：example 文件里 HOST_FINGERPRINT 留空即走缺省指纹
  const pick = (key: ConfigKey): string => {
    const fromEnv = process.env[key];
    if (fromEnv !== undefined && fromEnv !== '') return fromEnv;
    const fromFile = file[key];
    if (fromFile !== undefined && fromFile !== '') return fromFile;
    return '';
  };

  const platformWsUrl = pick('PLATFORM_WS_URL');
  if (!platformWsUrl) {
    throw new ConfigError('缺少 PLATFORM_WS_URL（env 或 agent.config.json）');
  }
  if (!/^wss?:\/\//.test(platformWsUrl)) {
    throw new ConfigError(`PLATFORM_WS_URL 须为 ws:// 或 wss:// 地址: ${platformWsUrl}`);
  }
  const agentToken = pick('AGENT_TOKEN');
  if (!agentToken) {
    throw new ConfigError('缺少 AGENT_TOKEN（env 或 agent.config.json）');
  }

  const wdaProjectPath = pick('WDA_PROJECT_PATH');
  return {
    platformWsUrl,
    agentToken,
    hostFingerprint: pick('HOST_FINGERPRINT') || machineFingerprint(),
    // 优先级：显式配置 > vendor/ 随包二进制 > PATH（adb）/ 未配置（hdc）
    adbPath: pick('ADB_PATH') || resolveVendoredTool('platform-tools', 'adb') || 'adb',
    hdcPath: pick('HDC_PATH') || resolveVendoredTool('hdc', 'hdc') || undefined,
    ideviceIdPath: pick('IDEVICE_PATH') || probeIdeviceId(),
    wdaXcodebuild: wdaProjectPath
      ? {
          projectPath: wdaProjectPath,
          teamId: pick('WDA_TEAM_ID') || undefined,
          bundleId: pick('WDA_BUNDLE_ID') || undefined,
          developerDir: pick('WDA_DEVELOPER_DIR') || undefined,
        }
      : undefined,
  };
}

/** 未显式配置时自动探测 idevice_id（brew ARM/Intel 常见安装位；探不到=iOS 发现关闭） */
function probeIdeviceId(): string | undefined {
  for (const candidate of ['/opt/homebrew/bin/idevice_id', '/usr/local/bin/idevice_id']) {
    if (existsSync(candidate)) return candidate;
  }
  return undefined;
}
