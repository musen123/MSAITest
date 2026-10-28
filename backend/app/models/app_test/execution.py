"""
APP 自动化执行记录数据模型

对应数据库表：app_execution（方案 §4 / 契约 §7 P2 增补）。
一条 = 一次回放（run_app_script exec 图跑一次）；ai_task_id 关联统一任务框架
（进度/事件流走 ai_task_event 双落地，这里只存执行结论与报告指针）。
"""

from enum import Enum

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class AppExecutionStatus(str, Enum):
    """执行状态（对齐统一任务框架终态）"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AppExecution(Base, IDMixin, TimestampMixin):
    """APP 自动化执行记录（回放一次一条）"""

    __tablename__ = "app_execution"

    script_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("app_script.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用例ID",
    )
    suite_execution_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("app_suite_execution.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属套件执行汇总ID（套件批量回放时挂靠；单跑为空）",
    )
    ai_task_id: Mapped[str | None] = mapped_column(
        VARCHAR(64),
        nullable=True,
        index=True,
        comment="统一任务框架 task_id（事件流/进度经 ai_task_event 回放）",
    )
    device_udid: Mapped[str] = mapped_column(
        VARCHAR(160),
        nullable=False,
        comment="执行设备 udid（{agent_id}:{serial}）",
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default=AppExecutionStatus.PENDING.value,
        comment="状态：pending/running/success/failed/cancelled",
    )
    steps_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="步骤结果摘要 JSON（总数/通过/失败/错误信息等）",
    )
    report_path: Mapped[str | None] = mapped_column(
        VARCHAR(255),
        nullable=True,
        comment="Midscene HTML 报告相对路径（鉴权端点展示，绝不落 /uploads）",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        INTEGER,
        nullable=True,
        comment="执行耗时（毫秒）",
    )
    retry_index: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="重试序号（0=首跑）",
    )

    def __repr__(self) -> str:
        return f"<AppExecution(id={self.id}, script_id={self.script_id}, status='{self.status}')>"
