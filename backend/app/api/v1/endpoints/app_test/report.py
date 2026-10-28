"""APP 自动化报表端点（项目域，页面重构配套）

GET /projects/{project_id}/app/report/stats?dimension=case|suite&days=7|14|30

执行概览聚合（与 web_test 报表 stats 同构，AppExecutionsReport 组件消费）：
- summary：总数/通过/失败/通过率（含上一窗口对比）/平均耗时/执行中
- daily：按天 通过/失败 计数（补齐空天，前端画堆叠柱）
- top_failures：失败次数 Top5（case=按用例，suite=按套件）
- dist：分布环（case=单跑/套件来源，suite=手动/定时触发）
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.models.app_test.execution import AppExecution
from app.models.app_test.script import AppScript
from app.models.app_test.suite import AppSuite
from app.models.app_test.suite_execution import AppSuiteExecution
from app.models.auth.user import User
from app.utils.project_permission import require_project_access

router = APIRouter()

_TERMINAL_OK = "success"
_TERMINAL_BAD = "failed"


def _window(days: int) -> tuple[datetime, datetime]:
    """当前窗口 [since, now)；上一窗口 = [since-days, since)"""
    now = datetime.utcnow()
    return now - timedelta(days=days), now


def _pass_rate(passed: int, failed: int) -> float | None:
    done = passed + failed
    return round(passed / done * 100, 1) if done else None


def _fill_daily(rows: list, days: int) -> list[dict]:
    """按天补齐空档：rows = [(date, status, count)]"""
    by_day: dict[str, dict[str, int]] = {}
    for d, status, count in rows:
        key = str(d)
        slot = by_day.setdefault(key, {"passed": 0, "failed": 0})
        if status == _TERMINAL_OK:
            slot["passed"] += count
        elif status in (_TERMINAL_BAD, "cancelled"):
            # 图表口径：取消归入"未通过"侧展示（量极小，避免第三个序列）
            slot["failed"] += count
    today = datetime.utcnow().date()
    out = []
    for i in range(days - 1, -1, -1):
        key = str(today - timedelta(days=i))
        slot = by_day.get(key, {"passed": 0, "failed": 0})
        out.append({"date": key, "passed": slot["passed"], "failed": slot["failed"]})
    return out


@router.get("/stats", summary="执行概览聚合（case/suite 双维度）")
async def get_report_stats(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
    dimension: str = Query("case", pattern="^(case|suite)$"),
    days: int = Query(7, ge=1, le=90),
):
    await require_project_access(db, project_id, current_user.id)
    since, now = _window(days)
    prev_since = since - timedelta(days=days)

    if dimension == "suite":
        model, time_col = AppSuiteExecution, AppSuiteExecution.created_at
        project_cond = [AppSuiteExecution.project_id == project_id]
        base_from = select(model)
    else:
        model, time_col = AppExecution, AppExecution.created_at
        project_cond = [AppScript.project_id == project_id]
        base_from = select(model).join(AppScript, AppExecution.script_id == AppScript.id)

    def _counts_stmt(lo: datetime, hi: datetime):
        stmt = (
            select(model.status, func.count())
            .where(*project_cond, time_col >= lo, time_col < hi)
            .group_by(model.status)
        )
        if dimension == "case":
            stmt = stmt.select_from(
                AppExecution.__table__.join(
                    AppScript.__table__, AppExecution.script_id == AppScript.id
                )
            )
        return stmt

    # ── summary（当前窗口 + 上一窗口通过率对比）──
    cur = dict((await db.execute(_counts_stmt(since, now))).all())
    prev = dict((await db.execute(_counts_stmt(prev_since, since))).all())
    passed = int(cur.get(_TERMINAL_OK, 0))
    failed = int(cur.get(_TERMINAL_BAD, 0)) + int(cur.get("cancelled", 0))
    running = int(cur.get("running", 0)) + int(cur.get("pending", 0))
    total = sum(int(v) for v in cur.values())

    avg_stmt = select(func.avg(model.duration_ms)).where(
        *project_cond,
        time_col >= since,
        model.duration_ms.isnot(None),
    )
    if dimension == "case":
        avg_stmt = avg_stmt.select_from(
            AppExecution.__table__.join(
                AppScript.__table__, AppExecution.script_id == AppScript.id
            )
        )
    avg_ms = (await db.execute(avg_stmt)).scalar_one_or_none()

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "running": running,
        "pass_rate": _pass_rate(passed, failed),
        "prev_pass_rate": _pass_rate(
            int(prev.get(_TERMINAL_OK, 0)),
            int(prev.get(_TERMINAL_BAD, 0)) + int(prev.get("cancelled", 0)),
        ),
        "avg_duration_ms": round(float(avg_ms)) if avg_ms is not None else None,
    }

    # ── daily 趋势 ──
    daily_stmt = (
        select(func.date(time_col), model.status, func.count())
        .where(*project_cond, time_col >= since)
        .group_by(func.date(time_col), model.status)
    )
    if dimension == "case":
        daily_stmt = daily_stmt.select_from(
            AppExecution.__table__.join(
                AppScript.__table__, AppExecution.script_id == AppScript.id
            )
        )
    daily = _fill_daily(list((await db.execute(daily_stmt)).all()), days)

    # ── top_failures + dist ──
    if dimension == "suite":
        top_stmt = (
            select(
                AppSuiteExecution.suite_id,
                AppSuite.name,
                func.count().label("failures"),
            )
            .join(AppSuite, AppSuiteExecution.suite_id == AppSuite.id)
            .where(*project_cond, time_col >= since, model.status == _TERMINAL_BAD)
            .group_by(AppSuiteExecution.suite_id, AppSuite.name)
            .order_by(func.count().desc())
            .limit(5)
        )
        runs_stmt = (
            select(AppSuiteExecution.suite_id, func.count())
            .where(*project_cond, time_col >= since)
            .group_by(AppSuiteExecution.suite_id)
        )
        dist_stmt = (
            select(AppSuiteExecution.trigger_type, func.count())
            .where(*project_cond, time_col >= since)
            .group_by(AppSuiteExecution.trigger_type)
        )
        runs = dict((await db.execute(runs_stmt)).all())
        top = [
            {"id": sid, "name": name, "failures": int(n), "runs": int(runs.get(sid, 0))}
            for sid, name, n in (await db.execute(top_stmt)).all()
        ]
        dist = {str(k): int(v) for k, v in (await db.execute(dist_stmt)).all()}
    else:
        top_stmt = (
            select(AppExecution.script_id, AppScript.name, func.count().label("failures"))
            .select_from(
                AppExecution.__table__.join(
                    AppScript.__table__, AppExecution.script_id == AppScript.id
                )
            )
            .where(*project_cond, time_col >= since, model.status == _TERMINAL_BAD)
            .group_by(AppExecution.script_id, AppScript.name)
            .order_by(func.count().desc())
            .limit(5)
        )
        runs_stmt = (
            select(AppExecution.script_id, func.count())
            .select_from(
                AppExecution.__table__.join(
                    AppScript.__table__, AppExecution.script_id == AppScript.id
                )
            )
            .where(*project_cond, time_col >= since)
            .group_by(AppExecution.script_id)
        )
        dist_stmt = (
            select(
                AppExecution.suite_execution_id.is_(None),
                func.count(),
            )
            .select_from(
                AppExecution.__table__.join(
                    AppScript.__table__, AppExecution.script_id == AppScript.id
                )
            )
            .where(*project_cond, time_col >= since)
            .group_by(AppExecution.suite_execution_id.is_(None))
        )
        runs = dict((await db.execute(runs_stmt)).all())
        top = [
            {"id": sid, "name": name, "failures": int(n), "runs": int(runs.get(sid, 0))}
            for sid, name, n in (await db.execute(top_stmt)).all()
        ]
        dist_rows = dict((await db.execute(dist_stmt)).all())
        dist = {
            "standalone": int(dist_rows.get(True, 0)),
            "suite": int(dist_rows.get(False, 0)),
        }

    return ResponseModel(
        data={"summary": summary, "daily": daily, "top_failures": top, "dist": dist}
    )
