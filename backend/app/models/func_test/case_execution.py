"""用例执行记录数据模型

对应数据库表：func_case_execution

记录用例的手工执行结果，与测试环境关联。
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.func_test.test_case import FuncTestCase
    from app.models.project.project import Project
    from app.models.test_environment.environment import TestEnvironment


class CaseExecuteResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class FuncCaseExecution(Base, IDMixin, TimestampMixin):
    """用例执行记录"""

    __tablename__ = "func_case_execution"

    test_case_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("func_test_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="测试用例ID",
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    environment_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("test_environment.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="测试环境ID",
    )
    execute_result: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        index=True,
        comment="执行结果：passed/failed/blocked/skipped",
    )
    executor_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="执行人ID",
    )
    notes: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="备注（失败原因/缺陷链接）"
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="执行时间"
    )
    duration: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, comment="执行耗时（秒）"
    )

    test_case: Mapped["FuncTestCase"] = relationship(
        "FuncTestCase",
        foreign_keys=[test_case_id],
        back_populates="executions",
        lazy="select",
    )
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    environment: Mapped["TestEnvironment | None"] = relationship(
        "TestEnvironment", foreign_keys=[environment_id], lazy="select"
    )
    executor: Mapped["User"] = relationship(
        "User", foreign_keys=[executor_id], lazy="select"
    )

    __table_args__ = (
        Index("idx_func_exec_case_time", "test_case_id", "executed_at"),
    )

    def __repr__(self) -> str:
        return f"<FuncCaseExecution(id={self.id}, case_id={self.test_case_id}, result='{self.execute_result}')>"
