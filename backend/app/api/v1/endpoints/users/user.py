"""
用户管理 API

用户列表、详情、创建、更新、删除等用户管理接口
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import PageResponseModel, ResponseModel
from app.core.security import get_password_hash, verify_password
from app.crud.auth import user_crud
from app.models.auth.user import User, UserStatus
from app.schemas.auth.role_manage import UserPermissionsResponse
from app.schemas.auth.user_manage import (
    AssignRoleRequest,
    ChangePasswordRequest,
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UpdateUserStatusRequest,
    UserDetailResponse,
    UserListItem,
)
from app.utils import delete_avatar_file, save_avatar_file, validate_avatar_file

router = APIRouter()


@router.get(
    "",
    summary="获取用户列表",
    response_model=PageResponseModel[UserListItem],
)
async def get_users(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("user:view"))],
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(None, description="搜索关键词"),
    status: UserStatus | None = Query(None, description="状态筛选"),
    role_id: int | None = Query(None, ge=1, description="角色筛选"),
) -> PageResponseModel[UserListItem]:
    """获取用户列表（需要 user:view 权限）"""
    skip = (page - 1) * page_size

    # 使用带预加载的查询方法
    users = await user_crud.get_multi_with_relations(
        db,
        skip=skip,
        limit=page_size,
        keyword=keyword,
        status=status,
        role_id=role_id,
    )
    total = await user_crud.count_search(
        db, keyword=keyword, status=status, role_id=role_id
    )

    from app.core.response import page_response

    return page_response(
        items=[UserListItem.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}",
    summary="获取用户详情",
    response_model=ResponseModel[UserDetailResponse],
)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
) -> ResponseModel[UserDetailResponse]:
    """获取用户详情（查看他人信息需要 user:view 权限，查看自己无需额外权限）"""
    from fastapi import HTTPException, status as http_status

    # 查看他人信息需要 user:view 权限
    if current_user.id != user_id and "user:view" not in current_user.permissions:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="没有权限查看其他用户信息",
        )

    user = await user_crud.get_with_relations(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return ResponseModel(data=UserDetailResponse.model_validate(user))


@router.post(
    "",
    summary="创建用户",
    response_model=ResponseModel[dict],
)
async def create_user(
    obj_in: CreateUserRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("user:create"))],
) -> ResponseModel[dict]:
    """创建用户（需要 user:create 权限）"""
    from fastapi import HTTPException, status

    # 检查用户名是否已存在
    existing_user = await user_crud.get_by_username(db, username=obj_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # 检查邮箱是否已存在
    existing_email = await user_crud.get_by_email(db, email=obj_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被注册",
        )

    # 检查手机号是否已存在
    if obj_in.phone:
        existing_phone = await user_crud.get_by_phone(db, phone=obj_in.phone)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="手机号已被注册",
            )

    hashed_password = get_password_hash(obj_in.password)

    # 未指定角色时自动分配默认"普通用户"角色
    if not obj_in.role_ids:
        from sqlalchemy import select
        from app.models.auth.role import Role
        role_result = await db.execute(
            select(Role).where(Role.code == "user", Role.deleted_at.is_(None))
        )
        default_role = role_result.scalar_one_or_none()
        if default_role:
            obj_in.role_ids = [default_role.id]

    user = await user_crud.create(db, obj_in=obj_in, hashed_password=hashed_password)

    return ResponseModel(
        data={"id": user.id, "username": user.username}, message="创建成功"
    )


@router.put(
    "/{user_id}",
    summary="更新用户信息",
    response_model=ResponseModel[dict],
)
async def update_user(
    user_id: int,
    obj_in: UpdateUserRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
) -> ResponseModel[dict]:
    """更新用户信息

    编辑他人需要 user:edit 权限；编辑**本人**资料无需额外权限。
    UpdateUserRequest 仅含 email/phone/real_name/bio，不涉及状态与角色，
    故本人自助编辑无越权风险（角色分配走独立的 /{user_id}/roles 接口）。
    """
    from fastapi import HTTPException, status

    if current_user.id != user_id and "user:edit" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限编辑其他用户信息",
        )

    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    updated_user = await user_crud.update(db, db_obj=user, obj_in=obj_in)
    return ResponseModel(data={"id": updated_user.id}, message="更新成功")


@router.put(
    "/{user_id}/roles",
    summary="为用户分配角色",
    response_model=ResponseModel[None],
)
async def assign_user_roles(
    user_id: int,
    obj_in: AssignRoleRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("user:edit"))],
) -> ResponseModel[None]:
    """为用户分配角色（需要 user:edit 权限）"""
    user = await user_crud.get(db, id=user_id)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    await user_crud.assign_roles(db, user=user, role_ids=obj_in.role_ids)
    return ResponseModel(message="角色分配成功")


@router.put(
    "/{user_id}/password",
    summary="修改密码",
    response_model=ResponseModel[None],
)
async def change_password(
    user_id: int,
    obj_in: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> ResponseModel[None]:
    """修改密码（用户本人）"""
    if current_user.id != user_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能修改自己的密码",
        )

    # 获取用户（需要密码哈希）
    user = await user_crud.get(db, id=user_id)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 验证旧密码
    if not verify_password(obj_in.old_password, user.password_hash):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误",
        )

    # 生成新密码哈希并更新
    hashed_password = get_password_hash(obj_in.new_password)
    await user_crud.update_password(db, user=user, hashed_password=hashed_password)

    return ResponseModel(message="密码修改成功")


@router.post(
    "/{user_id}/reset-password",
    summary="重置密码",
    response_model=ResponseModel[None],
)
async def reset_password(
    user_id: int,
    obj_in: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("user:edit"))],
) -> ResponseModel[None]:
    """重置密码（管理员）"""
    user = await user_crud.get(db, id=user_id)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    hashed_password = get_password_hash(obj_in.new_password)
    await user_crud.update_password(db, user=user, hashed_password=hashed_password)

    return ResponseModel(message="密码重置成功")


@router.post("/{user_id}/avatar", summary="上传头像")
async def upload_avatar(
    user_id: int,
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> ResponseModel[dict]:
    """
    上传用户头像

    - 支持的格式：JPG、JPEG、PNG、WEBP
    - 文件大小限制：2MB
    - 用户只能上传自己的头像
    """
    # 检查权限：用户只能上传自己的头像
    if current_user.id != user_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能上传自己的头像",
        )

    # 验证文件
    validate_avatar_file(file)

    # 获取用户当前头像
    user = await user_crud.get(db, id=user_id)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 保存新头像
    avatar_path = await save_avatar_file(file, user_id)

    # 删除旧头像文件
    if user.avatar:
        delete_avatar_file(user.avatar)

    # 更新用户头像
    user.avatar = avatar_path
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return ResponseModel(data={"url": avatar_path}, message="头像上传成功")


@router.put(
    "/{user_id}/status",
    summary="更新用户状态",
    response_model=ResponseModel[None],
)
async def update_user_status(
    user_id: int,
    obj_in: UpdateUserStatusRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("user:edit"))],
) -> ResponseModel[None]:
    """更新用户状态（需要 user:edit 权限）"""
    # 获取用户（包含角色信息）
    user = await user_crud.get_with_relations(db, user_id=user_id)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 检查是否是超级管理员
    super_admin_role = None
    for user_role in user.user_roles:
        if user_role.role.code == "super_admin":
            super_admin_role = user_role.role
            break

    if super_admin_role is not None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="超级管理员不能被禁用",
        )

    from app.models.auth.user import UserStatus

    status = UserStatus(obj_in.status)
    await user_crud.update_status(db, user=user, status=status)

    return ResponseModel(message="状态更新成功")


@router.delete(
    "/{user_id}",
    summary="删除用户",
    response_model=ResponseModel[None],
)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("user:delete"))],
) -> ResponseModel[None]:
    """删除用户（需要 user:delete 权限）"""
    # 获取用户（包含角色信息）
    user = await user_crud.get_with_relations(db, user_id=user_id)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 检查是否是超级管理员
    super_admin_role = None
    for user_role in user.user_roles:
        if user_role.role.code == "super_admin":
            super_admin_role = user_role.role
            break

    if super_admin_role is not None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="超级管理员不能被删除",
        )

    success = await user_crud.delete(db, id=user_id)
    if not success:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return ResponseModel(message="删除成功")


@router.get(
    "/{user_id}/permissions",
    summary="获取用户权限",
    response_model=ResponseModel[UserPermissionsResponse],
)
async def get_user_permissions(
    user_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
) -> ResponseModel[UserPermissionsResponse]:
    """获取用户的角色和权限列表（查看他人需要 user:view 权限，查看本人无需额外权限）"""

    from fastapi import HTTPException, status as http_status
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    if current_user.id != user_id and "user:view" not in current_user.permissions:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="没有权限查看其他用户信息",
        )

    from app.models.auth.role import Role
    from app.models.auth.user_role import UserRole

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.user_roles)
            .selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 构建响应数据
    roles_data = [
        {"id": role.id, "code": role.code, "name": role.name} for role in user.roles
    ]

    return ResponseModel(
        data=UserPermissionsResponse(
            roles=roles_data,
            permissions=user.permissions,
        ),
        message="获取成功",
    )
