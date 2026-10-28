"""
环境变量业务服务层

处理环境变量相关的业务逻辑
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException
from app.crud.test_environment import environment, environment_variable
from app.models.test_environment.variable import EnvironmentVariable
from app.schemas.test_environment.variable import (
    VariableBatchDeleteRequest,
    VariableBatchUpdateRequest,
    VariableImportRequest,
    VariableImportResponse,
)


class VariableService:
    """
    环境变量业务服务类
    """

    @staticmethod
    async def create_variable(
        db: AsyncSession,
        *,
        env_id: int,
        name: str,
        value: str,
        var_type: str,
        description: Optional[str] = None,
        is_active: bool = True,
    ) -> EnvironmentVariable:
        """
        创建环境变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            name: 变量名
            value: 变量值
            var_type: 变量类型
            description: 变量描述
            is_active: 是否启用

        Returns:
            EnvironmentVariable: 创建的变量

        Raises:
            NotFoundException: 环境不存在
            BusinessException: 变量名已存在
        """
        # 检查环境是否存在
        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")

        # 检查变量名是否存在
        if await environment_variable.name_exists(db, env_id=env_id, name=name):
            raise BusinessException("变量名已存在")

        # 获取最大排序值
        max_sort = await environment_variable.get_max_sort_order(db, env_id=env_id)

        return await environment_variable.create(
            db,
            obj_in={
                "env_id": env_id,
                "name": name,
                "value": value,
                "type": var_type,
                "description": description,
                "is_active": is_active,
                "sort_order": max_sort + 1,
            },
        )

    @staticmethod
    async def update_variable(
        db: AsyncSession,
        *,
        db_obj: EnvironmentVariable,
        value: Optional[str] = None,
        var_type: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> EnvironmentVariable:
        """
        更新环境变量

        Args:
            db: 数据库会话
            db_obj: 数据库中的变量
            value: 变量值
            var_type: 变量类型
            description: 变量描述
            is_active: 是否启用

        Returns:
            EnvironmentVariable: 更新后的变量
        """
        update_data = {}
        if value is not None:
            update_data["value"] = value
        if var_type is not None:
            update_data["type"] = var_type
        if description is not None:
            update_data["description"] = description
        if is_active is not None:
            update_data["is_active"] = is_active

        return await environment_variable.update(db, db_obj=db_obj, obj_in=update_data)

    @staticmethod
    async def batch_update_variables(
        db: AsyncSession,
        *,
        env_id: int,
        update_data: VariableBatchUpdateRequest,
    ) -> dict:
        """
        批量更新环境变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            update_data: 批量更新数据

        Returns:
            dict: 更新结果

        Raises:
            NotFoundException: 环境不存在
        """
        # 检查环境是否存在
        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")

        # 转换更新数据
        updates = [var.model_dump(exclude_unset=True) for var in update_data.variables]

        # 批量更新
        updated_count = await environment_variable.batch_update(
            db, env_id=env_id, updates=updates
        )

        return {"updated_count": updated_count}

    @staticmethod
    async def delete_variable(
        db: AsyncSession,
        *,
        var_id: int,
    ) -> bool:
        """
        删除环境变量

        Args:
            db: 数据库会话
            var_id: 变量ID

        Returns:
            bool: 是否删除成功

        Raises:
            NotFoundException: 变量不存在
        """
        var = await environment_variable.get(db, id=var_id)
        if not var:
            raise NotFoundException("变量不存在")

        return await environment_variable.delete(db, id=var_id)

    @staticmethod
    async def batch_delete_variables(
        db: AsyncSession,
        *,
        env_id: int,
        delete_data: VariableBatchDeleteRequest,
    ) -> dict:
        """
        批量删除环境变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            delete_data: 批量删除数据

        Returns:
            dict: 删除结果

        Raises:
            NotFoundException: 环境不存在
        """
        # 检查环境是否存在
        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")

        # 批量删除
        deleted_count = await environment_variable.batch_delete(
            db, env_id=env_id, ids=delete_data.ids
        )

        return {"deleted_count": deleted_count}

    @staticmethod
    async def export_variables(
        db: AsyncSession,
        *,
        env_id: int,
    ) -> dict:
        """
        导出环境变量

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            dict: 导出数据

        Raises:
            NotFoundException: 环境不存在
        """
        # 获取环境
        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")

        # 获取变量列表
        variables, _ = await environment_variable.get_multi_by_env(db, env_id=env_id)

        # 构建导出数据
        exported_vars = []
        for var in variables:
            var_data = {
                "name": var.name,
                "value": var.value,
                "type": var.type,
                "description": var.description,
            }
            exported_vars.append(var_data)

        content = {
            "environment": env.name,
            "exported_at": datetime.now().isoformat(),
            "variables": exported_vars,
        }

        filename = f"variables_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return {"filename": filename, "content": content}

    @staticmethod
    async def import_variables(  # noqa: C901
        db: AsyncSession,
        *,
        env_id: int,
        import_data: VariableImportRequest,
    ) -> VariableImportResponse:
        """
        导入环境变量

        Args:
            db: 数据库会话
            env_id: 环境ID
            import_data: 导入数据

        Returns:
            VariableImportResponse: 导入结果

        Raises:
            NotFoundException: 环境不存在
        """
        # 检查环境是否存在
        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")

        imported_count = 0
        skipped_count = 0
        failed_count = 0

        # 替换模式：删除所有现有变量
        if import_data.mode == "replace":
            await environment_variable.delete_by_env(db, env_id=env_id)

        # 处理导入的变量
        for var_data in import_data.content.variables:
            var_name = var_data.name
            var_exists = await environment_variable.name_exists(
                db, env_id=env_id, name=var_name
            )

            if var_exists:
                if import_data.mode == "merge":
                    # 合并模式：跳过已存在的变量
                    skipped_count += 1
                    continue
                else:
                    # 替换模式：更新变量
                    var_obj = await environment_variable.get_by_env_and_name(
                        db, env_id=env_id, name=var_name
                    )
                    if var_obj:
                        try:
                            await environment_variable.update(
                                db,
                                db_obj=var_obj,
                                obj_in={
                                    "value": var_data.value,
                                    "type": var_data.type,
                                    "description": var_data.description,
                                },
                            )
                            imported_count += 1
                        except Exception:
                            failed_count += 1
            else:
                # 创建新变量
                try:
                    max_sort = await environment_variable.get_max_sort_order(
                        db, env_id=env_id
                    )
                    await environment_variable.create(
                        db,
                        obj_in={
                            "env_id": env_id,
                            "name": var_data.name,
                            "value": var_data.value,
                            "type": var_data.type,
                            "description": var_data.description,
                            "is_active": True,
                            "sort_order": max_sort + 1,
                        },
                    )
                    imported_count += 1
                except Exception:
                    failed_count += 1

        return VariableImportResponse(
            imported_count=imported_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
        )


# 创建服务实例
variable_service = VariableService()
