"""APP 自动化设备域 Service

执行机 token 生成/轮转（明文只出现在响应一次，库存 sha256）、
心跳对账（设备 upsert + 差集下线）、在线状态现算（不落库派生列）。
"""

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.app_device.agent import crud_app_agent
from app.crud.app_device.device import build_udid, crud_app_device
from app.models.app_device.agent import AppAgent

# 在线判定窗口（契约 §7）：心跳 ≤30s=online、≤60s=stale、否则 offline
AGENT_ONLINE_WINDOW_S = 30
AGENT_STALE_WINDOW_S = 60


# ── 在线判定（纯函数）────────────────────────────────────────

def agent_status(
    last_heartbeat_at: Optional[datetime], now: Optional[datetime] = None
) -> str:
    """执行机在线状态：online / stale / offline（按最近心跳现算）。"""
    if last_heartbeat_at is None:
        return "offline"
    now = now or datetime.utcnow()
    elapsed = (now - last_heartbeat_at).total_seconds()
    if elapsed < 0:
        # 时钟漂移/未来时间戳按刚心跳处理
        return "online"
    if elapsed <= AGENT_ONLINE_WINDOW_S:
        return "online"
    if elapsed <= AGENT_STALE_WINDOW_S:
        return "stale"
    return "offline"


def device_online(agent_status_value: str, state: str) -> bool:
    """设备在线 = 所属 Agent online 且 adb 状态为 device。"""
    return agent_status_value == "online" and state == "device"


# ── Agent token ─────────────────────────────────────────────

def hash_token(token: str) -> str:
    """token 明文 → sha256 hex（网关握手校验用同一函数）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_agent_token() -> tuple[str, str]:
    """生成接入 token，返回 (明文, sha256)。明文仅签发响应返回一次。"""
    plain = secrets.token_urlsafe(32)
    return plain, hash_token(plain)


async def create_agent(
    db: AsyncSession, *, name: str, host_label: Optional[str] = None
) -> tuple[AppAgent, str]:
    """创建执行机，返回 (agent, 明文token)。"""
    plain, token_hash = generate_agent_token()
    agent = await crud_app_agent.create(
        db, values={"name": name, "host_label": host_label, "token_hash": token_hash}
    )
    return agent, plain


async def rotate_agent_token(
    db: AsyncSession, *, agent_id: int
) -> Optional[tuple[AppAgent, str]]:
    """轮转 token（version+1，旧 token 立即失效），返回 (agent, 新明文token)。"""
    agent = await crud_app_agent.get(db, agent_id)
    if agent is None:
        return None
    plain, token_hash = generate_agent_token()
    agent = await crud_app_agent.rotate_token(db, db_obj=agent, token_hash=token_hash)
    return agent, plain


# ── 心跳对账 ─────────────────────────────────────────────────

async def sync_heartbeat(
    db: AsyncSession,
    *,
    agent_id: int,
    devices: list[dict],
    ts: Optional[datetime] = None,
) -> dict:
    """心跳全量快照对账（契约 §2 heartbeat 帧）。

    ① 快照内设备逐台 upsert；② 差集下线（名下不在快照里的置 offline）；
    ③ 刷新 Agent last_heartbeat_at。全程单事务提交。
    """
    ts = ts or datetime.utcnow()
    present_udids: set[str] = set()
    upserted = 0
    for info in devices or []:
        obj = await crud_app_device.upsert(
            db, agent_id=agent_id, info=info, ts=ts, commit=False
        )
        if obj is not None:
            present_udids.add(build_udid(agent_id, (info.get("serial") or "").strip()))
            upserted += 1

    offlined = await crud_app_device.mark_missing_offline(
        db, agent_id=agent_id, present_udids=present_udids, commit=False
    )

    agent = await crud_app_agent.get(db, agent_id)
    if agent is not None:
        agent.last_heartbeat_at = ts
        db.add(agent)
    await db.commit()
    return {"upserted": upserted, "offlined": offlined}


async def apply_device_event(
    db: AsyncSession,
    *,
    agent_id: int,
    event: str,
    device: dict,
    ts: Optional[datetime] = None,
) -> None:
    """事件驱动的设备增量（契约 §2 device_event 帧，网关帧循环调用）。

    upsert → 单台 upsert；remove → 该台置 offline（行保留，同心跳差集口径）。
    未知 event 静默忽略（网关侧已做帧校验）。
    """
    ts = ts or datetime.utcnow()
    if event == "upsert":
        await crud_app_device.upsert(db, agent_id=agent_id, info=device, ts=ts)
        return
    if event == "remove":
        serial = (device.get("serial") or "").strip()
        if not serial:
            return
        obj = await crud_app_device.get_by_udid(db, build_udid(agent_id, serial))
        if obj is None or obj.state == "offline":
            return
        obj.state = "offline"
        obj.last_seen_at = ts
        db.add(obj)
        await db.commit()
