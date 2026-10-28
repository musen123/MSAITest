"""AI 任务事件流

对应数据库表：ai_task_event

append-only 事件日志，记录任务执行过程的阶段/进度/日志/AI 输出/结果等，
用于任务详情的「历史回放」（与 Redis 实时通道互补）。
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin


class AiTaskEventType(str, Enum):
    """AI 任务事件类型"""

    TASK_START = "task_start"
    STAGE = "stage"
    PROGRESS = "progress"
    LOG = "log"
    MESSAGE_DELTA = "message_delta"
    NODE_UPDATE = "node_update"
    RESULT = "result"
    ERROR = "error"
    TASK_END = "task_end"
    # 业务自定义事件（payload 含 kind 字段标识业务类型，前端按 kind 渲染）。
    # 用于超出通用协议的富事件，如 web_agent 的 command/screenshot/report
    BIZ = "biz"


class AiTaskEvent(Base, IDMixin):
    """AI 任务事件（append-only）"""

    __tablename__ = "ai_task_event"

    task_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("ai_task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属 AI 任务ID",
    )
    seq: Mapped[int] = mapped_column(
        INTEGER, nullable=False, comment="任务内单调序号（SSE Last-Event-ID）"
    )
    event_type: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        index=True,
        comment="事件类型：stage/progress/log/message_delta/result/...",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="事件数据体"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        Index("uq_ai_task_event_task_seq", "task_id", "seq", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<AiTaskEvent(task_id={self.task_id}, seq={self.seq}, "
            f"type='{self.event_type}')>"
        )
