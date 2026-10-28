"""
权限 CRUD 操作
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.auth.permission import Permission


class CRUDPermission(CRUDBase[Permission, None, None]):
    """
    权限 CRUD 操作类
    """

    async def get_by_code(
        self,
        db: AsyncSession,
        *,
        code: str,
    ) -> Optional[Permission]:
        """
        根据权限编码获取权限

        Args:
            db: 数据库会话
            code: 权限编码

        Returns:
            Optional[Permission]: 权限实例，不存在返回 None
        """
        stmt = select(Permission).where(Permission.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_module(
        self,
        db: AsyncSession,
        *,
        module: str,
    ) -> list[Permission]:
        """
        根据模块获取权限列表

        Args:
            db: 数据库会话
            module: 模块名称

        Returns:
            list[Permission]: 权限列表
        """
        stmt = select(Permission).where(Permission.module == module)
        stmt = stmt.order_by(Permission.sort_order)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_grouped_by_module(
        self,
        db: AsyncSession,
    ) -> dict[str, list[Permission]]:
        """
        按模块分组获取所有权限

        Args:
            db: 数据库会话

        Returns:
            dict[str, list[Permission]]: 按模块分组的权限字典
        """
        stmt = select(Permission).order_by(Permission.module, Permission.sort_order)
        result = await db.execute(stmt)
        permissions = result.scalars().all()

        grouped: dict[str, list[Permission]] = {}
        for perm in permissions:
            if perm.module not in grouped:
                grouped[perm.module] = []
            grouped[perm.module].append(perm)

        return grouped

    async def code_exists(
        self,
        db: AsyncSession,
        *,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查权限编码是否存在

        Args:
            db: 数据库会话
            code: 权限编码
            exclude_id: 排除的权限ID（用于更新时检查）

        Returns:
            bool: 编码是否存在
        """
        stmt = select(Permission).where(Permission.code == code)

        if exclude_id:
            stmt = stmt.where(Permission.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


# 创建单例实例
permission_crud = CRUDPermission(Permission)
