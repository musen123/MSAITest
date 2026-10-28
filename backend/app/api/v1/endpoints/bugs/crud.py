"""
Bug CRUD API 端点

处理 Bug 的创建、查询、更新、删除、归档操作。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.bug.bug import crud_bug
from app.crud.bug.bug_history import crud_bug_history
from app.models.auth.user import User
from app.models.bug.bug_history import BugAction
from app.schemas.bug.bug import (
    BugCreate,
    BugListItem,
    BugListResponse,
    BugResponse,
    BugUpdate,
)
from app.schemas.bug.bug_actions import BugArchive
from app.utils.project_permission import require_project_access

router = APIRouter()


def _build_bug_response(bug, has_ai_analysis: bool = False) -> BugResponse:
    """将 Bug ORM 对象转换为 BugResponse，补充关联字段名称。"""
    data = BugResponse.model_validate(bug)
    data.has_ai_analysis = has_ai_analysis
    if bug.module:
        data.module_name = bug.module.name
    if bug.assignee:
        data.assignee_name = bug.assignee.username
    if bug.creator:
        data.creator_name = bug.creator.username
    return data


def _build_list_item(bug) -> BugListItem:
    """将 Bug ORM 对象转换为列表简略项。"""
    item = BugListItem.model_validate(bug)
    if bug.module:
        item.module_name = bug.module.name
    if bug.assignee:
        item.assignee_name = bug.assignee.username
    if bug.creator:
        item.creator_name = bug.creator.username
    return item


@router.post(
    "",
    summary="创建 Bug",
    response_model=ResponseModel[BugResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_bug(
    project_id: int,
    body: BugCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:create")),
) -> ResponseModel[BugResponse]:
    """创建 Bug，自动生成编号，初始状态为 new（若已指派则为 assigned）。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        priority=body.priority,
        module_id=body.module_id,
        test_case_id=body.test_case_id,
        test_case_type=body.test_case_type,
        assigned_to=body.assigned_to,
        environment=body.environment,
        reproduction_steps=body.reproduction_steps,
        expected_result=body.expected_result,
        actual_result=body.actual_result,
        tags=body.tags,
        external_bug_key=body.external_bug_key,
    )
    await crud_bug_history.create(
        db,
        bug_id=bug.id,
        action=BugAction.CREATED.value,
        operated_by=current_user.id,
    )
    return ResponseModel(message="Bug 创建成功", data=_build_bug_response(bug))


@router.get(
    "/statistics",
    summary="Bug 统计概览",
    response_model=ResponseModel,
)
async def get_statistics(
    project_id: int,
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel:
    """获取 Bug 统计概览。"""
    await require_project_access(db, project_id, current_user.id)
    from datetime import date as date_type

    parsed_start = None
    parsed_end = None
    if start_date:
        try:
            parsed_start = date_type.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_date 格式无效，应为 YYYY-MM-DD",
            )
    if end_date:
        try:
            parsed_end = date_type.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date 格式无效，应为 YYYY-MM-DD",
            )

    stats = await crud_bug.get_statistics(
        db,
        project_id=project_id,
        start_date=parsed_start,
        end_date=parsed_end,
    )
    return ResponseModel(data=stats)


@router.get(
    "/trends",
    summary="Bug 趋势分析",
    response_model=ResponseModel,
)
async def get_trends(
    project_id: int,
    days: int = Query(default=30, description="最近天数：7/14/30/90"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel:
    """获取近 N 天的 Bug 趋势数据。"""
    await require_project_access(db, project_id, current_user.id)
    if days not in (7, 14, 30, 90):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="days 参数只允许 7/14/30/90",
        )
    trends = await crud_bug.get_trends(db, project_id=project_id, days=days)
    return ResponseModel(data=trends)


@router.get(
    "",
    summary="获取 Bug 列表",
    response_model=ResponseModel[BugListResponse],
)
async def list_bugs(
    project_id: int,
    status: Optional[str] = Query(default=None, description="状态筛选"),
    severity: Optional[str] = Query(default=None, description="严重程度筛选"),
    priority: Optional[str] = Query(default=None, description="优先级筛选"),
    assigned_to: Optional[int] = Query(default=None, description="指派人 ID"),
    module_id: Optional[int] = Query(default=None, description="模块 ID"),
    created_by: Optional[int] = Query(default=None, description="创建人 ID"),
    keyword: Optional[str] = Query(default=None, description="标题/编号模糊搜索"),
    is_archived: bool = Query(default=False, description="是否查询已归档"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel[BugListResponse]:
    """获取项目 Bug 列表，支持多维度筛选。"""
    await require_project_access(db, project_id, current_user.id)
    skip = (page - 1) * page_size
    bugs, total = await crud_bug.get_list(
        db,
        project_id=project_id,
        status=status,
        severity=severity,
        priority=priority,
        assigned_to=assigned_to,
        module_id=module_id,
        created_by=created_by,
        keyword=keyword,
        is_archived=is_archived,
        skip=skip,
        limit=page_size,
    )
    items = [_build_list_item(b) for b in bugs]
    return ResponseModel(
        data=BugListResponse(total=total, page=page, page_size=page_size, items=items)
    )


@router.get(
    "/{bug_id}",
    summary="获取 Bug 详情",
    response_model=ResponseModel[BugResponse],
)
async def get_bug(
    project_id: int,
    bug_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel[BugResponse]:
    """获取单条 Bug 详情。"""
    await require_project_access(db, project_id, current_user.id)
    from app.crud.bug.bug_ai_analysis import crud_bug_ai_analysis

    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    ai = await crud_bug_ai_analysis.get_by_bug(db, bug_id)
    return ResponseModel(data=_build_bug_response(bug, has_ai_analysis=ai is not None))


@router.put(
    "/{bug_id}",
    summary="更新 Bug",
    response_model=ResponseModel[BugResponse],
)
async def update_bug(
    project_id: int,
    bug_id: int,
    body: BugUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:edit")),
) -> ResponseModel[BugResponse]:
    """更新 Bug 基本信息（不含状态和指派人）。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    bug = await crud_bug.update(
        db,
        bug=bug,
        title=body.title,
        description=body.description,
        severity=body.severity,
        priority=body.priority,
        module_id=body.module_id,
        test_case_id=body.test_case_id,
        test_case_type=body.test_case_type,
        environment=body.environment,
        reproduction_steps=body.reproduction_steps,
        expected_result=body.expected_result,
        actual_result=body.actual_result,
        tags=body.tags,
        external_bug_key=body.external_bug_key,
    )
    return ResponseModel(data=_build_bug_response(bug))


@router.delete(
    "/{bug_id}",
    summary="删除 Bug",
    response_model=ResponseModel,
)
async def delete_bug(
    project_id: int,
    bug_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:delete")),
) -> ResponseModel:
    """软删除 Bug。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    await crud_bug.soft_delete(db, bug=bug)

    return ResponseModel(message="Bug 已删除")


@router.post(
    "/{bug_id}/archive",
    summary="归档 / 取消归档 Bug",
    response_model=ResponseModel,
)
async def archive_bug(
    project_id: int,
    bug_id: int,
    body: BugArchive,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:edit")),
) -> ResponseModel:
    """归档或取消归档 Bug。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    await crud_bug.archive(db, bug=bug, is_archived=body.is_archived)
    msg = "Bug 已归档" if body.is_archived else "Bug 已取消归档"
    return ResponseModel(message=msg)
