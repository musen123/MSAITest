"""
环境变量数据模型

对应数据库表：test_env_variable
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.test_environment.environment import TestEnvironment


class EnvironmentVariable(Base, IDMixin, TimestampMixin):
    """
    环境变量模型

    存储环境的变量配置
    """

    __tablename__ = "test_env_variable"

    # 基本信息
    env_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("test_environment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="环境ID",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="变量名",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="变量值",
    )
    type: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="text",
        comment="变量类型：text/password/json/dynamic",
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="变量描述",
    )

    # 配置
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序顺序",
    )

    # 关系
    environment: Mapped["TestEnvironment"] = relationship(
        "TestEnvironment",
        back_populates="variables",
    )

    def __repr__(self) -> str:
        return f"<EnvironmentVariable(id={self.id}, name='{self.name}', env_id={self.env_id})>"
