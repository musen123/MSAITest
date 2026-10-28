"""
操作日志模型

对应数据库表：sys_operation_log
"""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User


class Action(str, Enum):
    """操作类型枚举"""

    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    QUERY = "query"
    EXPORT = "export"
    IMPORT = "import"


class OperationLog(Base, IDMixin, TimestampMixin):
    """
    操作日志模型

    记录用户操作日志，用于审计
    """

    __tablename__ = "sys_operation_log"

    # 外键
    user_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="操作用户ID",
    )

    # 冗余字段
    username: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="操作用户名（冗余）",
    )

    # 操作信息
    module: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        index=True,
        comment="操作模块",
    )
    action: Mapped[Action] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="操作类型：login/logout/create/update/delete",
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="操作描述",
    )

    # 请求信息
    request_method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="请求方法：GET/POST/PUT/DELETE",
    )
    request_url: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="请求URL",
    )
    request_params: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="请求参数（JSON）",
    )
    response_status: Mapped[int | None] = mapped_column(
        INTEGER,
        nullable=True,
        comment="响应状态码",
    )

    # 客户端信息
    ip_address: Mapped[str | None] = mapped_column(
        VARCHAR(50),
        nullable=True,
        comment="操作IP地址",
    )
    user_agent: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="用户代理",
    )

    # 性能信息
    execution_time: Mapped[int | None] = mapped_column(
        INTEGER,
        nullable=True,
        comment="执行耗时（毫秒）",
    )

    # 关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="operation_logs",
        foreign_keys=[user_id],
    )

    # 索引
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_module", "module"),
        Index("idx_action", "action"),
        Index("idx_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<OperationLog(id={self.id}, user_id={self.user_id}, "
            f"module='{self.module}', action='{self.action}')>"
        )
