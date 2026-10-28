"""功能测试用例 API"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.func_test.test_case import (
    REVIEWABLE_STATUSES,
    crud_test_case,
)
from app.models.auth.user import User
from app.schemas.func_test.test_case import (
    TestCaseBatchReview,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseReview,
    TestCaseUpdate,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.post(
    "",
    summary="创建测试用例",
    response_model=ResponseModel[TestCaseResponse],
)
async def create_case(
    project_id: int,
    body: TestCaseCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:create"))
    ],
) -> ResponseModel[TestCaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    case = await crud_test_case.create(
        db,
        project_id=project_id,
        title=body.title,
        code=body.code,
        requirement_id=body.requirement_id,
        module_id=body.module_id,
        priority=body.priority,
        case_type=body.case_type,
        validation_level=body.validation_level,
        preconditions=body.preconditions,
        test_data=body.test_data,
        steps=[s.model_dump() for s in body.steps] if body.steps else None,
        expected_result=body.expected_result,
        tags=body.tags,
        ui_automatable=body.ui_automatable,
        created_by=current_user.id,
    )
    return success_response(data=TestCaseResponse.model_validate(case))


@router.get(
    "",
    summary="获取测试用例列表",
    response_model=ResponseModel[TestCaseListResponse],
)
async def list_cases(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
    requirement_id: Optional[int] = Query(default=None),
    module_id: Optional[int] = Query(default=None),
    status_: Optional[str] = Query(default=None, alias="status"),
    priority: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> ResponseModel[TestCaseListResponse]:
    await require_project_access(db, project_id, current_user.id)
    items, total = await crud_test_case.get_by_project(
        db,
        project_id=project_id,
        requirement_id=requirement_id,
        module_id=module_id,
        status=status_,
        priority=priority,
        source=source,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return success_response(
        data=TestCaseListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[TestCaseResponse.model_validate(c) for c in items],
        )
    )


@router.get(
    "/{case_id}",
    summary="获取测试用例详情",
    response_model=ResponseModel[TestCaseResponse],
)
async def get_case(
    project_id: int,
    case_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
) -> ResponseModel[TestCaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    case = await crud_test_case.get(db, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")
    return success_response(data=TestCaseResponse.model_validate(case))


@router.put(
    "/{case_id}",
    summary="更新测试用例",
    response_model=ResponseModel[TestCaseResponse],
)
async def update_case(
    project_id: int,
    case_id: int,
    body: TestCaseUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[TestCaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    case = await crud_test_case.get(db, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")

    update = body.model_dump(exclude_none=True)
    if body.steps is not None:
        update["steps"] = [s.model_dump() for s in body.steps]

    case = await crud_test_case.update(
        db, case=case, updated_by=current_user.id, **update
    )
    return success_response(data=TestCaseResponse.model_validate(case))


@router.post(
    "/batch-review",
    summary="批量评审测试用例",
    response_model=ResponseModel[dict],
)
async def batch_review_cases(
    project_id: int,
    body: TestCaseBatchReview,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[dict]:
    await require_project_access(db, project_id, current_user.id)
    if body.action not in ("approve", "reject"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="action 必须是 approve 或 reject",
        )
    reviewed = await crud_test_case.batch_review(
        db,
        project_id=project_id,
        case_ids=body.case_ids,
        action=body.action,
        reviewer_id=current_user.id,
        review_comment=body.review_comment,
    )
    return success_response(
        data={"reviewed": reviewed},
        message=f"已评审 {reviewed} 条用例",
    )


@router.post(
    "/{case_id}/review",
    summary="评审测试用例",
    response_model=ResponseModel[TestCaseResponse],
)
async def review_case(
    project_id: int,
    case_id: int,
    body: TestCaseReview,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[TestCaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    if body.action not in ("approve", "reject"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="action 必须是 approve 或 reject",
        )
    case = await crud_test_case.get(db, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")
    if case.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="仅草稿/待评审状态的用例可评审",
        )
    case = await crud_test_case.review(
        db,
        case=case,
        action=body.action,
        reviewer_id=current_user.id,
        review_comment=body.review_comment,
    )
    return success_response(data=TestCaseResponse.model_validate(case))


@router.delete(
    "/{case_id}",
    summary="删除测试用例",
    response_model=ResponseModel,
)
async def delete_case(
    project_id: int,
    case_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:delete"))
    ],
) -> ResponseModel:
    await require_project_access(db, project_id, current_user.id)
    case = await crud_test_case.get(db, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")
    await crud_test_case.soft_delete(db, case=case)
    return success_response(message="删除成功")
