"""知识图谱数据模型（P1b，设计文档《知识库自研-总体设计方案》§4.2 四表）

对应数据库表：kb_entity / kb_relation / kb_entity_mention / kb_relation_mention

核心语义（冻结，实现不再讨论）：
  - **canonical 键 = uq(project_id, name_norm)，不含 type**——GraphView 以 name 作
    节点 id，同名双节点在前端会错误折叠；name_norm = NFKC + lower + strip
  - **三大守护位**：human_edited（置位后自动抽取只增 mention 不覆写 name/type/
    description）、is_deleted（软删墓碑，自动抽取遇同 name_norm 墓碑跳过防复活）、
    merged_into_id（合并重定向，后续抽取命中旧名沿指针落到胜者）
  - **ref_count 唯一事实源 = mention 台账**，任何时刻可 COUNT(*) 重算不怕漂移；
    created_by 非空（手工创建）永不 GC
  - 实体 entity_type 是**受控 10 类词表**（KbEntityType），列仍用 VARCHAR 存值
    （词表演进不动 DDL），准入在抽取/维护 service 层校验
  - mention.chunk_id 无 FK（chunk 随重入库整批物理删插，应用层维护，同
    kb_chunk.parent_chunk_id 先例）；0 = 文档级出处（无法定位到具体块）
"""

from enum import Enum

from sqlalchemy import Boolean, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class KbEntityType(str, Enum):
    """受控实体类型词表（软件研发定制，10 类封顶；关系为开放 keywords 不受控）"""

    SYSTEM = "system"  # 系统/服务
    MODULE = "module"  # 模块/组件
    API = "api"  # 接口
    PAGE = "page"  # 页面/界面
    ROLE = "role"  # 角色/用户类型
    BUSINESS_RULE = "business_rule"  # 业务规则
    DATA_OBJECT = "data_object"  # 数据对象/表
    CONFIG = "config"  # 配置项/参数
    TERM = "term"  # 领域术语（兜底类）
    METRIC = "metric"  # 指标/阈值


class KbGraphStatus(str, Enum):
    """文档图谱抽取状态（与文档主 status 完全独立——失败隔离铁律）"""

    NONE = "none"  # 未抽取（回灌/历史文档默认）
    PENDING = "pending"  # 已派发待执行
    EXTRACTING = "extracting"  # 抽取中
    EXTRACTED = "extracted"  # 已抽取（部分批失败仍算 extracted）
    FAILED = "failed"  # 抽取失败（文档检索不受影响）
    SKIPPED = "skipped"  # 主动跳过（hash 未变短路 / doc_type 不在白名单）


class KbEntity(Base, IDMixin, TimestampMixin):
    """图谱实体（canonical 行）"""

    __tablename__ = "kb_entity"

    project_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="项目ID（硬隔离列，一切查询第一过滤条件）"
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="展示名（GraphView 节点 id）"
    )
    name_norm: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="归一化合并键（NFKC+lower+strip）"
    )
    entity_type: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        default=KbEntityType.TERM.value,
        comment="实体类型（受控 10 类词表，service 层准入）",
    )
    description: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="描述（多来源合并，≤2000 字）"
    )
    ref_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="引用计数（唯一事实源=mention 台账，可重算）"
    )
    doc_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="出现文档数（台账 DISTINCT document_id 重算）"
    )
    human_edited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="手工编辑保护位：置位后自动抽取只增 mention/计数，不覆写 name/type/description",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="软删墓碑：手工删除留行，自动抽取遇同 name_norm 墓碑跳过（防复活）",
    )
    merged_into_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="合并重定向：被合并者留墓碑指向胜者（无 FK，应用层维护，禁环）",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="非空=手工创建（ref_count=0 也永不 GC）",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name_norm", name="uq_kb_entity_project_name"),
        Index("idx_kb_entity_project_type", "project_id", "entity_type"),
        # 热门标签查询序（ORDER BY ref_count DESC 走 Backward Index Scan，无需 DESC 索引）
        Index("idx_kb_entity_project_hot", "project_id", "is_deleted", "ref_count"),
    )

    def __repr__(self) -> str:
        return f"<KbEntity(id={self.id}, project_id={self.project_id}, name='{self.name}')>"


class KbRelation(Base, IDMixin, TimestampMixin):
    """图谱关系（有向边；keywords 开放非受控）"""

    __tablename__ = "kb_relation"

    project_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="项目ID（硬隔离列）"
    )
    source_entity_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_entity.id", ondelete="CASCADE"),
        nullable=False,
        comment="源实体ID",
    )
    target_entity_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_entity.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标实体ID",
    )
    keywords: Mapped[str] = mapped_column(
        VARCHAR(200), nullable=False, default="", comment="关系关键词（开放词，展示为边标签）"
    )
    description: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="关系描述"
    )
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, comment="权重（重复抽取递增，前端映射边宽）"
    )
    ref_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="引用计数（台账重算）"
    )
    human_edited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="手工编辑保护位（同实体语义）"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="软删墓碑（防自动抽取复活）"
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="非空=手工创建，永不 GC",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_entity_id", "target_entity_id", name="uq_kb_relation_pair"
        ),
        Index("idx_kb_relation_project", "project_id"),
        Index("idx_kb_relation_source", "source_entity_id"),
        Index("idx_kb_relation_target", "target_entity_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<KbRelation(id={self.id}, {self.source_entity_id}->{self.target_entity_id})>"
        )


class KbEntityMention(Base, IDMixin, TimestampMixin):
    """实体出处台账（引用计数与溯源的唯一事实源）"""

    __tablename__ = "kb_entity_mention"

    project_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="项目ID（硬隔离列）"
    )
    entity_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_entity.id", ondelete="CASCADE"),
        nullable=False,
        comment="实体ID",
    )
    document_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_document.id", ondelete="CASCADE"),
        nullable=False,
        comment="来源文档ID（文档删除/重入库按此列一把清）",
    )
    chunk_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
        default=0,
        comment="来源分块ID（无 FK 应用层维护；0=文档级出处）",
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_id", "document_id", "chunk_id", name="uq_kb_entity_mention"
        ),
        Index("idx_kb_entity_mention_doc", "document_id"),
        Index("idx_kb_entity_mention_project", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<KbEntityMention(entity={self.entity_id}, doc={self.document_id})>"


class KbRelationMention(Base, IDMixin, TimestampMixin):
    """关系出处台账"""

    __tablename__ = "kb_relation_mention"

    project_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="项目ID（硬隔离列）"
    )
    relation_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_relation.id", ondelete="CASCADE"),
        nullable=False,
        comment="关系ID",
    )
    document_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_document.id", ondelete="CASCADE"),
        nullable=False,
        comment="来源文档ID",
    )
    chunk_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, comment="来源分块ID（无 FK；0=文档级出处）"
    )

    __table_args__ = (
        UniqueConstraint(
            "relation_id", "document_id", "chunk_id", name="uq_kb_relation_mention"
        ),
        Index("idx_kb_relation_mention_doc", "document_id"),
        Index("idx_kb_relation_mention_project", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<KbRelationMention(relation={self.relation_id}, doc={self.document_id})>"
