"""
Bug 操作历史数据模型

对应数据库表：bug_history
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, IDMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.bug.bug import Bug


class BugAction(str, Enum):
    """Bug 操作类型枚举"""

    CREATED = "created"  # 创建Bug
    STATUS_CHANGED = "status_changed"  # 状态变更
    ASSIGNED = "assigned"  # 指派人员变更
    SEVERITY_CHANGED = "severity_changed"  # 严重程度变更
    PRIORITY_CHANGED = "priority_changed"  # 优先级变更
    RESOLVED = "resolved"  # 标记解决
    REOPENED = "reopened"  # 重新打开
    CLOSED = "closed"  # 关闭


class BugHistory(Base, IDMixin):
    """Bug 操作历史模型 - 记录 Bug 生命周期内的所有变更操作"""

    __tablename__ = "bug_history"

    bug_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("bug.id", ondelete="CASCADE"),
        nullable=False,
        comment="Bug ID",
    )
    action: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        comment="操作类型",
    )
    from_value: Mapped[str | None] = mapped_column(
        VARCHAR(100),
        nullable=True,
        comment="变更前的值",
    )
    to_value: Mapped[str | None] = mapped_column(
        VARCHAR(100),
        nullable=True,
        comment="变更后的值",
    )
    comment: Mapped[str | None] = mapped_column(
        TEXT,
        nullable=True,
        comment="操作备注",
    )
    operated_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        comment="操作人ID",
    )
    operated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="操作时间",
    )

    # ── 关系 ──────────────────────────────────────────────────

    bug: Mapped["Bug"] = relationship(
        "Bug",
        back_populates="histories",
        lazy="select",
    )
    operator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[operated_by],
        lazy="select",
    )

    # ── 表约束 ────────────────────────────────────────────────

    __table_args__ = (
        Index("idx_bug_history_bug_id", "bug_id"),
        Index("idx_bug_history_action", "action"),
        Index("idx_bug_history_operated_by", "operated_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<BugHistory(id={self.id}, bug_id={self.bug_id}, action='{self.action}')>"
        )
