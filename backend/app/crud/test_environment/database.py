"""
数据库连接 CRUD 操作
"""

import json
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.test_environment.database import DatabaseConnection
from app.schemas.test_environment.database import (
    ConnectionStatus,
    DatabaseCreate,
    DatabaseUpdate,
)


class CRUDDatabase(CRUDBase[DatabaseConnection, DatabaseCreate, DatabaseUpdate]):
    """
    数据库连接 CRUD 操作类
    """

    async def get_by_project_and_name(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
    ) -> Optional[DatabaseConnection]:
        """
        根据项目ID和名称获取数据库连接

        Args:
            db: 数据库会话
            project_id: 项目ID
            name: 连接名称

        Returns:
            Optional[DatabaseConnection]: 数据库连接实例
        """
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.project_id == project_id,
            DatabaseConnection.name == name,
            DatabaseConnection.is_deleted.is_(False),
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
        db_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> tuple[list[DatabaseConnection], int]:
        """
        获取项目的数据库连接列表

        Args:
            db: 数据库会话
            project_id: 项目ID
            skip: 跳过数量
            limit: 限制数量
            db_type: 数据库类型筛选
            keyword: 搜索关键词

        Returns:
            tuple[list[DatabaseConnection], int]: 数据库连接列表和总数
        """
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.project_id == project_id,
            DatabaseConnection.is_deleted.is_(False),
        )
        count_stmt = select(func.count(DatabaseConnection.id)).where(
            DatabaseConnection.project_id == project_id,
            DatabaseConnection.is_deleted.is_(False),
        )

        # 数据库类型筛选
        if db_type:
            stmt = stmt.where(DatabaseConnection.db_type == db_type)
            count_stmt = count_stmt.where(DatabaseConnection.db_type == db_type)

        # 关键词搜索
        if keyword:
            search_filter = DatabaseConnection.name.like(f"%{keyword}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # 排序：按 ID 倒序
        stmt = stmt.order_by(DatabaseConnection.id.desc())

        # 分页
        stmt = stmt.offset(skip).limit(limit)

        # 执行查询
        result = await db.execute(stmt)
        databases = list(result.scalars().all())

        # 获取总数
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one() or 0

        return databases, total

    async def name_exists(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查连接名称是否存在（仅检查未删除的）

        Args:
            db: 数据库会话
            project_id: 项目ID
            name: 连接名称
            exclude_id: 排除的连接ID

        Returns:
            bool: 是否存在
        """
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.project_id == project_id,
            DatabaseConnection.name == name,
            DatabaseConnection.is_deleted.is_(False),
        )

        if exclude_id:
            stmt = stmt.where(DatabaseConnection.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: DatabaseCreate,
        project_id: int,
    ) -> DatabaseConnection:
        """
        创建数据库连接

        Args:
            db: 数据库会话
            obj_in: 创建数据
            project_id: 项目ID

        Returns:
            DatabaseConnection: 创建的数据库连接实例
        """
        obj_in_data = obj_in.model_dump()

        # 转换 connection_params 为 JSON 字符串
        if obj_in_data.get("connection_params"):
            obj_in_data["connection_params"] = json.dumps(
                obj_in_data["connection_params"], ensure_ascii=False
            )

        obj_in_data["project_id"] = project_id
        obj_in_data["connection_status"] = ConnectionStatus.UNKNOWN

        return await super().create(db, obj_in=obj_in_data)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: DatabaseConnection,
        obj_in: DatabaseUpdate | dict,
    ) -> DatabaseConnection:
        """
        更新数据库连接

        Args:
            db: 数据库会话
            db_obj: 数据库中的连接实例
            obj_in: 更新数据

        Returns:
            DatabaseConnection: 更新后的连接实例
        """
        if isinstance(obj_in, DatabaseUpdate):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        # 转换 connection_params 为 JSON 字符串
        if "connection_params" in update_data and update_data["connection_params"]:
            update_data["connection_params"] = json.dumps(
                update_data["connection_params"], ensure_ascii=False
            )

        # 重置连接状态为未知
        update_data["connection_status"] = ConnectionStatus.UNKNOWN

        return await super().update(db, db_obj=db_obj, obj_in=update_data)

    async def update_connection_status(
        self,
        db: AsyncSession,
        *,
        db_obj: DatabaseConnection,
        status: str,
        test_result: Optional[str] = None,
        test_time: Optional[int] = None,
    ) -> DatabaseConnection:
        """
        更新数据库连接状态

        Args:
            db: 数据库会话
            db_obj: 数据库连接实例
            status: 连接状态
            test_result: 测试结果描述
            test_time: 测试时间戳

        Returns:
            DatabaseConnection: 更新后的连接实例
        """
        db_obj.connection_status = status
        db_obj.last_test_time = test_time
        db_obj.last_test_result = test_result

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)

        return db_obj


# 创建实例
database = CRUDDatabase(DatabaseConnection)
