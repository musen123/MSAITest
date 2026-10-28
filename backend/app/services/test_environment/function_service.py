"""
全局函数业务服务层

处理全局函数相关的业务逻辑
"""

import json
import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException
from app.crud.test_environment import global_function
from app.models.test_environment.function import GlobalFunction
from app.schemas.test_environment.function import (
    BuiltInFunctionResponse,
    FunctionCreate,
    FunctionListResponse,
    FunctionTestResponse,
    FunctionUpdate,
)


class FunctionService:
    """
    全局函数业务服务类
    """

    @staticmethod
    async def get_functions_list(
        db: AsyncSession,
        *,
        project_id: Optional[int],
        language: Optional[str] = None,
    ) -> FunctionListResponse:
        """
        获取函数列表（内置函数 + 自定义函数）
        Args:
            db: 数据库会话
            project_id: 项目ID
            language: 编程语言筛选
        Returns:
            FunctionListResponse: 函数列表
        """
        # 获取内置函数
        built_in_funcs = await FunctionService.get_built_in_functions()

        # 获取自定义函数
        custom_funcs = await global_function.get_custom_functions(
            db, project_id=project_id
        )

        # 转换自定义函数为响应格式
        custom_funcs_data = []
        for func in custom_funcs:
            # 处理 params 字段：如果是字符串则解析，否则保持原样（JSON类型自动反序列化为list）
            params_value = func.params
            if params_value is None:
                params_value = []
            elif isinstance(params_value, str):
                try:
                    params_value = json.loads(params_value)
                except json.JSONDecodeError:
                    params_value = []

            custom_funcs_data.append(
                {
                    "id": func.id,
                    "project_id": func.project_id,
                    "name": func.name,
                    "display_name": func.display_name,
                    "language": func.language,
                    "description": func.description,
                    "code": func.code,
                    "params": params_value,
                    "return_type": func.return_type,
                    "example": func.example,
                    "is_built_in": func.is_built_in,
                    "is_active": func.is_active,
                    "created_by": func.created_by,
                    "created_at": (
                        func.created_at.isoformat() if func.created_at else ""
                    ),
                    "updated_at": (
                        func.updated_at.isoformat() if func.updated_at else ""
                    ),
                }
            )

        return FunctionListResponse(built_in=built_in_funcs, custom=custom_funcs_data)

    @staticmethod
    async def get_built_in_functions() -> list[BuiltInFunctionResponse]:
        """
        获取内置函数列表（从 global_function 模块自动提取）

        Returns:
            list[BuiltInFunctionResponse]: 内置函数列表
        """
        from app.utils.script_runtime.inspect_global_function import (
            global_function_list,
        )

        return [
            BuiltInFunctionResponse(
                name=func["name"],
                display_name=func["display_name"],
                language=func["language"],
                code=func["code"],
                description=func["description"],
                params=func["params"],
                return_type=func["return_type"],
                example=func["example"],
                is_built_in=True,
                is_active=True,
            )
            for func in global_function_list
        ]

    @staticmethod
    async def create_function(
        db: AsyncSession,
        *,
        obj_in: FunctionCreate,
        project_id: Optional[int],
        created_by: Optional[int] = None,
    ) -> GlobalFunction:
        """
        创建自定义函数

        Args:
            db: 数据库会话
            obj_in: 创建数据
            project_id: 项目ID
            created_by: 创建人ID

        Returns:
            GlobalFunction: 创建的函数

        Raises:
            BusinessException: 函数名已存在
        """
        # 检查函数名是否存在
        if await global_function.name_exists(
            db, project_id=project_id, name=obj_in.name
        ):
            raise BusinessException("函数名已存在")

        return await global_function.create(
            db, obj_in=obj_in, project_id=project_id, created_by=created_by
        )

    @staticmethod
    async def update_function(
        db: AsyncSession,
        *,
        db_obj: GlobalFunction,
        obj_in: FunctionUpdate,
    ) -> GlobalFunction:
        """
        更新函数

        Args:
            db: 数据库会话
            db_obj: 数据库中的函数
            obj_in: 更新数据

        Returns:
            GlobalFunction: 更新后的函数

        Raises:
            BusinessException: 函数名已存在
        """
        # 注意：编辑时不能修改函数名，所以不需要检查函数名重复

        return await global_function.update(db, db_obj=db_obj, obj_in=obj_in)

    @staticmethod
    async def update_function_status(
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
            GlobalFunction: 更新后的函数
        """
        return await global_function.update_status(
            db, db_obj=db_obj, is_active=is_active
        )

    @staticmethod
    async def delete_function(
        db: AsyncSession,
        *,
        func_id: int,
    ) -> bool:
        """
        删除函数

        Args:
            db: 数据库会话
            func_id: 函数ID

        Returns:
            bool: 是否删除成功

        Raises:
            NotFoundException: 函数不存在
            BusinessException: 不能删除内置函数
        """
        func = await global_function.get(db, id=func_id)
        if not func:
            raise NotFoundException("函数不存在")

        if func.is_built_in:
            raise BusinessException("不能删除内置函数")

        return await global_function.soft_delete(db, id=func_id)

    @staticmethod
    async def test_function(
        db: AsyncSession,
        *,
        db_obj: GlobalFunction,
        params: Optional[dict[str, Any]] = None,
    ) -> FunctionTestResponse:
        """
        测试函数执行

        Args:
            db: 数据库会话
            db_obj: 函数实例
            params: 函数参数

        Returns:
            FunctionTestResponse: 测试结果
        """
        start_time = time.time()
        executed_at = int(start_time * 1000)

        try:
            # 执行函数
            result = await FunctionService._execute_function(db_obj, params)

            execution_time = int((time.time() - start_time) * 1000)

            return FunctionTestResponse(
                success=True,
                result=result,
                execution_time=execution_time,
                executed_at=str(executed_at),
            )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)

            return FunctionTestResponse(
                success=False,
                error=str(e),
                execution_time=execution_time,
                executed_at=str(executed_at),
            )

    @staticmethod
    async def _execute_function(
        func_obj: GlobalFunction,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        执行函数

        Args:
            func_obj: 函数对象
            params: 函数参数

        Returns:
            Any: 执行结果

        Raises:
            BusinessException: 函数执行失败
        """
        params = params or {}

        if func_obj.language == "python":
            return await FunctionService._execute_python_function(func_obj, params)
        elif func_obj.language == "javascript":
            return await FunctionService._execute_javascript_function(func_obj, params)
        else:
            raise BusinessException(f"不支持的编程语言: {func_obj.language}")

    @staticmethod
    async def _execute_python_function(  # noqa: C901
        func_obj: GlobalFunction,
        params: dict[str, Any],
    ) -> Any:
        """
        执行 Python 函数

        Args:
            func_obj: 函数对象
            params: 函数参数

        Returns:
            Any: 执行结果
        """
        import sys
        from io import StringIO

        # 准备执行环境
        local_vars = {}
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            # 解析参数
            func_params = {}
            if func_obj.params:
                try:
                    param_list = json.loads(func_obj.params)
                    for param_def in param_list:
                        param_name = param_def["name"]
                        if param_name in params:
                            func_params[param_name] = params[param_name]
                        elif param_def.get("required") and "default" in param_def:
                            func_params[param_name] = param_def["default"]
                        elif param_def.get("required"):
                            raise BusinessException(f"缺少必填参数: {param_name}")
                except json.JSONDecodeError:
                    pass
            from app.utils.script_runtime.script_env import build_script_globals

            global_vars = build_script_globals()
            # 执行函数代码
            exec(func_obj.code, global_vars, local_vars)
            # 查找函数并执行
            func_name = func_obj.name
            if func_name not in local_vars:
                raise BusinessException(f"函数定义不存在: {func_name}")
            func = local_vars[func_name]
            result = func(**func_params)
            return result

        except Exception as e:
            raise BusinessException(f"函数执行失败: {str(e)}")

        finally:
            sys.stdout = old_stdout

    @staticmethod
    async def _execute_javascript_function(
        func_obj: GlobalFunction,
        params: dict[str, Any],
    ) -> Any:
        """
        执行 JavaScript 函数

        Args:
            func_obj: 函数对象
            params: 函数参数

        Returns:
            Any: 执行结果
        """
        # TODO: 实现 JavaScript 函数执行
        raise BusinessException("JavaScript 函数执行暂未实现")


# 创建服务实例
function_service = FunctionService()
