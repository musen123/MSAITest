"""
项目成员数据模型

对应数据库表：tb_project_member
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.role import Role
    from app.models.auth.user import User
    from app.models.project.project import Project


class ProjectMember(Base, IDMixin, TimestampMixin):
    """
    项目成员模型

    存储项目与用户的关联关系及角色信息
    项目角色直接关联 sys_role 表
    """

    __tablename__ = "tb_project_member"

    # 关联字段
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    project_role_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_role.id", ondelete="RESTRICT"),
        nullable=False,
        default=1,  # 默认角色ID，需要在迁移中设置
        index=True,
        comment="项目角色ID（关联 sys_role 表）",
    )

    # 活跃时间
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后活跃时间",
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="members",
        lazy="selectin",
    )
    user: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    project_role_obj: Mapped["Role"] = relationship(
        "Role",
        lazy="selectin",
    )

    # 表约束
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
        Index("idx_project_role", "project_id", "project_role_id"),
        Index("idx_user_project", "user_id", "project_id"),
    )

    @property
    def project_role(self) -> str:
        """获取角色代码（向后兼容）"""
        return self.project_role_obj.code if self.project_role_obj else ""

    @property
    def project_role_name(self) -> str:
        """获取角色名称"""
        return self.project_role_obj.name if self.project_role_obj else ""

    def __repr__(self) -> str:
        role_code = self.project_role_obj.code if self.project_role_obj else "unknown"
        return f"<ProjectMember(id={self.id}, project_id={self.project_id}, user_id={self.user_id}, role='{role_code}')>"
