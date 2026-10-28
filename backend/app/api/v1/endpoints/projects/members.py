"""
项目成员管理 API 端点

处理项目成员的添加、移除、角色修改、退出等
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel
from app.crud.project import project_member
from app.models.auth.user import User
from app.schemas.project import (
    MemberCreate,
    MemberPermissionsResponse,
    MemberResponse,
    MemberRoleUpdate,
    ProjectTransferRequest,
    ProjectTransferResponse,
    UserInProject,
)
from app.services.project import member_service, project_service
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.get(
    "",
    summary="获取项目成员列表",
    response_model=ResponseModel[list[MemberResponse]],
)
async def get_project_members(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("member:view"))
    ],
    project_id: int = Query(..., description="项目ID"),
    role: str | None = Query(default=None, description="角色筛选（角色代码）"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
) -> ResponseModel[list[MemberResponse]]:
    """
    获取项目成员列表

    支持按角色筛选和关键词搜索

    - **role**: 筛选指定角色（owner/test_lead/tester/viewer）
    - **keyword**: 搜索用户名或姓名
    """
    # 检查访问权限（超级管理员默认有权限）
    await require_project_access(db, project_id, current_user.id)

    members = await project_member.get_members_by_project(
        db, project_id=project_id, role=role, keyword=keyword
    )

    items = []
    for m in members:
        items.append(
            MemberResponse(
                id=m.id,
                user=UserInProject.model_validate(m.user) if m.user else None,
                project_role=m.project_role,
                joined_at=m.created_at.isoformat() if m.created_at else None,
                last_active_at=(
                    m.last_active_at.isoformat() if m.last_active_at else None
                ),
            )
        )

    return ResponseModel(data=items)


@router.post(
    "",
    summary="添加项目成员",
    response_model=ResponseModel[dict],
)
async def add_project_members(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("member:add"))
    ],
    obj_in: MemberCreate,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[dict]:
    """
    添加项目成员

    只有项目负责人可以添加成员

    - **user_ids**: 用户ID列表
    - **project_role**: 项目角色（owner/test_lead/tester/viewer）
    """
    try:
        members = await member_service.add_members(
            db, project_id=project_id, obj_in=obj_in, operator_id=current_user.id
        )

        member_list = [
            {"id": m.id, "user_id": m.user_id, "project_role": m.project_role}
            for m in members
        ]

        return ResponseModel(
            data={
                "added_count": len(members),
                "members": member_list,
            },
            message="添加成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.put(
    "/{member_id}/role",
    summary="修改成员角色",
    response_model=ResponseModel[dict],
)
async def update_member_role(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("member:edit_role"))
    ],
    member_id: int,
    obj_in: MemberRoleUpdate,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[dict]:
    """
    修改成员角色

    只有项目负责人可以修改成员角色

    - **project_role**: 新角色（owner/test_lead/tester/viewer）
    """
    try:
        member = await member_service.update_member_role(
            db,
            project_id=project_id,
            member_id=member_id,
            obj_in=obj_in,
            operator_id=current_user.id,
        )

        return ResponseModel(
            data={"id": member.id, "project_role": member.project_role},
            message="角色修改成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.delete(
    "/{member_id}",
    summary="移除项目成员",
    response_model=ResponseModel[None],
)
async def remove_project_member(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("member:remove"))
    ],
    member_id: int,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[None]:
    """
    移除项目成员

    - 项目负责人可以移除任何成员（包括自己）
    - 其他成员只能退出项目（使用 /quit 接口）
    - 最后一个项目负责人不能被移除
    """
    try:
        await member_service.remove_member(
            db,
            project_id=project_id,
            member_id=member_id,
            operator_id=current_user.id,
        )
        return ResponseModel(message="移除成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/quit",
    summary="退出项目",
    response_model=ResponseModel[None],
)
async def quit_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[None]:
    """
    退出项目

    用户主动退出项目

    注意：项目负责人不能退出，需要先转让负责人
    """
    try:
        await member_service.quit_project(
            db, project_id=project_id, user_id=current_user.id
        )
        return ResponseModel(message="已退出项目")
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.get(
    "/permissions",
    summary="获取用户在项目中的权限",
    response_model=ResponseModel[MemberPermissionsResponse],
)
async def get_user_permissions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[MemberPermissionsResponse]:
    """
    获取当前用户在项目中的权限信息

    返回用户在项目中的角色、权限列表等
    """
    # 获取权限信息
    permissions = await project_service.get_user_permissions(
        db, project_id=project_id, user_id=current_user.id
    )

    # 如果不是成员，返回空权限
    if permissions["project_role"] is None:
        return ResponseModel(
            data=MemberPermissionsResponse(
                project_role=None,
                permissions=[],
                can_edit_project=False,
                can_manage_members=False,
                can_delete_project=False,
            )
        )

    return ResponseModel(
        data=MemberPermissionsResponse(
            project_role=permissions["project_role"],
            permissions=permissions["permissions"],
            can_edit_project=permissions["can_edit_project"],
            can_manage_members=permissions["can_manage_members"],
            can_delete_project=permissions["can_delete_project"],
        )
    )


@router.post(
    "/transfer",
    summary="转让项目",
    response_model=ResponseModel[ProjectTransferResponse],
)
async def transfer_project_ownership(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("member:edit_role"))
    ],
    obj_in: ProjectTransferRequest,
    project_id: int = Query(..., description="项目ID"),
) -> ResponseModel[ProjectTransferResponse]:
    """
    转让项目负责人

    只有项目负责人可以转让项目

    - **to_user_id**: 接收人用户ID

    转让后：
    - 原负责人角色改为项目成员（project_member）
    - 接收人角色改为项目负责人（project_owner）
    """
    try:
        result = await member_service.transfer_ownership(
            db,
            project_id=project_id,
            from_user_id=current_user.id,
            to_user_id=obj_in.to_user_id,
        )

        return ResponseModel(
            data=ProjectTransferResponse(
                from_user_id=result["from_user_id"],
                to_user_id=result["to_user_id"],
                from_user_new_role=result["from_user_new_role"],
                to_user_new_role=result["to_user_new_role"],
            ),
            message="项目转让成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
