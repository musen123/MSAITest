"""项目概览仪表盘聚合统计

一个接口喂整页：统计卡、今日执行、三模块合并执行趋势、最近执行、
缺陷状态分布、知识库状态。

口径说明：
  - 三模块用例级执行表 project_id 均冗余直存，无需 JOIN 定义表
  - api_case_execution 历史混存两套状态枚举（pass/passed 等），统计时归并
  - 通过率分母 = passed + failed（含 error），running/skipped/blocked 不计入
  - 软删过滤：func/bug 用 is_deleted，api/web 定义表用 deleted_at，
    执行记录表无软删
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai.ai_task import AiTask
from app.models.app_test.execution import AppExecution
from app.models.app_test.script import AppScript
from app.models.app_test.suite import AppSuite
from app.models.app_test.suite_execution import AppSuiteExecution
from app.models.bug.bug import Bug
from app.models.func_test.case_execution import FuncCaseExecution
from app.models.func_test.test_case import FuncTestCase
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

_EXEC_SOURCES: list[dict[str, Any]] = [
    {
        "model": FuncCaseExecution,
        "status_col": "execute_result",
        "passed": ("passed",),
        "failed": ("failed",),
        "time_col": "executed_at",
    },
    {
        "model": AppExecution,
        "status_col": "status",
        "passed": ("success",),
        "failed": ("failed",),
        "time_col": "created_at",
        "project_join": (AppScript, AppScript.id == AppExecution.script_id),
    },
]


def _scoped_select(stmt: Any, src: dict[str, Any], project_id: int) -> Any:
    """给执行表查询加项目过滤：直存 project_id 直接 where，否则经 join 定位。"""
    join = src.get("project_join")
    if join is not None:
        join_model, on_clause = join
        return stmt.join(join_model, on_clause).where(
            join_model.project_id == project_id
        )
    return stmt.where(src["model"].project_id == project_id)


_BUG_BUCKETS: dict[str, tuple[str, ...]] = {
    "pending": ("new", "reopened"),
    "processing": ("assigned", "in_progress"),
    "resolved": ("resolved", "verified"),
    "closed": ("closed",),
    "suspended": ("postponed", "wontfix"),
}
_BUG_OPEN_STATUSES = (
    "new",
    "assigned",
    "in_progress",
    "resolved",
    "verified",
    "reopened",
)


def _growth(current: int, previous: int) -> Optional[float]:
    """数量环比增长率（%）；上期为 0 时：本期有量记 +100，无量记 None"""
    if previous == 0:
        return 100.0 if current > 0 else None
    return round((current - previous) / previous * 1000) / 10


def _rate(passed: int, failed: int) -> Optional[float]:
    done = passed + failed
    if done == 0:
        return None
    return round(passed / done * 1000) / 10


async def _exec_window_agg(
    db: AsyncSession,
    project_id: int,
    start: Optional[datetime],
    end: Optional[datetime],
) -> dict[str, int]:
    """五模块执行表在 [start, end) 窗口内的 total/passed/failed 合计"""
    total = passed = failed = 0
    for src in _EXEC_SOURCES:
        model = src["model"]
        status = getattr(model, src["status_col"])
        time_col = getattr(model, src["time_col"])
        stmt = select(
            func.count(model.id),
            func.sum(sa_case((status.in_(src["passed"]), 1), else_=0)),
            func.sum(sa_case((status.in_(src["failed"]), 1), else_=0)),
        )
        stmt = _scoped_select(stmt, src, project_id)
        if start is not None:
            stmt = stmt.where(time_col >= start)
        if end is not None:
            stmt = stmt.where(time_col < end)
        row = (await db.execute(stmt)).one()
        total += int(row[0] or 0)
        passed += int(row[1] or 0)
        failed += int(row[2] or 0)
    return {"total": total, "passed": passed, "failed": failed}


async def _case_counts(db: AsyncSession, project_id: int) -> dict[str, int]:
    functional = (
        await db.execute(
            select(func.count(FuncTestCase.id)).where(
                FuncTestCase.project_id == project_id,
                FuncTestCase.is_deleted.is_(False),
            )
        )
    ).scalar() or 0
    app = (
        await db.execute(
            select(func.count(AppScript.id)).where(AppScript.project_id == project_id)
        )
    ).scalar() or 0
    return {"functional": int(functional), "app": int(app)}


async def _new_case_count(
    db: AsyncSession, project_id: int, start: datetime, end: Optional[datetime]
) -> int:
    """窗口内新增用例数（五类合计；app_script 无软删列，soft=None 不过滤）"""
    total = 0
    for model, soft in ((FuncTestCase, "is_deleted"), (AppScript, None)):
        conds = [model.project_id == project_id, model.created_at >= start]
        if end is not None:
            conds.append(model.created_at < end)
        if soft == "is_deleted":
            conds.append(model.is_deleted.is_(False))
        elif soft == "deleted_at":
            conds.append(model.deleted_at.is_(None))
        n = (await db.execute(select(func.count(model.id)).where(*conds))).scalar() or 0
        total += int(n)
    return total


async def _daily_trend(
    db: AsyncSession, project_id: int, start: datetime, days: int
) -> list[dict[str, Any]]:
    """五模块执行按日合并，补零保证长度 = days"""
    bucket: dict[str, dict[str, int]] = {}
    for src in _EXEC_SOURCES:
        model = src["model"]
        status = getattr(model, src["status_col"])
        time_col = getattr(model, src["time_col"])
        date_expr = func.date(time_col)
        stmt = select(
            date_expr,
            func.sum(sa_case((status.in_(src["passed"]), 1), else_=0)),
            func.sum(sa_case((status.in_(src["failed"]), 1), else_=0)),
        )
        stmt = _scoped_select(stmt, src, project_id)
        stmt = stmt.where(time_col >= start).group_by(date_expr)
        rows = (await db.execute(stmt)).all()
        for d, p, f in rows:
            key = d.isoformat() if hasattr(d, "isoformat") else str(d)
            item = bucket.setdefault(key, {"passed": 0, "failed": 0})
            item["passed"] += int(p or 0)
            item["failed"] += int(f or 0)
    daily: list[dict[str, Any]] = []
    day0 = start.date()
    for i in range(days):
        key = (day0 + timedelta(days=i)).isoformat()
        item = bucket.get(key, {"passed": 0, "failed": 0})
        daily.append({"date": key, **item})
    return daily


async def _recent_executions(
    db: AsyncSession, project_id: int, limit: int = 8
) -> list[dict[str, Any]]:
    """跨模块最近套件/任务级执行（直读预聚合 counts 列）"""
    items: list[dict[str, Any]] = []

    async def _collect(
        exec_model: Any,
        name_model: Any,
        ref_col: str,
        module: str,
        kind: str,
        passed_col: str,
        failed_cols: tuple[str, ...],
        total_col: str,
        time_col: str = "started_at",
    ) -> None:
        ref = getattr(exec_model, ref_col)
        rows = (
            await db.execute(
                select(exec_model, name_model.name)
                .outerjoin(name_model, name_model.id == ref)
                .where(exec_model.project_id == project_id)
                .order_by(exec_model.id.desc())
                .limit(limit)
            )
        ).all()
        for rec, name in rows:
            failed = sum((int(getattr(rec, c) or 0) for c in failed_cols))
            ts = getattr(rec, time_col, None)
            items.append(
                {
                    "module": module,
                    "kind": kind,
                    "execution_id": rec.id,
                    "ref_id": getattr(rec, ref_col),
                    "name": name or f"{kind}#{getattr(rec, ref_col)}",
                    "status": rec.status,
                    "total": int(getattr(rec, total_col) or 0),
                    "passed": int(getattr(rec, passed_col) or 0),
                    "failed": failed,
                    "started_at": ts.isoformat() if ts else None,
                }
            )

    await _collect(
        AppSuiteExecution,
        AppSuite,
        "suite_id",
        "app",
        "suite",
        "passed_count",
        ("failed_count",),
        "total_cases",
        time_col="created_at",
    )
    items.sort(key=lambda x: x["started_at"] or "", reverse=True)
    return items[:limit]


async def get_dashboard(
    db: AsyncSession, *, project_id: int, days: int = 7
) -> dict[str, Any]:
    now = datetime.utcnow()
    today = now.date()
    start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
    prev_start = start - timedelta(days=days)
    today_start = datetime.combine(today, datetime.min.time())
    case_by_type = await _case_counts(db, project_id)
    ai_generated_cases = (
        await db.execute(
            select(func.count(FuncTestCase.id)).where(
                FuncTestCase.project_id == project_id,
                FuncTestCase.is_deleted.is_(False),
                FuncTestCase.source == "ai_generated",
            )
        )
    ).scalar() or 0
    cur = await _exec_window_agg(db, project_id, start, now)
    prev = await _exec_window_agg(db, project_id, prev_start, start)
    cur_rate = _rate(cur["passed"], cur["failed"])
    prev_rate = _rate(prev["passed"], prev["failed"])
    rate_trend = (
        round((cur_rate - prev_rate) * 10) / 10
        if cur_rate is not None and prev_rate is not None
        else None
    )
    open_bug_rows = (
        await db.execute(
            select(Bug.severity, func.count(Bug.id))
            .where(
                Bug.project_id == project_id,
                Bug.status.in_(_BUG_OPEN_STATUSES),
                Bug.is_deleted.is_(False),
                Bug.is_archived.is_(False),
            )
            .group_by(Bug.severity)
        )
    ).all()
    by_severity = {str(s): int(n) for (s, n) in open_bug_rows}
    ai_row = (
        await db.execute(
            select(
                func.count(AiTask.id),
                func.sum(sa_case((AiTask.status == "succeeded", 1), else_=0)),
                func.sum(sa_case((AiTask.status == "failed", 1), else_=0)),
            ).where(AiTask.project_id == project_id, AiTask.created_at >= start)
        )
    ).one()
    ai_total = int(ai_row[0] or 0)
    ai_ok, ai_fail = (int(ai_row[1] or 0), int(ai_row[2] or 0))
    new_cur = await _new_case_count(db, project_id, start, now)
    new_prev = await _new_case_count(db, project_id, prev_start, start)
    today_agg = await _exec_window_agg(db, project_id, today_start, now)
    bug_rows = (
        await db.execute(
            select(Bug.status, func.count(Bug.id))
            .where(
                Bug.project_id == project_id,
                Bug.is_deleted.is_(False),
                Bug.is_archived.is_(False),
            )
            .group_by(Bug.status)
        )
    ).all()
    raw_status = {str(s): int(n) for (s, n) in bug_rows}
    bug_status_dist = {
        bucket: sum((raw_status.get(s, 0) for s in statuses))
        for (bucket, statuses) in _BUG_BUCKETS.items()
    }
    kb = (
        await db.execute(
            select(ProjectKnowledgeBase).where(
                ProjectKnowledgeBase.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    return {
        "days": days,
        "stat_cards": {
            "case_total": {
                "value": sum(case_by_type.values()),
                "by_type": case_by_type,
                "ai_generated": int(ai_generated_cases),
            },
            "executions": {
                "value": cur["total"],
                "trend": _growth(cur["total"], prev["total"]),
            },
            "pass_rate": {"value": cur_rate, "trend": rate_trend},
            "open_bugs": {
                "value": sum(by_severity.values()),
                "by_severity": by_severity,
            },
            "ai_tasks": {"value": ai_total, "success_rate": _rate(ai_ok, ai_fail)},
            "new_cases": {"value": new_cur, "trend": _growth(new_cur, new_prev)},
        },
        "today": {
            "executions": today_agg["total"],
            "passed": today_agg["passed"],
            "pass_rate": _rate(today_agg["passed"], today_agg["failed"]),
        },
        "execution_trend": await _daily_trend(db, project_id, start, days),
        "recent_executions": await _recent_executions(db, project_id),
        "bug_status_dist": bug_status_dist,
        "kb": {
            "status": kb.status if kb else "inactive",
            "documents": kb.total_documents if kb else 0,
            "chunks": kb.total_chunks if kb else 0,
            "nodes": kb.total_nodes if kb else 0,
            "edges": kb.total_edges if kb else 0,
            "last_built_at": (
                kb.last_built_at.isoformat() if kb and kb.last_built_at else None
            ),
        },
    }
