"""
用户数据模型

对应数据库表：sys_user
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.role import Role
    from app.models.auth.user_llm_config import UserLlmConfig
    from app.models.auth.user_role import UserRole
    from app.models.auth.user_token import UserToken


class UserStatus(str, Enum):
    """用户状态枚举"""

    ACTIVE = "active"  # 启用
    DISABLED = "disabled"  # 禁用
    LOCKED = "locked"  # 锁定


class User(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """
    用户模型

    存储系统用户的基本信息
    """

    __tablename__ = "sys_user"

    # 基本信息字段
    username: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        unique=True,
        index=True,
        comment="用户名",
    )
    password_hash: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        comment="加密后的密码（bcrypt）",
    )
    email: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        unique=True,
        index=True,
        comment="邮箱",
    )
    phone: Mapped[str | None] = mapped_column(
        VARCHAR(20),
        nullable=True,
        unique=True,
        comment="手机号",
    )
    real_name: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="真实姓名",
    )
    avatar: Mapped[str | None] = mapped_column(
        VARCHAR(255),
        nullable=True,
        comment="头像URL",
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus),
        nullable=False,
        default=UserStatus.ACTIVE,
        index=True,
        comment="状态：active/disabled/locked",
    )
    bio: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="个人简介",
    )

    # 登录安全字段
    login_fail_count: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="登录失败次数",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="锁定到期时间",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="最后登录时间",
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="最后登录IP",
    )

    # 关系
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        foreign_keys="UserRole.user_id",
        cascade="all, delete-orphan",
    )
    tokens: Mapped[list["UserToken"]] = relationship(
        "UserToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    llm_configs: Mapped[List["UserLlmConfig"]] = relationship(
        "UserLlmConfig",
        back_populates="user",
        uselist=True,
        cascade="all, delete-orphan",
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        "OperationLog",
        back_populates="user",
        foreign_keys="OperationLog.user_id",
    )

    @property
    def roles(self) -> list["Role"]:
        """获取用户角色列表"""
        return [user_role.role for user_role in self.user_roles]

    @property
    def role_codes(self) -> list[str]:
        """获取用户角色编码列表"""
        return [role.code for role in self.roles]

    @property
    def permissions(self) -> list[str]:
        """获取用户所有权限（通过角色聚合）"""
        perm_set = set()
        for role in self.roles:
            for permission in role.permissions:
                perm_set.add(permission.code)
        return list(perm_set)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
