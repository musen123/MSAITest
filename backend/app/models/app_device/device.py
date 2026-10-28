"""
APP 自动化设备（Android 真机/模拟器）数据模型

对应数据库表：app_device
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class AppDeviceSource(str, Enum):
    """设备接入来源"""

    LOCAL_ADB = "local_adb"    # Agent 本机 adb 发现
    REMOTE_ADB = "remote_adb"  # adb connect 远程接入


class AppDeviceConnection(str, Enum):
    """设备连接方式"""

    USB = "usb"
    TCPIP = "tcpip"


class AppDevice(Base, IDMixin, TimestampMixin):
    """
    Android 设备模型

    由 Agent 心跳/设备事件 upsert 维护；udid = "{agent_id}:{serial}" 全局唯一。
    占用信息不落列，实时读 Redis 设备锁；online 由所属 Agent 心跳 + state 现算。
    """

    __tablename__ = "app_device"

    agent_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("app_agent.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属执行机ID",
    )
    serial: Mapped[str] = mapped_column(
        VARCHAR(128),
        nullable=False,
        comment="adb 设备序列号",
    )
    udid: Mapped[str] = mapped_column(
        VARCHAR(160),
        nullable=False,
        unique=True,
        index=True,
        comment="平台级设备唯一标识：{agent_id}:{serial}",
    )
    model: Mapped[str | None] = mapped_column(
        VARCHAR(64),
        nullable=True,
        comment="设备型号，如 Pixel 6",
    )
    brand: Mapped[str | None] = mapped_column(
        VARCHAR(64),
        nullable=True,
        comment="品牌",
    )
    android_version: Mapped[str | None] = mapped_column(
        VARCHAR(32),
        nullable=True,
        comment="系统版本（android=Android 版本；harmony=HarmonyOS 版本，字段名历史遗留）",
    )
    platform: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default="android",
        server_default="android",
        comment="设备平台：android（adb）/ harmony（鸿蒙 NEXT hdc）",
    )
    resolution: Mapped[str | None] = mapped_column(
        VARCHAR(32),
        nullable=True,
        comment="分辨率，如 1080x2400",
    )
    source: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default=AppDeviceSource.LOCAL_ADB.value,
        comment="接入来源：local_adb/remote_adb",
    )
    connection: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default=AppDeviceConnection.USB.value,
        comment="连接方式：usb/tcpip",
    )
    state: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default="offline",
        comment="adb 原始状态：device/offline/unauthorized",
    )
    project_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="归属项目ID（可选，未分配则平台级共享）",
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="最近一次在 Agent 心跳/事件中出现的时间",
    )

    def __repr__(self) -> str:
        return f"<AppDevice(id={self.id}, udid='{self.udid}', state='{self.state}')>"
