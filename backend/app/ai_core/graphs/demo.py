"""Demo 图 — P1 端到端验收用

一张 2 节点 LangGraph 图，演示节点如何用 TaskContext 上报：
  prepare -> work
不依赖真实 LLM（llm_kind="none"），用 writer 模拟阶段/进度/日志/逐字输出/结果。
"""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.events import W_LOG
from app.ai_core.runtime.registry import TaskSpec, register


class DemoState(TypedDict, total=False):
    text: str
    output: str


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def prepare(state: DemoState) -> dict:
        ctx.stage("准备", index=1, total=2)
        ctx.progress(10)
        ctx.log(f"收到输入：{state.get('text', '')}")
        await asyncio.sleep(0.05)
        return {}

    async def work(state: DemoState) -> dict:
        ctx.stage("生成", index=2, total=2)
        # 模拟逐字输出（用 custom log 模拟；真实任务由 messages 流产生 message_delta）
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        out = []
        for ch in "你好，这是一段流式输出示例。":
            out.append(ch)
            writer({W_LOG: ch, "_level": "stream"})
            await asyncio.sleep(0.02)
        ctx.progress(90)
        result_text = "".join(out)
        ctx.set_result(
            summary={"chars": len(result_text)},
            ref={"echo": state.get("text", "")},
        )
        return {"output": result_text}

    graph = StateGraph(DemoState)
    graph.add_node("prepare", prepare)
    graph.add_node("work", work)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "work")
    graph.add_edge("work", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {"text": params.get("text", "hello")}


def title(params: dict) -> str:
    return "Demo 任务"


register(
    TaskSpec(
        task_type="demo",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="none",
        dedupe=False,
    )
)
