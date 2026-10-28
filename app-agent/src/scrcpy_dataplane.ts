/**
 * 投屏数据面纯逻辑（契约 §3.1）—— 从 rpc/网络副作用中剥出可单测的决策：
 *  1) data-WS URL 推导（控制隧道 URL → data-ws URL + session_id 查询串）
 *  2) bounded-queue 丢帧决策（WS bufferedAmount 超阈值即丢当前视频帧，不堆积）
 *
 * 二者都无 IO，供 test/ 直接喂固定输入断言（真 WS/真 scrcpy 留给 Verify）。
 */

/** WS 发送缓冲超此阈值（字节）即丢视频帧，避免慢消费者下无界堆积 OOM（S1 backpressure 结论） */
export const VIDEO_BACKPRESSURE_BYTES = 4 * 1024 * 1024; // 4MB

/**
 * 由控制隧道 URL 推导 data-WS URL。
 * 契约 §2 控制隧道 = `.../api/v1/app/agents/ws`；
 * 契约 §3.1 数据面 = `.../api/v1/app/agents/data-ws?session_id=<sid>`。
 * 仅替换末段 `ws` → `data-ws` 并挂 session_id，协议/host/其余路径原样保留
 * （本地直连网关的 ws://127.0.0.1:8889/... 同样适用）。
 */
export function deriveDataWsUrl(controlWsUrl: string, sessionId: string): string {
  const url = new URL(controlWsUrl);
  // 末段 /ws → /data-ws；容错已带 data-ws 或非 /ws 结尾的自定义路径
  if (url.pathname.endsWith('/ws')) {
    url.pathname = `${url.pathname.slice(0, -'/ws'.length)}/data-ws`;
  } else if (!url.pathname.endsWith('/data-ws')) {
    // 非标准路径：直接追加 /data-ws（防御，正常配置不会走到）
    url.pathname = `${url.pathname.replace(/\/$/, '')}/data-ws`;
  }
  url.searchParams.set('session_id', sessionId);
  return url.toString();
}

/**
 * bounded-queue 丢帧决策：WS 发送缓冲已积压超阈值 → 丢当前视频帧（返回 true）。
 * 视频是可丢的（下一帧会追上），控制字节绝不走此路（控制不可丢）。
 */
export function shouldDropVideoFrame(
  bufferedAmount: number,
  threshold: number = VIDEO_BACKPRESSURE_BYTES,
): boolean {
  return bufferedAmount > threshold;
}

/** 数据面运行计数（丢帧数等），用于回执/日志观测 */
export interface DataPlaneStats {
  videoBytesForwarded: number;
  videoFramesForwarded: number;
  videoFramesDropped: number;
  controlBytesReceived: number;
}

export function emptyStats(): DataPlaneStats {
  return {
    videoBytesForwarded: 0,
    videoFramesForwarded: 0,
    videoFramesDropped: 0,
    controlBytesReceived: 0,
  };
}
