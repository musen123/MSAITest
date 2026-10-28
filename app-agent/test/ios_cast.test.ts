/** IosCastSession 单测：JPEG 帧切分 / 手势→W3C actions 编译 / 会话搭车与
 *  invalid-session 重试 / 生命周期（meta 先行、早到帧、流断联动、stop 幂等）。
 *  http/MJPEG 全替身，不碰真 WDA。 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  buildIosMetaFrame,
  compileGestureToActions,
  extractJpegFrames,
  IosCastSession,
  type GesturePoint,
  type MjpegOpener,
} from '../src/ios_cast.js';
import type { WdaLike } from '../src/wda.js';

const JPEG_A = Buffer.from([0xff, 0xd8, 0x01, 0x02, 0xff, 0xd9]);
const JPEG_B = Buffer.from([0xff, 0xd8, 0x03, 0xff, 0xd9]);

describe('extractJpegFrames', () => {
  it('multipart 头噪声中切出两帧，剩余保留半截帧', () => {
    const noise = Buffer.from('--Boundary\r\nContent-type: image/jpg\r\n\r\n');
    const half = Buffer.from([0xff, 0xd8, 0x09]);
    const { frames, rest } = extractJpegFrames(
      Buffer.concat([noise, JPEG_A, noise, JPEG_B, noise, half]),
    );
    assert.equal(frames.length, 2);
    assert.deepEqual(frames[0], JPEG_A);
    assert.deepEqual(frames[1], JPEG_B);
    assert.deepEqual(rest.subarray(0, 3), half); // 从 SOI 起保留
  });

  it('无帧头纯噪声：不出帧，超 4KB 只保尾', () => {
    const { frames, rest } = extractJpegFrames(Buffer.alloc(10_000, 0x41));
    assert.equal(frames.length, 0);
    assert.equal(rest.length, 4096);
  });
});

describe('compileGestureToActions', () => {
  const P = (t: GesturePoint['t'], x: number, y: number, ts: number): GesturePoint => ({
    t,
    x,
    y,
    ts,
  });

  it('纯点按：move(0)→down→pause(按住时长)→up', () => {
    const payload = compileGestureToActions([P('down', 100, 200, 1000), P('up', 100, 200, 1080)]);
    const seq = (payload as any).actions[0].actions;
    assert.deepEqual(
      seq.map((s: any) => s.type),
      ['pointerMove', 'pointerDown', 'pause', 'pointerUp'],
    );
    assert.equal(seq[0].x, 100);
    assert.equal(seq[2].duration, 80);
    assert.equal((payload as any).actions[0].parameters.pointerType, 'touch');
  });

  it('长按：pause=按住时长，钳制到 3000ms 上限', () => {
    const payload = compileGestureToActions([P('down', 1, 1, 0), P('up', 1, 1, 9_000)]);
    const seq = (payload as any).actions[0].actions;
    assert.equal(seq[2].duration, 3_000);
  });

  it('滑动压缩成直线甩动：只保尾点一步（XCTest 每 move ~0.4s,1 步 1.3s vs 6 步 3.15s）', () => {
    const payload = compileGestureToActions([
      P('down', 0, 0, 0),
      P('move', 10, 10, 5),
      P('move', 20, 20, 1_000), // 真实拖了 1s → 总时长钳到 300ms
      P('up', 20, 20, 1_050),
    ]);
    const seq = (payload as any).actions[0].actions;
    assert.deepEqual(
      seq.map((s: any) => s.type),
      ['pointerMove', 'pointerDown', 'pointerMove', 'pointerUp'],
    );
    assert.equal(seq[2].duration, 300); // 单步扛全程时长
    assert.equal(seq[2].x, 20); // 直线到尾点
  });

  it('极快轻扫：总时长托底 60ms（过短 WDA 忽略）', () => {
    const payload = compileGestureToActions([
      P('down', 0, 0, 0),
      P('move', 50, 50, 10),
      P('move', 100, 100, 20), // 真实 20ms → 托底 60ms
      P('up', 100, 100, 25),
    ]);
    const seq = (payload as any).actions[0].actions;
    assert.equal(seq[2].duration, 60);
    assert.equal(seq[2].x, 100);
  });

  it('move 过密仍只出 1 步直线且保尾点', () => {
    const pts: GesturePoint[] = [P('down', 0, 0, 0)];
    for (let i = 1; i <= 200; i++) pts.push(P('move', i, i, i * 3));
    pts.push(P('up', 200, 200, 700));
    const seq = (compileGestureToActions(pts) as any).actions[0].actions;
    const moves = seq.filter((s: any) => s.type === 'pointerMove' && s.duration > 0);
    assert.equal(moves.length, 1);
    assert.equal(moves[0].x, 200);
    assert.equal(moves[0].duration, 300); // 末点 ts=600 → 钳 300
  });

  it('残缺手势（无 down / 无 up / 单点）回 null', () => {
    assert.equal(compileGestureToActions([P('move', 1, 1, 0), P('up', 1, 1, 5)]), null);
    assert.equal(compileGestureToActions([P('down', 1, 1, 0)]), null);
  });
});

// ==================== 会话级（http/MJPEG 替身） ====================

interface HttpCall {
  url: string;
  method: string;
  body?: string;
}

function makeSession(opts?: {
  statusSessionId?: string | null;
  actionsFailFirst?: 'invalid_session' | 'other';
  /** 首次 actions 挂起直到 signal abort（模拟失效 session POST 卡死→超时） */
  actionsHangFirst?: boolean;
  actionsTimeoutMs?: number;
}) {
  const calls: HttpCall[] = [];
  let actionsFailArmed = opts?.actionsFailFirst != null;
  let actionsHangArmed = opts?.actionsHangFirst === true;
  let createdCount = 0;
  const wda: WdaLike & { ensured: string[] } = {
    port: 8100,
    ensured: [],
    async ensureAlive(udid: string) {
      this.ensured.push(udid);
    },
    async pressHome() {},
  };
  let mjpegHandlers: Parameters<MjpegOpener>[0] | undefined;
  let aborted = false;
  const session = new IosCastSession({
    serial: 'UDID-1',
    wda,
    actionsTimeoutMs: opts?.actionsTimeoutMs,
    httpImpl: async (url, init) => {
      const method = init?.method ?? 'GET';
      calls.push({ url, method, body: init?.body });
      const reply = (obj: unknown, ok = true, status = 200) => ({
        ok,
        status,
        json: async () => obj,
      });
      if (url.endsWith('/status')) {
        return reply({ value: {}, sessionId: opts?.statusSessionId ?? null });
      }
      if (url.endsWith('/session') && method === 'POST') {
        createdCount += 1;
        return reply({ value: { sessionId: `created-${createdCount}` } });
      }
      if (url.includes('/window/rect')) {
        return reply({ value: { width: 810, height: 1080 } });
      }
      if (url.endsWith('/actions')) {
        if (actionsHangArmed) {
          actionsHangArmed = false;
          // 挂起直到 signal abort（失效 session POST 卡死的还原），reject AbortError
          return await new Promise((_res, rej) => {
            init?.signal?.addEventListener('abort', () =>
              rej(new DOMException('This operation was aborted', 'AbortError')),
            );
          });
        }
        if (actionsFailArmed) {
          actionsFailArmed = false;
          if (opts?.actionsFailFirst === 'invalid_session') {
            return reply({ value: { error: 'invalid session id' } }, false, 404);
          }
          return reply({ value: { error: 'boom' } }, false, 500);
        }
        return reply({ value: null });
      }
      throw new Error(`unexpected url ${url}`);
    },
    openMjpeg: (handlers) => {
      mjpegHandlers = handlers;
      return {
        abort: () => {
          aborted = true;
        },
      };
    },
  });
  return {
    session,
    calls,
    wda,
    feed: (b: Buffer) => mjpegHandlers?.onChunk(b),
    endStream: () => mjpegHandlers?.onEnd(),
    wasAborted: () => aborted,
    actionsCalls: () => calls.filter((c) => c.url.endsWith('/actions')),
    sidOf: (c: HttpCall) => /\/session\/([^/]+)\/actions/.exec(c.url)?.[1],
  };
}

