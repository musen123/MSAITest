"""
项目模块管理 API 端点

处理项目模块的 CRUD 操作、移动、树形结构等
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel
from app.crud.project import project_module
from app.models.auth.user import User
from app.schemas.project import (
    ModuleCreate,
    ModuleMove,
    ModuleResponse,
    ModuleTreeNode,
    ModuleUpdate,
)
from app.services.project import module_service
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.get(
    "/tree",
    summary="获取模块树",
    response_model=ResponseModel[list[ModuleTreeNode]],
)
async def get_module_tree(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("module:view"))
    ],
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[list[ModuleTreeNode]]:
    """
    获取项目的完整模块树

    返回树形结构的模块列表，包含层级关系
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    tree = await module_service.build_module_tree(db, project_id=project_id)

    return ResponseModel(data=tree)


@router.get(
    "/{module_id}",
    summary="获取模块详情",
    response_model=ResponseModel[ModuleResponse],
)
async def get_module(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("module:view"))
    ],
    module_id: int,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[ModuleResponse]:
    """
    获取模块详情

    返回指定模块的详细信息
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    module_obj = await project_module.get_by_project(
        db, project_id=project_id, module_id=module_id
    )

    if not module_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模块不存在",
        )

    # 获取子模块数量
    children_count = await project_module.count_children(db, parent_id=module_id)

    return ResponseModel(
        data=ModuleResponse(
            id=module_obj.id,
            name=module_obj.name,
            parent_id=module_obj.parent_id,
            sort_order=module_obj.sort_order,
            description=module_obj.description,
            path=module_obj.path,
            case_count=0,  # TODO: 实现用例统计
            children_count=children_count,
            created_at=(
                module_obj.created_at.isoformat() if module_obj.created_at else None
            ),
            updated_at=(
                module_obj.updated_at.isoformat() if module_obj.updated_at else None
            ),
        )
    )


@router.post(
    "",
    summary="创建模块",
    response_model=ResponseModel[dict],
)
async def create_module(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("module:add"))
    ],
    obj_in: ModuleCreate,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[dict]:
    """
    创建模块

    项目成员可以创建模块

    - **name**: 模块名称（1-100字符）
    - **parent_id**: 父模块ID（可选，为空则创建根模块）
    - **sort_order**: 排序顺序（默认0）
    - **description**: 模块描述（可选）
    - **module_type**: 模块类型（默认feature）
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    try:
        module_obj = await module_service.create_module(
            db, project_id=project_id, obj_in=obj_in
        )
        return ResponseModel(
            data={"id": module_obj.id, "name": module_obj.name},
            message="创建成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.put(
    "/{module_id}",
    summary="更新模块",
    response_model=ResponseModel[dict],
)
async def update_module(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("module:edit"))
    ],
    module_id: int,
    obj_in: ModuleUpdate,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[dict]:
    """
    更新模块信息

    项目成员可以更新模块信息
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    try:
        module_obj = await module_service.update_module(
            db, project_id=project_id, module_id=module_id, obj_in=obj_in
        )
        return ResponseModel(
            data={"id": module_obj.id, "name": module_obj.name},
            message="更新成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/{module_id}/move",
    summary="移动模块",
    response_model=ResponseModel[dict],
)
async def move_module(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("module:edit"))
    ],
    module_id: int,
    obj_in: ModuleMove,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[dict]:
    """
    移动模块

    将模块移动到新的父模块下，并更新排序

    - **parent_id**: 新父模块ID（可选，为空则移动到根级）
    - **sort_order**: 新排序顺序
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    try:
        module_obj = await module_service.move_module(
            db, project_id=project_id, module_id=module_id, obj_in=obj_in
        )
        return ResponseModel(
            data={
                "id": module_obj.id,
                "parent_id": module_obj.parent_id,
                "sort_order": module_obj.sort_order,
            },
            message="移动成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{module_id}",
    summary="删除模块",
    response_model=ResponseModel[None],
)
async def delete_module(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("module:delete"))
    ],
    module_id: int,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[None]:
    """
    删除模块

    只能删除没有子模块且没有关联用例的模块
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    try:
        await module_service.delete_module(
            db, project_id=project_id, module_id=module_id
        )
        return ResponseModel(message="删除成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
