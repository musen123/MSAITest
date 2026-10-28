"""用例执行记录 API"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.func_test.case_execution import crud_case_execution
from app.crud.func_test.test_case import crud_test_case
from app.models.auth.user import User
from app.schemas.func_test.case_execution import (
    CaseExecutionCreate,
    CaseExecutionListResponse,
    CaseExecutionResponse,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.post(
    "/{case_id}/executions",
    summary="提交用例执行结果",
    response_model=ResponseModel[CaseExecutionResponse],
)
async def submit_execution(
    project_id: int,
    case_id: int,
    body: CaseExecutionCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:execute"))
    ],
) -> ResponseModel[CaseExecutionResponse]:
    await require_project_access(db, project_id, current_user.id)
    case = await crud_test_case.get(db, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")

    rec = await crud_case_execution.create(
        db,
        test_case_id=case_id,
        project_id=project_id,
        executor_id=current_user.id,
        execute_result=body.execute_result,
        environment_id=body.environment_id,
        notes=body.notes,
        duration=body.duration,
        executed_at=body.executed_at,
    )
    return success_response(data=CaseExecutionResponse.model_validate(rec))


@router.get(
    "/{case_id}/executions",
    summary="获取用例执行记录",
    response_model=ResponseModel[CaseExecutionListResponse],
)
async def list_executions(
    project_id: int,
    case_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[CaseExecutionListResponse]:
    await require_project_access(db, project_id, current_user.id)
    case = await crud_test_case.get(db, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")

    items, total = await crud_case_execution.list_by_case(
        db,
        test_case_id=case_id,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return success_response(
        data=CaseExecutionListResponse(
            total=total,
            items=[CaseExecutionResponse.model_validate(i) for i in items],
        )
    )
