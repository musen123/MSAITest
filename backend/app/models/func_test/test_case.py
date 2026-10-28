"""功能测试用例数据模型

对应数据库表：func_test_case

steps 字段存储测试步骤 JSON 数组：
[{"step_no": 1, "action": "...", "expected": "..."}]
test_data 字段存储测试数据 JSON 对象。
review_info 字段存储 AI 评审结果（result/decs）。
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.func_test.case_execution import FuncCaseExecution
    from app.models.func_test.requirement import TestRequirement
    from app.models.project.module import ProjectModule
    from app.models.project.project import Project


class CasePriority(str, Enum):
    """用例优先级（同时兼容 P0/P1/P2 表示，存数据库统一存 high/medium/low 等）"""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CaseType(str, Enum):
    FUNCTIONAL = "functional"
    SMOKE = "smoke"
    REGRESSION = "regression"
    EXPLORATORY = "exploratory"


class ValidationLevel(str, Enum):
    SYSTEM = "system"
    INTEGRATION = "integration"
    UNIT = "unit"


class CaseStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    DEPRECATED = "deprecated"


class CaseSource(str, Enum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class FuncTestCase(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """功能测试用例"""

    __tablename__ = "func_test_case"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    code: Mapped[str | None] = mapped_column(
        VARCHAR(80), nullable=True, comment="用例编号"
    )
    title: Mapped[str] = mapped_column(
        VARCHAR(200), nullable=False, comment="用例标题"
    )
    module_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("tb_project_module.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属模块ID",
    )
    requirement_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("func_test_requirement.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联需求ID",
    )
    priority: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=CasePriority.MEDIUM.value,
        comment="优先级",
    )
    case_type: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=CaseType.FUNCTIONAL.value,
        comment="用例类型",
    )
    validation_level: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=ValidationLevel.SYSTEM.value,
        comment="验证层级",
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(30),
        nullable=False,
        default=CaseStatus.DRAFT.value,
        index=True,
        comment="状态",
    )
    preconditions: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="前置条件（文本或 JSON 字符串）"
    )
    test_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="测试数据（JSON 对象）"
    )
    steps: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="测试步骤列表"
    )
    expected_result: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="预期结果列表"
    )
    tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="标签"
    )
    ui_automatable: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=(
            "是否适合 Web UI 自动化：true=适合，false=不适合（本质是接口/后端层校验、"
            "页面上无对应操作路径），null=未评估。生成期由 AI 初判，评审期定判（更可靠）；"
            "下游转 Web 自动化脚本据此把关"
        ),
    )
    review_info: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="AI 评审结果：{review_result, review_decs}",
    )
    review_comment: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True, comment="人工评审意见"
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="评审人ID",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="评审时间"
    )
    source: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=CaseSource.MANUAL.value,
        index=True,
        comment="来源：manual/ai_generated",
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="创建人ID",
    )
    updated_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="最后更新人ID",
    )

    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    module: Mapped["ProjectModule | None"] = relationship(
        "ProjectModule", foreign_keys=[module_id], lazy="select"
    )
    requirement: Mapped["TestRequirement | None"] = relationship(
        "TestRequirement",
        foreign_keys=[requirement_id],
        back_populates="test_cases",
        lazy="select",
    )
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="select"
    )
    updater: Mapped["User | None"] = relationship(
        "User", foreign_keys=[updated_by], lazy="select"
    )
    executions: Mapped[list["FuncCaseExecution"]] = relationship(
        "FuncCaseExecution", back_populates="test_case", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_func_case_project_code"),
        Index("idx_func_case_source", "source"),
        Index("idx_func_case_req", "requirement_id"),
    )

    def __repr__(self) -> str:
        return f"<FuncTestCase(id={self.id}, title='{self.title}', status='{self.status}')>"
