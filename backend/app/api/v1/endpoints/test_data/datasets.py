"""测试数据集 API 端点

前缀：/projects/{project_id}/test-datasets
执行绑定：Web 执行配置选数据集+取行策略，选中行注入为变量覆盖（D3 接线）。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import PageResponseModel, ResponseModel, page_response, success_response
from app.crud.test_data import crud_test_dataset
from app.models.auth.user import User
from app.schemas.test_data import (
    TestDatasetCreate,
    TestDatasetListResponse,
    TestDatasetResponse,
    TestDatasetUpdate,
)
from app.schemas.test_data.dataset import _validate_columns_rows
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.post(
    "",
    response_model=ResponseModel[TestDatasetResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建测试数据集",
)
async def create_dataset(
    project_id: int,
    body: TestDatasetCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:create"))],
) -> ResponseModel[TestDatasetResponse]:
    await require_project_access(db, project_id, current_user.id)
    if await crud_test_dataset.get_by_name(db, project_id=project_id, name=body.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"数据集「{body.name}」已存在")
    obj = await crud_test_dataset.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        name=body.name,
        description=body.description,
        columns=body.columns,
        rows=body.rows,
        source=body.source,
    )
    return success_response(data=TestDatasetResponse.model_validate(obj))


@router.get("", response_model=PageResponseModel[TestDatasetListResponse], summary="测试数据集列表")
async def list_datasets(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = Query(default=None),
) -> PageResponseModel[TestDatasetListResponse]:
    await require_project_access(db, project_id, current_user.id)
    items, total = await crud_test_dataset.list_by_project(
        db,
        project_id=project_id,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return page_response(
        items=[TestDatasetListResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{dataset_id}",
    response_model=ResponseModel[TestDatasetResponse],
    summary="数据集详情（含数据行）",
)
async def get_dataset(
    project_id: int,
    dataset_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:view"))],
) -> ResponseModel[TestDatasetResponse]:
    await require_project_access(db, project_id, current_user.id)
    obj = await crud_test_dataset.get_detail(db, dataset_id=dataset_id, project_id=project_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="数据集不存在")
    return success_response(data=TestDatasetResponse.model_validate(obj))


@router.put(
    "/{dataset_id}",
    response_model=ResponseModel[TestDatasetResponse],
    summary="更新测试数据集",
)
async def update_dataset(
    project_id: int,
    dataset_id: int,
    body: TestDatasetUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:edit"))],
) -> ResponseModel[TestDatasetResponse]:
    await require_project_access(db, project_id, current_user.id)
    obj = await crud_test_dataset.get_detail(db, dataset_id=dataset_id, project_id=project_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="数据集不存在")
    values = body.model_dump(exclude_unset=True)
    if "name" in values and values["name"] != obj.name:
        if await crud_test_dataset.get_by_name(db, project_id=project_id, name=values["name"]):
            raise HTTPException(status.HTTP_409_CONFLICT, detail=f"数据集「{values['name']}」已存在")
    # 单独改 rows（不带 columns）时用库中现有列定义做行键校验
    if "rows" in values and "columns" not in values:
        try:
            _validate_columns_rows(obj.columns or [], values["rows"])
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    obj = await crud_test_dataset.update(db, db_obj=obj, values=values)
    return success_response(data=TestDatasetResponse.model_validate(obj))


@router.delete("/{dataset_id}", response_model=ResponseModel, summary="删除测试数据集（软删）")
async def delete_dataset(
    project_id: int,
    dataset_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:delete"))],
) -> ResponseModel:
    await require_project_access(db, project_id, current_user.id)
    ok = await crud_test_dataset.soft_delete(db, dataset_id=dataset_id, project_id=project_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="数据集不存在")
    return success_response(message="删除成功")
