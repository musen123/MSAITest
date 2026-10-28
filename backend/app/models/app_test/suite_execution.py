"""
APP 自动化套件执行汇总数据模型

对应数据库表：app_suite_execution（P4）。一条 = run_app_suite 图跑一次
（手动或定时触发），只存套件级结论与计数；单条用例结果复用 app_execution
（挂 suite_execution_id 外键，SET NULL——套件汇总删除后用例级历史仍留在
用例名下）。事件流/进度经 ai_task_event 回放，同单用例执行约定。
"""

from enum import Enum

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class AppSuiteExecutionStatus(str, Enum):
    """套件执行状态（对齐统一任务框架终态；partial 语义看计数）"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"      # 全部启用用例通过
    FAILED = "failed"        # ≥1 条失败或套件级错误
    CANCELLED = "cancelled"


class AppSuiteExecution(Base, IDMixin, TimestampMixin):
    """APP 套件执行汇总（批量回放一次一条）"""

    __tablename__ = "app_suite_execution"

    suite_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("app_suite.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="套件ID",
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID（免 join 列表）",
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
    trigger_type: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default="manual",
        comment="触发方式：manual/scheduled",
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default=AppSuiteExecutionStatus.PENDING.value,
        comment="状态：pending/running/success/failed/cancelled",
    )
    total_cases: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="参与执行的用例总数（enabled）"
    )
    passed_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="通过数"
    )
    failed_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="失败数"
    )
    skipped_count: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="跳过数（stop 策略中断/取消后未执行的余量）",
    )
    error: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="套件级错误信息（抢锁失败/设备离线等；单条失败看用例级记录）",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        INTEGER,
        nullable=True,
        comment="总耗时（毫秒）",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="触发人（定时触发=计划创建人）",
    )

    def __repr__(self) -> str:
        return (
            f"<AppSuiteExecution(id={self.id}, suite_id={self.suite_id}, "
            f"status='{self.status}')>"
        )
