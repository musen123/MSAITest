"""
项目数据模型

对应数据库表：tb_project
"""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, TEXT, TINYINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.project.member import ProjectMember
    from app.models.project.module import ProjectModule


class ProjectStatus(str, Enum):
    """项目状态枚举"""

    ACTIVE = "active"  # 活跃
    ARCHIVED = "archived"  # 归档
    DELETED = "deleted"  # 已删除


class Project(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """
    项目模型

    存储测试项目的基本信息
    """

    __tablename__ = "tb_project"

    # 基本信息字段
    name: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        unique=True,
        index=True,
        comment="项目名称",
    )
    code: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        unique=True,
        index=True,
        comment="项目标识（用于URL和API路径）",
    )
    description: Mapped[str | None] = mapped_column(
        TEXT,
        nullable=True,
        comment="项目描述",
    )
    avatar: Mapped[str | None] = mapped_column(
        VARCHAR(255),
        nullable=True,
        comment="项目图标URL",
    )
    status: Mapped[ProjectStatus] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=ProjectStatus.ACTIVE,
        index=True,
        comment="项目状态：active/archived/deleted",
    )
    is_public: Mapped[bool] = mapped_column(
        TINYINT,
        nullable=False,
        default=False,
        comment="是否公开项目",
    )

    # 项目时间字段
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="计划开始日期",
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="计划结束日期",
    )

    # 创建者信息
    created_by_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="创建者ID",
    )

    # 关系
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    modules: Mapped[list["ProjectModule"]] = relationship(
        "ProjectModule",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 表约束
    __table_args__ = (
        UniqueConstraint("name", name="uq_project_name"),
        UniqueConstraint("code", name="uq_project_code"),
        Index("idx_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', code='{self.code}')>"
