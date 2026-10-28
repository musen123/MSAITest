"""
用户Token模型

对应数据库表：sys_user_token
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User


class TokenType(str, Enum):
    """Token类型枚举"""

    ACCESS = "access"  # 访问令牌
    REFRESH = "refresh"  # 刷新令牌


class UserToken(Base, IDMixin, TimestampMixin):
    """
    用户Token模型

    存储用户的访问令牌
    """

    __tablename__ = "sys_user_token"

    # 外键
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )

    # Token信息
    token_type: Mapped[TokenType] = mapped_column(
        VARCHAR(20),
        nullable=False,
        comment="Token类型：access/refresh",
    )
    token: Mapped[str] = mapped_column(
        VARCHAR(500),
        nullable=False,
        unique=True,
        comment="Token值",
    )
    expires_at: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
        index=True,
        comment="过期时间",
    )

    # 撤销状态
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否已撤销",
    )
    revoked_at: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="撤销时间",
    )

    # 请求信息
    ip_address: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="创建时的IP",
    )
    user_agent: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="用户代理",
    )

    # 关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tokens",
        foreign_keys=[user_id],
    )

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("token", name="uk_token"),
        Index("idx_user_id", "user_id"),
        Index("idx_user_type", "user_id", "token_type"),
        Index("idx_expires_at", "expires_at"),
    )

    @property
    def is_expired(self) -> bool:
        """Token是否已过期"""
        return int(datetime.now(timezone.utc).timestamp()) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        """Token是否有效（未过期且未撤销）"""
        return not self.revoked and not self.is_expired

    def __repr__(self) -> str:
        return (
            f"<UserToken(id={self.id}, user_id={self.user_id}, "
            f"token_type='{self.token_type}', revoked={self.revoked})>"
        )
