"""
项目权限检查工具

提供统一的项目访问权限检查逻辑
超级管理员默认拥有所有项目的访问权限
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.project import project as project_crud
from app.crud.project import project_member
from app.services.project.project_service import ProjectService


async def check_project_access(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    require_membership: bool = True,
) -> bool:
    """
    检查用户是否有项目访问权限

    超级管理员可以访问所有项目，无需是项目成员

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        require_membership: 是否要求必须是项目成员（False时公开项目也可访问）

    Returns:
        bool: 是否有访问权限

    Raises:
        HTTPException: 项目不存在时抛出 404 错误
    """
    from fastapi import HTTPException, status

    # 检查项目是否存在
    project_obj = await project_crud.get(db, id=project_id)
    if not project_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 超级管理员可以访问所有项目
    if await ProjectService._is_super_admin(db, user_id):
        return True

    # 公开项目所有人可访问（如果 require_membership 为 False）
    if not require_membership and project_obj.is_public:
        return True

    # 检查是否是项目成员
    return await project_member.is_member(db, project_id=project_id, user_id=user_id)


async def check_project_management_permission(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> bool:
    """
    检查用户是否有项目管理权限（编辑、删除、管理成员等）

    超级管理员默认拥有所有项目的管理权限

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID

    Returns:
        bool: 是否有管理权限
    """
    from fastapi import HTTPException, status

    # 检查项目是否存在
    project_obj = await project_crud.get(db, id=project_id)
    if not project_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 超级管理员拥有所有项目的管理权限
    if await ProjectService._is_super_admin(db, user_id):
        return True

    # 检查项目管理权限
    return await project_member.can_manage_project(
        db, project_id=project_id, user_id=user_id
    )


async def require_project_access(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    require_membership: bool = True,
) -> None:
    """
    要求项目访问权限，如果没有权限则抛出异常

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        require_membership: 是否要求必须是项目成员

    Raises:
        HTTPException: 没有访问权限时抛出 403 错误
    """
    from fastapi import HTTPException, status

    if not await check_project_access(db, project_id, user_id, require_membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )


async def require_project_management_permission(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> None:
    """
    要求项目管理权限，如果没有权限则抛出异常

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID

    Raises:
        HTTPException: 没有管理权限时抛出 403 错误
    """
    from fastapi import HTTPException, status

    if not await check_project_management_permission(db, project_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人可以执行此操作",
        )
