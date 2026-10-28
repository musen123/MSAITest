"""智能体 Agent 工厂

使用 langgraph 的 prebuilt create_react_agent 构建 ReAct 模式智能体。
持久化用 AsyncSqliteSaver，本地 data/chat_checkpoints.db。

每次调用通过用户的 LLM ContextVar 切换模型，因此不在工厂内绑定模型，
而是采用"每次新建 agent"的简单策略（性能开销可接受）。
"""

import asyncio
import logging
import os
from typing import Any, Optional

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import create_react_agent

from app.ai_core.chat_agent.context_hook import context_hook
from app.ai_core.chat_agent.system_prompt import get_system_prompt
from app.ai_core.chat_agent.tools import ALL_TOOLS
from app.ai_core.llm_context import get_current_llm
from app.core.config import settings

logger = logging.getLogger(__name__)


_CHECKPOINT_DIR = os.path.join(settings.UPLOAD_DIR, "..", "checkpoints")
_CHECKPOINT_PATH = os.path.join(_CHECKPOINT_DIR, "chat_checkpoints.db")

_checkpointer: Optional[AsyncSqliteSaver] = None
_init_lock = asyncio.Lock()


async def _ensure_checkpointer() -> AsyncSqliteSaver:
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    async with _init_lock:
        if _checkpointer is not None:
            return _checkpointer
        os.makedirs(_CHECKPOINT_DIR, exist_ok=True)
        conn = await aiosqlite.connect(_CHECKPOINT_PATH)
        cp = AsyncSqliteSaver(conn)
        await cp.setup()
        _checkpointer = cp
        logger.info("chat agent checkpointer ready: %s", _CHECKPOINT_PATH)
        return cp


async def create_chat_agent() -> Any:
    """创建一个绑定到当前用户 LLM 的 ReAct agent

    每次调用都重新构造（共享 checkpointer + 工具）。
    """
    llm = get_current_llm()
    checkpointer = await _ensure_checkpointer()
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=get_system_prompt(),
        checkpointer=checkpointer,
        # 上下文治理：喂 LLM 前注入实时项目快照 + 剥离往轮次工具结果 + 窗口/压缩/限长
        # （checkpoint 里的完整 messages 不动，只改喂模型的 llm_input_messages）
        pre_model_hook=context_hook,
    )


async def aget_state_snapshot(conversation_id: int) -> Optional[dict]:
    """读取某 thread 的消息数（WS init 帧使用）

    如果该会话从未发过消息，返回 None。
    """
    # 这里允许在没有 LLM 的情况下读取（只查状态），但 create_react_agent 需要 model。
    # 我们用一个 dummy 模型规避，或者直接通过 checkpointer 读 state。
    try:
        cp = await _ensure_checkpointer()
        config = {"configurable": {"thread_id": str(conversation_id)}}
        snap = await cp.aget(config)
        if not snap:
            return None
        # snap 是 Checkpoint 字典
        channel_values = snap.get("channel_values", {})
        msgs = channel_values.get("messages") or []
        return {"message_count": len(msgs), "has_state": bool(msgs)}
    except Exception as exc:
        logger.warning("aget_state_snapshot 失败 conv=%s: %s", conversation_id, exc)
        return None


async def aclose_chat_agent() -> None:
    """应用关闭时清理 checkpointer 连接"""
    global _checkpointer
    cp = _checkpointer
    _checkpointer = None
    if cp is None:
        return
    conn = getattr(cp, "conn", None)
    if conn is None:
        return
    try:
        await conn.close()
    except Exception:
        logger.exception("aclose_chat_agent: close sqlite connection failed")
