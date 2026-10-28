"""功能测试和 App 自动化执行报告。"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.app_test.execution import AppExecution
from app.models.app_test.script import AppScript
from app.models.auth.user import User
from app.models.func_test.case_execution import FuncCaseExecution
from app.models.func_test.test_case import FuncTestCase
from app.schemas.report.report import (
    ReportExecutionItem,
    ReportExecutionListResponse,
    ReportSummary,
)


def _sources(project_id: int):
    return [
        (
            "functional",
            FuncCaseExecution,
            FuncCaseExecution.project_id == project_id,
            FuncCaseExecution.executed_at,
            FuncCaseExecution.execute_result,
            "passed",
        ),
        (
            "app",
            AppExecution,
            AppExecution.script_id.in_(
                select(AppScript.id).where(AppScript.project_id == project_id)
            ),
            AppExecution.created_at,
            AppExecution.status,
            "success",
        ),
    ]


class ReportService:
    @staticmethod
    def _resolve_date_range(start: Optional[datetime], end: Optional[datetime]):
        now = datetime.utcnow()
        return start or now - timedelta(days=30), end or now

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        *,
        project_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ReportSummary:
        start, end = ReportService._resolve_date_range(start_date, end_date)
        stats = {}
        for kind, model, scope, time, status, passed in _sources(project_id):
            row = (
                await db.execute(
                    select(
                        func.count(model.id),
                        func.sum(case((status == passed, 1), else_=0)),
                        func.sum(case((status == "failed", 1), else_=0)),
                    ).where(scope, time >= start, time <= end)
                )
            ).one()
            stats[kind] = tuple(int(v or 0) for v in row)

        def rate(passed, failed):
            return (
                round(passed / (passed + failed) * 100, 1) if passed + failed else 0.0
            )

        return ReportSummary(
            total_executions=sum(v[0] for v in stats.values()),
            functional_executions=stats["functional"][0],
            app_executions=stats["app"][0],
            functional_pass_rate=rate(*stats["functional"][1:]),
            app_pass_rate=rate(*stats["app"][1:]),
            overall_pass_rate=rate(
                sum(v[1] for v in stats.values()), sum(v[2] for v in stats.values())
            ),
        )

    @staticmethod
    async def get_executions(
        db: AsyncSession,
        *,
        project_id: int,
        exec_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ReportExecutionListResponse:
        start, end = ReportService._resolve_date_range(start_date, end_date)
        total, items = 0, []
        for kind, model, scope, time, status, pass_status in _sources(project_id):
            if exec_type is not None and exec_type != kind:
                continue
            conds = (scope, time >= start, time <= end)
            total += int(
                (await db.execute(select(func.count(model.id)).where(*conds))).scalar()
                or 0
            )
            if kind == "functional":
                stmt = (
                    select(model, FuncTestCase.title, User.real_name, User.username)
                    .outerjoin(FuncTestCase, FuncTestCase.id == model.test_case_id)
                    .outerjoin(User, User.id == model.executor_id)
                )
            else:
                stmt = select(model, AppScript.name).outerjoin(
                    AppScript, AppScript.id == model.script_id
                )
            rows = (
                await db.execute(
                    stmt.where(*conds)
                    .order_by(time.desc(), model.id.desc())
                    .limit(page * page_size)
                )
            ).all()
            for row in rows:
                record, name = row[:2]
                state = getattr(record, status.key)
                passed, failed = int(state == pass_status), int(state == "failed")
                duration = (
                    (record.duration or 0) * 1000
                    if kind == "functional"
                    else record.duration_ms or 0
                )
                items.append(
                    ReportExecutionItem(
                        id=record.id,
                        exec_type=kind,
                        name=name or f"用例 #{record.id}",
                        status=state,
                        total=1,
                        passed=passed,
                        failed=failed,
                        pass_rate=100.0 if passed else 0.0,
                        duration_ms=duration,
                        executor_name=(
                            (row[2] or row[3]) if kind == "functional" else None
                        ),
                        executed_at=getattr(record, time.key),
                    )
                )
        items.sort(
            key=lambda item: (item.executed_at.replace(tzinfo=None), item.id),
            reverse=True,
        )
        offset = (page - 1) * page_size
        return ReportExecutionListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items[offset : offset + page_size],
        )
