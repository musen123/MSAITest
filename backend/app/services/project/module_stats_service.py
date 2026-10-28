"""列表页全量统计

各业务列表页顶部统计卡片的统一数据源：按模块返回全项目维度的
计数（此前卡片用当前分页数据假算，翻页即失真）。

口径与 report_center_service 一致：软删三形态
（func is_deleted / api·bug deleted_at / web deleted_at），
by_status 返回数据库真实分布，组合口径（如 bug 待处理=new+assigned+reopened）
由前端按展示需要拼装。
"""

from typing import Any
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.bug.bug import Bug
from app.models.func_test.requirement import TestRequirement
from app.models.func_test.test_case import FuncTestCase

MODULES = ("func_cases", "requirements", "bugs")


async def _count(db: AsyncSession, model: Any, *conds: Any) -> int:
    return int(
        (await db.execute(select(func.count(model.id)).where(*conds))).scalar() or 0
    )


async def _by_status(db: AsyncSession, model: Any, *conds: Any) -> dict[str, int]:
    rows = (
        await db.execute(
            select(model.status, func.count(model.id))
            .where(*conds)
            .group_by(model.status)
        )
    ).all()
    return {str(r[0]): int(r[1]) for r in rows}


async def _func_cases(db: AsyncSession, project_id: int) -> dict[str, Any]:
    conds = (FuncTestCase.project_id == project_id, FuncTestCase.is_deleted.is_(False))
    by_status = await _by_status(db, FuncTestCase, *conds)
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "ai_generated": await _count(
            db, FuncTestCase, *conds, FuncTestCase.source == "ai_generated"
        ),
    }


async def _requirements(db: AsyncSession, project_id: int) -> dict[str, Any]:
    conds = (
        TestRequirement.project_id == project_id,
        TestRequirement.is_deleted.is_(False),
    )
    by_status = await _by_status(db, TestRequirement, *conds)
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "ai_generated": await _count(
            db, TestRequirement, *conds, TestRequirement.source == "ai_generated"
        ),
    }


async def _bugs(db: AsyncSession, project_id: int) -> dict[str, Any]:
    conds = (
        Bug.project_id == project_id,
        Bug.is_deleted.is_(False),
        Bug.is_archived.is_(False),
    )
    by_status = await _by_status(db, Bug, *conds)
    return {"total": sum(by_status.values()), "by_status": by_status}


_HANDLERS = {"func_cases": _func_cases, "requirements": _requirements, "bugs": _bugs}


async def get_module_stats(
    db: AsyncSession, *, project_id: int, module: str
) -> dict[str, Any]:
    handler = _HANDLERS.get(module)
    if handler is None:
        raise ValueError(f"未知统计模块: {module}")
    return await handler(db, project_id)
