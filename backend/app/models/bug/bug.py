"""
缺陷管理 Bug 数据模型

对应数据库表：bug
"""

from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.bug.bug_ai_analysis import BugAiAnalysis
    from app.models.bug.bug_history import BugHistory
    from app.models.project.module import ProjectModule
    from app.models.project.project import Project


class BugSeverity(str, Enum):
    """Bug 严重程度枚举"""

    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    TRIVIAL = "trivial"


class BugPriority(str, Enum):
    """Bug 优先级枚举"""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugStatus(str, Enum):
    """Bug 状态枚举"""

    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    REOPENED = "reopened"
    CLOSED = "closed"
    POSTPONED = "postponed"
    WONTFIX = "wontfix"


class TestCaseType(str, Enum):
    """关联测试用例类型枚举"""

    FUNCTIONAL = "functional"


class Bug(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """缺陷模型 - 存储 Bug 的完整生命周期信息"""

    __tablename__ = "bug"
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    bug_key: Mapped[str] = mapped_column(
        VARCHAR(50), nullable=False, comment="Bug编号，格式：BUG-{YYYYMMDD}-{序号4位}"
    )
    title: Mapped[str] = mapped_column(VARCHAR(255), nullable=False, comment="Bug标题")
    description: Mapped[str] = mapped_column(
        TEXT, nullable=False, comment="Bug详细描述"
    )
    severity: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        comment="严重程度：critical/major/moderate/minor/trivial",
    )
    priority: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, comment="优先级：urgent/high/medium/low"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=BugStatus.NEW.value,
        comment="状态：new/assigned/in_progress/resolved/verified/reopened/closed/postponed/wontfix",
    )
    module_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("tb_project_module.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联模块ID",
    )
    test_case_id: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, comment="关联测试用例ID"
    )
    test_case_type: Mapped[str | None] = mapped_column(
        VARCHAR(20), nullable=True, comment="用例类型：functional/api/web"
    )
    assigned_to: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="指派给谁（用户ID）",
    )
    environment: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, comment="发现环境描述"
    )
    reproduction_steps: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="复现步骤"
    )
    expected_result: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="预期结果"
    )
    actual_result: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="实际结果"
    )
    external_bug_key: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, comment="外部系统Bug编号（如Jira）"
    )
    tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="标签列表（JSON数组）"
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否已归档"
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建人ID",
    )
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    module: Mapped["ProjectModule | None"] = relationship(
        "ProjectModule", foreign_keys=[module_id], lazy="select"
    )
    assignee: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assigned_to], lazy="select"
    )
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="select"
    )
    histories: Mapped[list["BugHistory"]] = relationship(
        "BugHistory", back_populates="bug", lazy="select"
    )
    ai_analysis: Mapped["BugAiAnalysis | None"] = relationship(
        "BugAiAnalysis", back_populates="bug", uselist=False, lazy="select"
    )
    __table_args__ = (
        UniqueConstraint("bug_key", name="uk_bug_key"),
        Index("idx_bug_project_status", "project_id", "status"),
        Index("idx_bug_severity", "severity"),
        Index("idx_bug_priority", "priority"),
        Index("idx_bug_assigned_to", "assigned_to"),
        Index("idx_bug_module_id", "module_id"),
        Index("idx_bug_test_case_id", "test_case_id"),
        Index("idx_bug_external_key", "external_bug_key"),
        Index("idx_bug_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<Bug(id={self.id}, key='{self.bug_key}', status='{self.status}')>"
