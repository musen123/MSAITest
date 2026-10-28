"""APP 自动化设备域 Service

- lock：Redis 设备锁（网关只读复用）
- ticket：投屏控制 WS 一次性 ticket
- service：Agent token / 心跳对账 / 在线判定
"""

from app.services.app_device.lock import DeviceLock, device_lock
from app.services.app_device.ticket import consume_ticket, issue_ticket

__all__ = [
    "DeviceLock",
    "device_lock",
    "issue_ticket",
    "consume_ticket",
]
