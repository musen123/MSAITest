"""定时计划 CRUD"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduler.scheduled_job import ScheduledJob, ScheduledJobRun


class CRUDScheduledJob:

    async def get(
        self, db: AsyncSession, job_id: int
    ) -> Optional[ScheduledJob]:
        job = await db.get(ScheduledJob, job_id)
        if job is None or job.is_deleted:
            return None
        return job

    async def list_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        enabled: Optional[bool] = None,
        job_type: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ScheduledJob], int]:
        cond = [
            ScheduledJob.project_id == project_id,
            ScheduledJob.is_deleted.is_(False),
        ]
        if enabled is not None:
            cond.append(ScheduledJob.enabled.is_(enabled))
        if job_type:
            cond.append(ScheduledJob.job_type == job_type)
        if keyword:
            cond.append(ScheduledJob.name.like(f"%{keyword}%"))

        stmt = (
            select(ScheduledJob)
            .where(*cond)
            .order_by(ScheduledJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count()).select_from(ScheduledJob).where(*cond)
        )
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def list_due(
        self, db: AsyncSession, *, now: datetime, limit: int = 50
    ) -> list[ScheduledJob]:
        """到期待派发的计划（跨项目，dispatch 巡检用）"""
        stmt = (
            select(ScheduledJob)
            .where(
                ScheduledJob.enabled.is_(True),
                ScheduledJob.is_deleted.is_(False),
                ScheduledJob.next_run_at.is_not(None),
                ScheduledJob.next_run_at <= now,
            )
            .order_by(ScheduledJob.next_run_at.asc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def claim(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        expected_next: datetime,
        new_next: Optional[datetime],
    ) -> bool:
        """原子抢占：仅当 next_run_at 未被他人推进时才更新（防重复派发）"""
        result = await db.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.id == job_id,
                ScheduledJob.next_run_at == expected_next,
            )
            .values(next_run_at=new_next)
        )
        await db.commit()
        return bool(result.rowcount)

    async def update_fields(
        self, db: AsyncSession, *, job: ScheduledJob, **kwargs: Any
    ) -> ScheduledJob:
        for k, v in kwargs.items():
            setattr(job, k, v)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def mark_fired(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        fired_at: datetime,
        status: str,
        ai_task_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> None:
        """记录一次派发结果：更新摘要 + 写流水"""
        values: dict[str, Any] = {
            "last_run_at": fired_at,
            "last_status": status,
        }
        if ai_task_id is not None:
            values["last_task_id"] = ai_task_id
        if status == "dispatched":
            values["total_runs"] = ScheduledJob.total_runs + 1
        await db.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == job_id)
            .values(**values)
        )
        db.add(
            ScheduledJobRun(
                job_id=job_id,
                ai_task_id=ai_task_id,
                fired_at=fired_at,
                status=status,
                note=note,
            )
        )
        await db.commit()

    async def list_runs(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ScheduledJobRun], int]:
        stmt = (
            select(ScheduledJobRun)
            .where(ScheduledJobRun.job_id == job_id)
            .order_by(ScheduledJobRun.id.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(ScheduledJobRun)
            .where(ScheduledJobRun.job_id == job_id)
        )
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def soft_delete(
        self, db: AsyncSession, *, job: ScheduledJob
    ) -> None:
        job.is_deleted = True
        job.deleted_at = datetime.utcnow()
        job.enabled = False
        db.add(job)
        await db.commit()


crud_scheduled_job = CRUDScheduledJob()
