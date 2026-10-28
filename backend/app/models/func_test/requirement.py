"""测试需求数据模型

对应数据库表：func_test_requirement

支持手工创建 + AI 解析两种来源。
attachments 字段存图片 URL 数组，用于 VLM 多模态需求理解。
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.func_test.document import ProjectDocument
    from app.models.func_test.test_case import FuncTestCase
    from app.models.project.module import ProjectModule
    from app.models.project.project import Project


class RequirementPriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class RequirementSource(str, Enum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class TestRequirement(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """测试需求"""

    __tablename__ = "func_test_requirement"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    code: Mapped[str | None] = mapped_column(
        VARCHAR(50), nullable=True, comment="需求编号"
    )
    title: Mapped[str] = mapped_column(
        VARCHAR(200), nullable=False, comment="需求标题"
    )
    module_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("tb_project_module.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属模块ID",
    )
    priority: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=RequirementPriority.MEDIUM.value,
        comment="优先级：urgent/high/medium/low",
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(30),
        nullable=False,
        default=RequirementStatus.DRAFT.value,
        index=True,
        comment="状态：draft/pending_review/reviewed/published/deprecated",
    )
    description: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="需求描述（Markdown）"
    )
    acceptance_criteria: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="验收标准"
    )
    understood_content: Mapped[str | None] = mapped_column(
        TEXT,
        nullable=True,
        comment="AI 需求理解结果（VLM + LLM 整理后的 Markdown）",
    )
    attachments: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="附件图片URL列表"
    )
    source: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=RequirementSource.MANUAL.value,
        index=True,
        comment="来源：manual/ai_generated",
    )
    document_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("func_project_document.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="来源文档ID",
    )
    review_comment: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True, comment="审核意见"
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人ID",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="审核时间"
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="创建人ID",
    )

    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    module: Mapped["ProjectModule | None"] = relationship(
        "ProjectModule", foreign_keys=[module_id], lazy="select"
    )
    document: Mapped["ProjectDocument | None"] = relationship(
        "ProjectDocument", foreign_keys=[document_id], lazy="select"
    )
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="select"
    )
    reviewer: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by], lazy="select"
    )
    test_cases: Mapped[list["FuncTestCase"]] = relationship(
        "FuncTestCase", back_populates="requirement", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_func_req_project_code"),
        Index("idx_func_req_source", "source"),
        Index("idx_func_req_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<TestRequirement(id={self.id}, title='{self.title}', status='{self.status}')>"
