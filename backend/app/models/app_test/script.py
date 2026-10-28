"""
APP 自动化用例（脚本）数据模型

对应数据库表：app_script（方案 §4 / 契约 §7 P2 增补）。
用例载体 = Midscene YAML tasks 段（runYaml 官方只解析 tasks），平台不发明
自己的步骤 schema；yaml_content 即回放输入，Monaco 编辑。
"""

from enum import Enum

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class AppScriptStatus(str, Enum):
    """用例状态"""

    DRAFT = "draft"        # 草稿（录制中/未启用）
    ACTIVE = "active"      # 启用（可回放）
    DISABLED = "disabled"  # 停用


class AppScript(Base, IDMixin, TimestampMixin):
    """APP 自动化用例（YAML 载体）"""

    __tablename__ = "app_script"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目ID",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(128),
        nullable=False,
        comment="用例名称",
    )
    platform: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default="android",
        comment="平台：android（预留 ios/harmony）",
    )
    target_app: Mapped[str | None] = mapped_column(
        VARCHAR(128),
        nullable=True,
        comment="目标应用包名/名称（回放前 launch 用，可空）",
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="用例描述",
    )
    yaml_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Midscene YAML（tasks 段为回放输入）",
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default=AppScriptStatus.DRAFT.value,
        comment="状态：draft/active/disabled",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人（录制者）",
    )

    def __repr__(self) -> str:
        return f"<AppScript(id={self.id}, name='{self.name}', status='{self.status}')>"
