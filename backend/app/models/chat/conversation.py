"""智能体对话数据模型

对应数据库表：
  - chat_conversation     对话会话
  - chat_message          消息（user/assistant/system）
"""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, JSON, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.user import User
    from app.models.project.project import Project


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base, IDMixin, TimestampMixin):
    """对话会话"""

    __tablename__ = "chat_conversation"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    title: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, default="新对话", comment="对话标题"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=ConversationStatus.ACTIVE.value,
        index=True,
        comment="状态：active/completed/archived",
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
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="select"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("idx_chat_conv_project_status", "project_id", "status"),
    )


class Message(Base, IDMixin, TimestampMixin):
    """对话消息"""

    __tablename__ = "chat_message"

    conversation_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("chat_conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="会话ID",
    )
    role: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        comment="角色：user/assistant/system",
    )
    content: Mapped[str] = mapped_column(
        TEXT, nullable=False, default="", comment="消息文本内容"
    )
    tool_calls: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="工具调用记录列表（runId/toolName/toolInput/toolOutput/status/...）",
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
