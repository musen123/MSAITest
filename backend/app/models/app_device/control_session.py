"""
APP 自动化设备控制会话审计数据模型

对应数据库表：app_control_session
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.mysql import BIGINT, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin


class AppControlKind(str, Enum):
    """设备占用类型（与 Redis 锁 value.kind 一致；observe 不占锁仅审计）"""

    CONTROL = "control"  # 远程操控（投屏）
    RECORD = "record"    # 录制
    REPLAY = "replay"    # 回放执行
    OBSERVE = "observe"  # 观战（只读观看，不占锁——P4 观战锁）


class AppControlSession(Base, IDMixin):
    """
    设备控制会话审计模型

    每次占锁控制（control-ticket 签发）落一条；结束时补 ended_at/end_reason。
    审计不依赖 Agent/用户存续，故 agent_id/owner_user_id 存裸列不建外键。
    actions_summary 只记动作计数（如 {"clipboard_inject":3,"key_events":120}），不记明文内容。
    """

    __tablename__ = "app_control_session"

    session_id: Mapped[str] = mapped_column(
        VARCHAR(64),
        nullable=False,
        unique=True,
        index=True,
        comment="控制会话ID（s-uuid，与 Redis 锁/ticket 中的 session_id 一致）",
    )
    udid: Mapped[str] = mapped_column(
        VARCHAR(160),
        nullable=False,
        index=True,
        comment="被控设备 udid",
    )
    agent_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
        comment="设备所属执行机ID（审计快照，无外键）",
    )
    owner_user_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
        index=True,
        comment="占用者用户ID（审计快照，无外键）",
    )
    kind: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default=AppControlKind.CONTROL.value,
        comment="占用类型：control/record/replay",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="会话开始时间",
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="会话结束时间",
    )
    end_reason: Mapped[str | None] = mapped_column(
        VARCHAR(32),
        nullable=True,
        comment="结束原因：released/takeover/ws_closed/ttl_expired 等",
    )
    actions_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="动作计数摘要（不含明文内容）",
    )

    def __repr__(self) -> str:
        return f"<AppControlSession(id={self.id}, session_id='{self.session_id}', udid='{self.udid}')>"
