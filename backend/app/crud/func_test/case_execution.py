"""用例执行记录 CRUD"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.func_test.case_execution import FuncCaseExecution


class CRUDCaseExecution:
    """用例执行记录 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        *,
        test_case_id: int,
        project_id: int,
        executor_id: int,
        execute_result: str,
        environment_id: Optional[int] = None,
        notes: Optional[str] = None,
        duration: Optional[int] = None,
        executed_at: Optional[datetime] = None,
    ) -> FuncCaseExecution:
        rec = FuncCaseExecution(
            test_case_id=test_case_id,
            project_id=project_id,
            executor_id=executor_id,
            execute_result=execute_result,
            environment_id=environment_id,
            notes=notes,
            duration=duration,
            # UTC：与 api/web 执行表及报表统计窗口（utcnow）统一时钟
            executed_at=executed_at or datetime.utcnow(),
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return rec

    async def list_by_case(
        self,
        db: AsyncSession,
        *,
        test_case_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[FuncCaseExecution], int]:
        stmt = (
            select(FuncCaseExecution)
            .where(FuncCaseExecution.test_case_id == test_case_id)
            .order_by(FuncCaseExecution.executed_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(FuncCaseExecution)
            .where(FuncCaseExecution.test_case_id == test_case_id)
        )
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total


crud_case_execution = CRUDCaseExecution()
