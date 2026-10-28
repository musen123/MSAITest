"""测试文件资产数据模型

对应数据库表：test_file_asset

测试数据中心的"文件"数据源：AI 造数/手动上传的测试文件（合同 PDF、导入模板
xlsx、图片等），落平台存储得 storage_key。Web 脚本 upload 步骤通过
``${{file:资产名}}`` 引用（渲染期解析为 storage_key），根治"用例编造本地
文件路径、执行时取不到"的断裂。

``name`` 是项目内引用键（file:名），服务层保证未删除记录内唯一
（不加 DB 唯一约束——软删后重名再建是合法诉求）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class TestFileAsset(Base, IDMixin, TimestampMixin):
    """测试文件资产：平台存储中的可引用测试文件。"""

    __tablename__ = "test_file_asset"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="资产名（项目内引用键 file:名）"
    )
    file_name: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="文件名（含扩展名）"
    )
    storage_key: Mapped[str] = mapped_column(
        VARCHAR(500), nullable=False, comment="平台存储键（本地/COS）"
    )
    mime: Mapped[str | None] = mapped_column(
        VARCHAR(100), nullable=True, comment="MIME 类型"
    )
    size_bytes: Mapped[int | None] = mapped_column(
        BIGINT, nullable=True, comment="文件大小（字节）"
    )
    source: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="manual",
        server_default="manual",
        comment="来源：manual/ai",
    )
    spec: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="造数意图/文件内容说明（AI 生成时记录规格）"
    )
    # 回溯 AI 生成任务;SET NULL:删 ai_task 不连带删资产
    ai_task_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("ai_task.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="AI 生成任务ID",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="创建人ID",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, comment="删除时间(软删)"
    )

    def __repr__(self) -> str:
        return (
            f"<TestFileAsset(id={self.id}, name='{self.name}', "
            f"file='{self.file_name}', source='{self.source}')>"
        )
