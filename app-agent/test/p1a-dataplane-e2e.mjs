// p1a-dataplane-e2e.mjs
// P1A · Agent 数据面端到端验证（假网关，独占模拟器，避开登录/ticket）。
//
// 验的是 PRODUCT 代码：app-agent 的真 ScrcpyManager + 真 ScrcpySession（真 adb /
// 真 scrcpy-server 3.3.3 forward tunnel），只把"网关"替换成本脚本起的假 ws server。
// 数据面用默认 WS 工厂（deriveDataWsUrl 从 platformWsUrl 推 data-ws + session_id），
// 只是 platformWsUrl 指向假网关 → 完整走产品出站链路。
//
// 断言四件事（契约 §3.1 + S1 铁律）：
//   1) 假网关经 data-WS 收到 H264 video 字节 ≥ 阈值（打印字节数/包数/首包解析）
//   2) 经 data-WS 发一个 HOME 控制注入回 Agent → 设备焦点从 Settings 变到 launcher
//   3) stop_scrcpy 后设备端 scrcpy Server pid 消失（优雅退出，S1 铁律 #1）
//   4) 一次一台 gate：活跃会话在时第 2 路 start_scrcpy 回 busy
//
// 运行：node spikes/s1-scrcpy/p1a-dataplane-e2e.mjs
// 前置：模拟器已 boot_completed=1 且 /data/local/tmp/scrcpy-server.jar 为钉版 3.3.3。

import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';

import {
  AndroidKeyCode,
  AndroidKeyEventAction,
  ScrcpyControlMessageSerializer,
  ScrcpyOptions3_3_3,
  ScrcpyVideoCodecNameMap,
} from '@yume-chan/scrcpy';
import { ReadableStream } from '@yume-chan/stream-extra';
import { WebSocketServer } from 'ws';

// 产品代码（tsx 直接吃 .ts；这里从 app-agent 源码导入真类）
import { ScrcpyManager } from '../src/scrcpy_manager.ts';

const ADB = process.env.ADB || 'adb';
const SERIAL = process.env.ANDROID_SERIAL || 'emulator-5554';
// server 启动参数（必须与浏览器侧解码用的 ScrcpyOptions3_3_3 一致 → 此处也用它解视频）
const MAX_SIZE = 800;
const BIT_RATE = 2_000_000;
const MAX_FPS = 15;
const TARGET_VIDEO_BYTES = 20_000; // ≥ 若干包（首帧 keyframe 通常就上万字节）
const GATEWAY_PORT = 18899;

