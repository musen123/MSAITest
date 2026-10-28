"""智能体对话编排层

包含：
  - StreamRegistry      按 conversation_id 跟踪"忙/闲"状态 + 中断事件
  - AgentOrchestrator   per-connection 实例，astream_events(v2) → 协议事件流
  - ThinkSplitter       跨 chunk 增量拆分 reasoning / text（<think>...</think>）

设计参考 TestAgent_2604.agent_service，做了以下调整：
  - 适配 langgraph create_react_agent（而非 deepagents）
  - 去掉 deepagents 专属的 _HIDDEN_TOOL_NAMES 过滤（task / write_todos）
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Optional

from app.ai_core.chat_agent.agent import create_chat_agent
from app.ai_core.chat_agent.agent_context import AgentContext, set_agent_context

logger = logging.getLogger(__name__)


# ============== 常量 ==============

EVENT_TIMEOUT = 300.0


# ============== StreamRegistry ==============


class StreamRegistry:
    """conv_id 维度的忙/闲登记 + 中断信号"""

    def __init__(self) -> None:
        self._busy: set[int] = set()
        self._events: dict[int, asyncio.Event] = {}

    def mark_streaming(self, conv_id: int) -> bool:
        """抢位。成功 True，失败 False"""
        if conv_id in self._busy:
            return False
        self._busy.add(conv_id)
        ev = self._events.get(conv_id)
        if ev is None:
            self._events[conv_id] = asyncio.Event()
        else:
            ev.clear()
        return True

    def clear(self, conv_id: int) -> None:
        self._busy.discard(conv_id)

    def is_busy(self, conv_id: int) -> bool:
        return conv_id in self._busy

    def interrupt(self, conv_id: int) -> bool:
        ev = self._events.get(conv_id)
        if ev is None or ev.is_set():
            return False
        ev.set()
        return True

    def event_for(self, conv_id: int) -> asyncio.Event:
        ev = self._events.get(conv_id)
        if ev is None:
            ev = asyncio.Event()
            self._events[conv_id] = ev
        return ev


registry = StreamRegistry()


# ============== 工具函数 ==============


def _new_block_id(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def _to_jsonable(value: Any) -> str:
    """把工具的输入/输出序列化为字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        from langchain_core.messages import ToolMessage

        if isinstance(value, ToolMessage):
            return (
                value.content
                if isinstance(value.content, str)
                else str(value.content)
            )
    except Exception:
        pass
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


def _extract_action(output_str: str) -> Optional[dict]:
    """从工具输出 JSON 顶层取 _action（前端渲染为动作卡片）"""
    if not output_str or "_action" not in output_str:
        return None
    try:
        data = json.loads(output_str)
    except (json.JSONDecodeError, TypeError):
        return None
    action = data.get("_action") if isinstance(data, dict) else None
    return action if isinstance(action, dict) else None


