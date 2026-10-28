"""
项目模块 CRUD 操作
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.project import ProjectModule
from app.schemas.project import ModuleCreate, ModuleUpdate


class CRUDProjectModule(CRUDBase[ProjectModule, ModuleCreate, ModuleUpdate]):
    """
    项目模块 CRUD 操作类
    """

    async def get_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        module_id: int,
    ) -> Optional[ProjectModule]:
        """
        获取项目中的指定模块

        Args:
            db: 数据库会话
            project_id: 项目ID
            module_id: 模块ID

        Returns:
            Optional[ProjectModule]: 模块实例
        """
        stmt = (
            select(ProjectModule)
            .where(
                ProjectModule.id == module_id,
                ProjectModule.project_id == project_id,
            )
            .options(selectinload(ProjectModule.project))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_parent(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        parent_id: Optional[int],
    ) -> list[ProjectModule]:
        """
        获取指定父模块下的子模块列表

        Args:
            db: 数据库会话
            project_id: 项目ID
            parent_id: 父模块ID（None表示根模块）

        Returns:
            list[ProjectModule]: 模块列表
        """
        stmt = (
            select(ProjectModule)
            .where(
                ProjectModule.project_id == project_id,
                (
                    ProjectModule.parent_id == parent_id
                    if parent_id is not None
                    else ProjectModule.parent_id.is_(None)
                ),
            )
            .order_by(ProjectModule.sort_order.asc(), ProjectModule.id.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_tree(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> list[ProjectModule]:
        """
        获取项目的完整模块树

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            list[ProjectModule]: 模块列表（平铺，包含层级信息）
        """
        stmt = (
            select(ProjectModule)
            .where(ProjectModule.project_id == project_id)
            .order_by(
                ProjectModule.level.asc(),
                ProjectModule.sort_order.asc(),
                ProjectModule.id.asc(),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_children(
        self,
        db: AsyncSession,
        *,
        parent_id: int,
    ) -> list[ProjectModule]:
        """
        获取子模块列表

        Args:
            db: 数据库会话
            parent_id: 父模块ID

        Returns:
            list[ProjectModule]: 子模块列表
        """
        stmt = (
            select(ProjectModule)
            .where(ProjectModule.parent_id == parent_id)
            .order_by(ProjectModule.sort_order.asc(), ProjectModule.id.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> int:
        """
        统计项目的模块数量

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            int: 模块数量
        """
        stmt = select(func.count(ProjectModule.id)).where(
            ProjectModule.project_id == project_id
        )
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def count_children(
        self,
        db: AsyncSession,
        *,
        parent_id: int,
    ) -> int:
        """
        统计子模块数量

        Args:
            db: 数据库会话
            parent_id: 父模块ID

        Returns:
            int: 子模块数量
        """
        stmt = select(func.count(ProjectModule.id)).where(
            ProjectModule.parent_id == parent_id
        )
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def name_exists_in_parent(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
        parent_id: Optional[int],
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查同一父模块下是否存在同名模块

        Args:
            db: 数据库会话
            project_id: 项目ID
            name: 模块名称
            parent_id: 父模块ID
            exclude_id: 排除的模块ID

        Returns:
            bool: 是否存在
        """
        stmt = select(ProjectModule).where(
            ProjectModule.project_id == project_id,
            ProjectModule.name == name,
            (
                ProjectModule.parent_id == parent_id
                if parent_id is not None
                else ProjectModule.parent_id.is_(None)
            ),
        )

        if exclude_id:
            stmt = stmt.where(ProjectModule.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_max_level(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> int:
        """
        获取项目中模块的最大层级深度

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            int: 最大层级深度
        """
        stmt = select(func.max(ProjectModule.level)).where(
            ProjectModule.project_id == project_id
        )
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def update_path(
        self,
        db: AsyncSession,
        *,
        module: ProjectModule,
    ) -> ProjectModule:
        """
        更新模块路径

        Args:
            db: 数据库会话
            module: 模块实例

        Returns:
            ProjectModule: 更新后的模块
        """
        # 构建路径
        path_parts = [module.name]

        if module.parent_id:
            # 递归查找父模块构建路径
            parent = await self.get(db, id=module.parent_id)
            while parent:
                path_parts.insert(0, parent.name)
                if parent.parent_id:
                    parent = await self.get(db, id=parent.parent_id)
                else:
                    break

        module.path = "/".join(path_parts)
        db.add(module)
        await db.commit()
        await db.refresh(module)
        return module

    async def move(
        self,
        db: AsyncSession,
        *,
        module_id: int,
        new_parent_id: Optional[int],
        new_sort_order: int,
    ) -> Optional[ProjectModule]:
        """
        移动模块到新位置

        Args:
            db: 数据库会话
            module_id: 模块ID
            new_parent_id: 新父模块ID
            new_sort_order: 新排序顺序

        Returns:
            Optional[ProjectModule]: 移动后的模块
        """
        module = await self.get(db, id=module_id)
        if not module:
            return None

        # 计算新层级
        new_level = 1
        if new_parent_id:
            parent = await self.get(db, id=new_parent_id)
            if parent:
                new_level = parent.level + 1

        # 验证层级深度不超过5
        if new_level > 5:
            raise ValueError("模块层级深度不能超过5级")

        # 更新模块信息
        module.parent_id = new_parent_id
        module.sort_order = new_sort_order
        module.level = new_level

        db.add(module)
        await db.commit()
        await db.refresh(module)

        # 更新路径
        await self.update_path(db, module=module)

        return module

    async def has_children(
        self,
        db: AsyncSession,
        *,
        module_id: int,
    ) -> bool:
        """
        检查模块是否有子模块

        Args:
            db: 数据库会话
            module_id: 模块ID

        Returns:
            bool: 是否有子模块
        """
        count = await self.count_children(db, parent_id=module_id)
        return count > 0

    async def delete_with_check(
        self,
        db: AsyncSession,
        *,
        module_id: int,
    ) -> bool:
        """
        删除模块（检查是否有子模块或关联用例）

        Args:
            db: 数据库会话
            module_id: 模块ID

        Returns:
            bool: 是否删除成功
        """
        # 检查是否有子模块
        if await self.has_children(db, module_id=module_id):
            raise ValueError("该模块下存在子模块，无法删除")

        # TODO: 检查是否有关联用例
        # 需要实现用例模块后再补充

        return await self.delete(db, id=module_id)


# 创建实例
project_module = CRUDProjectModule(ProjectModule)
