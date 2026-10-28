"""TaskContext — graph 节点内的统一上报接口

节点（或单次调用任务）通过 ctx 上报阶段/进度/日志/结果。
底层走 langgraph ``get_stream_writer()`` 发 custom 事件，由 StreamAdapter 翻译落库 + 实时推送。

用法（节点内）：
    def my_node(state):
        ctx.stage("评审用例", index=2, total=4)
        ctx.progress(50)
        ctx.log("调用 LLM 评审 12 条用例")
        ...
        ctx.set_result(summary={"count": 12}, ref={"case_ids": [...]})
"""

from typing import Any, Optional

from app.ai_core.runtime.events import (
    W_LOG,
    W_LOG_LEVEL,
    W_PROGRESS,
    W_STAGE,
    W_STAGE_INDEX,
    W_STAGE_TOTAL,
)


def _writer():
    """取 langgraph 的 stream writer；不在 graph 上下文时返回 no-op。"""
    try:
        from langgraph.config import get_stream_writer

        return get_stream_writer()
    except Exception:  # noqa: BLE001
        return lambda *_a, **_k: None


class TaskContext:
    """任务运行时上下文（注入 graph，节点内可用）"""

    def __init__(self, *, task_id: int, project_id: int, user_id: int) -> None:
        self.task_id = task_id
        self.project_id = project_id
        self.user_id = user_id
        # 由 set_result 写入，shell 兜底从此读取（优先于 final_state 提取）
        self.result_summary: Optional[dict] = None
        self.result_ref: Optional[dict] = None

    def stage(self, name: str, index: Optional[int] = None, total: Optional[int] = None) -> None:
        _writer()({W_STAGE: name, W_STAGE_INDEX: index, W_STAGE_TOTAL: total})

    def progress(self, percent: int) -> None:
        _writer()({W_PROGRESS: int(percent)})

    def log(self, message: str, level: str = "info") -> None:
        _writer()({W_LOG: message, W_LOG_LEVEL: level})

    def set_result(self, summary: Optional[dict] = None, ref: Optional[dict] = None) -> None:
        self.result_summary = summary
        self.result_ref = ref
        # 同时发一个 custom 事件用于实时展示
        _writer()({"_result": {"summary": summary or {}, "ref": ref or {}}})

    def emit(self, data: dict[str, Any]) -> None:
        """发送任意 custom 事件（高级用法）。"""
        _writer()(data)
