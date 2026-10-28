"""测试需求管理 API

需求理解已迁移至统一 AI 任务框架（task_type=understand_requirement，
见 app/ai_core/graphs/func_test/understand_requirement.py），
前端通过 /projects/{id}/ai-tasks 提交并订阅。
"""

from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.func_test.requirement import crud_requirement
from app.models.auth.user import User
from app.schemas.func_test.requirement import (
    AttachmentUploadResponse,
    RequirementCreate,
    RequirementListResponse,
    RequirementResponse,
    RequirementReview,
    RequirementUpdate,
)
from app.utils.document_storage import save_attachment_file
from app.utils.project_permission import require_project_access
from app.utils.storage_utils import get_access_url

router = APIRouter()


# ─── 附件上传 ────────────────────────────────────────────────


@router.post(
    "/attachments",
    summary="上传需求附件图片",
    response_model=ResponseModel[AttachmentUploadResponse],
)
async def upload_attachment(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:create"))
    ],
    file: UploadFile = File(...),
) -> ResponseModel[AttachmentUploadResponse]:
    """上传需求附件图片，返回可访问 URL（供前端塞入 attachments 数组）"""
    await require_project_access(db, project_id, current_user.id)
    storage_key = await save_attachment_file(file, project_id)
    url = get_access_url(storage_key)
    return success_response(data=AttachmentUploadResponse(url=url))


# ─── 需求 CRUD ───────────────────────────────────────────────


@router.post(
    "",
    summary="创建需求",
    response_model=ResponseModel[RequirementResponse],
)
async def create_requirement(
    project_id: int,
    body: RequirementCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:create"))
    ],
) -> ResponseModel[RequirementResponse]:
    await require_project_access(db, project_id, current_user.id)
    req = await crud_requirement.create(
        db,
        project_id=project_id,
        title=body.title,
        code=body.code,
        module_id=body.module_id,
        priority=body.priority,
        description=body.description,
        acceptance_criteria=body.acceptance_criteria,
        attachments=body.attachments,
        source="manual",
        created_by=current_user.id,
    )
    return success_response(data=RequirementResponse.model_validate(req))


@router.get(
    "",
    summary="获取需求列表",
    response_model=ResponseModel[RequirementListResponse],
)
async def list_requirements(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
    status_: Optional[str] = Query(default=None, alias="status"),
    source: Optional[str] = Query(default=None),
    module_id: Optional[int] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
) -> ResponseModel[RequirementListResponse]:
    await require_project_access(db, project_id, current_user.id)
    reqs, total = await crud_requirement.get_by_project(
        db,
        project_id=project_id,
        status=status_,
        source=source,
        module_id=module_id,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )

    # 批量统计各需求的关联用例数（避免 N+1）
    from sqlalchemy import func as sa_func
    from sqlalchemy import select

    from app.models.func_test.test_case import FuncTestCase

    count_map: dict[int, int] = {}
    req_ids = [r.id for r in reqs]
    if req_ids:
        rows = await db.execute(
            select(
                FuncTestCase.requirement_id,
                sa_func.count(FuncTestCase.id),
            )
            .where(
                FuncTestCase.requirement_id.in_(req_ids),
                FuncTestCase.is_deleted.is_(False),
            )
            .group_by(FuncTestCase.requirement_id)
        )
        count_map = {row[0]: row[1] for row in rows.all()}

    items = []
    for r in reqs:
        item = RequirementResponse.model_validate(r)
        item.case_count = count_map.get(r.id, 0)
        items.append(item)

    return success_response(
        data=RequirementListResponse(total=total, items=items)
    )


@router.get(
    "/{req_id}",
    summary="获取需求详情",
    response_model=ResponseModel[RequirementResponse],
)
async def get_requirement(
    project_id: int,
    req_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
) -> ResponseModel[RequirementResponse]:
    await require_project_access(db, project_id, current_user.id)
    req = await crud_requirement.get(db, req_id)
    if not req or req.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="需求不存在")
    return success_response(data=RequirementResponse.model_validate(req))


@router.put(
    "/{req_id}",
    summary="更新需求",
    response_model=ResponseModel[RequirementResponse],
)
async def update_requirement(
    project_id: int,
    req_id: int,
    body: RequirementUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[RequirementResponse]:
    await require_project_access(db, project_id, current_user.id)
    req = await crud_requirement.get(db, req_id)
    if not req or req.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="需求不存在")
    req = await crud_requirement.update(
        db, req=req, **body.model_dump(exclude_none=True)
    )
    return success_response(data=RequirementResponse.model_validate(req))


@router.delete(
    "/{req_id}",
    summary="删除需求",
    response_model=ResponseModel,
)
async def delete_requirement(
    project_id: int,
    req_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:delete"))
    ],
) -> ResponseModel:
    await require_project_access(db, project_id, current_user.id)
    req = await crud_requirement.get(db, req_id)
    if not req or req.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="需求不存在")
    await crud_requirement.soft_delete(db, req=req)
    return success_response(message="需求已删除")


@router.post(
    "/{req_id}/review",
    summary="审核需求",
    response_model=ResponseModel[RequirementResponse],
)
async def review_requirement(
    project_id: int,
    req_id: int,
    body: RequirementReview,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[RequirementResponse]:
    await require_project_access(db, project_id, current_user.id)
    if body.action not in ("approve", "reject"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="action 必须是 approve 或 reject",
        )
    req = await crud_requirement.get(db, req_id)
    if not req or req.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="需求不存在")
    req = await crud_requirement.review(
        db,
        req=req,
        action=body.action,
        reviewer_id=current_user.id,
        review_comment=body.review_comment,
    )
    return success_response(data=RequirementResponse.model_validate(req))
