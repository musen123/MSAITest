"""
APP 自动化执行机（宿主机 Agent）数据模型

对应数据库表：app_agent
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.mysql import INTEGER, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class AppAgent(Base, IDMixin, TimestampMixin):
    """
    宿主机 Agent 模型

    每台接入平台的宿主机（跑 adb / scrcpy 的机器）注册为一条 Agent 记录。
    token 明文仅创建/轮转响应返回一次，库中只存 sha256。
    在线状态不落库，由 last_heartbeat_at 现算（service 层在线判定函数）。
    """

    __tablename__ = "app_agent"

    name: Mapped[str] = mapped_column(
        VARCHAR(64),
        nullable=False,
        comment="执行机名称",
    )
    host_label: Mapped[str | None] = mapped_column(
        VARCHAR(128),
        nullable=True,
        comment="宿主机标签（机房/工位等备注）",
    )
    token_hash: Mapped[str] = mapped_column(
        VARCHAR(64),
        nullable=False,
        unique=True,
        index=True,
        comment="接入 token 的 sha256（hex），明文不落库",
    )
    token_version: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=1,
        comment="token 版本号，轮转 +1",
    )
    host_fingerprint: Mapped[str | None] = mapped_column(
        VARCHAR(128),
        nullable=True,
        comment="宿主机硬件指纹（首连绑定，后续不符拒连）",
    )
    agent_version: Mapped[str | None] = mapped_column(
        VARCHAR(32),
        nullable=True,
        comment="Agent 程序版本（register 帧上报）",
    )
    capabilities: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Agent 能力列表，如 ['scrcpy']",
    )
    protocol_version: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=1,
        comment="隧道控制帧协议版本",
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="最近心跳时间（在线判定依据：≤30s=online、≤60s=stale、否则 offline）",
    )

    def __repr__(self) -> str:
        return f"<AppAgent(id={self.id}, name='{self.name}')>"
