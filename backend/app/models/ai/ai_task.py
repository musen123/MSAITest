"""统一 AI 任务主表

对应数据库表：ai_task

跨模块（func_test / api_test / web_test / knowledge）统一记录所有
基于 LangGraph + Celery 异步执行的 AI 任务的状态、进度、产出与心跳。

任务类型由 ``task_type`` 标识，对应 ``app.ai_core.runtime.registry`` 中注册的图。
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.project.project import Project


class AiTaskStatus(str, Enum):
    """AI 任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class AiTask(Base, IDMixin, TimestampMixin):
    """统一 AI 任务"""

    __tablename__ = "ai_task"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="发起人ID",
    )
    task_type: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        index=True,
        comment="任务类型（registry key）：generate_case/parse_document/...",
    )
    title: Mapped[str] = mapped_column(
        VARCHAR(200), nullable=False, default="", comment="任务展示名"
    )
    biz_ref_type: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="业务关联类型：document/requirement/interface...",
    )
    biz_ref_id: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, index=True, comment="业务关联ID"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=AiTaskStatus.PENDING.value,
        index=True,
        comment="状态：pending/running/succeeded/failed/canceled",
    )
    progress: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="进度百分比（0-100）"
    )
    current_stage: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, comment="当前阶段名"
    )
    stage_index: Mapped[int | None] = mapped_column(
        INTEGER, nullable=True, comment="当前第几阶段"
    )
    total_stages: Mapped[int | None] = mapped_column(
        INTEGER, nullable=True, comment="阶段总数"
    )
    ai_model: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, comment="使用的 AI 模型"
    )
    input_params: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="任务输入参数快照（retry 用）"
    )
    result_summary: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="产出摘要（数量/覆盖率等）"
    )
    result_ref: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="结果定位（如 {case_ids:[...]}）"
    )
    error_message: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="错误信息"
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, index=True, comment="Celery 任务 ID"
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="worker 心跳时间（僵尸巡检用）"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="完成时间"
    )

    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="select"
    )

    __table_args__ = (
        Index("idx_ai_task_project_status", "project_id", "status"),
        Index("idx_ai_task_type_status", "task_type", "status"),
        Index("idx_ai_task_biz_ref", "biz_ref_type", "biz_ref_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AiTask(id={self.id}, type='{self.task_type}', "
            f"status='{self.status}', progress={self.progress})>"
        )
