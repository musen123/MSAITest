"""APP 自动化套件执行汇总端点（项目域，P4，读侧）

/projects/{project_id}/app/suite-executions：汇总列表 / 详情（含用例级明细下钻）。
执行提交在 suites 路由（POST /app/suites/{suite_id}/run）；单条用例的报告仍走
/app/executions/{execution_id}/report（明细行就是 app_execution）。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, page_response
from app.crud.app_test import crud_app_execution, crud_app_suite_execution
from app.models.auth.user import User
from app.schemas.app_test import AppExecutionOut, AppSuiteExecutionOut
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.get("", summary="套件执行汇总列表（项目内）")
async def list_suite_executions(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
    suite_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    await require_project_access(db, project_id, current_user.id)
    rows, total = await crud_app_suite_execution.get_list(
        db,
        project_id,
        suite_id=suite_id,
        status=status_filter,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = []
    for execution, suite_name, device_model, device_platform in rows:
        out = AppSuiteExecutionOut.model_validate(execution)
        out.suite_name = suite_name
        out.device_name = device_model
        out.device_platform = device_platform
        items.append(out.model_dump(mode="json"))
    return page_response(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{execution_id}",
    summary="套件执行详情（含用例级明细）",
    response_model=ResponseModel[dict],
)
async def get_suite_execution(
    project_id: int,
    execution_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
):
    await require_project_access(db, project_id, current_user.id)
    execution = await crud_app_suite_execution.get_in_project(
        db, project_id, execution_id
    )
    if execution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="套件执行记录不存在")

    from app.crud.app_test import crud_app_suite

    suite = await crud_app_suite.get(db, execution.suite_id)
    out = AppSuiteExecutionOut.model_validate(execution)
    out.suite_name = suite.name if suite else None
    cases = [
        {
            **AppExecutionOut.model_validate(e).model_dump(mode="json"),
            "script_name": script_name,
        }
        for e, script_name in await crud_app_execution.get_by_suite_execution(
            db, execution_id
        )
    ]
    return ResponseModel(
        data={**out.model_dump(mode="json"), "cases": cases}
    )
