"""
项目模块业务服务层

处理项目模块相关的业务逻辑
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.crud.project import project
from app.crud.project import project_module as module_crud
from app.models.project import ProjectModule
from app.schemas.project import ModuleCreate, ModuleMove, ModuleTreeNode, ModuleUpdate


class ModuleService:
    """
    项目模块业务服务类
    """

    @staticmethod
    async def create_module(
        db: AsyncSession,
        *,
        project_id: int,
        obj_in: ModuleCreate,
    ) -> ProjectModule:
        """
        创建模块

        Args:
            db: 数据库会话
            project_id: 项目ID
            obj_in: 创建数据

        Returns:
            ProjectModule: 创建的模块

        Raises:
            BusinessException: 项目不存在、模块名称重复、层级深度超限
        """
        # 检查项目是否存在
        project_obj = await project.get(db, id=project_id)
        if not project_obj:
            raise BusinessException("项目不存在")

        # 检查同级模块名称是否重复
        if await module_crud.name_exists_in_parent(
            db,
            project_id=project_id,
            name=obj_in.name,
            parent_id=obj_in.parent_id,
        ):
            raise BusinessException("同级模块下已存在同名模块")

        # 计算层级深度
        level = 1
        if obj_in.parent_id:
            parent = await module_crud.get(db, id=obj_in.parent_id)
            if not parent or parent.project_id != project_id:
                raise BusinessException("父模块不存在")
            level = parent.level + 1

        # 检查层级深度
        if level > 5:
            raise BusinessException("模块层级深度不能超过5级")

        # 创建模块
        module_data = obj_in.model_dump()
        module_data["project_id"] = project_id
        module_data["level"] = level

        db_obj = await module_crud.create(db, obj_in=module_data)

        # 更新路径
        await module_crud.update_path(db, module=db_obj)

        return db_obj

    @staticmethod
    async def update_module(
        db: AsyncSession,
        *,
        project_id: int,
        module_id: int,
        obj_in: ModuleUpdate,
    ) -> ProjectModule:
        """
        更新模块

        Args:
            db: 数据库会话
            project_id: 项目ID
            module_id: 模块ID
            obj_in: 更新数据

        Returns:
            ProjectModule: 更新后的模块

        Raises:
            BusinessException: 模块不存在、名称重复
        """
        # 获取模块
        db_obj = await module_crud.get_by_project(
            db, project_id=project_id, module_id=module_id
        )
        if not db_obj:
            raise BusinessException("模块不存在")

        # 如果更新名称，检查是否重复
        if obj_in.name and obj_in.name != db_obj.name:
            if await module_crud.name_exists_in_parent(
                db,
                project_id=project_id,
                name=obj_in.name,
                parent_id=db_obj.parent_id,
                exclude_id=module_id,
            ):
                raise BusinessException("同级模块下已存在同名模块")

        # 执行更新
        return await module_crud.update(db, db_obj=db_obj, obj_in=obj_in)

    @staticmethod
    async def move_module(
        db: AsyncSession,
        *,
        project_id: int,
        module_id: int,
        obj_in: ModuleMove,
    ) -> ProjectModule:
        """
        移动模块

        Args:
            db: 数据库会话
            project_id: 项目ID
            module_id: 模块ID
            obj_in: 移动数据

        Returns:
            ProjectModule: 移动后的模块

        Raises:
            BusinessException: 模块不存在、层级深度超限、循环移动
        """
        # 获取模块
        db_obj = await module_crud.get_by_project(
            db, project_id=project_id, module_id=module_id
        )
        if not db_obj:
            raise BusinessException("模块不存在")

        # 检查是否移动到自己的子模块下（会导致循环）
        if obj_in.parent_id:
            if obj_in.parent_id == module_id:
                raise BusinessException("不能将模块移动到自己下面")

            # 递归检查是否是自己的子孙模块
            current = await module_crud.get(db, id=obj_in.parent_id)
            while current and current.parent_id:
                if current.parent_id == module_id:
                    raise BusinessException("不能将模块移动到自己的子模块下")
                current = await module_crud.get(db, id=current.parent_id)

        # 执行移动
        return await module_crud.move(
            db,
            module_id=module_id,
            new_parent_id=obj_in.parent_id,
            new_sort_order=obj_in.sort_order,
        )

    @staticmethod
    async def delete_module(
        db: AsyncSession,
        *,
        project_id: int,
        module_id: int,
    ) -> bool:
        """
        删除模块

        Args:
            db: 数据库会话
            project_id: 项目ID
            module_id: 模块ID

        Returns:
            bool: 是否删除成功

        Raises:
            BusinessException: 模块不存在、有子模块或关联用例
        """
        # 检查模块是否存在
        db_obj = await module_crud.get_by_project(
            db, project_id=project_id, module_id=module_id
        )
        if not db_obj:
            raise BusinessException("模块不存在")

        # 执行删除（会检查子模块和关联用例）
        try:
            return await module_crud.delete_with_check(db, module_id=module_id)
        except ValueError as e:
            raise BusinessException(str(e))

    @staticmethod
    async def build_module_tree(
        db: AsyncSession,
        *,
        project_id: int,
    ) -> list[ModuleTreeNode]:
        """
        构建模块树

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            list[ModuleTreeNode]: 模块树
        """
        # 获取所有模块
        all_modules = await module_crud.get_tree(db, project_id=project_id)

        # 构建ID到模块的映射
        module_map = {m.id: ModuleTreeNode.model_validate(m) for m in all_modules}

        # 构建树形结构
        root_modules: list[ModuleTreeNode] = []

        for module_node in module_map.values():
            if module_node.parent_id is None:
                # 根模块
                root_modules.append(module_node)
            else:
                # 添加到父模块的children中
                parent = module_map.get(module_node.parent_id)
                if parent:
                    if not parent.children:
                        parent.children = []
                    parent.children.append(module_node)

        return root_modules


# 创建服务实例
module_service = ModuleService()
