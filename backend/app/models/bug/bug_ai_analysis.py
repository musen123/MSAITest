"""
Bug AI 分析结果数据模型

对应数据库表：bug_ai_analysis
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, IDMixin

if TYPE_CHECKING:
    from app.models.bug.bug import Bug


class AnalysisStatus(str, Enum):
    """AI 分析状态枚举"""

    PROCESSING = "processing"  # 分析中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class BugAiAnalysis(Base, IDMixin):
    """Bug AI 分析结果模型 - 存储 AI 对 Bug 的智能分析结果（与 Bug 一对一）"""

    __tablename__ = "bug_ai_analysis"

    bug_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("bug.id", ondelete="CASCADE"),
        nullable=False,
        comment="Bug ID（唯一，一对一）",
    )
    analysis_id: Mapped[str] = mapped_column(
        VARCHAR(100),
        nullable=False,
        comment="分析任务ID（唯一）",
    )
    root_cause_analysis: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="根因分析结果",
    )
    solution_recommendation: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="解决方案推荐",
    )
    similar_bugs: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="相似Bug列表",
    )
    severity_assessment: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="严重程度评估",
    )
    analysis_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=AnalysisStatus.PROCESSING.value,
        comment="分析状态：processing/completed/failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        TEXT,
        nullable=True,
        comment="失败时的错误信息",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="完成时间",
    )

    # ── 关系 ──────────────────────────────────────────────────

    bug: Mapped["Bug"] = relationship(
        "Bug",
        back_populates="ai_analysis",
        lazy="select",
    )

    # ── 表约束 ────────────────────────────────────────────────

    __table_args__ = (
        UniqueConstraint("bug_id", name="uk_bug_ai_bug_id"),
        UniqueConstraint("analysis_id", name="uk_bug_ai_analysis_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<BugAiAnalysis(id={self.id}, bug_id={self.bug_id}, "
            f"status='{self.analysis_status}')>"
        )
