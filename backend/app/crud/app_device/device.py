"""AppDevice CRUD 操作"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_device.device import AppDevice

# 心跳 DeviceInfo → 模型列的直通字段
_INFO_FIELDS = ("model", "brand", "android_version", "resolution", "connection", "state", "platform")


def build_udid(agent_id: int, serial: str) -> str:
    """平台级设备唯一标识：{agent_id}:{serial}（契约 §7）。"""
    return f"{agent_id}:{serial}"


class CRUDAppDevice:
    """设备 CRUD"""

    async def get_by_udid(self, db: AsyncSession, udid: str) -> Optional[AppDevice]:
        stmt = select(AppDevice).where(AppDevice.udid == udid)
        return (await db.execute(stmt)).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        *,
        agent_id: Optional[int] = None,
        project_id: Optional[int] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AppDevice], int]:
        cond = []
        if agent_id is not None:
            cond.append(AppDevice.agent_id == agent_id)
        if project_id is not None:
            cond.append(AppDevice.project_id == project_id)
        if keyword:
            cond.append(
                AppDevice.udid.like(f"%{keyword}%")
                | AppDevice.model.like(f"%{keyword}%")
                | AppDevice.brand.like(f"%{keyword}%")
            )
        stmt = (
            select(AppDevice)
            .where(*cond)
            .order_by(AppDevice.last_seen_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(AppDevice).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def upsert(
        self,
        db: AsyncSession,
        *,
        agent_id: int,
        info: dict,
        ts: Optional[datetime] = None,
        commit: bool = True,
    ) -> Optional[AppDevice]:
        """按 udid upsert 一条设备信息（info = 契约 §2 DeviceInfo）。

        serial 缺失的脏数据直接丢弃；commit=False 供批量对账最后一次性提交。
        """
        serial = (info.get("serial") or "").strip()
        if not serial:
            return None
        udid = build_udid(agent_id, serial)
        obj = await self.get_by_udid(db, udid)
        if obj is None:
            obj = AppDevice(agent_id=agent_id, serial=serial, udid=udid)
        for field in _INFO_FIELDS:
            value = info.get(field)
            if value is not None:
                setattr(obj, field, value)
        obj.last_seen_at = ts or datetime.utcnow()
        db.add(obj)
        if commit:
            await db.commit()
            await db.refresh(obj)
        return obj

    async def mark_missing_offline(
        self,
        db: AsyncSession,
        *,
        agent_id: int,
        present_udids: set[str],
        commit: bool = True,
    ) -> int:
        """差集下线：该 Agent 名下不在本次心跳快照里的设备置 offline。"""
        cond = [
            AppDevice.agent_id == agent_id,
            AppDevice.state != "offline",
        ]
        if present_udids:
            cond.append(AppDevice.udid.notin_(present_udids))
        result = await db.execute(update(AppDevice).where(*cond).values(state="offline"))
        if commit:
            await db.commit()
        return result.rowcount or 0


crud_app_device = CRUDAppDevice()
