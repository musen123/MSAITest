"""
环境变量 CRUD 操作
"""

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.test_environment.variable import EnvironmentVariable
from app.schemas.test_environment.variable import (
    EnvironmentVariableCreate,
    EnvironmentVariableUpdate,
)


class CRUDEnvironmentVariable(
    CRUDBase[EnvironmentVariable, EnvironmentVariableCreate, EnvironmentVariableUpdate]
):
    """
    环境变量 CRUD 操作类
    """

    async def get_by_env_and_name(
        self,
        db: AsyncSession,
        *,
        env_id: int,
        name: str,
    ) -> Optional[EnvironmentVariable]:
        """
        根据环境ID和变量名获取变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            name: 变量名

        Returns:
            Optional[EnvironmentVariable]: 变量实例
        """
        stmt = select(EnvironmentVariable).where(
            EnvironmentVariable.env_id == env_id,
            EnvironmentVariable.name == name,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_by_env(
        self,
        db: AsyncSession,
        *,
        env_id: int,
        skip: int = 0,
        limit: int = 100,
        keyword: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> tuple[list[EnvironmentVariable], int]:
        """
        获取环境的变量列表

        Args:
            db: 数据库会话
            env_id: 环境ID
            skip: 跳过数量
            limit: 限制数量
            keyword: 搜索关键词
            is_active: 是否仅获取启用的变量

        Returns:
            tuple[list[EnvironmentVariable], int]: 变量列表和总数
        """
        stmt = select(EnvironmentVariable).where(EnvironmentVariable.env_id == env_id)
        count_stmt = select(func.count(EnvironmentVariable.id)).where(
            EnvironmentVariable.env_id == env_id
        )

        # 关键词搜索
        if keyword:
            search_filter = or_(
                EnvironmentVariable.name.like(f"%{keyword}%"),
                EnvironmentVariable.description.like(f"%{keyword}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # 启用状态筛选
        if is_active is not None:
            stmt = stmt.where(EnvironmentVariable.is_active == is_active)
            count_stmt = count_stmt.where(EnvironmentVariable.is_active == is_active)

        # 排序：按 sort_order 升序
        stmt = stmt.order_by(
            EnvironmentVariable.sort_order.asc(), EnvironmentVariable.id.asc()
        )

        # 分页
        stmt = stmt.offset(skip).limit(limit)

        # 执行查询
        result = await db.execute(stmt)
        variables = list(result.scalars().all())

        # 获取总数
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one() or 0

        return variables, total

    async def name_exists(
        self,
        db: AsyncSession,
        *,
        env_id: int,
        name: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查变量名是否存在

        Args:
            db: 数据库会话
            env_id: 环境ID
            name: 变量名
            exclude_id: 排除的变量ID

        Returns:
            bool: 是否存在
        """
        stmt = select(EnvironmentVariable).where(
            EnvironmentVariable.env_id == env_id,
            EnvironmentVariable.name == name,
        )

        if exclude_id:
            stmt = stmt.where(EnvironmentVariable.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def batch_update(
        self,
        db: AsyncSession,
        *,
        env_id: int,
        updates: list[dict],
    ) -> int:
        """
        批量更新变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            updates: 更新数据列表，每项包含 id 和要更新的字段

        Returns:
            int: 更新数量
        """
        updated_count = 0
        for update_data in updates:
            var_id = update_data.get("id")
            if not var_id:
                continue

            var_obj = await self.get(db, id=var_id)
            if var_obj and var_obj.env_id == env_id:
                # 移除 id 字段，只更新其他字段
                update_fields = {k: v for k, v in update_data.items() if k != "id"}
                if update_fields:
                    await self.update(db, db_obj=var_obj, obj_in=update_fields)
                    updated_count += 1

        return updated_count

    async def batch_create(
        self,
        db: AsyncSession,
        *,
        env_id: int,
        variables: list[dict],
    ) -> list[EnvironmentVariable]:
        """
        批量创建变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            variables: 变量数据列表

        Returns:
            list[EnvironmentVariable]: 创建的变量列表
        """
        created_vars = []
        for var_data in variables:
            var_data["env_id"] = env_id
            var_obj = await self.create(db, obj_in=var_data)
            created_vars.append(var_obj)

        return created_vars

    async def batch_delete(
        self,
        db: AsyncSession,
        *,
        env_id: int,
        ids: list[int],
    ) -> int:
        """
        批量删除变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            ids: 变量ID列表

        Returns:
            int: 删除数量
        """
        deleted_count = 0
        for var_id in ids:
            var = await self.get(db, id=var_id)
            if var and var.env_id == env_id:
                await self.delete(db, id=var_id)
                deleted_count += 1

        return deleted_count

    async def delete_by_env(
        self,
        db: AsyncSession,
        *,
        env_id: int,
    ) -> int:
        """
        删除环境的所有变量

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            int: 删除数量
        """
        stmt = select(EnvironmentVariable).where(EnvironmentVariable.env_id == env_id)
        result = await db.execute(stmt)
        variables = result.scalars().all()

        deleted_count = 0
        for var in variables:
            await db.delete(var)
            deleted_count += 1

        await db.commit()
        return deleted_count

    async def get_max_sort_order(
        self,
        db: AsyncSession,
        *,
        env_id: int,
    ) -> int:
        """
        获取环境中变量的最大排序值

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            int: 最大排序值
        """
        stmt = select(func.max(EnvironmentVariable.sort_order)).where(
            EnvironmentVariable.env_id == env_id
        )
        result = await db.execute(stmt)
        max_order = result.scalar_one()
        return max_order if max_order is not None else 0


# 创建实例
environment_variable = CRUDEnvironmentVariable(EnvironmentVariable)
