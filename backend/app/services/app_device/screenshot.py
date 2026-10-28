"""设备静态截图缓存（契约 §2.1）

网关收到 Agent 的 device_screenshot 帧后写入；业务 API 的截图端点读取。
存 base64 字符串（Redis 客户端 decode_responses=True，二进制不友好；base64
是 ASCII，直接当字符串存最省事），端点侧再解码回 PNG bytes。

TTL 10 分钟：设备离线不再上报即自然过期，前端回落默认壁纸。不建表、不落磁盘。
"""

from __future__ import annotations

import base64

from app.ai_core.runtime.event_bus import get_redis

# TTL：略大于 Agent 采集周期（5min），容忍一次丢帧
SHOT_TTL_S = 600
# 单张上限（base64 后约 4MB*4/3 ≈ 5.3MB），防异常大图占爆 Redis
_MAX_B64_LEN = 6 * 1024 * 1024


def _shot_key(udid: str) -> str:
    return f"app:device:shot:{udid}"


async def store_screenshot(udid: str, data_b64: str) -> None:
    """写入设备截图（base64 字符串）。超限静默丢弃。"""
    if not data_b64 or len(data_b64) > _MAX_B64_LEN:
        return
    await get_redis().set(_shot_key(udid), data_b64, ex=SHOT_TTL_S)


async def load_screenshot(udid: str) -> bytes | None:
    """读取设备截图，解码为 PNG bytes；无缓存/解码失败返回 None。"""
    raw = await get_redis().get(_shot_key(udid))
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except (ValueError, TypeError):
        return None
