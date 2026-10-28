"""数据报表中心聚合统计

三个维度报表，各一个聚合函数喂整页：
  - get_assets_report   测试资产（盘点/覆盖率/增长/评审/优先级/来源）
  - get_quality_report  缺陷质量（收敛趋势/解决时长/负载/积压预警）
  - get_ai_report       AI 提效（任务量/生成质量/节省工时估算）

口径沿用 dashboard_service 的约定：软删三形态、utcnow 窗口、
通过率分母不含 running/skipped。
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy import case as sa_case
from sqlalchemy import distinct, func, null, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai.ai_task import AiTask
from app.models.app_test.execution import AppExecution
from app.models.app_test.script import AppScript
from app.models.app_test.suite import AppSuite
from app.models.auth.user import User
from app.models.bug.bug import Bug
from app.models.bug.bug_ai_analysis import BugAiAnalysis
from app.models.bug.bug_history import BugHistory
from app.models.func_test.case_execution import FuncCaseExecution
from app.models.func_test.requirement import TestRequirement
from app.models.func_test.test_case import FuncTestCase
from app.models.knowledge.document import KbDocument


def _rate(part: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return round(part / total * 1000) / 10


def _growth(current: int, previous: int) -> Optional[float]:
    if previous == 0:
        return 100.0 if current > 0 else None
    return round((current - previous) / previous * 1000) / 10


def _window(days: int) -> tuple[datetime, datetime, datetime]:
    """返回 (start, prev_start, now)"""
    now = datetime.utcnow()
    start = datetime.combine(now.date() - timedelta(days=days - 1), datetime.min.time())
    prev_start = start - timedelta(days=days)
    return (start, prev_start, now)


def _fill_daily(
    bucket: dict[str, dict[str, int]], start: datetime, days: int, keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    """补零：每一天都有记录，长度恒等于 days"""
    daily: list[dict[str, Any]] = []
    day0 = start.date()
    empty = {k: 0 for k in keys}
    for i in range(days):
        key = (day0 + timedelta(days=i)).isoformat()
        daily.append({"date": key, **bucket.get(key, empty)})
    return daily


def _date_key(d: Any) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


async def _count(db: AsyncSession, model: Any, *conds: Any) -> int:
    return int(
        (await db.execute(select(func.count(model.id)).where(*conds))).scalar() or 0
    )


_CASE_KEYS: tuple[str, ...] = ("functional", "app")


def _case_models() -> list[tuple[Any, Any, str]]:
    return [
        (FuncTestCase, FuncTestCase.is_deleted.is_(False), "functional"),
        (AppScript, AppScript.id.isnot(None), "app"),
    ]


async def get_assets_report(
    db: AsyncSession, *, project_id: int, days: int = 30
) -> dict[str, Any]:
    start, _, _ = _window(days)
    by_type = {
        key: await _count(db, model, model.project_id == project_id, alive)
        for (model, alive, key) in _case_models()
    }
    req_base = (
        TestRequirement.project_id == project_id,
        TestRequirement.is_deleted.is_(False),
    )
    case_base = (
        FuncTestCase.project_id == project_id,
        FuncTestCase.is_deleted.is_(False),
    )
    req_total = await _count(db, TestRequirement, *req_base)
    req_reviewed = await _count(
        db,
        TestRequirement,
        *req_base,
        TestRequirement.status.in_(("reviewed", "published")),
    )
    covered = int(
        (
            await db.execute(
                select(func.count(distinct(FuncTestCase.requirement_id))).where(
                    *case_base,
                    FuncTestCase.requirement_id.in_(
                        select(TestRequirement.id).where(*req_base)
                    ),
                )
            )
        ).scalar()
        or 0
    )
    reviewed = await _count(
        db, FuncTestCase, *case_base, FuncTestCase.status.in_(("reviewed", "published"))
    )
    ai_cases = await _count(
        db, FuncTestCase, *case_base, FuncTestCase.source == "ai_generated"
    )
    kb_base = (KbDocument.project_id == project_id, KbDocument.status != "deleted")
    kb_total = await _count(db, KbDocument, *kb_base)
    kb_ready = await _count(db, KbDocument, *kb_base, KbDocument.status == "ready")
    bucket = {}
    for model, alive, key in _case_models():
        rows = (
            await db.execute(
                select(func.date(model.created_at), func.count(model.id))
                .where(model.project_id == project_id, alive, model.created_at >= start)
                .group_by(func.date(model.created_at))
            )
        ).all()
        for date, count in rows:
            bucket.setdefault(_date_key(date), {"functional": 0, "app": 0})[key] += int(
                count
            )
    growth = _fill_daily(bucket, start, days, _CASE_KEYS)
    statuses = (
        await db.execute(
            select(FuncTestCase.status, func.count(FuncTestCase.id))
            .where(*case_base)
            .group_by(FuncTestCase.status)
        )
    ).all()
    priorities = (
        await db.execute(
            select(FuncTestCase.priority, func.count(FuncTestCase.id))
            .where(*case_base)
            .group_by(FuncTestCase.priority)
        )
    ).all()
    return {
        "days": days,
        "cards": {
            "case_total": {"value": sum(by_type.values()), "by_type": by_type},
            "requirements": {"value": req_total, "reviewed": req_reviewed},
            "suites": {
                "value": await _count(db, AppSuite, AppSuite.project_id == project_id)
            },
            "kb_documents": {"value": kb_total, "processed": kb_ready},
            "ai_cases": {
                "value": ai_cases,
                "pct": _rate(ai_cases, by_type["functional"]),
            },
        },
        "coverage": {
            "requirement": {
                "rate": _rate(covered, req_total),
                "covered": covered,
                "total": req_total,
            },
            "review": {
                "rate": _rate(reviewed, by_type["functional"]),
                "reviewed": reviewed,
                "total": by_type["functional"],
            },
        },
        "growth_trend": growth,
        "review_status": {"functional": {str(k): int(v) for (k, v) in statuses}},
        "priority_dist": {str(k): int(v) for (k, v) in priorities},
        "source_dist": {
            "ai_generated": ai_cases,
            "manual": by_type["functional"] - ai_cases,
        },
    }


_BUG_ALIVE = (Bug.is_deleted.is_(False), Bug.is_archived.is_(False))
_BUG_OPEN = ("new", "assigned", "in_progress", "resolved", "verified", "reopened")
_BUG_BUCKETS: dict[str, tuple[str, ...]] = {
    "pending": ("new", "reopened"),
    "processing": ("assigned", "in_progress"),
    "resolved": ("resolved", "verified"),
    "closed": ("closed",),
    "suspended": ("postponed", "wontfix"),
}


async def get_quality_report(
    db: AsyncSession, *, project_id: int, days: int = 30
) -> dict[str, Any]:
    start, prev_start, now = _window(days)
    stale_before = now - timedelta(days=7)
    open_rows = (
        await db.execute(
            select(Bug.severity, func.count(Bug.id))
            .where(Bug.project_id == project_id, Bug.status.in_(_BUG_OPEN), *_BUG_ALIVE)
            .group_by(Bug.severity)
        )
    ).all()
    open_by_sev = {str(s): int(n) for (s, n) in open_rows}
    open_total = sum(open_by_sev.values())
    urgent = open_by_sev.get("critical", 0) + open_by_sev.get("major", 0)
    created_cur = await _count(
        db,
        Bug,
        Bug.project_id == project_id,
        Bug.created_at >= start,
        Bug.created_at < now,
        *_BUG_ALIVE,
    )
    created_prev = await _count(
        db,
        Bug,
        Bug.project_id == project_id,
        Bug.created_at >= prev_start,
        Bug.created_at < start,
        *_BUG_ALIVE,
    )
    closed_expr = (
        select(func.count(BugHistory.id))
        .join(Bug, Bug.id == BugHistory.bug_id)
        .where(Bug.project_id == project_id, BugHistory.action == "closed")
    )
    closed_cur = int(
        (
            await db.execute(
                closed_expr.where(
                    BugHistory.operated_at >= start, BugHistory.operated_at < now
                )
            )
        ).scalar()
        or 0
    )
    from sqlalchemy import text as sa_text

    avg_resolve_sec = (
        await db.execute(
            sa_text(
                "\n                SELECT AVG(TIMESTAMPDIFF(SECOND, b.created_at, h.operated_at))\n                FROM bug_history h\n                JOIN bug b ON b.id = h.bug_id\n                WHERE b.project_id = :pid\n                  AND h.action = 'resolved'\n                  AND h.operated_at >= :start\n                "
            ),
            {"pid": project_id, "start": start},
        )
    ).scalar()
    avg_resolve_days = (
        round(float(avg_resolve_sec) / 86400 * 10) / 10
        if avg_resolve_sec is not None
        else None
    )
    total_bugs = await _count(db, Bug, Bug.project_id == project_id, *_BUG_ALIVE)
    resolved_or_closed = await _count(
        db,
        Bug,
        Bug.project_id == project_id,
        Bug.status.in_(("resolved", "verified", "closed")),
        *_BUG_ALIVE,
    )
    reopened_cur = int(
        (
            await db.execute(
                select(func.count(BugHistory.id))
                .join(Bug, Bug.id == BugHistory.bug_id)
                .where(
                    Bug.project_id == project_id,
                    BugHistory.action == "reopened",
                    BugHistory.operated_at >= start,
                )
            )
        ).scalar()
        or 0
    )
    ai_analyzed = int(
        (
            await db.execute(
                select(func.count(BugAiAnalysis.id))
                .join(Bug, Bug.id == BugAiAnalysis.bug_id)
                .where(
                    Bug.project_id == project_id,
                    BugAiAnalysis.analysis_status == "completed",
                )
            )
        ).scalar()
        or 0
    )
    stale_count = await _count(
        db,
        Bug,
        Bug.project_id == project_id,
        Bug.status.in_(_BUG_OPEN),
        Bug.updated_at < stale_before,
        *_BUG_ALIVE,
    )
    bucket: dict[str, dict[str, int]] = {}
    rows = (
        await db.execute(
            select(func.date(Bug.created_at), func.count(Bug.id))
            .where(Bug.project_id == project_id, Bug.created_at >= start, *_BUG_ALIVE)
            .group_by(func.date(Bug.created_at))
        )
    ).all()
    for d, n in rows:
        bucket.setdefault(_date_key(d), {"created": 0, "closed": 0})["created"] = int(
            n or 0
        )
    rows = (
        await db.execute(
            select(func.date(BugHistory.operated_at), func.count(BugHistory.id))
            .join(Bug, Bug.id == BugHistory.bug_id)
            .where(
                Bug.project_id == project_id,
                BugHistory.action == "closed",
                BugHistory.operated_at >= start,
            )
            .group_by(func.date(BugHistory.operated_at))
        )
    ).all()
    for d, n in rows:
        bucket.setdefault(_date_key(d), {"created": 0, "closed": 0})["closed"] = int(
            n or 0
        )
    trend = _fill_daily(bucket, start, days, ("created", "closed"))
    running = open_total
    for item in reversed(trend):
        item["open"] = running
        running = running - item["created"] + item["closed"]
    status_rows = (
        await db.execute(
            select(Bug.status, func.count(Bug.id))
            .where(Bug.project_id == project_id, *_BUG_ALIVE)
            .group_by(Bug.status)
        )
    ).all()
    raw_status = {str(s): int(n) for (s, n) in status_rows}
    status_dist = {
        b: sum((raw_status.get(s, 0) for s in ss)) for (b, ss) in _BUG_BUCKETS.items()
    }
    assignee_rows = (
        await db.execute(
            select(
                Bug.assigned_to,
                func.max(User.real_name),
                func.max(User.username),
                func.count(Bug.id),
            )
            .outerjoin(User, User.id == Bug.assigned_to)
            .where(Bug.project_id == project_id, Bug.status.in_(_BUG_OPEN), *_BUG_ALIVE)
            .group_by(Bug.assigned_to)
            .order_by(func.count(Bug.id).desc())
            .limit(5)
        )
    ).all()
    assignee_load = [
        {
            "user_id": uid,
            "name": real or uname or "未指派" if uid else "未指派",
            "count": int(n),
        }
        for (uid, real, uname, n) in assignee_rows
    ]
    source_rows = (
        await db.execute(
            select(Bug.test_case_type, func.count(Bug.id))
            .where(Bug.project_id == project_id, *_BUG_ALIVE)
            .group_by(Bug.test_case_type)
        )
    ).all()
    source_dist = {str(s): int(n) for (s, n) in source_rows if s}
    stale_rows = (
        await db.execute(
            select(Bug.id, Bug.title, Bug.updated_at)
            .where(
                Bug.project_id == project_id,
                Bug.status.in_(_BUG_OPEN),
                Bug.updated_at < stale_before,
                *_BUG_ALIVE,
            )
            .order_by(Bug.updated_at.asc())
            .limit(5)
        )
    ).all()
    stale_list = [
        {
            "id": bid,
            "title": title,
            "days": max(0, (now - updated).days) if updated else 0,
        }
        for (bid, title, updated) in stale_rows
    ]
    return {
        "days": days,
        "cards": {
            "open": {"value": open_total, "urgent": urgent},
            "created": {
                "value": created_cur,
                "trend": _growth(created_cur, created_prev),
            },
            "closed": {"value": closed_cur, "converging": closed_cur >= created_cur},
            "avg_resolve_days": avg_resolve_days,
            "resolve_rate": _rate(resolved_or_closed, total_bugs),
            "reopened": reopened_cur,
            "ai_coverage": _rate(ai_analyzed, total_bugs),
            "stale": stale_count,
        },
        "trend": trend,
        "severity_dist": open_by_sev,
        "status_dist": status_dist,
        "assignee_load": assignee_load,
        "source_dist": source_dist,
        "stale_list": stale_list,
    }


_SAVED_RULES: list[dict[str, Any]] = [
    {
        "key": "ai_func_cases",
        "label": "生成功能用例",
        "unit": "条",
        "minutes": 15,
        "kind": "func_ai_cases",
    },
    {
        "key": "understand",
        "label": "需求理解",
        "unit": "次",
        "minutes": 30,
        "kind": "task",
        "task_type": "understand_requirement",
    },
    {
        "key": "parse_document",
        "label": "文档解析",
        "unit": "次",
        "minutes": 10,
        "kind": "task",
        "task_type": "parse_document",
    },
    {
        "key": "bug_analysis",
        "label": "缺陷 AI 分析",
        "unit": "次",
        "minutes": 15,
        "kind": "bug_analysis",
    },
]


async def get_ai_report(
    db: AsyncSession, *, project_id: int, days: int = 30
) -> dict[str, Any]:
    start, prev_start, now = _window(days)
    base = (AiTask.project_id == project_id,)
    in_window = (AiTask.created_at >= start, AiTask.created_at < now)
    row = (
        await db.execute(
            select(
                func.count(AiTask.id),
                func.sum(sa_case((AiTask.status == "succeeded", 1), else_=0)),
                func.sum(sa_case((AiTask.status == "failed", 1), else_=0)),
            ).where(*base, *in_window)
        )
    ).one()
    total = int(row[0] or 0)
    ok, fail = (int(row[1] or 0), int(row[2] or 0))
    prev_total = await _count(
        db, AiTask, *base, AiTask.created_at >= prev_start, AiTask.created_at < start
    )
    ai_cases = await _count(
        db,
        FuncTestCase,
        FuncTestCase.project_id == project_id,
        FuncTestCase.is_deleted.is_(False),
        FuncTestCase.source == "ai_generated",
    )
    func_total = await _count(
        db,
        FuncTestCase,
        FuncTestCase.project_id == project_id,
        FuncTestCase.is_deleted.is_(False),
    )
    ai_reviewed = await _count(
        db,
        FuncTestCase,
        FuncTestCase.project_id == project_id,
        FuncTestCase.is_deleted.is_(False),
        FuncTestCase.source == "ai_generated",
        FuncTestCase.status == "reviewed",
    )
    type_rows = (
        await db.execute(
            select(
                AiTask.task_type,
                func.count(AiTask.id),
                func.sum(sa_case((AiTask.status == "succeeded", 1), else_=0)),
            )
            .where(*base, *in_window)
            .group_by(AiTask.task_type)
            .order_by(func.count(AiTask.id).desc())
        )
    ).all()
    type_dist = [
        {
            "type": t,
            "count": int(n),
            "succeeded": int(s or 0),
            "success_rate": _rate(int(s or 0), int(n)),
        }
        for (t, n, s) in type_rows
    ]
    from sqlalchemy import text as sa_text

    dur_rows = (
        await db.execute(
            sa_text(
                "\n                SELECT task_type,\n                       AVG(TIMESTAMPDIFF(SECOND, started_at, completed_at))\n                FROM ai_task\n                WHERE project_id = :pid\n                  AND created_at >= :start\n                  AND started_at IS NOT NULL\n                  AND completed_at IS NOT NULL\n                GROUP BY task_type\n                "
            ),
            {"pid": project_id, "start": start},
        )
    ).all()
    type_avg_duration = {
        str(t): round(float(s) / 60 * 10) / 10 for (t, s) in dur_rows if s
    }
    overall_avg_min = (
        round(sum(type_avg_duration.values()) / len(type_avg_duration) * 10) / 10
        if type_avg_duration
        else None
    )
    bucket: dict[str, dict[str, int]] = {}
    rows = (
        await db.execute(
            select(
                func.date(AiTask.created_at),
                func.count(AiTask.id),
                func.sum(sa_case((AiTask.status == "succeeded", 1), else_=0)),
            )
            .where(*base, AiTask.created_at >= start)
            .group_by(func.date(AiTask.created_at))
        )
    ).all()
    for d, n, s in rows:
        bucket[_date_key(d)] = {"count": int(n or 0), "succeeded": int(s or 0)}
    trend = _fill_daily(bucket, start, days, ("count", "succeeded"))
    week_buckets: list[dict[str, Any]] = []
    for w in range(4):
        w_end = now - timedelta(days=7 * w)
        w_start = w_end - timedelta(days=7)
        ai_n = await _count(
            db,
            FuncTestCase,
            FuncTestCase.project_id == project_id,
            FuncTestCase.is_deleted.is_(False),
            FuncTestCase.source == "ai_generated",
            FuncTestCase.created_at >= w_start,
            FuncTestCase.created_at < w_end,
        )
        manual_n = await _count(
            db,
            FuncTestCase,
            FuncTestCase.project_id == project_id,
            FuncTestCase.is_deleted.is_(False),
            FuncTestCase.source != "ai_generated",
            FuncTestCase.created_at >= w_start,
            FuncTestCase.created_at < w_end,
        )
        week_buckets.append({"week": f"W{4 - w}", "ai": ai_n, "manual": manual_n})
    week_buckets.reverse()
    ok_rows = (
        await db.execute(
            select(AiTask.task_type, func.count(AiTask.id))
            .where(*base, AiTask.status == "succeeded")
            .group_by(AiTask.task_type)
        )
    ).all()
    ok_by_type = {str(t): int(n) for (t, n) in ok_rows}
    bug_analyzed = int(
        (
            await db.execute(
                select(func.count(BugAiAnalysis.id))
                .join(Bug, Bug.id == BugAiAnalysis.bug_id)
                .where(
                    Bug.project_id == project_id,
                    BugAiAnalysis.analysis_status == "completed",
                )
            )
        ).scalar()
        or 0
    )

    def _rule_count(rule: dict[str, Any]) -> int:
        kind = rule["kind"]
        if kind == "func_ai_cases":
            return ai_cases
        if kind == "task":
            return ok_by_type.get(rule["task_type"], 0)
        if kind == "bug_analysis":
            return bug_analyzed
        return 0

    saved_breakdown = []
    for rule in _SAVED_RULES:
        count = _rule_count(rule)
        saved_breakdown.append(
            {
                "key": rule["key"],
                "label": rule["label"],
                "unit": rule["unit"],
                "unit_minutes": rule["minutes"],
                "count": count,
                "minutes": count * rule["minutes"],
            }
        )
    saved_hours = round(sum((v["minutes"] for v in saved_breakdown)) / 60 * 10) / 10
    return {
        "days": days,
        "cards": {
            "total": {"value": total, "trend": _growth(total, prev_total)},
            "success_rate": _rate(ok, ok + fail),
            "ai_cases": {"value": ai_cases, "pct": _rate(ai_cases, func_total)},
            "ai_review_pass": _rate(ai_reviewed, ai_cases),
            "avg_duration_min": overall_avg_min,
            "saved_hours": saved_hours,
        },
        "type_dist": type_dist,
        "trend": trend,
        "ai_vs_manual": week_buckets,
        "type_avg_duration": type_avg_duration,
        "saved_breakdown": saved_breakdown,
        "saved_rule": "按各类 AI 产出的保守人工耗时折算（每项费率见构成明细）",
    }


_EXEC_MODULES: list[dict[str, Any]] = [
    {
        "key": "functional",
        "model": FuncCaseExecution,
        "status_col": "execute_result",
        "time_col": "executed_at",
        "case_col": "test_case_id",
        "user_col": "executor_id",
        "duration_col": "duration",
        "duration_factor": 1.0,
        "case_model": FuncTestCase,
        "case_name_col": "title",
        "case_alive": FuncTestCase.is_deleted.is_(False),
        "passed": ("passed",),
        "failed": ("failed",),
        "skipped": ("blocked", "skipped"),
    },
    {
        "key": "app",
        "model": AppExecution,
        "status_col": "status",
        "time_col": "created_at",
        "case_col": "script_id",
        "user_col": None,
        "duration_col": "duration_ms",
        "duration_factor": 0.001,
        "case_model": AppScript,
        "case_name_col": "name",
        "case_alive": AppScript.id.isnot(None),
        "passed": ("success",),
        "failed": ("failed",),
        "skipped": ("cancelled",),
        "project_scope": lambda pid: AppExecution.script_id.in_(
            select(AppScript.id).where(AppScript.project_id == pid)
        ),
    },
]


def _pf_case(status_col: Any, values: tuple[str, ...]) -> Any:
    return func.sum(sa_case((status_col.in_(values), 1), else_=0))


def _proj_cond(m: dict[str, Any], project_id: int) -> Any:
    """执行模块的项目过滤条件：直存 project_id 用等值，否则用声明的子查询作用域。"""
    scope = m.get("project_scope")
    if scope is not None:
        return scope(project_id)
    return m["model"].project_id == project_id


def _exec_rate(passed: int, failed: int) -> Optional[float]:
    """执行通过率：分母 = passed + failed，running/skipped 不计入"""
    done = passed + failed
    if done == 0:
        return None
    return round(passed / done * 1000) / 10


async def get_execution_report(
    db: AsyncSession, *, project_id: int, days: int = 30
) -> dict[str, Any]:
    start, prev_start, now = _window(days)
    today_start = datetime.combine(now.date(), datetime.min.time())
    modules: list[dict[str, Any]] = []
    trend_bucket: dict[str, dict[str, int]] = {}
    result_dist = {"passed": 0, "failed": 0, "skipped": 0, "running": 0}
    executor_bucket: dict[int, dict[str, int]] = {}
    failure_rows: list[dict[str, Any]] = []
    totals = {"cur": [0, 0, 0], "prev": [0, 0, 0], "today": [0, 0, 0]}
    executed_cases = 0
    for m in _EXEC_MODULES:
        model = m["model"]
        status_col = getattr(model, m["status_col"])
        time_col = getattr(model, m["time_col"])
        case_col = getattr(model, m["case_col"])
        user_col = getattr(model, m["user_col"]) if m.get("user_col") else None
        duration_expr = (
            getattr(model, m["duration_col"]) if m.get("duration_col") else null()
        )
        base = (_proj_cond(m, project_id),)
        win = (*base, time_col >= start)
        done_statuses = (*m["passed"], *m["failed"])
        row = (
            await db.execute(
                select(
                    func.count(model.id),
                    _pf_case(status_col, m["passed"]),
                    _pf_case(status_col, m["failed"]),
                    func.avg(
                        sa_case(
                            (status_col.in_(done_statuses), duration_expr), else_=None
                        )
                    ),
                ).where(*win)
            )
        ).one()
        cur_total, cur_passed, cur_failed = (
            int(row[0] or 0),
            int(row[1] or 0),
            int(row[2] or 0),
        )
        avg_duration_s = (
            round(float(row[3]) * m["duration_factor"] * 10) / 10
            if row[3] is not None
            else None
        )
        case_model = m["case_model"]
        distinct_cases = int(
            (
                await db.execute(
                    select(func.count(distinct(case_col))).where(
                        *win, case_col.in_(select(case_model.id).where(m["case_alive"]))
                    )
                )
            ).scalar()
            or 0
        )
        prow = (
            await db.execute(
                select(
                    func.count(model.id),
                    _pf_case(status_col, m["passed"]),
                    _pf_case(status_col, m["failed"]),
                ).where(*base, time_col >= prev_start, time_col < start)
            )
        ).one()
        trow = (
            await db.execute(
                select(
                    func.count(model.id),
                    _pf_case(status_col, m["passed"]),
                    _pf_case(status_col, m["failed"]),
                ).where(*base, time_col >= today_start)
            )
        ).one()
        for slot, r in (("cur", row), ("prev", prow), ("today", trow)):
            totals[slot][0] += int(r[0] or 0)
            totals[slot][1] += int(r[1] or 0)
            totals[slot][2] += int(r[2] or 0)
        executed_cases += distinct_cases
        srows = (
            await db.execute(
                select(status_col, func.count(model.id))
                .where(*win)
                .group_by(status_col)
            )
        ).all()
        for s, n in srows:
            s = str(s)
            if s in m["passed"]:
                result_dist["passed"] += int(n)
            elif s in m["failed"]:
                result_dist["failed"] += int(n)
            elif s in m["skipped"]:
                result_dist["skipped"] += int(n)
            else:
                result_dist["running"] += int(n)
        date_expr = func.date(time_col)
        drows = (
            await db.execute(
                select(
                    date_expr,
                    func.count(model.id),
                    _pf_case(status_col, m["passed"]),
                    _pf_case(status_col, m["failed"]),
                )
                .where(*win)
                .group_by(date_expr)
            )
        ).all()
        for d, n, p, f in drows:
            item = trend_bucket.setdefault(
                _date_key(d), {**{k: 0 for k in _CASE_KEYS}, "passed": 0, "failed": 0}
            )
            item[m["key"]] += int(n or 0)
            item["passed"] += int(p or 0)
            item["failed"] += int(f or 0)
        if user_col is not None:
            urows = (
                await db.execute(
                    select(
                        user_col,
                        func.count(model.id),
                        _pf_case(status_col, m["passed"]),
                        _pf_case(status_col, m["failed"]),
                    )
                    .where(*win)
                    .group_by(user_col)
                )
            ).all()
            for uid, n, p, f in urows:
                if uid is None:
                    continue
                item = executor_bucket.setdefault(
                    int(uid), {"count": 0, "passed": 0, "failed": 0}
                )
                item["count"] += int(n or 0)
                item["passed"] += int(p or 0)
                item["failed"] += int(f or 0)
        fail_expr = _pf_case(status_col, m["failed"])
        frows = (
            await db.execute(
                select(case_col, func.count(model.id), fail_expr)
                .where(*win)
                .group_by(case_col)
                .having(fail_expr > 0)
                .order_by(fail_expr.desc())
                .limit(8)
            )
        ).all()
        frows = [r for r in frows if r[0] is not None]
        if frows:
            ids = [int(r[0]) for r in frows]
            name_col = getattr(case_model, m["case_name_col"])
            nrows = (
                await db.execute(
                    select(case_model.id, name_col).where(case_model.id.in_(ids))
                )
            ).all()
            names = {int(i): str(t) for (i, t) in nrows}
            for cid, n, fc in frows:
                failure_rows.append(
                    {
                        "module": m["key"],
                        "case_id": int(cid),
                        "name": names.get(int(cid), f"用例#{cid}"),
                        "fail_count": int(fc or 0),
                        "exec_count": int(n or 0),
                        "fail_rate": _rate(int(fc or 0), int(n or 0)),
                    }
                )
        modules.append(
            {
                "key": m["key"],
                "executions": cur_total,
                "exec_trend": _growth(cur_total, int(prow[0] or 0)),
                "passed": cur_passed,
                "failed": cur_failed,
                "pass_rate": _exec_rate(cur_passed, cur_failed),
                "cases": distinct_cases,
                "avg_duration_s": avg_duration_s,
            }
        )
    trend: list[dict[str, Any]] = []
    day0 = start.date()
    for i in range(days):
        key = (day0 + timedelta(days=i)).isoformat()
        item = trend_bucket.get(
            key, {**{k: 0 for k in _CASE_KEYS}, "passed": 0, "failed": 0}
        )
        trend.append(
            {
                "date": key,
                **{k: item[k] for k in _CASE_KEYS},
                "total": sum((item[k] for k in _CASE_KEYS)),
                "pass_rate": _exec_rate(item["passed"], item["failed"]),
            }
        )
    rank = sorted(executor_bucket.items(), key=lambda kv: kv[1]["count"], reverse=True)[
        :8
    ]
    names: dict[int, str] = {}
    if rank:
        urows2 = (
            await db.execute(
                select(User.id, User.real_name, User.username).where(
                    User.id.in_([uid for (uid, _) in rank])
                )
            )
        ).all()
        names = {int(i): real or uname or f"用户#{i}" for (i, real, uname) in urows2}
    executor_rank = [
        {
            "user_id": uid,
            "name": names.get(uid, f"用户#{uid}"),
            "count": item["count"],
            "passed": item["passed"],
            "pass_rate": _exec_rate(item["passed"], item["failed"]),
        }
        for (uid, item) in rank
    ]
    top_failures = sorted(failure_rows, key=lambda x: x["fail_count"], reverse=True)[:8]
    total_cases = 0
    for case_model, alive, _key in _case_models():
        total_cases += await _count(
            db, case_model, case_model.project_id == project_id, alive
        )
    cur_t, cur_p, cur_f = totals["cur"]
    prev_t, prev_p, prev_f = totals["prev"]
    today_t, today_p, today_f = totals["today"]
    cur_rate = _exec_rate(cur_p, cur_f)
    prev_rate = _exec_rate(prev_p, prev_f)
    return {
        "days": days,
        "cards": {
            "executions": {"value": cur_t, "trend": _growth(cur_t, prev_t)},
            "pass_rate": {
                "value": cur_rate,
                "trend": (
                    round((cur_rate - prev_rate) * 10) / 10
                    if cur_rate is not None and prev_rate is not None
                    else None
                ),
            },
            "failed": {"value": cur_f, "trend": _growth(cur_f, prev_f)},
            "executed_cases": {
                "value": executed_cases,
                "total_cases": total_cases,
                "coverage": _rate(executed_cases, total_cases),
            },
            "today": {"value": today_t, "pass_rate": _exec_rate(today_p, today_f)},
        },
        "trend": trend,
        "modules": modules,
        "result_dist": result_dist,
        "executor_rank": executor_rank,
        "top_failures": top_failures,
    }
