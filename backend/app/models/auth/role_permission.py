"""
角色权限关联表模型

对应数据库表：sys_role_permission
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.permission import Permission
    from app.models.auth.role import Role


class RolePermission(Base, IDMixin, TimestampMixin):
    """
    角色权限关联模型

    实现角色与权限的多对多关联
    """

    __tablename__ = "sys_role_permission"

    # 外键
    role_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_role.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="角色ID",
    )
    permission_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_permission.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="权限ID",
    )

    # 关系
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="role_permissions",
        foreign_keys=[role_id],
    )
    permission: Mapped["Permission"] = relationship(
        "Permission",
        back_populates="role_permissions",
        foreign_keys=[permission_id],
    )

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uk_role_permission"),
        Index("idx_role_id", "role_id"),
        Index("idx_permission_id", "permission_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<RolePermission(id={self.id}, role_id={self.role_id}, "
            f"permission_id={self.permission_id})>"
        )
