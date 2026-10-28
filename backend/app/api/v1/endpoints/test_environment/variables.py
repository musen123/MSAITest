"""
环境变量管理 API 端点

处理环境变量的 CRUD、批量操作、导入导出等操作
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel
from app.crud.test_environment import environment, environment_variable
from app.models.auth.user import User
from app.schemas.test_environment.variable import (
    EnvironmentVariableCreate,
    EnvironmentVariableResponse,
    EnvironmentVariableUpdate,
    VariableBatchDeleteRequest,
    VariableBatchDeleteResponse,
    VariableBatchUpdateRequest,
    VariableBatchUpdateResponse,
    VariableExportResponse,
    VariableImportRequest,
    VariableImportResponse,
)
from app.services.test_environment.variable_service import VariableService

router = APIRouter()


async def check_environment_access(
    db: AsyncSession,
    env_id: int,
    user_id: int,
) -> bool:
    """
    检查用户是否有环境访问权限

    系统管理员可以访问所有环境
    """
    # 获取环境
    env = await environment.get(db, id=env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境不存在",
        )

    # 系统管理员可以访问所有项目
    from app.services.project.project_service import ProjectService

    if await ProjectService._is_super_admin(db, user_id):
        return True

    from app.crud.project import project_member

    return await project_member.is_member(
        db, project_id=env.project_id, user_id=user_id
    )


@router.get(
    "",
    summary="获取环境变量列表",
    response_model=ResponseModel[list[EnvironmentVariableResponse]],
)
async def get_variables(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    env_id: int,
    project_id: int,
    keyword: str | None = Query(default=None, description="搜索关键词"),
) -> ResponseModel[list[EnvironmentVariableResponse]]:
    """
    获取环境变量列表

    支持按关键词搜索变量名

    - **keyword**: 搜索变量名
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    # 获取变量列表
    variables, _ = await environment_variable.get_multi_by_env(
        db, env_id=env_id, keyword=keyword
    )

    # 转换为响应格式（隐藏 password 类型的值）
    items = []
    for var in variables:
        items.append(
            EnvironmentVariableResponse(
                id=var.id,
                env_id=var.env_id,
                name=var.name,
                value="****" if var.type == "password" else var.value,
                type=var.type,
                description=var.description,
                is_active=var.is_active,
                sort_order=var.sort_order,
                created_at=var.created_at.isoformat() if var.created_at else "",
                updated_at=var.updated_at.isoformat() if var.updated_at else "",
            )
        )

    return ResponseModel(data=items)


@router.post(
    "",
    summary="创建变量",
    response_model=ResponseModel[dict],
)
async def create_variable(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:create"))
    ],
    obj_in: EnvironmentVariableCreate,
    env_id: int,
    project_id: int,
) -> ResponseModel[dict]:
    """
    创建环境变量

    - **name**: 变量名
    - **value**: 变量值
    - **type**: 变量类型（text/password/json/dynamic）
    - **description**: 变量描述
    - **is_active**: 是否启用
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        var = await VariableService.create_variable(
            db,
            env_id=env_id,
            name=obj_in.name,
            value=obj_in.value,
            var_type=obj_in.type,
            description=obj_in.description,
            is_active=obj_in.is_active,
        )
        return ResponseModel(
            data={"id": var.id, "name": var.name},
            message="创建成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.put(
    "/batch",
    summary="批量更新变量",
    response_model=ResponseModel[VariableBatchUpdateResponse],
)
async def batch_update_variables(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:edit"))
    ],
    update_data: VariableBatchUpdateRequest,
    env_id: int,
    project_id: int,
) -> ResponseModel[VariableBatchUpdateResponse]:
    """
    批量更新环境变量

    - **variables**: 变量列表，包含 id、value、is_active
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        result = await VariableService.batch_update_variables(
            db, env_id=env_id, update_data=update_data
        )
        return ResponseModel(
            data=VariableBatchUpdateResponse(**result),
            message="更新成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.put(
    "/{var_id}",
    summary="更新变量",
    response_model=ResponseModel[dict],
)
async def update_variable(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:edit"))
    ],
    var_id: int,
    obj_in: "EnvironmentVariableUpdate",
    env_id: int,
    project_id: int,
) -> ResponseModel[dict]:
    """
    更新环境变量

    - **value**: 变量值
    - **type**: 变量类型
    - **description**: 变量描述
    - **is_active**: 是否启用
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        # 先获取变量对象
        var = await environment_variable.get(db, id=var_id)
        if not var:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="变量不存在",
            )

        # 调用更新服务
        updated_var = await VariableService.update_variable(
            db,
            db_obj=var,
            value=obj_in.value,
            var_type=obj_in.type,
            description=obj_in.description,
            is_active=obj_in.is_active,
        )
        return ResponseModel(
            data={"id": updated_var.id, "name": updated_var.name},
            message="更新成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.delete(
    "/{var_id}",
    summary="删除变量",
    response_model=ResponseModel[None],
)
async def delete_variable(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:delete"))
    ],
    var_id: int,
    env_id: int,
    project_id: int,
) -> ResponseModel[None]:
    """
    删除环境变量
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        await VariableService.delete_variable(db, var_id=var_id)
        return ResponseModel(message="删除成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.delete(
    "/batch",
    summary="批量删除变量",
    response_model=ResponseModel[VariableBatchDeleteResponse],
)
async def batch_delete_variables(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:delete"))
    ],
    delete_data: VariableBatchDeleteRequest,
    env_id: int,
    project_id: int,
) -> ResponseModel[VariableBatchDeleteResponse]:
    """
    批量删除环境变量

    - **ids**: 变量ID列表
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        result = await VariableService.batch_delete_variables(
            db, env_id=env_id, delete_data=delete_data
        )
        return ResponseModel(
            data=VariableBatchDeleteResponse(**result),
            message="删除成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.get(
    "/export",
    summary="导出变量",
    response_model=ResponseModel[VariableExportResponse],
)
async def export_variables(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    env_id: int,
    project_id: int,
) -> ResponseModel[VariableExportResponse]:
    """
    导出环境变量

    导出为 JSON 格式，包含所有变量信息
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        export_data = await VariableService.export_variables(db, env_id=env_id)
        return ResponseModel(data=VariableExportResponse(**export_data))
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.post(
    "/import",
    summary="导入变量",
    response_model=ResponseModel[VariableImportResponse],
)
async def import_variables(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:edit"))
    ],
    import_data: VariableImportRequest,
    env_id: int,
    project_id: int,
) -> ResponseModel[VariableImportResponse]:
    """
    导入环境变量

    - **content**: 导入内容
    - **mode**: 导入模式（merge：合并/replace：替换）
    """
    # 检查访问权限
    if not await check_environment_access(db, env_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该环境",
        )

    try:
        result = await VariableService.import_variables(
            db, env_id=env_id, import_data=import_data
        )
        return ResponseModel(data=result, message="导入成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )
