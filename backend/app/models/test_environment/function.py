"""
全局函数数据模型

对应数据库表：test_global_function
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.mysql import BIGINT, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class GlobalFunction(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """
    全局函数模型

    存储全局函数定义
    """

    __tablename__ = "test_global_function"

    # 基本信息
    project_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="项目ID，NULL表示全局函数",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="函数名称（调用标识）",
    )
    display_name: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="函数显示名称",
    )
    language: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        comment="编程语言：python/javascript",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="函数代码",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="函数描述",
    )

    # 函数配置
    params: Mapped[str | None] = mapped_column(
        JSON,
        nullable=True,
        comment="参数说明（JSON数组）",
    )
    return_type: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="返回值类型",
    )
    example: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="使用示例",
    )

    # 状态
    is_built_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="是否内置函数",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="是否启用",
    )

    # 创建信息
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )

    def __repr__(self) -> str:
        return f"<GlobalFunction(id={self.id}, name='{self.name}', is_built_in={self.is_built_in})>"
