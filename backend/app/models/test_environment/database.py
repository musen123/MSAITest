"""
数据库连接数据模型

对应数据库表：test_database
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.mysql import BIGINT, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class DatabaseConnection(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """
    数据库连接模型

    存储数据库连接配置
    """

    __tablename__ = "test_database"

    # 基本信息
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="连接名称",
    )
    db_type: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        index=True,
        comment="数据库类型：MySQL/PostgreSQL/Oracle/SQLServer/MongoDB/Redis",
    )
    host: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        comment="数据库地址",
    )
    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="端口号",
    )
    database: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="数据库名",
    )
    username: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="用户名",
    )
    password: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        comment="密码（AES-256加密）",
    )

    # 额外配置
    charset: Mapped[str | None] = mapped_column(
        VARCHAR(20),
        nullable=True,
        comment="字符集，默认utf8mb4",
    )
    connection_params: Mapped[str | None] = mapped_column(
        JSON,
        nullable=True,
        comment="额外连接参数（JSON）",
    )

    # 写操作开关：脚本/SQL 节点里的写语句（DELETE/UPDATE/INSERT/DDL）需该连接显式开启，
    # 默认关闭——防止误把破坏性 SQL 打到生产库。读操作（SELECT/内省）不受此限。
    allow_write: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="是否允许写操作（造数/清理等破坏性 SQL），默认关闭",
    )

    # 连接状态
    connection_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="unknown",
        comment="连接状态：connected/disconnected/unknown",
    )
    last_test_time: Mapped[str | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="最后测试连接时间",
    )
    last_test_result: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="最后测试结果",
    )

    def __repr__(self) -> str:
        return f"<DatabaseConnection(id={self.id}, name='{self.name}', db_type='{self.db_type}')>"
