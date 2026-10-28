from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.models.func_test.test_case import FuncTestCase
from app.models.func_test.case_execution import FuncCaseExecution, CaseExecuteResult


async def get_case_count(db: AsyncSession, project_id: int) -> int:
    """获取功能测试用例数量"""
    result = await db.scalar(
        select(func.count()).where(FuncTestCase.project_id == project_id, FuncTestCase.is_deleted == 0)
    )
    return result or 0


async def get_execution_stats(db: AsyncSession, project_id: int) -> dict[str, int]:
    """获取执行统计数据"""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(
                case(
                    (FuncCaseExecution.execute_result == CaseExecuteResult.PASSED.value, 1),
                    else_=0,
                )
            ).label("passed"),
            func.sum(
                case(
                    (FuncCaseExecution.execute_result == CaseExecuteResult.FAILED.value, 1),
                    else_=0,
                )
            ).label("failed"),
        ).where(FuncCaseExecution.project_id == project_id)
    )
    row = result.one_or_none()
    if row:
        return {
            "total": int(row.total or 0),
            "passed": int(row.passed or 0),
            "failed": int(row.failed or 0),
        }
    return {"total": 0, "passed": 0, "failed": 0}
