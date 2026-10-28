"""项目文档数据模型

对应数据库表：func_project_document

存储项目下的需求文档、原型图、数据库字典等。
文件统一通过 app/utils/document_storage.py 写入本地或 COS。

数据流：上传 → AI 解析（parsed_*） → 导入知识库（kb_*） → 在内容管理可见。
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, LONGTEXT, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.project.project import Project


class DocumentType(str, Enum):
    """文档类型"""

    REQUIREMENT = "requirement"
    PROTOTYPE = "prototype"
    DB_DICT = "db_dict"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """文档状态"""

    ACTIVE = "active"
    DELETED = "deleted"


class DocumentParseStatus(str, Enum):
    """AI 解析状态"""

    PENDING = "pending"  # 未解析
    PARSING = "parsing"  # 正在解析
    PARSED = "parsed"  # 解析完成
    FAILED = "failed"  # 解析失败


class DocumentKbStatus(str, Enum):
    """知识库入库状态"""

    NOT_INGESTED = "not_ingested"  # 未入库
    INGESTING = "ingesting"  # 正在入库
    INGESTED = "ingested"  # 已入库
    INGEST_FAILED = "ingest_failed"  # 入库失败


class ProjectDocument(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """项目文档"""

    __tablename__ = "func_project_document"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(200), nullable=False, comment="文档名称（用户自定义）"
    )
    doc_type: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=DocumentType.OTHER.value,
        index=True,
        comment="文档类型：requirement/prototype/db_dict/other",
    )
    file_name: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="原始文件名"
    )
    file_path: Mapped[str] = mapped_column(
        VARCHAR(500), nullable=False, comment="存储路径（本地相对路径或 COS key）"
    )
    file_size: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="文件大小（字节）"
    )
    file_ext: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, comment="文件扩展名"
    )
    description: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="文档描述"
    )
    version: Mapped[str | None] = mapped_column(
        VARCHAR(50), nullable=True, comment="版本号"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=DocumentStatus.ACTIVE.value,
        index=True,
        comment="状态：active/deleted",
    )
    uploaded_by: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="上传人ID",
    )

    # ─────────── AI 解析 ───────────
    parse_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=DocumentParseStatus.PENDING.value,
        index=True,
        comment="AI 解析状态：pending/parsing/parsed/failed",
    )
    parsed_content: Mapped[Optional[str]] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="AI 解析后的 Markdown 内容（适合 LightRAG 检索）",
    )
    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后解析完成时间"
    )
    parse_error_message: Mapped[Optional[str]] = mapped_column(
        TEXT, nullable=True, comment="解析失败原因"
    )

    # ─────────── 知识库入库 ───────────
    kb_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=DocumentKbStatus.NOT_INGESTED.value,
        index=True,
        comment="知识库入库状态：not_ingested/ingesting/ingested/ingest_failed",
    )
    kb_document_id: Mapped[Optional[int]] = mapped_column(
        BIGINT,
        nullable=True,
        index=True,
        comment="自研知识库文档 ID（kb_document.id，入库桥接回写；无 FK：跨模块软引用）",
    )
    kb_ingested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后入库时间"
    )

    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], lazy="select"
    )
    uploader: Mapped["User"] = relationship(
        "User", foreign_keys=[uploaded_by], lazy="select"
    )

    __table_args__ = (Index("idx_func_doc_project_type", "project_id", "doc_type"),)

    def __repr__(self) -> str:
        return f"<ProjectDocument(id={self.id}, name='{self.name}', type='{self.doc_type}')>"
