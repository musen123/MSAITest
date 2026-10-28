/**
 * 宿主机 Agent 入口 —— 装配置、校验 scrcpy jar + adb、起设备轮询、连平台隧道、
 * 装配投屏数据面（ScrcpyManager），收 SIGINT/SIGTERM 优雅退出（清活跃投屏会话）。
 * 运行：`npx tsx src/index.ts`（部署示例见 README）。
 */

import {
  AGENT_VERSION,
  ConfigError,
  checkAdbAvailable,
  loadConfig,
  verifyScrcpyServerJar,
} from './config.js';
import { AutomationManager } from './automation_manager.js';
import { DeviceWatcher } from './devices.js';
import { HdcWatcher } from './hdc_devices.js';
import { IosWatcher } from './ios_devices.js';
import { log } from './log.js';
import { ManualRecordManager } from './manual_record.js';
import { ReportCleaner } from './report_cleaner.js';
import { buildRpcDispatcher, dispatchRpcWithTimeout } from './rpc.js';
import { ScreenshotCapturer } from './screenshot.js';
import { ScrcpyManager } from './scrcpy_manager.js';
import { Tunnel } from './tunnel.js';
import { WdaManager } from './wda.js';

async function main(): Promise<void> {
  let cfg;
  try {
    cfg = loadConfig();
    // 契约 §3.1 编码器地雷防护第 0 道闸：钉版 jar 校验 + adb 可用性，缺一即拒启
    verifyScrcpyServerJar();
    await checkAdbAvailable(cfg.adbPath);
  } catch (err) {
    if (err instanceof ConfigError) {
      log('error', `配置错误: ${err.message}`);
      process.exit(1);
    }
    throw err;
  }

  log('info', '宿主机 Agent 启动', {
    version: AGENT_VERSION,
    url: cfg.platformWsUrl,
    // 指纹只打前 12 位，日志里不落全量标识
    fingerprint: cfg.hostFingerprint.slice(0, 12),
    adbPath: cfg.adbPath,
    hdc: cfg.hdcPath ? cfg.hdcPath : '(未配置,鸿蒙发现关闭)',
    idevice: cfg.ideviceIdPath ? cfg.ideviceIdPath : '(未探测到,iOS 发现关闭)',
    wdaAutoStart: cfg.wdaXcodebuild ? cfg.wdaXcodebuild.projectPath : '(未配置,WDA 死时仅报错)',
  });

  // Midscene 走与 Agent 同一个 adb（避免连错设备），显式钉路径
  process.env.MIDSCENE_ADB_PATH = cfg.adbPath;
  // 鸿蒙:Midscene harmony agent 会 spawn hdc,钉 server 端口默认 8710（实测教训:
  // 已有 server 时新端口不接管,全线统一到默认端口才能打到同一 server）
  if (cfg.hdcPath) process.env.HDC_SERVER_PORT ??= '8710';

  // 投屏编排：一次一台 gate + data-WS 数据面（android=ScrcpySession /
  // harmony=HarmonyCastSession,按合并快照的 platform 分派;闭包惰性求值,
  // watcher 在下方才初始化,首次 start_scrcpy RPC 时早已就绪）
  // serial → platform（adb + hdc 合并快照查询）；投屏与自动化共用
  const resolvePlatform = (serial: string) =>
    [...watcher.snapshot(), ...(hdcWatcher?.snapshot() ?? []), ...(iosWatcher?.snapshot() ?? [])].find((d) => d.serial === serial)
      ?.platform ?? 'android';
  // WDA 存活管理（I2/I3）：iOS 执行/投屏前探活→iproxy 自拉起→可选 xcodebuild 自启。
  // 与 iOS 设备发现同门槛（idevice 工具链在才有 iproxy 兄弟可用）
  const wda = cfg.ideviceIdPath
    ? new WdaManager({ ideviceIdPath: cfg.ideviceIdPath, xcodebuild: cfg.wdaXcodebuild })
    : undefined;
  const scrcpy = new ScrcpyManager(cfg, { resolvePlatform, wda });
  // 自动化执行内核：一次一台录制/回放会话（android=AndroidAgent /
  // harmony=HarmonyAgent / ios=IOSAgent,按 platform 三路分派）
  const automation = new AutomationManager({ resolvePlatform, hdcPath: cfg.hdcPath, wda });
  // 手动录制：投屏触控流 tee → VL 语义化步骤（操作台「手动录制」，安卓/鸿蒙/iOS 同构）
  const manualRecord = new ManualRecordManager({
    adbPath: cfg.adbPath,
    hdcPath: cfg.hdcPath,
    wda,
    resolvePlatform,
  });
  scrcpy.setControlObserver((sessionId, data) => manualRecord.onControl(sessionId, data));
  // 单 iOS 守卫探针（wda 构造早于三管理器，后绑）：已绑定 iOS 设备有活跃
  // 执行/投屏/录制会话时，另一台 iOS 的 ensureAlive 明确拒绝而非杀旧换绑
  wda?.setBusyProbe(
    (udid) =>
      automation.hasSessionForSerial(udid) ||
      scrcpy.hasSessionForSerial(udid) ||
      manualRecord.hasSessionForSerial(udid),
  );
  const dispatch = buildRpcDispatcher({ scrcpy, automation, manualRecord });

  const tunnel = new Tunnel(cfg, {
    // adb + hdc 两路 watcher 的合并快照（心跳/对账共用）
    getSnapshot: () =>
      [...watcher.snapshot(), ...(hdcWatcher?.snapshot() ?? []), ...(iosWatcher?.snapshot() ?? [])],
    dispatchRpc: (cmd, params, timeoutMs) =>
      dispatchRpcWithTimeout(dispatch, cmd, params, timeoutMs),
    // 控制隧道断开：清活跃投屏 + 自动化会话（网关侧已无法下发 stop/abort，Agent 兜底）
    onDisconnect: (reason) => {
      void scrcpy.stopAll(reason);
      void automation.stopAll(reason);
      void manualRecord.stopAll(reason);
    },
  });
  const watcher = new DeviceWatcher(cfg.adbPath, ({ event, device }) =>
    tunnel.sendDeviceEvent(event, device),
  );
  // 鸿蒙 NEXT 设备发现（H1）：配置了 HDC_PATH 才启用，与 adb 侧同构共用事件出口
  const hdcWatcher = cfg.hdcPath
    ? new HdcWatcher(cfg.hdcPath, ({ event, device }) => tunnel.sendDeviceEvent(event, device))
    : undefined;
  // iOS 设备发现（I1）：配置/探测到 idevice_id 才启用，与 adb/hdc 侧同构共用事件出口
  const iosWatcher = cfg.ideviceIdPath
    ? new IosWatcher(cfg.ideviceIdPath, ({ event, device }) => tunnel.sendDeviceEvent(event, device))
    : undefined;

  // 设备静态截图采集（列表缩略图，契约 §2.1；android+harmony+ios 三通道）
  const screenshots = new ScreenshotCapturer({
    adbPath: cfg.adbPath,
    hdcPath: cfg.hdcPath,
    ideviceIdPath: cfg.ideviceIdPath,
    getSnapshot: () =>
      [...watcher.snapshot(), ...(hdcWatcher?.snapshot() ?? []), ...(iosWatcher?.snapshot() ?? [])],
    isReady: () => tunnel.isReady(),
    onShot: (serial, dataB64, capturedAt) => tunnel.sendScreenshot(serial, dataB64, capturedAt),
  });

  // Midscene 落盘报告磁盘守护（启动全清孤儿 332MB→0 + 周期清超龄），
  // baseDir=cwd 与 automation.ts reportFilePath 同源
  const reportCleaner = new ReportCleaner(process.cwd());

  watcher.start();
  hdcWatcher?.start();
  iosWatcher?.start();
  tunnel.start();
  screenshots.start();
  void reportCleaner.start();

  // 自动化会话空闲自愈：图死了（worker 崩）而隧道没断时，会话没人来 end，
  // 每 60s 扫一次，空闲超 10min 的会话自动 dispose 释放设备（终极兜底；
  // 图活着的正常回收走平台 reap_zombies→cancel→图内 abort）。
  const SESSION_IDLE_TTL_MS = 10 * 60_000;
  const idleSweep = setInterval(() => automation.reapIdle(SESSION_IDLE_TTL_MS), 60_000);
  idleSweep.unref?.();

  let shuttingDown = false;
  const shutdown = (signal: string): void => {
    if (shuttingDown) return;
    shuttingDown = true;
    log('info', `收到 ${signal}，优雅退出`);
    clearInterval(idleSweep);
    reportCleaner.stop();
    screenshots.stop();
    watcher.stop();
    hdcWatcher?.stop();
    iosWatcher?.stop();
    tunnel.stop();
    wda?.stop(); // 只杀本进程 spawn 的 iproxy/xcodebuild，手起的不动
    // 先优雅停投屏（关 socket 让 server release 编码器，S1 铁律）+ 停自动化
    // （abort aiAct + 清 modelConfig）再退出进程
    void Promise.allSettled([
      scrcpy.stopAll(`signal_${signal}`),
      automation.stopAll(`signal_${signal}`),
      manualRecord.stopAll(`signal_${signal}`),
    ]).finally(() => process.exit(0));
  };
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

void main();
