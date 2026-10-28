"""小测持久记忆层（对标 Claude Code 的 CLAUDE.md / memory/）。

存跨对话、跨会话的**小而精**的用户偏好/约定（如「以后压测默认用环境7」「重点关注
支付模块」），按 (project_id, user_id) 命名空间隔离。每轮由 context_hook 注入「已记
事项」短块；用户可用 remember/recall/forget 工具增删查。

刻意与「实时数据」分开：记忆是用户的**约定/偏好**，不是数据快照——数量/列表等仍必须
现查（见 context_hook 的实时快照 + system_prompt 铁律）。带上限，只增不爆。

自持一个 sqlite 文件（data/checkpoints/chat_memory.db），每操作独立连接、无共享态，
避免并发连接争用；低频写，开销可忽略。
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from app.ai_core.chat_agent.tools.base import ctx_ids
from app.core.config import settings

logger = logging.getLogger(__name__)

_DIR = os.path.join(settings.UPLOAD_DIR, "..", "checkpoints")
_PATH = os.path.join(_DIR, "chat_memory.db")

MAX_MEMORIES_PER_SCOPE = 40      # 每 (project,user) 记忆条数上限，超出淘汰最旧
MAX_INJECT = 20                  # 注入上下文时最多带几条
_MAX_KEY = 60
_MAX_VALUE = 500

_CREATE = """
CREATE TABLE IF NOT EXISTS chat_memory (
    project_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    mem_key    TEXT NOT NULL,
    mem_value  TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, user_id, mem_key)
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _connect() -> aiosqlite.Connection:
    os.makedirs(_DIR, exist_ok=True)
    conn = await aiosqlite.connect(_PATH)
    await conn.execute(_CREATE)
    await conn.commit()
    return conn


async def remember(key: str, value: str) -> None:
    """记住/覆盖一条（当前 project+user 命名空间）。超上限淘汰最旧。"""
    project_id, user_id = ctx_ids()
    key = (key or "").strip()[:_MAX_KEY]
    value = (value or "").strip()[:_MAX_VALUE]
    conn = await _connect()
    try:
        await conn.execute(
            "INSERT INTO chat_memory(project_id,user_id,mem_key,mem_value,updated_at) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(project_id,user_id,mem_key) "
            "DO UPDATE SET mem_value=excluded.mem_value, updated_at=excluded.updated_at",
            (project_id, user_id, key, value, _now()),
        )
        await conn.execute(
            "DELETE FROM chat_memory WHERE project_id=? AND user_id=? AND mem_key NOT IN "
            "(SELECT mem_key FROM chat_memory WHERE project_id=? AND user_id=? "
            " ORDER BY updated_at DESC LIMIT ?)",
            (project_id, user_id, project_id, user_id, MAX_MEMORIES_PER_SCOPE),
        )
        await conn.commit()
    finally:
        await conn.close()


async def recall() -> list[dict]:
    """列出当前 project+user 的记忆（最近更新在前）。"""
    project_id, user_id = ctx_ids()
    conn = await _connect()
    try:
        cur = await conn.execute(
            "SELECT mem_key, mem_value, updated_at FROM chat_memory "
            "WHERE project_id=? AND user_id=? ORDER BY updated_at DESC",
            (project_id, user_id),
        )
        rows = await cur.fetchall()
    finally:
        await conn.close()
    return [{"key": r[0], "value": r[1], "updated_at": r[2]} for r in rows]


async def forget(key: str) -> bool:
    """删除一条。返回是否删到。"""
    project_id, user_id = ctx_ids()
    conn = await _connect()
    try:
        cur = await conn.execute(
            "DELETE FROM chat_memory WHERE project_id=? AND user_id=? AND mem_key=?",
            (project_id, user_id, (key or "").strip()),
        )
        await conn.commit()
        return cur.rowcount > 0
    finally:
        await conn.close()


async def format_memories_for_context() -> Optional[str]:
    """给 context_hook 用：把当前 project+user 的记忆拼成一段注入文本，无则 None。"""
    try:
        items = await recall()
    except Exception as exc:  # noqa: BLE001
        logger.debug("recall for context failed: %s", exc)
        return None
    if not items:
        return None
    lines = "；".join(f"{it['key']}：{it['value']}" for it in items[:MAX_INJECT])
    return (
        f"【已记事项 · 本项目本人】{lines}。"
        "（这些是你之前记下的偏好/约定，作为背景参考；仍可能过期，涉及具体数据请现查。）"
    )
