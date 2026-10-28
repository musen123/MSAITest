"""
项目配置 CRUD 操作
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.project import ProjectConfig
from app.schemas.project import ConfigCreate, ConfigUpdate


class CRUDProjectConfig(CRUDBase[ProjectConfig, ConfigCreate, ConfigUpdate]):
    """
    项目配置 CRUD 操作类
    """

    async def get_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> Optional[ProjectConfig]:
        """
        根据项目ID获取配置

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            Optional[ProjectConfig]: 配置实例
        """
        stmt = select(ProjectConfig).where(ProjectConfig.project_id == project_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> ProjectConfig:
        """
        获取或创建项目配置

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            ProjectConfig: 配置实例
        """
        config = await self.get_by_project(db, project_id=project_id)
        if not config:
            # 创建默认配置
            config = ProjectConfig(project_id=project_id)
            db.add(config)
            await db.commit()
            await db.refresh(config)
        return config

    async def update_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        obj_in: ConfigUpdate,
    ) -> Optional[ProjectConfig]:
        """
        更新项目配置

        Args:
            db: 数据库会话
            project_id: 项目ID
            obj_in: 更新数据

        Returns:
            Optional[ProjectConfig]: 更新后的配置
        """
        config = await self.get_by_project(db, project_id=project_id)
        if not config:
            return None

        return await self.update(db, db_obj=config, obj_in=obj_in)

    async def delete_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> bool:
        """
        删除项目配置

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            bool: 是否删除成功
        """
        config = await self.get_by_project(db, project_id=project_id)
        if config:
            await db.delete(config)
            await db.commit()
            return True
        return False


# 创建实例
project_config = CRUDProjectConfig(ProjectConfig)