const down = (x: number, y: number) =>
  Buffer.from(JSON.stringify({ t: 'down', x, y }), 'utf-8');
const up = (x: number, y: number) => Buffer.from(JSON.stringify({ t: 'up', x, y }), 'utf-8');

async function settle(): Promise<void> {
  await new Promise((r) => setTimeout(r, 10));
}

describe('IosCastSession', () => {
  it('start：ensureAlive → meta(point 尺寸)先行 → 帧流接通转发', async () => {
    const h = makeSession();
    await h.session.start();
    assert.deepEqual(h.wda.ensured, ['UDID-1']);
    const got: Uint8Array[] = [];
    h.session.onVideoBytes((b) => got.push(b));
    // meta 是早到帧（start 内 push），注册即补发
    assert.equal(got.length, 1);
    const meta = JSON.parse(Buffer.from(got[0]!).toString('utf-8'));
    assert.deepEqual(meta, { type: 'ios_meta', width: 810, height: 1080 });
    h.feed(Buffer.concat([JPEG_A, JPEG_B]));
    assert.equal(got.length, 3);
    assert.equal(got[1]![0], 0xff);
    await h.session.stop();
  });

  it('搭车现存 WDA 会话（/status 有 sessionId 时不 POST /session）', async () => {
    const h = makeSession({ statusSessionId: 'midscene-sess' });
    await h.session.start();
    h.session.writeControl(down(10, 20));
    h.session.writeControl(up(10, 20));
    await settle();
    assert.equal(h.actionsCalls().length, 1);
    assert.equal(h.sidOf(h.actionsCalls()[0]!), 'midscene-sess');
    assert.ok(!h.calls.some((c) => c.url.endsWith('/session') && c.method === 'POST'));
    await h.session.stop();
  });

  it('无现存会话：自建一次并复用；invalid session 时刷新重试一次', async () => {
    const h = makeSession({ actionsFailFirst: 'invalid_session' });
    await h.session.start();
    h.session.writeControl(down(1, 1));
    h.session.writeControl(up(1, 1));
    await settle();
    // 第一次 actions 用 created-1 → invalid → 重建 created-2 重试成功
    const acts = h.actionsCalls();
    assert.equal(acts.length, 2);
    assert.equal(h.sidOf(acts[0]!), 'created-1');
    assert.equal(h.sidOf(acts[1]!), 'created-2');
    await h.session.stop();
  });

  it('搭车失效残留会话 → actions 超时 → forceNew 新建重试（不再搭车 status）', async () => {
    // start 搭车 stale-sess（失效但 GET window/rect 能用），tap 时 actions 卡死超时
    const h = makeSession({
      statusSessionId: 'stale-sess',
      actionsHangFirst: true,
      actionsTimeoutMs: 30,
    });
    await h.session.start();
    h.session.writeControl(down(5, 5));
    h.session.writeControl(up(5, 5));
    await new Promise((r) => setTimeout(r, 120)); // 等超时(30ms)+重试
    const acts = h.actionsCalls();
    assert.equal(acts.length, 2);
    assert.equal(h.sidOf(acts[0]!), 'stale-sess'); // 首次搭车失效 sid
    assert.equal(h.sidOf(acts[1]!), 'created-1'); // 超时后 forceNew 建新的
    // 重试走 forceNew → 不再 GET /status（全程只 start 时搭车过一次）
    assert.equal(h.calls.filter((c) => c.url.endsWith('/status')).length, 1);
    await h.session.stop();
  });

  it('手势编译进 actions 载荷（down/up 成对,孤儿 move 丢弃）', async () => {
    const h = makeSession();
    await h.session.start();
    h.session.writeControl(Buffer.from(JSON.stringify({ t: 'move', x: 5, y: 5 }), 'utf-8'));
    await settle();
    assert.equal(h.actionsCalls().length, 0); // 无 down 的孤儿 move
    h.session.writeControl(down(100, 200));
    h.session.writeControl(up(100, 200));
    await settle();
    const body = JSON.parse(h.actionsCalls()[0]!.body ?? '{}');
    assert.equal(body.actions[0].actions[0].x, 100);
    await h.session.stop();
  });

  it('MJPEG 流断 → onClosed 联动（ScrcpyManager teardown 语义）', async () => {
    const h = makeSession();
    await h.session.start();
    let closed = false;
    h.session.onClosed(() => (closed = true));
    h.endStream();
    await settle();
    assert.equal(closed, true);
  });

  it('stop 幂等：断拉流 + 不再收帧/控制', async () => {
    const h = makeSession();
    await h.session.start();
    const got: Uint8Array[] = [];
    h.session.onVideoBytes((b) => got.push(b));
    await h.session.stop();
    await h.session.stop();
    assert.equal(h.wasAborted(), true);
    const n = got.length;
    h.feed(JPEG_A);
    h.session.writeControl(down(1, 1));
    h.session.writeControl(up(1, 1));
    await settle();
    assert.equal(got.length, n);
    assert.equal(h.actionsCalls().length, 0);
  });
});

describe('buildIosMetaFrame', () => {
  it('首字节 0x7B（前端与 JPEG 0xFFD8 分流依据）', () => {
    const f = buildIosMetaFrame(810, 1080);
    assert.equal(f[0], 0x7b);
  });
});
