"""
测试环境数据模型

对应数据库表：test_environment
"""

from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.test_environment.variable import EnvironmentVariable


class TestEnvironment(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """
    测试环境模型

    存储测试环境的基本配置
    """

    __tablename__ = "test_environment"
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False, comment="环境名称")
    base_url: Mapped[str] = mapped_column(
        VARCHAR(500), nullable=False, comment="环境基础URL"
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True, comment="环境描述"
    )
    env_type: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, comment="环境类型: 1=功能测试 2=App测试"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否默认环境"
    )
    is_global: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="是否全局环境（所有项目可用）",
    )
    proxy_url: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True, comment="代理URL"
    )
    timeout: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, comment="请求超时时间（秒）"
    )
    verify_ssl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        comment="是否校验 HTTPS 证书（自签测试环境可关）",
    )
    allow_redirects: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        comment="是否跟随重定向（关掉可断言 3xx）",
    )
    keep_cookies: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="是否保持 Cookie 会话（登录后续用例复用 Set-Cookie）",
    )
    retry_times: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="连接类异常自动重试次数",
    )
    pre_script: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="前置脚本（JSON格式）"
    )
    post_script: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="后置脚本（JSON格式）"
    )
    variables: Mapped[list["EnvironmentVariable"]] = relationship(
        "EnvironmentVariable",
        back_populates="environment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TestEnvironment(id={self.id}, name='{self.name}', project_id={self.project_id})>"
