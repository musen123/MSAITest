"""测试文件资产 API 端点

前缀：/projects/{project_id}/test-files
上传走 multipart；资产名是项目内引用键（Web 脚本 ${{file:名}} 渲染期解析为
storage_key）。软删保留存储文件（v1 便于恢复；避免删除即打断在跑的回放）。
"""

import mimetypes
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import PageResponseModel, ResponseModel, page_response, success_response
from app.crud.test_data import crud_test_file_asset
from app.models.auth.user import User
from app.schemas.test_data import TestFileAssetListResponse, TestFileAssetResponse, TestFileAssetUpdate
from app.schemas.test_data.file_asset import validate_asset_name
from app.utils.project_permission import require_project_access
from app.utils.storage_utils import get_access_url, save_bytes

router = APIRouter()

# 单文件上限（内部平台；大文件测试场景由 AI 造数按 spec 生成，上传通道限普通样本）
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _to_response(obj) -> TestFileAssetResponse:
    resp = TestFileAssetResponse.model_validate(obj)
    resp.url = get_access_url(obj.storage_key)
    return resp


def build_asset_storage_key(project_id: int, file_name: str) -> str:
    ext = Path(file_name).suffix.lower()
    return f"test_data/{project_id}/{uuid.uuid4().hex}{ext}"


@router.post(
    "",
    response_model=ResponseModel[TestFileAssetResponse],
    status_code=status.HTTP_201_CREATED,
    summary="上传测试文件资产",
)
async def upload_file_asset(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:create"))],
    file: UploadFile = File(...),
    name: Optional[str] = Form(default=None, description="资产名（引用键），缺省用文件名去扩展"),
    spec: Optional[str] = Form(default=None, description="文件用途/内容说明"),
) -> ResponseModel[TestFileAssetResponse]:
    await require_project_access(db, project_id, current_user.id)
    file_name = file.filename or "unnamed"
    asset_name = (name or Path(file_name).stem).strip()
    try:
        validate_asset_name(asset_name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if await crud_test_file_asset.get_by_name(db, project_id=project_id, name=asset_name):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"资产名「{asset_name}」已存在（引用键须唯一）"
        )
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"文件超过上限 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )
    storage_key = build_asset_storage_key(project_id, file_name)
    save_bytes(content, storage_key)
    mime = file.content_type or mimetypes.guess_type(file_name)[0]
    obj = await crud_test_file_asset.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        name=asset_name,
        file_name=file_name,
        storage_key=storage_key,
        mime=mime,
        size_bytes=len(content),
        source="manual",
        spec=spec,
    )
    return success_response(data=_to_response(obj))


@router.get("", response_model=PageResponseModel[TestFileAssetListResponse], summary="文件资产列表")
async def list_file_assets(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None, description="manual/ai"),
) -> PageResponseModel[TestFileAssetListResponse]:
    await require_project_access(db, project_id, current_user.id)
    items, total = await crud_test_file_asset.list_by_project(
        db,
        project_id=project_id,
        keyword=keyword,
        source=source,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return page_response(
        items=[TestFileAssetListResponse.model_validate({**i.__dict__, "url": get_access_url(i.storage_key)}) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{asset_id}",
    response_model=ResponseModel[TestFileAssetResponse],
    summary="文件资产详情",
)
async def get_file_asset(
    project_id: int,
    asset_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:view"))],
) -> ResponseModel[TestFileAssetResponse]:
    await require_project_access(db, project_id, current_user.id)
    obj = await crud_test_file_asset.get_detail(db, asset_id=asset_id, project_id=project_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文件资产不存在")
    return success_response(data=_to_response(obj))


@router.put(
    "/{asset_id}",
    response_model=ResponseModel[TestFileAssetResponse],
    summary="更新文件资产（改名/说明）",
)
async def update_file_asset(
    project_id: int,
    asset_id: int,
    body: TestFileAssetUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:edit"))],
) -> ResponseModel[TestFileAssetResponse]:
    await require_project_access(db, project_id, current_user.id)
    obj = await crud_test_file_asset.get_detail(db, asset_id=asset_id, project_id=project_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文件资产不存在")
    values = body.model_dump(exclude_unset=True)
    if values.get("name") and values["name"] != obj.name:
        if await crud_test_file_asset.get_by_name(db, project_id=project_id, name=values["name"]):
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"资产名「{values['name']}」已存在"
            )
    obj = await crud_test_file_asset.update(db, db_obj=obj, values=values)
    return success_response(data=_to_response(obj))


@router.delete("/{asset_id}", response_model=ResponseModel, summary="删除文件资产（软删）")
async def delete_file_asset(
    project_id: int,
    asset_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("test_data:delete"))],
) -> ResponseModel:
    """软删。注意：若有 Web 脚本以 ${{file:名}} 引用该资产，删除后回放会失败——
    前端删除确认时提示；引用扫描/删除拦截列为后续增强。"""
    await require_project_access(db, project_id, current_user.id)
    ok = await crud_test_file_asset.soft_delete(db, asset_id=asset_id, project_id=project_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文件资产不存在")
    return success_response(message="删除成功")
