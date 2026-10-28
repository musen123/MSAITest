"""投屏控制 WS 一次性 ticket（backend-core 签发，网关消费）

key   app:ws:ticket:{ticket}
value JSON {"user_id":1,"udid":"3:ABC","session_id":"s-uuid","mode":"control|observe"}
TTL   30s

mode（P4 观战锁）：control=占锁可注入（缺省）；observe=不占锁只读观看——
网关对 observe 会话不续锁、不做逐帧锁校验、丢弃一切入站控制字节。
消费用 GETDEL 保证一次性；网关拿到后须校验 udid 与 WS 路径一致（契约 §5）。
"""

import json
import secrets
from typing import Optional

from app.ai_core.runtime.event_bus import get_redis

TICKET_TTL_S = 30


def _ticket_key(ticket: str) -> str:
    return f"app:ws:ticket:{ticket}"


async def issue_ticket(
    user_id: int, udid: str, session_id: str, mode: str = "control"
) -> str:
    """签发一次性 ticket（30s 有效）。"""
    ticket = secrets.token_urlsafe(32)
    payload = json.dumps(
        {"user_id": user_id, "udid": udid, "session_id": session_id, "mode": mode},
        ensure_ascii=False,
    )
    await get_redis().set(_ticket_key(ticket), payload, ex=TICKET_TTL_S)
    return ticket


async def consume_ticket(ticket: str) -> Optional[dict]:
    """消费 ticket（GETDEL，一次性）。无效/过期/已消费返回 None。"""
    if not ticket:
        return None
    raw = await get_redis().getdel(_ticket_key(ticket))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None
