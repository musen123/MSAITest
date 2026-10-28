"""
角色管理 API

角色列表、详情、创建、更新、删除等角色管理接口
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.auth import permission_crud, role_crud
from app.models.auth.user import User
from app.schemas.auth.role_manage import (
    CreateRoleRequest,
    PermissionListItem,
    PermissionModule,
    PermissionsResponse,
    RoleDetailResponse,
    RoleListItem,
    UpdateRoleRequest,
)

router = APIRouter()


@router.get(
    "",
    summary="获取角色列表",
    response_model=ResponseModel[list[RoleListItem]],
)
async def get_roles(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("role:view"))],
) -> ResponseModel[list[RoleListItem]]:
    """获取角色列表（需要 role:view 权限）"""
    # 使用带预加载的查询方法
    roles = await role_crud.get_multi_with_relations(db, skip=0, limit=100)
    return ResponseModel(
        data=[RoleListItem.model_validate(r) for r in roles],
        message="获取成功",
    )


@router.get(
    "/permissions",
    summary="获取所有权限列表",
    response_model=ResponseModel[PermissionsResponse],
)
async def get_permissions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("permission:view"))
    ],
) -> ResponseModel[PermissionsResponse]:
    """获取所有权限列表（按模块分组）"""
    grouped_permissions = await permission_crud.get_grouped_by_module(db)

    # 构建响应数据
    permission_modules = []
    for module, permissions in grouped_permissions.items():
        permission_modules.append(
            PermissionModule(
                module=module,
                permissions=[
                    PermissionListItem(
                        code=p.code,
                        name=p.name,
                    )
                    for p in permissions
                ],
            )
        )

    return ResponseModel(
        data=PermissionsResponse(data=permission_modules),
        message="获取成功",
    )


@router.get(
    "/{role_id}",
    summary="获取角色详情",
    response_model=ResponseModel[RoleDetailResponse],
)
async def get_role(
    role_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("role:view"))],
) -> ResponseModel[RoleDetailResponse]:
    """获取角色详情（需要 role:view 权限）"""
    # 使用带预加载的查询方法
    role = await role_crud.get_with_relations(db, role_id=role_id)
    if not role:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在",
        )

    return ResponseModel(data=RoleDetailResponse.model_validate(role))


@router.post(
    "",
    summary="创建角色",
    response_model=ResponseModel[dict],
)
async def create_role(
    obj_in: CreateRoleRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("role:create"))],
) -> ResponseModel[dict]:
    """创建角色（需要 role:create 权限）"""
    # 检查编码是否存在
    if await role_crud.code_exists(db, code=obj_in.code):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="角色编码已存在",
        )

    # 创建角色并关联权限
    from app.models.auth.permission import Permission
    from app.models.auth.role import Role
    from app.models.auth.role_permission import RolePermission

    # 1. 创建角色
    role = Role(
        code=obj_in.code,
        name=obj_in.name,
        description=obj_in.description,
        is_system=False,
    )
    db.add(role)
    await db.flush()  # flush 以获取 role.id

    # 2. 关联权限
    if obj_in.permissions:
        # 查询权限对象
        perm_stmt = select(Permission).where(Permission.code.in_(obj_in.permissions))
        perm_result = await db.execute(perm_stmt)
        permissions = perm_result.scalars().all()

        # 创建角色-权限关联
        for perm in permissions:
            role_permission = RolePermission(role_id=role.id, permission_id=perm.id)
            db.add(role_permission)

    await db.commit()
    await db.refresh(role)

    return ResponseModel(data={"id": role.id, "code": role.code}, message="创建成功")


@router.put(
    "/{role_id}",
    summary="更新角色",
    response_model=ResponseModel[dict],
)
async def update_role(
    role_id: int,
    obj_in: UpdateRoleRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("role:edit"))],
) -> ResponseModel[dict]:
    """更新角色（需要 role:edit 权限）"""
    # 使用带预加载的查询方法
    role = await role_crud.get_with_relations(db, role_id=role_id)
    if not role:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在",
        )

    # 系统预定义角色不能修改名称
    if role.is_system and obj_in.name:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="系统预定义角色不能修改名称",
        )

    # 更新角色字段
    if obj_in.name is not None:
        role.name = obj_in.name
    if obj_in.description is not None:
        role.description = obj_in.description

    # 更新权限关联（如果提供了权限列表）
    if obj_in.permissions is not None:
        from sqlalchemy import delete

        from app.models.auth.permission import Permission
        from app.models.auth.role_permission import RolePermission

        # 删除旧的权限关联
        await db.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )

        # 添加新的权限关联
        if obj_in.permissions:
            # 查询权限对象
            perm_stmt = select(Permission).where(
                Permission.code.in_(obj_in.permissions)
            )
            perm_result = await db.execute(perm_stmt)
            permissions = perm_result.scalars().all()

            # 创建角色-权限关联
            for perm in permissions:
                role_permission = RolePermission(role_id=role_id, permission_id=perm.id)
                db.add(role_permission)

    await db.commit()
    await db.refresh(role)

    return ResponseModel(data={"id": role.id, "code": role.code}, message="更新成功")


@router.delete(
    "/{role_id}",
    summary="删除角色",
    response_model=ResponseModel[None],
)
async def delete_role(
    role_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("role:delete"))],
) -> ResponseModel[None]:
    """删除角色（需要 role:delete 权限）"""
    role = await role_crud.get(db, id=role_id)
    if not role:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在",
        )

    if role.is_system:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="系统预定义角色不能删除",
        )

    success = await role_crud.delete(db, id=role_id)
    if not success:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="删除失败",
        )

    return ResponseModel(message="删除成功")

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。