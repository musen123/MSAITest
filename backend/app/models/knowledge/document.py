"""知识库文档元数据数据模型

对应数据库表：kb_document

自研版（设计文档《知识库自研-总体设计方案》§4.1 ②）：
  - doc_type 类型体系是「软件研发知识库」的锚点（类型化检索过滤 / 分块 profile / 图谱抽取开关）
  - storage_key：新流程**必填**（应用层校验），原件先落 COS/本地再入库 —— 可重建性根基。
    列保持可空是因为存量 LightRAG 时代行全为 NULL（原件从未落盘），直接 NOT NULL 迁移必失败
  - content_md：解析产物 Markdown（重分块/重嵌入的数据源，不再重复解析）
  - 状态机由统一 AI 任务事件驱动（ai_task_id），不再轮询 LightRAG track_status
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.project.project import Project


class KbDocumentStatus(str, Enum):
    """文档状态（契约冻结：pending/parsing/chunking/embedding/ready/failed/deleted）

    分阶段状态让失败可定位到环节（评审吸收：容错粒度从「整任务失败」降到「单环节可见」）。
    """

    PENDING = "pending"  # 已建行/已提交任务，等待执行
    PARSING = "parsing"  # 解析中（提取文本/表格/VLM）
    CHUNKING = "chunking"  # 分块中
    EMBEDDING = "embedding"  # 向量化中
    READY = "ready"  # 可检索
    FAILED = "failed"  # 失败（error_message 有值，可重试）
    DELETED = "deleted"  # 软删


class KbDocType(str, Enum):
    """文档类型（契约冻结，10 类图谱词表/分块 profile/检索过滤共用此锚点）"""

    REQUIREMENT = "requirement"  # 需求文档/PRD
    API_DOC = "api_doc"  # 接口文档
    DESIGN = "design"  # 设计文档
    TEST_CASE = "test_case"  # 测试用例
    BUG_REVIEW = "bug_review"  # 缺陷复盘
    MEETING = "meeting"  # 会议纪要
    OTHER = "other"  # 其他


class KbDocSourceType(str, Enum):
    """文档来源（契约冻结）"""

    UPLOAD = "upload"  # 知识库页直传文件
    TEXT = "text"  # 纯文本直插
    FUNC_DOC = "func_doc"  # 功能测试文档桥接（source_id=func_project_document.id）
    ENTITY = "entity"  # P2 预留：平台结构化实体反向入库


class KbDocValidity(str, Enum):
    """文档生效性（P0 建列缺省 effective；P1a 才有显式替换/废弃操作）"""

    EFFECTIVE = "effective"  # 生效（参与召回）
    DEPRECATED = "deprecated"  # 已废弃（chunk 同事务物理删除，不参与召回）


class KbParseMode(str, Enum):
    """解析模式（引用溯源的忠实性标注，评审吸收）"""

    RAW = "raw"  # 确定性提取（md/txt 直读、docx 段落+表格、pdf 纯抽取）
    LLM_NORMALIZED = "llm_normalized"  # 经 LLM 规整（PDF 版面混乱/图片 VLM），内容为改写产物


class KbDocument(Base, IDMixin, TimestampMixin):
    """知识库文档"""

    __tablename__ = "kb_document"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    file_name: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="原始文件名"
    )
    file_size: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, comment="文件大小（字节）"
    )
    file_ext: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="", comment="文件扩展名"
    )
    doc_type: Mapped[str] = mapped_column(
        VARCHAR(30),
        nullable=False,
        default=KbDocType.OTHER.value,
        comment="文档类型：requirement/api_doc/design/test_case/bug_review/meeting/other",
    )
    source_type: Mapped[str] = mapped_column(
        VARCHAR(30),
        nullable=False,
        default=KbDocSourceType.UPLOAD.value,
        comment="来源：upload/text/func_doc/entity",
    )
    source_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="来源实体ID（func_doc→func_project_document.id；upload/text 为 NULL）",
    )
    storage_key: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="原件存储路径（本地/COS）。新流程应用层必填；存量 LightRAG 行恒 NULL 故列可空",
    )
    content_md: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="解析产物 Markdown（重分块/重嵌入数据源；func_doc 源直取 parsed_content 时也回填）",
    )
    content_hash: Mapped[str | None] = mapped_column(
        VARCHAR(64), nullable=True, comment="content_md 的 SHA256（幂等/去重键）"
    )
    version: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=1, comment="版本号（P1a 显式替换上传时 +1）"
    )
    validity: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=KbDocValidity.EFFECTIVE.value,
        comment="生效性：effective/deprecated（deprecated 的 chunk 已物理删除）",
    )
    parse_mode: Mapped[str | None] = mapped_column(
        VARCHAR(20),
        nullable=True,
        comment="解析模式：raw=确定性提取 / llm_normalized=LLM 规整（引用忠实性标注）",
    )
    truncated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="解析是否发生截断（用户可见,不静默丢内容）"
    )
    chunk_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="分块数（index 节点回写）"
    )
    ai_task_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
        index=True,
        comment="最近一次入库任务ID（统一壳执行，前端跳任务详情/SSE；无 FK：ai_task 生命周期独立）",
    )

    # —— 图谱抽取（P1b，与文档主 status 完全独立——失败隔离铁律） ——
    graph_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="none",
        comment="图谱抽取状态：none/pending/extracting/extracted/failed/skipped（独立于主 status）",
    )
    graph_task_id: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, comment="最近一次图谱抽取任务ID（无 FK）"
    )
    graph_source_hash: Mapped[str | None] = mapped_column(
        VARCHAR(64),
        nullable=True,
        comment="最近一次成功抽取时的 sha256(content_md)（增量短路键：hash 未变跳过重抽）",
    )
    entity_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="本文档贡献实体数（finalize 回写）"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=KbDocumentStatus.PENDING.value,
        index=True,
        comment="状态：pending/parsing/chunking/embedding/ready/failed/deleted（任务事件驱动）",
    )
    error_message: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="错误信息"
    )
    uploaded_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="上传人ID",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次入库完成时间"
    )

    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    uploader: Mapped["User"] = relationship(
        "User", foreign_keys=[uploaded_by], lazy="select"
    )

    __table_args__ = (
        Index("idx_kb_doc_project_status", "project_id", "status"),
        Index("idx_kb_doc_project_type", "project_id", "doc_type"),
        Index("idx_kb_doc_project_hash", "project_id", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<KbDocument(id={self.id}, file_name='{self.file_name}', status='{self.status}')>"