function adb(args) {
  return execFileSync(ADB, ['-s', SERIAL, ...args], { encoding: 'utf8' });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function currentFocusOnce() {
  try {
    const out = adb(['shell', 'dumpsys activity activities | grep -m1 topResumedActivity']);
    const m = out.match(/topResumedActivity=ActivityRecord\{[^ ]+ [^ ]+ ([^ }]+)/);
    if (m) return m[1].trim();
  } catch {}
  try {
    const out = adb(['shell', 'dumpsys window | grep -m1 mCurrentFocus']);
    const m = out.match(/mCurrentFocus=Window\{[^ ]+ [^ ]+ ([^ }]+)/);
    if (m) return m[1].trim();
  } catch {}
  return null;
}
function currentFocus() {
  for (let i = 0; i < 10; i++) {
    const f = currentFocusOnce();
    if (f) return f;
    try { execFileSync('sleep', ['0.2']); } catch {}
  }
  return '(none)';
}
function deviceScrcpyPids() {
  try {
    const out = adb([
      'shell',
      'ps -A -o PID,ARGS | grep com.genymobile.scrcpy.Server | grep -v grep',
    ]);
    return out
      .trim()
      .split('\n')
      .filter(Boolean)
      .map((l) => l.trim().split(/\s+/)[0]);
  } catch {
    return []; // grep 无匹配 exit 1
  }
}

async function main() {
  const report = {
    video: { bytes: 0, frames: 0, meta: null, firstPackets: [], pass: false },
    control: { focusBefore: null, focusAfter: null, pass: false },
    gracefulStop: { pidsBefore: [], pidsAfter: [], pass: false },
    gate: { secondStart: null, pass: false },
  };

  // ── 假网关：ws server 扮演平台 data-ws 端点 ──
  // Agent 出站会连 ws://127.0.0.1:<port>/api/v1/app/agents/data-ws?session_id=<sid>
  const httpServer = createServer();
  const wss = new WebSocketServer({ server: httpServer, path: '/api/v1/app/agents/data-ws' });
  let gatewaySocket = null; // Agent 连上来的那条
  const gatewayReady = new Promise((resolve) => {
    wss.on('connection', (sock, req) => {
      gatewaySocket = sock;
      console.log('[gateway] Agent data-WS 连入:', req.url);
      sock.on('message', (data, isBinary) => {
        if (!isBinary) return;
        report.video.bytes += data.length;
        report.video.frames += 1;
        pushVideoChunk(data);
      });
      sock.on('close', (code) => console.log('[gateway] Agent data-WS 关闭 code=', code));
      resolve();
    });
  });
  await new Promise((r) => httpServer.listen(GATEWAY_PORT, '127.0.0.1', r));
  console.log(`[gateway] 假网关 data-ws 监听 :${GATEWAY_PORT}`);

  // 把假网关收到的 video 字节喂给 @yume-chan 解析器（证明真是可解的 H264 流）
  let videoController = null;
  const videoBuffer = [];
  const videoStream = new ReadableStream({
    start(c) {
      videoController = c;
      for (const b of videoBuffer) c.enqueue(b);
      videoBuffer.length = 0;
    },
  });
  function pushVideoChunk(data) {
    const u8 = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    if (videoController) videoController.enqueue(u8);
    else videoBuffer.push(u8);
  }

  const options = new ScrcpyOptions3_3_3({
    audio: false,
    control: true,
    maxSize: MAX_SIZE,
    videoBitRate: BIT_RATE,
    maxFps: MAX_FPS,
  });

  // ── 驱动产品 ScrcpyManager（真 ScrcpySession + 默认 WS 工厂指向假网关）──
  const cfg = {
    platformWsUrl: `ws://127.0.0.1:${GATEWAY_PORT}/api/v1/app/agents/ws`,
    agentToken: 'e2e-fake-token',
    hostFingerprint: 'e2e',
    adbPath: ADB,
  };
  const manager = new ScrcpyManager(cfg);
  const sessionId = `s-e2e-${Date.now()}`;

  // 先把设备置于非 launcher（打开 Settings），让 HOME 有可见效果
  adb(['shell', 'am', 'start', '-n', 'com.android.settings/.Settings']);
  await sleep(2500);
  report.control.focusBefore = currentFocus();
  console.log('[ctrl] focus BEFORE HOME:', report.control.focusBefore);

  try {
    // ── start_scrcpy #1 ──
    console.log('[e2e] startScrcpy #1 …');
    const started = await manager.startScrcpy({
      serial: SERIAL,
      sessionId,
      maxFps: MAX_FPS,
      bitRate: BIT_RATE,
      // maxSize 不在 StartScrcpyParams 契约里；会话层缺省 1080。此处用契约参数即可，
      // 解码只需 codec/尺寸从流 metadata 读，不依赖客户端预设 maxSize。
    });
    console.log('[e2e] startScrcpy #1 ->', JSON.stringify(started));
    await gatewayReady;

    // ── 一次一台 gate：第 2 路 start 应 busy ──
    try {
      await manager.startScrcpy({ serial: SERIAL, sessionId: `${sessionId}-2` });
      report.gate.secondStart = 'UNEXPECTED_OK';
    } catch (err) {
      report.gate.secondStart = err && err.message ? err.message : String(err);
    }
    report.gate.pass = report.gate.secondStart === 'busy';
    console.log('[gate] 第 2 路 start ->', report.gate.secondStart, report.gate.pass ? 'PASS' : 'FAIL');

    // ── 收视频 + 解析 ──
    // 制造屏幕活动逼编码器出帧（静态屏几乎不出帧）
    let stirring = true;
    (async () => {
      let toggle = false;
      while (stirring) {
        try {
          toggle = !toggle;
          adb(['shell', 'input', 'swipe', '300', toggle ? '1200' : '400', '300', toggle ? '400' : '1200', '120']);
        } catch {}
        await sleep(250);
      }
    })();

    // 解析 metadata（证明假网关经 data-WS 转出的字节是可解的 H264 流）
    let metadata, packetSource;
    try {
      const parsed = await Promise.race([
        options.parseVideoStreamMetadata(videoStream),
        (async () => { await sleep(15000); throw new Error('parse metadata timeout'); })(),
      ]);
      metadata = parsed.metadata;
      packetSource = parsed.stream;
      const codecName =
        ScrcpyVideoCodecNameMap.get(metadata.codec) ?? `0x${metadata.codec.toString(16)}`;
      report.video.meta = {
        deviceName: metadata.deviceName,
        codec: codecName,
        width: metadata.width,
        height: metadata.height,
      };
      console.log('[video] metadata:', JSON.stringify(report.video.meta));
    } catch (e) {
      console.log('[video] metadata 解析失败/超时:', e.message);
    }

    if (packetSource) {
      const packetStream = packetSource.pipeThrough(options.createMediaStreamTransformer());
      const reader = packetStream.getReader();
      const pktDeadline = Date.now() + 15000;
      let dataPackets = 0;
      let configPackets = 0;
      while (report.video.bytes < TARGET_VIDEO_BYTES || dataPackets < 5) {
        if (Date.now() > pktDeadline) break;
        const { value: packet, done } = await reader.read();
        if (done) break;
        if (packet.type === 'configuration') {
          configPackets += 1;
          continue;
        }
        dataPackets += 1;
        if (report.video.firstPackets.length < 5) {
          report.video.firstPackets.push({
            n: dataPackets,
            size: packet.data.length,
            keyframe: !!packet.keyframe,
            pts: packet.pts?.toString(),
          });
        }
      }
      reader.releaseLock();
      report.video.configPackets = configPackets;
      report.video.dataPackets = dataPackets;
    }
    stirring = false;

    report.video.pass =
      report.video.bytes >= TARGET_VIDEO_BYTES && !!(report.video.meta && report.video.meta.width);
    console.log(
      `[video] 假网关收到 video 字节=${report.video.bytes} 帧=${report.video.frames} dataPkts=${report.video.dataPackets} cfgPkts=${report.video.configPackets}`,
    );
    console.log('[video] first packets:', JSON.stringify(report.video.firstPackets));

    // ── 控制注入：经 data-WS 发 HOME down/up 回 Agent → Agent writeControl 到设备 ──
    // 先重置回 Settings（stir 的 swipe 不会切走 activity，但保险）
    adb(['shell', 'am', 'start', '-n', 'com.android.settings/.Settings']);
    await sleep(1500);
    const focusBeforeHome = currentFocus();
    report.control.focusBefore = focusBeforeHome;
    console.log('[ctrl] focus BEFORE HOME (re-check):', focusBeforeHome);

    const serializer = new ScrcpyControlMessageSerializer(options);
    const downBytes = serializer.injectKeyCode({
      action: AndroidKeyEventAction.Down,
      keyCode: AndroidKeyCode.AndroidHome,
      repeat: 0,
      metaState: 0,
    });
    const upBytes = serializer.injectKeyCode({
      action: AndroidKeyEventAction.Up,
      keyCode: AndroidKeyCode.AndroidHome,
      repeat: 0,
      metaState: 0,
    });
    console.log('[ctrl] HOME down hex:', Buffer.from(downBytes).toString('hex'));
    // 经假网关的 data-WS 二进制帧发回 Agent（浏览器→Agent 方向）
    gatewaySocket.send(Buffer.from(downBytes));
    await sleep(60);
    gatewaySocket.send(Buffer.from(upBytes));
    await sleep(2500);
    report.control.focusAfter = currentFocus();
    console.log('[ctrl] focus AFTER HOME:', report.control.focusAfter);
    const isLauncher = (f) => /Launcher|launcher/.test(f || '');
    report.control.pass =
      report.control.focusBefore !== report.control.focusAfter &&
      isLauncher(report.control.focusAfter) &&
      !isLauncher(report.control.focusBefore);

    // ── stop_scrcpy → 设备端 scrcpy pid 应消失（优雅退出）──
    report.gracefulStop.pidsBefore = deviceScrcpyPids();
    console.log('[stop] 停前设备 scrcpy pids:', JSON.stringify(report.gracefulStop.pidsBefore));
    const stopped = await manager.stopScrcpy(sessionId);
    console.log('[stop] stopScrcpy ->', JSON.stringify(stopped));
    // teardown 内部已轮询 pid 消失；再确认一次
    await sleep(500);
    report.gracefulStop.pidsAfter = deviceScrcpyPids();
    console.log('[stop] 停后设备 scrcpy pids:', JSON.stringify(report.gracefulStop.pidsAfter));
    report.gracefulStop.pass =
      report.gracefulStop.pidsBefore.length > 0 && report.gracefulStop.pidsAfter.length === 0;
  } finally {
    // 兜底清理：无论如何停所有会话 + 关假网关
    try { await manager.stopAll('e2e_cleanup'); } catch {}
    try { wss.close(); } catch {}
    try { httpServer.close(); } catch {}
  }

  const allPass =
    report.video.pass && report.control.pass && report.gracefulStop.pass && report.gate.pass;

  console.log('\n========== P1A DATAPLANE E2E RESULT ==========');
  console.log(JSON.stringify(report, null, 2));
  console.log('==============================================');
  console.log(`① video 字节到达假网关+可解 : ${report.video.pass ? 'PASS' : 'FAIL'} (${report.video.bytes} bytes)`);
  console.log(`② HOME 控制注入生效         : ${report.control.pass ? 'PASS' : 'FAIL'}`);
  console.log(`③ stop 后设备 pid 消失      : ${report.gracefulStop.pass ? 'PASS' : 'FAIL'}`);
  console.log(`④ 一次一台 gate（busy）     : ${report.gate.pass ? 'PASS' : 'FAIL'}`);
  console.log(`总裁决: ${allPass ? 'GO' : 'NO-GO'}`);

  await sleep(500); // 让 server 彻底 release 编码器
  process.exit(allPass ? 0 : 1);
}

main().catch(async (err) => {
  console.error('FATAL:', err);
  process.exit(2);
});
