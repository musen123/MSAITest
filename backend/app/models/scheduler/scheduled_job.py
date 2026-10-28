"""定时任务调度模型

sys_scheduled_job：定时计划（数据库即调度配置，增删改即时生效）。
beat 每 30s 触发 dispatch 巡检，扫描 enabled 且 next_run_at 到期的
计划，原子推进 next_run_at 抢占后创建 ai_task 投递执行。

sys_scheduled_job_run：派发流水（每次到期一行），终态经 ai_task_id
回链 ai_task 查询，不重复存储。
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, BOOLEAN, INTEGER, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin


class ScheduledJobType(str, Enum):
    APP_SUITE = "app_suite"


class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"


class ScheduledJob(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """定时计划"""

    __tablename__ = "sys_scheduled_job"
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False, comment="计划名称")
    description: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True, comment="描述"
    )
    job_type: Mapped[str] = mapped_column(
        VARCHAR(30), nullable=False, comment="执行对象类型：app_suite"
    )
    target_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="执行对象ID（App 套件）"
    )
    params: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="执行参数：{environment_id, run_mode, ...}"
    )
    schedule_type: Mapped[str] = mapped_column(
        VARCHAR(10),
        nullable=False,
        default=ScheduleType.CRON.value,
        comment="调度方式：cron/interval",
    )
    cron_expr: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, comment="5 段 cron 表达式（按本地时区语义）"
    )
    interval_seconds: Mapped[int | None] = mapped_column(
        INTEGER, nullable=True, comment="固定间隔秒数（interval 模式）"
    )
    enabled: Mapped[bool] = mapped_column(
        BOOLEAN, nullable=False, default=True, comment="是否启用"
    )
    allow_overlap: Mapped[bool] = mapped_column(
        BOOLEAN,
        nullable=False,
        default=False,
        comment="上次执行未完成时是否允许并行触发",
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="下次运行时间（UTC，派发扫描键）"
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次派发时间（UTC）"
    )
    last_status: Mapped[str | None] = mapped_column(
        VARCHAR(20),
        nullable=True,
        comment="最近一次派发结果：dispatched/skipped/failed",
    )
    last_task_id: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, comment="最近一次派发的 ai_task ID"
    )
    total_runs: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="累计派发次数"
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建人ID（派发任务以此身份执行）",
    )
    __table_args__ = (Index("idx_sched_job_due", "enabled", "next_run_at"),)

    def __repr__(self) -> str:
        return f"<ScheduledJob(id={self.id}, name='{self.name}', type='{self.job_type}', next={self.next_run_at})>"


class ScheduledJobRun(Base, IDMixin):
    """定时计划派发流水"""

    __tablename__ = "sys_scheduled_job_run"
    job_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_scheduled_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属定时计划ID",
    )
    ai_task_id: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, comment="派发产生的 ai_task ID（跳过时为空）"
    )
    fired_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="派发时间（UTC）"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        comment="派发结果：dispatched/skipped_overlap/failed",
    )
    note: Mapped[str | None] = mapped_column(
        VARCHAR(200), nullable=True, comment="说明（跳过/失败原因）"
    )

    def __repr__(self) -> str:
        return f"<ScheduledJobRun(id={self.id}, job_id={self.job_id}, status='{self.status}')>"
