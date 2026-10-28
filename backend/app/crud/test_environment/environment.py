"""
测试环境 CRUD 操作
"""

import json
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.test_environment.environment import TestEnvironment
from app.schemas.test_environment.environment import (
    EnvironmentCreate,
    EnvironmentUpdate,
)


class CRUDEnvironment(CRUDBase[TestEnvironment, EnvironmentCreate, EnvironmentUpdate]):
    """
    测试环境 CRUD 操作类
    """

    async def get_by_project_and_name(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
    ) -> Optional[TestEnvironment]:
        """
        根据项目ID和名称获取环境

        Args:
            db: 数据库会话
            project_id: 项目ID
            name: 环境名称

        Returns:
            Optional[TestEnvironment]: 环境实例
        """
        stmt = select(TestEnvironment).where(
            TestEnvironment.project_id == project_id,
            TestEnvironment.name == name,
            TestEnvironment.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_variables(
        self,
        db: AsyncSession,
        *,
        env_id: int,
    ) -> Optional[TestEnvironment]:
        """
        获取环境详情（包含变量）

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            Optional[TestEnvironment]: 环境实例
        """
        stmt = (
            select(TestEnvironment)
            .where(
                TestEnvironment.id == env_id,
                TestEnvironment.is_deleted.is_(False),
            )
            .options(selectinload(TestEnvironment.variables))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        skip: int = 0,
        limit: int = 20,
        is_global: Optional[bool] = None,
        env_type: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> tuple[list[TestEnvironment], int]:
        """
        获取项目的环境列表

        Args:
            db: 数据库会话
            project_id: 项目ID
            skip: 跳过数量
            limit: 限制数量
            is_global: 是否仅获取全局环境
            keyword: 搜索关键词

        Returns:
            tuple[list[TestEnvironment], int]: 环境列表和总数
        """
        # 构建查询 - 包含项目自己的环境和全局环境
        stmt = select(TestEnvironment).where(
            TestEnvironment.is_deleted.is_(False),
            or_(
                TestEnvironment.project_id == project_id,
                TestEnvironment.is_global.is_(True),
            ),
        )
        count_stmt = select(func.count(TestEnvironment.id)).where(
            TestEnvironment.is_deleted.is_(False),
            or_(
                TestEnvironment.project_id == project_id,
                TestEnvironment.is_global.is_(True),
            ),
        )

        # 全局环境筛选
        if is_global is not None:
            stmt = stmt.where(TestEnvironment.is_global == is_global)
            count_stmt = count_stmt.where(TestEnvironment.is_global == is_global)

        # 环境类型筛选
        if env_type is not None:
            stmt = stmt.where(TestEnvironment.env_type == env_type)
            count_stmt = count_stmt.where(TestEnvironment.env_type == env_type)

        # 关键词搜索
        if keyword:
            search_filter = or_(
                TestEnvironment.name.like(f"%{keyword}%"),
                TestEnvironment.description.like(f"%{keyword}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # 排序：默认环境在前
        stmt = stmt.order_by(
            TestEnvironment.is_default.desc(), TestEnvironment.id.asc()
        )

        # 分页
        stmt = stmt.offset(skip).limit(limit)

        # 执行查询
        result = await db.execute(stmt)
        environments = list(result.scalars().all())

        # 获取总数
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one() or 0

        return environments, total

    async def name_exists(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查环境名称是否存在

        Args:
            db: 数据库会话
            project_id: 项目ID
            name: 环境名称
            exclude_id: 排除的环境ID

        Returns:
            bool: 是否存在
        """
        stmt = select(TestEnvironment).where(
            TestEnvironment.project_id == project_id,
            TestEnvironment.name == name,
            TestEnvironment.is_deleted.is_(False),
        )

        if exclude_id:
            stmt = stmt.where(TestEnvironment.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_default_environment(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> Optional[TestEnvironment]:
        """
        获取项目的默认环境

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            Optional[TestEnvironment]: 默认环境实例
        """
        stmt = (
            select(TestEnvironment)
            .where(
                TestEnvironment.project_id == project_id,
                TestEnvironment.is_default.is_(True),
                TestEnvironment.is_deleted.is_(False),
            )
            .order_by(TestEnvironment.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_default_environment(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        env_id: int,
        commit: bool = True,
    ) -> Optional[TestEnvironment]:
        """
        设置默认环境（会取消其他环境的默认状态）

        Args:
            db: 数据库会话
            project_id: 项目ID
            env_id: 环境ID（如果为0，只取消其他环境的默认状态，不设置新的默认环境）
            commit: 是否提交事务（默认True，设置为False可以在同一个事务中进行其他操作）

        Returns:
            Optional[TestEnvironment]: 设置为默认的环境实例
        """
        # 取消所有环境的默认状态
        stmt = select(TestEnvironment).where(
            TestEnvironment.project_id == project_id,
            TestEnvironment.is_default.is_(True),
            TestEnvironment.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        old_defaults = result.scalars().all()

        for env in old_defaults:
            env.is_default = False
            db.add(env)

        # 设置新的默认环境（env_id不为0时）
        new_default = None
        if env_id != 0:
            new_default = await self.get(db, id=env_id)
            if new_default:
                new_default.is_default = True
                db.add(new_default)

        # 提交事务
        if commit:
            await db.commit()
            if new_default:
                await db.refresh(new_default)

        return new_default

    async def count_variables(
        self,
        db: AsyncSession,
        *,
        env_id: int,
    ) -> int:
        """
        统计环境的变量数量

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            int: 变量数量
        """
        from app.models.test_environment.variable import EnvironmentVariable

        stmt = select(func.count(EnvironmentVariable.id)).where(
            EnvironmentVariable.env_id == env_id
        )
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: EnvironmentCreate,
        project_id: int,
    ) -> TestEnvironment:
        """
        创建环境

        Args:
            db: 数据库会话
            obj_in: 创建数据
            project_id: 项目ID

        Returns:
            TestEnvironment: 创建的环境实例
        """
        # 转换脚本配置为 JSON 字符串
        obj_in_data = obj_in.model_dump()
        if obj_in_data.get("pre_script") is not None:
            obj_in_data["pre_script"] = json.dumps(
                obj_in_data["pre_script"], ensure_ascii=False
            )
        if obj_in_data.get("post_script") is not None:
            obj_in_data["post_script"] = json.dumps(
                obj_in_data["post_script"], ensure_ascii=False
            )

        obj_in_data["project_id"] = project_id
        return await super().create(db, obj_in=obj_in_data)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: TestEnvironment,
        obj_in: EnvironmentUpdate | dict,
    ) -> TestEnvironment:
        """
        更新环境

        Args:
            db: 数据库会话
            db_obj: 数据库中的环境实例
            obj_in: 更新数据

        Returns:
            TestEnvironment: 更新后的环境实例
        """
        if isinstance(obj_in, EnvironmentUpdate):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        # 转换脚本配置为 JSON 字符串
        if "pre_script" in update_data and update_data["pre_script"] is not None:
            update_data["pre_script"] = json.dumps(
                update_data["pre_script"], ensure_ascii=False
            )
        if "post_script" in update_data and update_data["post_script"] is not None:
            update_data["post_script"] = json.dumps(
                update_data["post_script"], ensure_ascii=False
            )

        return await super().update(db, db_obj=db_obj, obj_in=update_data)


# 创建实例
environment = CRUDEnvironment(TestEnvironment)
