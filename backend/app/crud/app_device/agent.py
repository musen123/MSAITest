"""AppAgent CRUD 操作"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_device.agent import AppAgent


class CRUDAppAgent:
    """执行机 CRUD"""

    async def get(self, db: AsyncSession, agent_id: int) -> Optional[AppAgent]:
        return await db.get(AppAgent, agent_id)

    async def get_by_token_hash(
        self, db: AsyncSession, token_hash: str
    ) -> Optional[AppAgent]:
        """按 token sha256 取（网关握手鉴权用）。"""
        stmt = select(AppAgent).where(AppAgent.token_hash == token_hash)
        return (await db.execute(stmt)).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AppAgent], int]:
        cond = []
        if keyword:
            cond.append(AppAgent.name.like(f"%{keyword}%"))
        stmt = (
            select(AppAgent)
            .where(*cond)
            .order_by(AppAgent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(AppAgent).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def create(self, db: AsyncSession, *, values: dict) -> AppAgent:
        obj = AppAgent(**values)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def rotate_token(
        self, db: AsyncSession, *, db_obj: AppAgent, token_hash: str
    ) -> AppAgent:
        """换 token：更新 hash，版本 +1（旧 token 立即失效）。"""
        db_obj.token_hash = token_hash
        db_obj.token_version = (db_obj.token_version or 0) + 1
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_on_register(
        self,
        db: AsyncSession,
        *,
        db_obj: AppAgent,
        agent_version: Optional[str] = None,
        capabilities: Optional[list] = None,
        protocol_version: Optional[int] = None,
        host_fingerprint: Optional[str] = None,
    ) -> AppAgent:
        """register 帧落库：版本/能力快照 + 首连绑定指纹（已有指纹不覆盖）。"""
        if agent_version is not None:
            db_obj.agent_version = agent_version
        if capabilities is not None:
            db_obj.capabilities = capabilities
        if protocol_version is not None:
            db_obj.protocol_version = protocol_version
        if host_fingerprint and not db_obj.host_fingerprint:
            db_obj.host_fingerprint = host_fingerprint
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def touch_heartbeat(
        self, db: AsyncSession, *, agent_id: int, ts: Optional[datetime] = None
    ) -> None:
        """刷新最近心跳时间。"""
        obj = await db.get(AppAgent, agent_id)
        if obj is None:
            return
        obj.last_heartbeat_at = ts or datetime.utcnow()
        db.add(obj)
        await db.commit()


crud_app_agent = CRUDAppAgent()
