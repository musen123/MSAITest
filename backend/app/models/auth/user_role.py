"""
用户角色关联表模型

对应数据库表：sys_user_role
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.role import Role
    from app.models.auth.user import User


class UserRole(Base, IDMixin, TimestampMixin):
    """
    用户角色关联模型

    实现用户与角色的多对多关联
    """

    __tablename__ = "sys_user_role"

    # 外键
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    role_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_role.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="角色ID",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )

    # 关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_roles",
        foreign_keys=[user_id],
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="user_roles",
        foreign_keys=[role_id],
    )

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uk_user_role"),
        Index("idx_user_id", "user_id"),
        Index("idx_role_id", "role_id"),
    )

    def __repr__(self) -> str:
        return f"<UserRole(id={self.id}, user_id={self.user_id}, role_id={self.role_id})>"
