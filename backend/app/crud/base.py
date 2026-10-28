"""
基础 CRUD 类

提供通用的数据库操作方法
"""

from datetime import datetime
from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    基础 CRUD 类

    提供通用的增删改查操作
    """

    def __init__(self, model: Type[ModelType]) -> None:
        """
        初始化 CRUD 基类

        Args:
            model: ORM 模型类
        """
        self.model = model

    async def get(
        self,
        db: AsyncSession,
        id: Any,
    ) -> Optional[ModelType]:
        """
        根据 ID 获取单条记录

        Args:
            db: 数据库会话
            id: 记录 ID

        Returns:
            Optional[ModelType]: 模型实例，不存在返回 None
        """
        return await db.get(self.model, id)

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelType]:
        """
        获取多条记录

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 限制数量

        Returns:
            Sequence[ModelType]: 模型实例列表
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_multi_by(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> Sequence[ModelType]:
        """
        根据条件获取多条记录

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 限制数量
            filters: 过滤条件字典

        Returns:
            Sequence[ModelType]: 模型实例列表
        """
        stmt = select(self.model)

        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        db: AsyncSession,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """
        统计记录数量

        Args:
            db: 数据库会话
            filters: 过滤条件字典

        Returns:
            int: 记录数量
        """
        stmt = select(func.count(self.model.id))

        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)

        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
    ) -> ModelType:
        """
        创建新记录

        Args:
            db: 数据库会话
            obj_in: 创建 Schema

        Returns:
            ModelType: 创建的模型实例
        """
        obj_in_data = obj_in.model_dump() if isinstance(obj_in, BaseModel) else obj_in

        # 显式设置时间戳字段（如果模型有这些字段）
        if hasattr(self.model, "created_at"):
            obj_in_data["created_at"] = datetime.utcnow()
        if hasattr(self.model, "updated_at"):
            obj_in_data["updated_at"] = datetime.utcnow()

        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        """
        更新记录

        Args:
            db: 数据库会话
            db_obj: 数据库中的模型实例
            obj_in: 更新 Schema 或字典

        Returns:
            ModelType: 更新后的模型实例
        """
        if isinstance(obj_in, BaseModel):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # 更新 updated_at 时间戳（如果模型有这个字段）
        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.utcnow()

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: int,
    ) -> bool:
        """
        删除记录

        Args:
            db: 数据库会话
            id: 记录 ID

        Returns:
            bool: 是否删除成功
        """
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
            return True
        return False

    async def soft_delete(
        self,
        db: AsyncSession,
        *,
        id: int,
    ) -> bool:
        """
        软删除记录（设置 is_deleted=True）

        Args:
            db: 数据库会话
            id: 记录 ID

        Returns:
            bool: 是否删除成功

        Raises:
            AttributeError: 如果模型没有 is_deleted 字段
        """
        obj = await self.get(db, id)
        if obj:
            if hasattr(obj, "is_deleted"):
                obj.is_deleted = True
            if hasattr(obj, "deleted_at"):
                obj.deleted_at = datetime.utcnow()
            db.add(obj)
            await db.commit()
            return True
        return False

    async def exists(
        self,
        db: AsyncSession,
        *,
        id: int,
    ) -> bool:
        """
        检查记录是否存在

        Args:
            db: 数据库会话
            id: 记录 ID

        Returns:
            bool: 记录是否存在
        """
        return await self.get(db, id) is not None
