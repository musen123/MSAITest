"""
权限数据模型

对应数据库表：sys_permission
"""

from typing import TYPE_CHECKING

from sqlalchemy.dialects.mysql import INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.role_permission import RolePermission


class Permission(Base, IDMixin, TimestampMixin):
    """
    权限模型

    存储系统权限定义
    """

    __tablename__ = "sys_permission"

    code: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        unique=True,
        index=True,
        comment="权限编码",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        comment="权限名称",
    )
    module: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        index=True,
        comment="所属模块",
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(200),
        nullable=True,
        comment="权限描述",
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
        back_populates="permission",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code='{self.code}', name='{self.name}')>"
