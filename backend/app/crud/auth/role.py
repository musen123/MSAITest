"""
角色 CRUD 操作
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.auth.role import Role
from app.models.auth.role_permission import RolePermission
from app.schemas.auth.role_manage import CreateRoleRequest, UpdateRoleRequest


class CRUDRole(CRUDBase[Role, CreateRoleRequest, UpdateRoleRequest]):
    """
    角色 CRUD 操作类
    """

    async def get_by_code(
        self,
        db: AsyncSession,
        *,
        code: str,
    ) -> Optional[Role]:
        """
        根据角色编码获取角色

        Args:
            db: 数据库会话
            code: 角色编码

        Returns:
            Optional[Role]: 角色实例，不存在返回 None
        """
        stmt = select(Role).where(Role.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_system_roles(
        self,
        db: AsyncSession,
    ) -> list[Role]:
        """
        获取所有系统预定义角色

        Args:
            db: 数据库会话

        Returns:
            list[Role]: 系统角色列表
        """
        stmt = select(Role).where(Role.is_system.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_custom_roles(
        self,
        db: AsyncSession,
    ) -> list[Role]:
        """
        获取所有自定义角色

        Args:
            db: 数据库会话

        Returns:
            list[Role]: 自定义角色列表
        """
        stmt = select(Role).where(Role.is_system.is_(False))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def code_exists(
        self,
        db: AsyncSession,
        *,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查角色编码是否存在

        Args:
            db: 数据库会话
            code: 角色编码
            exclude_id: 排除的角色ID（用于更新时检查）

        Returns:
            bool: 编码是否存在
        """
        stmt = select(Role).where(Role.code == code)

        if exclude_id:
            stmt = stmt.where(Role.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_with_relations(
        self,
        db: AsyncSession,
        *,
        role_id: int,
    ) -> Optional[Role]:
        """
        根据 ID 获取角色（包含权限关系）

        预加载权限关系，避免异步懒加载问题：
        Role -> RolePermission -> Permission

        Args:
            db: 数据库会话
            role_id: 角色 ID

        Returns:
            Optional[Role]: 角色实例，不存在返回 None
        """
        stmt = (
            select(Role)
            .options(
                selectinload(Role.role_permissions).selectinload(
                    RolePermission.permission
                )
            )
            .where(Role.id == role_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_with_relations(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Role]:
        """
        获取角色列表（预加载权限关系）

        预加载权限关系，避免异步懒加载问题：
        Role -> RolePermission -> Permission

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 限制数量

        Returns:
            list[Role]: 角色列表
        """
        stmt = (
            select(Role)
            .options(
                selectinload(Role.role_permissions).selectinload(
                    RolePermission.permission
                )
            )
            .order_by(Role.id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# 创建单例实例
role_crud = CRUDRole(Role)
