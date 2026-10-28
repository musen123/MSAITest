"""小测上下文/记忆治理 —— create_react_agent 的 pre_model_hook。

对标 Claude Code 的上下文策略，喂给模型前对历史做「策展」(checkpoint 里的完整
messages 不动，只改喂 LLM 的视图 `llm_input_messages`)：

  A 实时事实层（对标 system-reminder）：每轮注入**当轮新查**的「当前项目快照」系统
    消息——模型永远看到当前数量，不会拿历史轮次里的旧数字作答(修 281→0 那类 bug)。
  B 工作记忆层（对标 /compact）：
    - 剥离**往轮次**的工具结果 → 折叠占位(保留 tool_call_id 链接，只换 content)，
      当前轮的工具结果保留；
    - 窗口：只保留最近 N 轮原文，更早的抽取式压成一条「更早对话摘要」(仅留用户意图)；
    - 单条消息内容限长兜底。
  C 持久记忆层（对标 CLAUDE.md/memory）：注入 (project,user) 维度的「已记事项」——
    见 memory_store，本 hook 负责把它拼进前缀。

设计要点：所有注入的系统消息(快照/记忆/摘要)集中放在**会话前缀**、彼此相邻，避免
在对话中间插系统消息导致个别 provider 不接受。
"""

import logging
from typing import Any, Optional

from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

# —— 可调参数 ——
WINDOW_TURNS = 6           # 保留最近 N 轮(每轮=一条 user 消息起)的原文
MAX_CONTENT_CHARS = 4000   # 单条消息内容进上下文的硬上限(兜底防超长工具输出)
MAX_INTENTS_IN_SUMMARY = 12  # 压缩摘要里最多保留多少条历史用户意图

STALE_TOOL_PLACEHOLDER = "[历史查询结果已省略——数据会变，如需当前值请重新调用查询工具]"


def _mtype(m: Any) -> Optional[str]:
    return getattr(m, "type", None)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _cap_content(m: Any, limit: int) -> Any:
    """内容超长则截断(用 model_copy 保留 tool_calls / tool_call_id 等结构)。"""
    c = getattr(m, "content", None)
    if isinstance(c, str) and len(c) > limit:
        return m.model_copy(update={"content": c[:limit] + "…[已截断]"})
    return m


def _compaction_note(dropped: list) -> Optional[SystemMessage]:
    """把被移出窗口的更早轮次抽取式压缩成一条摘要(只留用户意图，零 LLM 调用)。"""
    intents = [
        m.content
        for m in dropped
        if _mtype(m) == "human" and isinstance(m.content, str) and m.content.strip()
    ]
    if not intents:
        return None
    lines = "；".join(_clip(x.strip(), 80) for x in intents[-MAX_INTENTS_IN_SUMMARY:])
    return SystemMessage(
        content=(
            f"【更早对话摘要】此前用户先后问过/要求过：{lines}。"
            "（更早的工具结果与中间过程已省略；涉及具体数据请重新查询。）"
        )
    )


def curate_history(
    messages: list,
    *,
    window_turns: int = WINDOW_TURNS,
    max_content: int = MAX_CONTENT_CHARS,
) -> tuple[list, list]:
    """返回 (视图, 被移出窗口的更早消息)。纯函数，可单测。

    视图 = 窗口内消息，且：往轮次的工具结果 content 换成占位、当前轮工具结果保留、
    所有消息内容限长。**不含**注入的系统前缀(快照/记忆/摘要由 hook 拼)。
    """
    if not messages:
        return [], []
    human_pos = [i for i, m in enumerate(messages) if _mtype(m) == "human"]
    if len(human_pos) > window_turns:
        cut = human_pos[-window_turns]
        dropped, kept = messages[:cut], messages[cut:]
    else:
        dropped, kept = [], messages

    kept_humans = [i for i, m in enumerate(kept) if _mtype(m) == "human"]
    last_human = kept_humans[-1] if kept_humans else -1

    view = []
    for i, m in enumerate(kept):
        if _mtype(m) == "tool" and i < last_human:
            # 往轮次的工具结果：折叠占位(保留 tool_call_id 链接，防孤儿 tool_calls)
            view.append(m.model_copy(update={"content": STALE_TOOL_PLACEHOLDER}))
        else:
            view.append(_cap_content(m, max_content))
    return view, dropped


async def _build_snapshot_message() -> Optional[SystemMessage]:
    """A 层：当轮新查的「当前项目快照」——修「拿旧数字作答」的根。"""
    from app.ai_core.chat_agent.tools.base import ctx_ids
    from app.db.session import async_session_maker

    try:
        project_id, _ = ctx_ids()
    except Exception:  # noqa: BLE001
        return None
    try:
        from app.services.project.module_stats_service import (
            MODULES,
            get_module_stats,
        )

        parts = []
        async with async_session_maker() as db:
            for mod in MODULES:
                stats = await get_module_stats(db, project_id=project_id, module=mod)
                parts.append(f"{mod}={stats.get('total', 0)}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("build snapshot failed: %s", exc)
        return None
    return SystemMessage(
        content=(
            f"【当前项目实时快照 · project_id={project_id} · 本轮查询】"
            f"各模块总数：{'，'.join(parts)}。"
            "这是**此刻**的准确数量；回答数量类问题以此为准，"
            "需要列表/明细/其它统计请调用对应查询工具现查(工具返回同样是查询那一刻的快照)。"
        )
    )


async def _build_memory_message() -> Optional[SystemMessage]:
    """C 层：注入 (project,user) 维度的「已记事项」。memory_store 未接入时返回 None。"""
    try:
        from app.ai_core.chat_agent.memory_store import format_memories_for_context

        text = await format_memories_for_context()
    except Exception as exc:  # noqa: BLE001
        logger.debug("build memory message skipped: %s", exc)
        return None
    if not text:
        return None
    return SystemMessage(content=text)


async def context_hook(state: dict) -> dict:
    """pre_model_hook：喂给模型前做上下文策展。返回 llm_input_messages(不改 messages)。"""
    messages = state.get("messages") or []
    view, dropped = curate_history(messages)
    prefix: list = []
    snap = await _build_snapshot_message()
    memo = await _build_memory_message()
    note = _compaction_note(dropped)
    for msg in (snap, memo, note):
        if msg is not None:
            prefix.append(msg)
    return {"llm_input_messages": [*prefix, *view]}
