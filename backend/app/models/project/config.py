"""
项目配置数据模型

对应数据库表：tb_project_config
"""

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class ProjectConfig(Base, IDMixin, TimestampMixin):
    """
    项目配置模型

    存储项目的配置信息
    """

    __tablename__ = "tb_project_config"

    # 关联字段
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="项目ID",
    )

    # 测试环境配置
    default_env_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="默认测试环境ID",
    )

    # Bug 配置
    bug_auto_assign: Mapped[bool] = mapped_column(
        TINYINT,
        nullable=False,
        default=True,
        comment="Bug是否自动分配给创建者",
    )
    bug_severity_default: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="medium",
        comment="Bug默认严重程度：critical/high/medium/low/trivial",
    )

    # 测试用例配置
    test_case_priority_default: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="medium",
        comment="用例默认优先级：critical/high/medium/low",
    )

    # 报告配置
    allow_public_report: Mapped[bool] = mapped_column(
        TINYINT,
        nullable=False,
        default=False,
        comment="是否允许公开查看测试报告",
    )

    # 数据保留配置
    retention_days: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=90,
        comment="数据保留天数（归档后）",
    )

    # 表约束
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_config_project"),
        Index("idx_project_env", "project_id", "default_env_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectConfig(id={self.id}, project_id={self.project_id})>"
