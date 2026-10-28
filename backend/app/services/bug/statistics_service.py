from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.bug.bug import Bug

async def get_bug_stats(db: AsyncSession, project_id: int) -> dict:
    """返回 Bug 统计数据，供项目模块调用"""
    rows = await db.execute(
        select(Bug.status, func.count().label("cnt"))
        .where(Bug.project_id == project_id, Bug.is_deleted == 0)
        .group_by(Bug.status)
    )
    by_status = {row.status: row.cnt for row in rows}
    total = sum(by_status.values())
    resolved = by_status.get("resolved", 0)
    closed = by_status.get("closed", 0)
    return {
        "total": total,
        "by_status": by_status,
        "resolution_rate": round((resolved + closed) / total * 100, 1) if total else 0.0,
    }
