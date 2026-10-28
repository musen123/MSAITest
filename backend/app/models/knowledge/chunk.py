"""知识库分块数据模型（自研检索的核心资产）

对应数据库表：kb_chunk

设计文档《知识库自研-总体设计方案》§4.1 ③：
  - **父子块**：child 是嵌入与召回单元（embedding 有值），parent 是上下文单元
    （embedding 为 NULL，chunk_type='parent'）。parent 行既不进向量召回也不进
    全文召回（全文查询硬带 chunk_type != 'parent'，否则父子超集/子集双重命中）
  - **embedding LONGBLOB** = float32 little-endian packed（len = kb.embed_dim × 4），
    numpy frombuffer 零拷贝反序列化。MySQL 只做字节仓库，相似度在应用层 numpy 算
  - **FULLTEXT ngram 索引**建在 (heading_path, content) 复合列上 —— 不在模型里声明，
    由 alembic 迁移 op.execute 手写 DDL（autogenerate 生成不了 WITH PARSER ngram）
  - 被嵌入/被索引文本 = heading_path + "\\n" + content 拼接（脱离章节即无意义的块
    靠上下文头找回召回质量，评审吸收 §3#7）
  - 删除策略：物理删除（随文档删除/重入库同事务 DELETE），原文可从 content_md 重建
"""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGBLOB, MEDIUMTEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.knowledge.document import KbDocument


class KbChunkType(str, Enum):
    """分块类型（契约冻结：text/table/code/case/parent）"""

    TEXT = "text"  # 普通文本 child 块
    TABLE = "table"  # 表格原子块（整表或按行组切、每片重复表头）
    CODE = "code"  # 代码原子块
    CASE = "case"  # 用例原子块（P1a test_case 分块 profile）
    PARENT = "parent"  # 父块（上下文单元，不参与召回，embedding 为 NULL）


class KbChunk(Base, IDMixin, TimestampMixin):
    """知识库分块"""

    __tablename__ = "kb_chunk"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
        comment="项目ID（冗余硬隔离列，一切查询第一过滤条件；归属校验铁律）",
    )
    document_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("kb_document.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档ID",
    )
    seq: Mapped[int] = mapped_column(
        INTEGER, nullable=False, comment="文档内序号（parent/child 统一编号，相邻性用于区间去重）"
    )
    parent_chunk_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
        comment="父块ID（child 指向 parent；parent 行为 NULL。无 FK：同文档整批删插，应用层维护）",
    )
    chunk_type: Mapped[str] = mapped_column(
        VARCHAR(10),
        nullable=False,
        default=KbChunkType.TEXT.value,
        comment="类型：text/table/code/case/parent",
    )
    heading_path: Mapped[str] = mapped_column(
        VARCHAR(768),
        nullable=False,
        default="",
        comment="标题面包屑（如「3 退款 › 3.2 退款时效」，引用溯源载体，与 content 同入全文索引）",
    )
    content: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="分块正文（全文索引列；重嵌入的数据源）"
    )
    char_len: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="字符数"
    )
    token_len: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="token 数（上下文扩展 8000 封顶的计量）"
    )
    content_hash: Mapped[str] = mapped_column(
        VARCHAR(64), nullable=False, default="", comment="content 的 SHA256（P1 图谱抽取缓存键）"
    )
    embedding: Mapped[bytes | None] = mapped_column(
        LONGBLOB,
        nullable=True,
        comment="float32 LE packed 向量（len=embed_dim×4，numpy frombuffer 读；parent 为 NULL）",
    )

    document: Mapped["KbDocument"] = relationship(
        "KbDocument", foreign_keys=[document_id], lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "seq", name="uq_kb_chunk_doc_seq"),
        Index("idx_kb_chunk_project", "project_id"),
        Index("idx_kb_chunk_project_doc", "project_id", "document_id"),
        # FULLTEXT INDEX ft_kb_chunk_content (heading_path, content) WITH PARSER ngram
        # —— 见 alembic 迁移手写 DDL，SQLAlchemy 模型层不声明（autogenerate 不支持）
    )

    def __repr__(self) -> str:
        return f"<KbChunk(id={self.id}, document_id={self.document_id}, seq={self.seq}, type='{self.chunk_type}')>"
