"""AppControlSession（控制会话审计）CRUD 操作"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_device.control_session import AppControlSession


class CRUDAppControlSession:
    """控制会话审计 CRUD"""

    async def get_by_session_id(
        self, db: AsyncSession, session_id: str
    ) -> Optional[AppControlSession]:
        stmt = select(AppControlSession).where(AppControlSession.session_id == session_id)
        return (await db.execute(stmt)).scalars().first()

    async def create(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        udid: str,
        agent_id: int,
        owner_user_id: int,
        kind: str,
    ) -> AppControlSession:
        obj = AppControlSession(
            session_id=session_id,
            udid=udid,
            agent_id=agent_id,
            owner_user_id=owner_user_id,
            kind=kind,
            started_at=datetime.utcnow(),
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def end(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        end_reason: str,
        actions_summary: Optional[dict] = None,
    ) -> Optional[AppControlSession]:
        """结束会话（幂等：已结束的不覆盖首个 end_reason）。"""
        obj = await self.get_by_session_id(db, session_id)
        if obj is None or obj.ended_at is not None:
            return obj
        obj.ended_at = datetime.utcnow()
        obj.end_reason = end_reason
        if actions_summary is not None:
            obj.actions_summary = actions_summary
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj


crud_app_control_session = CRUDAppControlSession()