class ThinkSplitter:
    """跨 chunk 的 <think>…</think> 增量拆分器。

    流式输出时标签经常被拆在两个 chunk 里（如 "<thi" + "nk>…"），
    单 chunk 正则匹配不到会把思考内容漏进正文。这里维护
    in_think 状态 + 尾部半截标签缓冲，逐段切分。
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self.in_think = False
        self.buf = ""

    def feed(self, s: str) -> tuple[str, str]:
        """喂入一个 chunk，返回 (reasoning, text)"""
        data = self.buf + s
        self.buf = ""
        reasoning: list[str] = []
        text: list[str] = []
        i = 0
        while i < len(data):
            tag = self._CLOSE if self.in_think else self._OPEN
            sink = reasoning if self.in_think else text
            j = data.find(tag, i)
            if j == -1:
                # 尾部可能是半截标签，留到下个 chunk 再判
                keep = self._partial_tail_len(data, i, tag)
                cut = len(data) - keep
                sink.append(data[i:cut])
                self.buf = data[cut:]
                break
            sink.append(data[i:j])
            i = j + len(tag)
            self.in_think = not self.in_think
        return "".join(reasoning), "".join(text)

    def flush(self) -> tuple[str, str]:
        """LLM 调用结束：清空缓冲并复位状态"""
        rest = self.buf
        reasoning, text = ("", "")
        if rest:
            reasoning, text = (rest, "") if self.in_think else ("", rest)
        self.buf = ""
        self.in_think = False
        return reasoning, text

    @staticmethod
    def _partial_tail_len(data: str, start: int, tag: str) -> int:
        max_k = min(len(tag) - 1, len(data) - start)
        for k in range(max_k, 0, -1):
            if data.endswith(tag[:k]):
                return k
        return 0


def _split_parts(content: Any) -> list[tuple[str, str]]:
    """把 chunk.content 归一化为 [(kind, text)]，kind ∈ reasoning|text。

    text 段仍可能内嵌 <think> 标签，由调用方的 ThinkSplitter 二次切分。
    """
    if content is None:
        return []
    if isinstance(content, list):
        parts: list[tuple[str, str]] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            t = part.get("text", "")
            if not isinstance(t, str) or not t:
                continue
            kind = part.get("type")
            if kind == "reasoning":
                parts.append(("reasoning", t))
            elif kind == "text":
                parts.append(("text", t))
        return parts
    if isinstance(content, str):
        return [("text", content)] if content else []
    return [("text", str(content))]


# ============== AgentOrchestrator ==============


class AgentOrchestrator:
    """per-connection 实例，运行一轮智能体并产出协议事件"""

    def __init__(
        self,
        conv_id: int,
        user_text: str,
        *,
        agent_context: AgentContext,
    ) -> None:
        self.conv_id = conv_id
        self.user_text = user_text
        self.agent_context = agent_context
        self.interrupt_event: asyncio.Event = registry.event_for(conv_id)

        self._text_id: Optional[str] = None
        self._thinking_id: Optional[str] = None
        self._tool_ids: dict[str, str] = {}
        self._splitter = ThinkSplitter()

        # 累积用于落库
        self._text_chunks: list[str] = []
        self._thinking_chunks: list[str] = []
        self._tool_calls: list[dict] = []

    async def stream(self) -> AsyncIterator[dict]:
        """运行一轮 + 转协议事件。

        中断是协作式的：只在事件边界检查（不硬打断进行中的工具——
        执行派发类工具的提交/补偿临界段不能被中途掐断）；
        EVENT_TIMEOUT 看门狗兜底 LLM 流停滞，避免会话被永久占用。
        """
        # 注入 AgentContext，工具内部可通过 get_agent_context() 读取
        set_agent_context(self.agent_context)

        stream_iter = None
        try:
            agent = await create_chat_agent()
            config = {"configurable": {"thread_id": str(self.conv_id)}}
            stream_iter = agent.astream_events(
                {"messages": [{"role": "user", "content": self.user_text}]},
                config=config,
                version="v2",
            ).__aiter__()
            while True:
                try:
                    raw = await asyncio.wait_for(
                        stream_iter.__anext__(), timeout=EVENT_TIMEOUT
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    # 生成停滞看门狗：LLM/工具超过 EVENT_TIMEOUT 无任何
                    # 事件产出，按错误收尾释放会话
                    logger.warning(
                        "stream stalled conv=%s (>%ss no event)",
                        self.conv_id,
                        int(EVENT_TIMEOUT),
                    )
                    for ev in self._finalize_blocks("error"):
                        yield ev
                    yield {
                        "type": "error",
                        "error": "生成超时（长时间无输出），请重试",
                    }
                    return
                if self.interrupt_event.is_set():
                    for ev in self._finalize_interrupted():
                        yield ev
                    return
                for ev in self._convert(raw):
                    yield ev
            # 自然结束：flush 未关的 block
            for ev in self._flush_blocks_success():
                yield ev
        except asyncio.CancelledError:
            for ev in self._finalize_interrupted():
                yield ev
            raise
        except Exception as exc:
            logger.exception("orchestrator stream error")
            # 协议契约：每个 block_start 必须有配对的 block_end，
            # 否则前端块永远停留在"运行中"
            for ev in self._finalize_blocks("error"):
                yield ev
            yield {"type": "error", "error": str(exc)}
        finally:
            if stream_iter is not None:
                try:
                    await stream_iter.aclose()
                except Exception:  # noqa: BLE001
                    pass

    def _emit_reasoning_text(
        self, reasoning: str, text: str, out: list[dict]
    ) -> None:
        """把一段 reasoning/text 写入对应块（按需开块/切块）"""
        if reasoning:
            if self._thinking_id is None:
                self._thinking_id = _new_block_id("think_")
                out.append(
                    {
                        "type": "block_start",
                        "block_id": self._thinking_id,
                        "block_type": "thinking",
                    }
                )
            self._thinking_chunks.append(reasoning)
            out.append(
                {
                    "type": "block_delta",
                    "block_id": self._thinking_id,
                    "delta": reasoning,
                }
            )
        if text:
            if self._thinking_id is not None:
                out.append(
                    {
                        "type": "block_end",
                        "block_id": self._thinking_id,
                        "status": "success",
                    }
                )
                self._thinking_id = None
            if self._text_id is None:
                self._text_id = _new_block_id("text_")
                out.append(
                    {
                        "type": "block_start",
                        "block_id": self._text_id,
                        "block_type": "text",
                    }
                )
            self._text_chunks.append(text)
            out.append(
                {
                    "type": "block_delta",
                    "block_id": self._text_id,
                    "delta": text,
                }
            )

    def _convert(self, event: dict) -> list[dict]:
        kind = event.get("event", "")
        out: list[dict] = []

        if kind == "on_chat_model_start":
            out.append({"type": "thinking_start"})

        elif kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk is None:
                return out
            for part_kind, part_text in _split_parts(
                getattr(chunk, "content", None)
            ):
                if part_kind == "reasoning":
                    self._emit_reasoning_text(part_text, "", out)
                else:
                    # text 段可能内嵌（跨 chunk 断开的）<think> 标签
                    reasoning, text = self._splitter.feed(part_text)
                    self._emit_reasoning_text(reasoning, text, out)

        elif kind == "on_chat_model_end":
            # 一段 LLM 输出结束：先吐出拆分器缓冲，再关闭 text/thinking 块
            reasoning, text = self._splitter.flush()
            self._emit_reasoning_text(reasoning, text, out)
            if self._text_id is not None:
                out.append(
                    {
                        "type": "block_end",
                        "block_id": self._text_id,
                        "status": "success",
                    }
                )
                self._text_id = None
            if self._thinking_id is not None:
                out.append(
                    {
                        "type": "block_end",
                        "block_id": self._thinking_id,
                        "status": "success",
                    }
                )
                self._thinking_id = None

        elif kind == "on_tool_start":
            run_id = str(event.get("run_id", ""))
            tool_name = event.get("name", "")
            tool_input = event.get("data", {}).get("input", {})

            block_id = _new_block_id("tool_")
            self._tool_ids[run_id] = block_id
            input_str = _to_jsonable(tool_input)
            self._tool_calls.append(
                {
                    "runId": run_id,
                    "toolName": tool_name,
                    "toolInput": input_str,
                    "toolOutput": None,
                    "status": "running",
                    "startedAt": int(time.time() * 1000),
                    "endedAt": None,
                }
            )
            out.append(
                {
                    "type": "block_start",
                    "block_id": block_id,
                    "block_type": "tool",
                    "run_id": run_id,
                    "tool_name": tool_name,
                    "tool_input": input_str,
                }
            )

        elif kind == "on_tool_end":
            run_id = str(event.get("run_id", ""))
            tool_name = event.get("name", "")
            tool_output = event.get("data", {}).get("output", "")
            block_id = self._tool_ids.pop(run_id, _new_block_id("tool_"))
            output_str = _to_jsonable(tool_output)
            action = _extract_action(output_str)
            for tc in self._tool_calls:
                if tc["runId"] == run_id:
                    tc["toolOutput"] = output_str
                    tc["status"] = "success"
                    tc["endedAt"] = int(time.time() * 1000)
                    if action:
                        tc["action"] = action
                    break
            end_frame = {
                "type": "block_end",
                "block_id": block_id,
                "block_type": "tool",
                "status": "success",
                "run_id": run_id,
                "tool_name": tool_name,
                "tool_output": output_str,
            }
            if action:
                end_frame["action"] = action
            out.append(end_frame)

        elif kind == "on_tool_error":
            run_id = str(event.get("run_id", ""))
            tool_name = event.get("name", "")
            err = str(event.get("data", {}).get("error", "unknown"))
            block_id = self._tool_ids.pop(run_id, _new_block_id("tool_"))
            for tc in self._tool_calls:
                if tc["runId"] == run_id:
                    tc["status"] = "error"
                    tc["endedAt"] = int(time.time() * 1000)
                    tc["error"] = err
                    break
            out.append(
                {
                    "type": "block_end",
                    "block_id": block_id,
                    "block_type": "tool",
                    "status": "error",
                    "run_id": run_id,
                    "tool_name": tool_name,
                    "error": err,
                }
            )

        return out

    def _flush_blocks_success(self) -> list[dict]:
        out = []
        if self._text_id is not None:
            out.append(
                {
                    "type": "block_end",
                    "block_id": self._text_id,
                    "status": "success",
                }
            )
            self._text_id = None
        if self._thinking_id is not None:
            out.append(
                {
                    "type": "block_end",
                    "block_id": self._thinking_id,
                    "status": "success",
                }
            )
            self._thinking_id = None
        return out

    def _finalize_blocks(self, status: str) -> list[dict]:
        """把所有未关闭的块按指定状态收尾（协议契约：开块必关）"""
        out = []
        if self._text_id is not None:
            out.append(
                {
                    "type": "block_end",
                    "block_id": self._text_id,
                    "status": status,
                }
            )
            self._text_id = None
        if self._thinking_id is not None:
            out.append(
                {
                    "type": "block_end",
                    "block_id": self._thinking_id,
                    "status": status,
                }
            )
            self._thinking_id = None
        for run_id, block_id in list(self._tool_ids.items()):
            out.append(
                {
                    "type": "block_end",
                    "block_id": block_id,
                    "status": status,
                }
            )
            for tc in self._tool_calls:
                if tc["runId"] == run_id and tc.get("status") == "running":
                    tc["status"] = status
                    tc["endedAt"] = int(time.time() * 1000)
                    break
        self._tool_ids.clear()
        return out

    def _finalize_interrupted(self) -> list[dict]:
        out = self._finalize_blocks("interrupted")
        out.append({"type": "interrupted", "conversation_id": self.conv_id})
        return out
