"""
全局函数 CRUD 操作
"""

import json
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.test_environment.function import GlobalFunction
from app.schemas.test_environment.function import (
    FunctionCreate,
    FunctionUpdate,
)


class CRUDGlobalFunction(CRUDBase[GlobalFunction, FunctionCreate, FunctionUpdate]):
    """
    全局函数 CRUD 操作类
    """

    async def get_by_project_and_name(
        self,
        db: AsyncSession,
        *,
        project_id: Optional[int],
        name: str,
    ) -> Optional[GlobalFunction]:
        """
        根据项目ID和函数名获取函数

        Args:
            db: 数据库会话
            project_id: 项目ID（None表示全局函数）
            name: 函数名称

        Returns:
            Optional[GlobalFunction]: 函数实例
        """
        stmt = select(GlobalFunction).where(
            GlobalFunction.project_id == project_id,
            GlobalFunction.name == name,
            GlobalFunction.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: Optional[int],
        skip: int = 0,
        limit: int = 20,
        language: Optional[str] = None,
        keyword: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> tuple[list[GlobalFunction], int]:
        """
        获取项目的函数列表（包含全局函数）

        Args:
            db: 数据库会话
            project_id: 项目ID（None表示仅获取全局函数）
            skip: 跳过数量
            limit: 限制数量
            language: 编程语言筛选
            keyword: 搜索关键词
            is_active: 是否仅获取启用的函数

        Returns:
            tuple[list[GlobalFunction], int]: 函数列表和总数
        """
        # 查询条件：项目自己的函数 + 全局函数
        stmt = select(GlobalFunction).where(
            GlobalFunction.is_deleted.is_(False),
            or_(
                GlobalFunction.project_id == project_id,
                GlobalFunction.project_id.is_(None),
            ),
        )
        count_stmt = select(func.count(GlobalFunction.id)).where(
            GlobalFunction.is_deleted.is_(False),
            or_(
                GlobalFunction.project_id == project_id,
                GlobalFunction.project_id.is_(None),
            ),
        )

        # 编程语言筛选
        if language:
            stmt = stmt.where(GlobalFunction.language == language)
            count_stmt = count_stmt.where(GlobalFunction.language == language)

        # 启用状态筛选
        if is_active is not None:
            stmt = stmt.where(GlobalFunction.is_active == is_active)
            count_stmt = count_stmt.where(GlobalFunction.is_active == is_active)

        # 关键词搜索
        if keyword:
            search_filter = or_(
                GlobalFunction.name.like(f"%{keyword}%"),
                GlobalFunction.display_name.like(f"%{keyword}%"),
                GlobalFunction.description.like(f"%{keyword}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # 排序：内置函数在前，然后按名称排序
        stmt = stmt.order_by(
            GlobalFunction.is_built_in.desc(),
            GlobalFunction.name.asc(),
        )

        # 分页
        stmt = stmt.offset(skip).limit(limit)

        # 执行查询
        result = await db.execute(stmt)
        functions = list(result.scalars().all())

        # 获取总数
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one() or 0

        return functions, total

    async def get_built_in_functions(
        self,
        db: AsyncSession,
        *,
        language: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[GlobalFunction]:
        """
        获取内置函数列表

        Args:
            db: 数据库会话
            language: 编程语言筛选
            is_active: 是否仅获取启用的函数

        Returns:
            list[GlobalFunction]: 内置函数列表
        """
        stmt = select(GlobalFunction).where(
            GlobalFunction.is_built_in.is_(True),
            GlobalFunction.is_deleted.is_(False),
        )

        if language:
            stmt = stmt.where(GlobalFunction.language == language)

        if is_active is not None:
            stmt = stmt.where(GlobalFunction.is_active == is_active)

        stmt = stmt.order_by(GlobalFunction.name.asc())

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_custom_functions(
        self,
        db: AsyncSession,
        *,
        project_id: Optional[int] = None,
    ) -> list[GlobalFunction]:
        """
        获取自定义函数列表

        Args:
            db: 数据库会话
            project_id: 项目ID（None表示全局自定义函数）

        Returns:
            list[GlobalFunction]: 自定义函数列表
        """
        stmt = select(GlobalFunction).where(
            GlobalFunction.is_built_in.is_(False),
            GlobalFunction.is_deleted.is_(False),
        )

        if project_id is None:
            # 仅获取全局自定义函数
            stmt = stmt.where(GlobalFunction.project_id.is_(None))
        else:
            # 获取项目自定义函数 + 全局自定义函数
            stmt = stmt.where(
                or_(
                    GlobalFunction.project_id == project_id,
                    GlobalFunction.project_id.is_(None),
                )
            )

        stmt = stmt.order_by(GlobalFunction.name.asc())

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def name_exists(
        self,
        db: AsyncSession,
        *,
        project_id: Optional[int],
        name: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查函数名是否存在

        Args:
            db: 数据库会话
            project_id: 项目ID
            name: 函数名
            exclude_id: 排除的函数ID

        Returns:
            bool: 是否存在
        """
        stmt = select(GlobalFunction).where(
            GlobalFunction.project_id == project_id,
            GlobalFunction.name == name,
            GlobalFunction.is_deleted.is_(False),
        )

        if exclude_id:
            stmt = stmt.where(GlobalFunction.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: FunctionCreate,
        project_id: Optional[int],
        created_by: Optional[int] = None,
    ) -> GlobalFunction:
        """
        创建函数

        Args:
            db: 数据库会话
            obj_in: 创建数据
            project_id: 项目ID（None表示全局函数）
            created_by: 创建人ID

        Returns:
            GlobalFunction: 创建的函数实例
        """
        obj_in_data = obj_in.model_dump()

        # 转换 params 为 JSON 字符串
        if obj_in_data.get("params"):
            params_list = obj_in_data["params"]
            # params 已经被 model_dump() 转换为 dict，直接序列化
            obj_in_data["params"] = json.dumps(params_list, ensure_ascii=False)

        obj_in_data["project_id"] = project_id
        obj_in_data["created_by"] = created_by
        obj_in_data["is_built_in"] = False

        return await super().create(db, obj_in=obj_in_data)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: GlobalFunction,
        obj_in: FunctionUpdate | dict,
    ) -> GlobalFunction:
        """
        更新函数

        Args:
            db: 数据库会话
            db_obj: 数据库中的函数实例
            obj_in: 更新数据

        Returns:
            GlobalFunction: 更新后的函数实例
        """
        if isinstance(obj_in, FunctionUpdate):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        # 转换 params 为 JSON 字符串
        if "params" in update_data and update_data["params"]:
            params_list = update_data["params"]
            # 检查第一个元素是 dict 还是 Pydantic 模型
            if params_list and isinstance(params_list[0], dict):
                # 已经是 dict，直接序列化
                update_data["params"] = json.dumps(params_list, ensure_ascii=False)
            else:
                # 是 Pydantic 模型，需要 model_dump()
                update_data["params"] = json.dumps(
                    [p.model_dump() for p in params_list], ensure_ascii=False
                )

        # 内置函数不允许修改某些字段
        if db_obj.is_built_in:
            # 移除不允许修改的字段
            protected_fields = {"name", "language", "is_built_in"}
            update_data = {
                k: v for k, v in update_data.items() if k not in protected_fields
            }

        return await super().update(db, db_obj=db_obj, obj_in=update_data)

    async def update_status(
        self,
        db: AsyncSession,
        *,
        db_obj: GlobalFunction,
        is_active: bool,
    ) -> GlobalFunction:
        """
        更新函数状态

        Args:
            db: 数据库会话
            db_obj: 函数实例
            is_active: 是否启用

        Returns:
            GlobalFunction: 更新后的函数实例
        """
        db_obj.is_active = is_active
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)

        return db_obj


# 创建实例
global_function = CRUDGlobalFunction(GlobalFunction)
