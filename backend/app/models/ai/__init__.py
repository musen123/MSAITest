"""统一 AI 任务数据模型

跨模块统一的 AI 任务执行记录与事件流：
  - AiTask        统一 AI 任务主表（状态/进度/结果/心跳）
  - AiTaskEvent   AI 任务事件流（append-only，支持实时回放）
"""

from app.models.ai.ai_task import AiTask, AiTaskStatus
from app.models.ai.ai_task_event import AiTaskEvent, AiTaskEventType

__all__ = [
    "AiTask",
    "AiTaskStatus",
    "AiTaskEvent",
    "AiTaskEventType",
]
