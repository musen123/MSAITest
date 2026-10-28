"""AI 任务事件协议

统一事件信封：
    {
        "seq": int,       # 任务内单调序号（SSE Last-Event-ID）
        "type": str,      # 见 EventType
        "ts": str,        # ISO 时间戳
        "payload": dict,  # 各类型数据体
    }

节点作者约定（通过 langgraph ``get_stream_writer()`` 发 dict）：
    writer({"_stage": "评审", "_index": 2, "_total": 4})  -> stage 事件
    writer({"_progress": 50})                              -> progress 事件
    writer({"_log": "调用 LLM 评审 12 条", "_level": "info"}) -> log 事件
    其余 custom dict 一律归为 log 事件。
"""

from datetime import datetime
from typing import Any

# 复用模型层定义的事件类型，避免重复
from app.models.ai.ai_task_event import AiTaskEventType as EventType

# writer dict 的保留 key
W_STAGE = "_stage"
W_STAGE_INDEX = "_index"
W_STAGE_TOTAL = "_total"
W_PROGRESS = "_progress"
W_LOG = "_log"
W_LOG_LEVEL = "_level"
# 业务自定义事件：writer({"_biz": {"kind": "command", ...}}) -> biz 事件（原样透传）
W_BIZ = "_biz"


def make_event(seq: int, event_type: str, payload: dict[str, Any] | None = None) -> dict:
    """构造统一事件信封"""
    return {
        "seq": seq,
        "type": event_type,
        "ts": datetime.now().isoformat(),
        "payload": payload or {},
    }


# ── 各类型 payload 约定（构造便捷函数，payload 部分）────────────────

def task_start_payload(task_type: str, title: str, total_stages: int | None) -> dict:
    return {"task_type": task_type, "title": title, "total_stages": total_stages}


def stage_payload(name: str, index: int | None = None, total: int | None = None) -> dict:
    return {"name": name, "index": index, "total": total}


def progress_payload(percent: int) -> dict:
    return {"percent": max(0, min(100, int(percent)))}


def log_payload(message: str, level: str = "info") -> dict:
    return {"message": message, "level": level}


def message_delta_payload(text: str, node: str | None = None) -> dict:
    return {"text": text, "node": node}


def node_update_payload(node: str, keys: list[str]) -> dict:
    return {"node": node, "keys": keys}


def result_payload(summary: dict | None, ref: dict | None) -> dict:
    return {"summary": summary or {}, "ref": ref or {}}


def error_payload(message: str, traceback: str | None = None) -> dict:
    return {"message": message, "traceback": traceback}


def task_end_payload(status: str, duration_ms: int | None = None) -> dict:
    return {"status": status, "duration_ms": duration_ms}
