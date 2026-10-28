"""
项目模块数据模型

对应数据库表：tb_project_module
"""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.project.project import Project


class ModuleType(str, Enum):
    """模块类型枚举"""

    FEATURE = "feature"  # 功能模块
    BUSINESS = "business"  # 业务流程
    INTERFACE = "interface"  # 接口模块
    PAGE = "page"  # 页面模块


class ProjectModule(Base, IDMixin, TimestampMixin):
    """
    项目模块模型

    存储项目的模块层级结构
    """

    __tablename__ = "tb_project_module"

    # 基本信息字段
    name: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="模块名称",
    )
    parent_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("tb_project_module.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="父模块ID",
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目ID",
    )
    sort_order: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="排序顺序",
    )
    description: Mapped[str | None] = mapped_column(
        TEXT,
        nullable=True,
        comment="模块描述",
    )
    module_type: Mapped[ModuleType] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=ModuleType.FEATURE,
        comment="模块类型：feature/business/interface/page",
    )
    level: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=1,
        comment="层级深度（1-5）",
    )
    path: Mapped[str] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="模块路径（如：用户模块/登录注册）",
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="modules",
        lazy="selectin",
    )

    # 表约束
    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 5", name="ck_module_level"),
        CheckConstraint("sort_order >= 0", name="ck_module_sort_order"),
        Index("idx_project_parent", "project_id", "parent_id"),
        Index("idx_project_sort", "project_id", "sort_order"),
    )

    def __repr__(self) -> str:
        return f"<ProjectModule(id={self.id}, name='{self.name}', project_id={self.project_id})>"
