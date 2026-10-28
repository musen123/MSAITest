"""项目知识库元信息数据模型

对应数据库表：kb_project_knowledge_base

每个项目对应一个知识库实例（uq_kb_project 唯一约束）。
自研版（设计文档《知识库自研-总体设计方案》§4.1）：
  - embedding 配置**库级钉定**（embed_* 五字段 + 探针钉维），检索/入库一律用库配置，
    换模型 = 显式全量重建 —— 解决「配置是用户级、库是项目级」的一致性矛盾
  - index_version 是检索向量缓存的失效键，一切 chunk 写路径必须经
    crud 层 bump_index_version 单点函数递增（含计数原子增量）
  - total_* 统计口径 = 本项目真实计数（修正 LightRAG 时代全局求和错账）
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.project.project import Project


class KnowledgeBaseStatus(str, Enum):
    """知识库状态（契约冻结：empty/ready/rebuilding/error）"""

    EMPTY = "empty"  # 尚无已就绪文档
    READY = "ready"  # 正常可用
    REBUILDING = "rebuilding"  # 全量重建中（换 embed 模型/分块策略）
    ERROR = "error"  # 异常


class KbEmbedStatus(str, Enum):
    """库级 embed 配置状态（仅绑定后有意义）"""

    ACTIVE = "active"  # 配置可用
    INVALID = "invalid"  # 来源配置被删/停用/维度不符，需 rebind 或重建


class ProjectKnowledgeBase(Base, IDMixin, TimestampMixin):
    """项目级知识库"""

    __tablename__ = "kb_project_knowledge_base"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=KnowledgeBaseStatus.EMPTY.value,
        index=True,
        comment="状态：empty/ready/rebuilding/error",
    )

    # —— embedding 库级钉定（设计文档 §3#5：首次入库快照提交者 EMBED 配置） ——
    embed_provider: Mapped[str | None] = mapped_column(
        VARCHAR(50), nullable=True, comment="钉定 embed 提供方（openai 兼容）"
    )
    embed_model: Mapped[str | None] = mapped_column(
        VARCHAR(200), nullable=True, comment="钉定 embed 模型名（换模型=全量重建）"
    )
    embed_base_url: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True, comment="钉定 embed base_url"
    )
    embed_dim: Mapped[int | None] = mapped_column(
        INTEGER, nullable=True, comment="向量维度（首绑探针实测钉死，每批断言）"
    )
    embed_bound_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="钉定来源用户（api_key 实时从其 UserLlmConfig 读，轮换 key 免重建）",
    )
    embed_bound_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="钉定时间"
    )
    embed_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=KbEmbedStatus.ACTIVE.value,
        comment="embed 配置状态：active/invalid（invalid=来源配置失效，检索降级纯全文）",
    )

    index_version: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="索引版本（chunk 任何写路径 +1，检索向量缓存失效键）",
    )
    settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="库级参数（分块/检索开关等，缺省用全局常量）"
    )
    graph_doc_types: Mapped[str] = mapped_column(
        VARCHAR(200),
        nullable=False,
        default="requirement,design,api_doc",
        comment="图谱自动抽取 doc_type 白名单（逗号分隔；入库完成后按此派发 kb_extract）",
    )

    total_documents: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="文档总数（本项目真实口径）"
    )
    total_chunks: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="chunk 总数（本项目真实口径，SQL 原子增量维护）"
    )
    total_nodes: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="知识图谱实体数（P1b kb_extract 维护，本项目口径）"
    )
    total_edges: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="知识图谱关系数（P1b kb_extract 维护，本项目口径）"
    )
    project_summary: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="项目概要（AI 提炼）"
    )
    error_message: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="错误信息"
    )
    last_built_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次构建时间"
    )

    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_kb_project"),
    )

    def __repr__(self) -> str:
        return f"<ProjectKnowledgeBase(id={self.id}, project_id={self.project_id}, status='{self.status}')>"
