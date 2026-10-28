"""
角色数据模型

对应数据库表：sys_role
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy.dialects.mysql import INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.permission import Permission
    from app.models.auth.role_permission import RolePermission
    from app.models.auth.user_role import UserRole


class Role(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """
    角色模型

    存储系统角色信息
    """

    __tablename__ = "sys_role"

    code: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        unique=True,
        index=True,
        comment="角色编码",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        comment="角色名称",
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(200),
        nullable=True,
        comment="角色描述",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否系统预定义角色",
    )
    sort_order: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="排序顺序",
    )

    # 关系
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    @property
    def permissions(self) -> list["Permission"]:
        """获取角色权限列表"""
        return [rp.permission for rp in self.role_permissions]

    @property
    def permission_codes(self) -> list[str]:
        """获取角色权限编码列表"""
        return [p.code for p in self.permissions]

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, code='{self.code}', name='{self.name}')>"
