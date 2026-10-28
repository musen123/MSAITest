"""上下文/记忆治理回归测试（纯逻辑 + 记忆存储往返，无需 LLM）。

守护 P0/P1/P2 三层的关键不变量：
  - 往轮次工具结果被折叠、当前轮保留（修 281→0 那类"拿旧快照作答"）；
  - 折叠只换 content、保留 tool_call_id（不产生孤儿 tool_calls → 不炸 provider）；
  - 窗口裁到最近 N 轮、更早的进 dropped 供压缩；单条内容限长；
  - 记忆存储按 (project,user) 隔离、往返正确。
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.ai_core.chat_agent.agent_context import AgentContext, set_agent_context
from app.ai_core.chat_agent.context_hook import (
    MAX_CONTENT_CHARS,
    STALE_TOOL_PLACEHOLDER,
    WINDOW_TURNS,
    curate_history,
)


def _turn(user_text: str, tool_out: str) -> list:
    """一轮：human → ai(带 tool_call) → tool(结果) → ai(最终答)。"""
    cid = f"call_{user_text}"
    return [
        HumanMessage(content=user_text),
        AIMessage(
            content="",
            tool_calls=[{"id": cid, "name": "query_x", "args": {}}],
        ),
        ToolMessage(content=tool_out, tool_call_id=cid),
        AIMessage(content=f"答：{tool_out}"),
    ]


class TestCurateHistory:
    def test_prior_tool_stripped_current_kept(self) -> None:
        msgs = _turn("q1", '{"total": 281}') + _turn("q2", '{"total": 0}')
        view, _ = curate_history(msgs)
        tools = [m for m in view if m.type == "tool"]
        # 往轮次(q1=281)工具结果被折叠为占位；当前轮(q2=0)保留原文
        assert any(m.content == STALE_TOOL_PLACEHOLDER for m in tools)
        assert any('"total": 0' in (m.content or "") for m in tools)
        # 旧值 281 不再出现在喂给模型的视图里
        assert not any("281" in (m.content or "") for m in tools)

    def test_tool_call_linkage_preserved(self) -> None:
        msgs = _turn("q1", "old") + _turn("q2", "new")
        view, _ = curate_history(msgs)
        tool_msgs = [m for m in view if m.type == "tool"]
        assert tool_msgs and all(
            getattr(m, "tool_call_id", None) for m in tool_msgs
        )

    def test_windowing_drops_old_turns(self) -> None:
        msgs: list = []
        for i in range(WINDOW_TURNS + 3):
            msgs += _turn(f"q{i}", "x")
        view, dropped = curate_history(msgs)
        assert any(m.type == "human" for m in dropped)
        assert len([m for m in view if m.type == "human"]) == WINDOW_TURNS

    def test_content_capped(self) -> None:
        big = "y" * (MAX_CONTENT_CHARS + 500)
        view, _ = curate_history([HumanMessage(content="q"), AIMessage(content=big)])
        assert all(
            len(m.content) <= MAX_CONTENT_CHARS + 20
            for m in view
            if isinstance(m.content, str)
        )

    def test_empty(self) -> None:
        assert curate_history([]) == ([], [])


class TestMemoryStore:
    async def test_roundtrip(self, tmp_path, monkeypatch) -> None:
        from app.ai_core.chat_agent import memory_store as ms

        monkeypatch.setattr(ms, "_DIR", str(tmp_path))
        monkeypatch.setattr(ms, "_PATH", str(tmp_path / "mem.db"))
        set_agent_context(AgentContext(project_id=7, user_id=3, conversation_id=0))
        await ms.remember("默认压测环境", "环境7")
        items = await ms.recall()
        assert any(
            i["key"] == "默认压测环境" and i["value"] == "环境7" for i in items
        )
        ctx = await ms.format_memories_for_context()
        assert ctx and "环境7" in ctx
        assert await ms.forget("默认压测环境") is True
        assert await ms.recall() == []

    async def test_scope_isolation(self, tmp_path, monkeypatch) -> None:
        from app.ai_core.chat_agent import memory_store as ms

        monkeypatch.setattr(ms, "_DIR", str(tmp_path))
        monkeypatch.setattr(ms, "_PATH", str(tmp_path / "mem.db"))
        set_agent_context(AgentContext(project_id=1, user_id=1, conversation_id=0))
        await ms.remember("k", "v1")
        # 换项目 → 看不到别的项目的记忆
        set_agent_context(AgentContext(project_id=2, user_id=1, conversation_id=0))
        assert await ms.recall() == []
