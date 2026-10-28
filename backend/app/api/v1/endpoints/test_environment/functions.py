"""
全局函数管理 API 端点

处理全局函数的 CRUD、测试执行等操作
"""

import json
import logging
import re
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.llm_context import get_current_llm
from app.utils.script_runtime.global_function_builder import _compile_db_function
from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel
from app.crud.project import project as project_crud
from app.crud.test_environment import global_function
from app.models.auth.user import User
from app.schemas.test_environment.function import (
    BuiltInFunctionResponse,
    FunctionAIGenerateRequest,
    FunctionCreate,
    FunctionListResponse,
    FunctionParam,
    FunctionResponse,
    FunctionStatusUpdate,
    FunctionTestRequest,
    FunctionTestResponse,
    FunctionUpdate,
)
from app.services.test_environment.function_service import FunctionService


class _GeneratedParam(BaseModel):
    name: str = Field(description="参数名")
    type: str = Field(default="str", description="参数类型，如 str/int/bool/list/dict")
    description: str = Field(default="", description="参数描述")
    required: bool = Field(default=True, description="是否必填")
    default: Optional[str] = Field(default=None, description="默认值（字符串形式）")


class _GeneratedFunction(BaseModel):
    name: str = Field(description="函数名（snake_case，如 get_timestamp）")
    display_name: str = Field(description="函数中文显示名称")
    code: str = Field(description="完整的 Python 函数定义代码，不含 markdown 标记")
    description: str = Field(description="函数功能描述")
    params: list[_GeneratedParam] = Field(default=[], description="函数参数列表")
    return_type: str = Field(default="str", description="返回值类型")
    example: str = Field(default="", description="调用示例")


router = APIRouter()


async def check_project_access(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> bool:
    """
    检查用户是否有项目访问权限

    系统管理员可以访问所有项目
    """
    project_obj = await project_crud.get(db, id=project_id)
    if not project_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 系统管理员可以访问所有项目
    from app.services.project.project_service import ProjectService

    if await ProjectService._is_super_admin(db, user_id):
        return True

    from app.crud.project import project_member

    return await project_member.is_member(db, project_id=project_id, user_id=user_id)


@router.get(
    "",
    summary="获取函数列表",
    response_model=ResponseModel[FunctionListResponse],
)
async def get_functions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
    project_id: int,
    type: str | None = Query(default=None, description="函数类型：built-in/custom"),
    language: str | None = Query(
        default=None, description="编程语言：python/javascript"
    ),
    keyword: str | None = Query(default=None, description="搜索关键词"),
) -> ResponseModel[FunctionListResponse]:
    """
    获取函数列表

    返回内置函数和自定义函数列表

    - **type**: 函数类型筛选
    - **language**: 编程语言筛选
    - **keyword**: 搜索关键词
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取函数列表
    result = await FunctionService.get_functions_list(
        db, project_id=project_id, language=language
    )

    return ResponseModel(data=result)


@router.get(
    "/libraries",
    summary="获取可用库列表",
)
async def get_available_libraries(
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
) -> ResponseModel:
    """
    获取全局函数执行环境中可用的第三方库及其说明

    返回库名、完整模块路径、功能描述和使用示例
    """
    from app.utils.script_runtime.script_env import LIBRARY_DOCS

    libraries = []
    for name, (full_name, desc, example) in LIBRARY_DOCS.items():
        libraries.append(
            {"name": name, "module": full_name, "description": desc, "example": example}
        )
    return ResponseModel(data=libraries)


@router.get(
    "/built-in",
    summary="获取内置函数列表",
    response_model=ResponseModel[list[BuiltInFunctionResponse]],
)
async def get_built_in_functions(
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
) -> ResponseModel[list[BuiltInFunctionResponse]]:
    """
    获取内置函数列表

    返回系统预置的所有内置函数，不需要 project_id
    """
    built_in_funcs = await FunctionService.get_built_in_functions()
    return ResponseModel(data=built_in_funcs)


@router.post(
    "/built-in/{func_name}/test",
    summary="测试内置函数",
    response_model=ResponseModel[FunctionTestResponse],
)
async def test_built_in_function(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
    func_name: str,
    test_request: FunctionTestRequest,
) -> ResponseModel[FunctionTestResponse]:
    """
    测试执行内置函数

    - **func_name**: 内置函数名称
    - **params**: 函数参数
    """
    import time

    from app.ai_core.llm_client import build_llm_from_config
    from app.ai_core.llm_context import set_current_llm, set_current_vision_llm
    from app.utils.script_runtime import global_function as gf_module
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.models.auth.user_llm_config import ModelType

    # 注入视觉模型和文本模型到上下文（至少需要配置一个）
    vision_config = await crud_user_llm_config.get_default(
        db, user_id=current_user.id, model_type=ModelType.VISION
    )
    if vision_config and vision_config.is_active:
        set_current_vision_llm(build_llm_from_config(vision_config))

    text_config = await crud_user_llm_config.get_default(
        db, user_id=current_user.id, model_type=ModelType.TEXT
    )
    if text_config and text_config.is_active:
        set_current_llm(build_llm_from_config(text_config))

    func_obj = getattr(gf_module, func_name, None)
    if func_obj is None or not callable(func_obj):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"内置函数不存在: {func_name}",
        )

    params = test_request.params or {}
    start_time = time.time()
    executed_at = int(start_time * 1000)

    try:
        result = func_obj(**params)
        execution_time = int((time.time() - start_time) * 1000)
        return ResponseModel(
            data=FunctionTestResponse(
                success=True,
                result=result,
                execution_time=execution_time,
                executed_at=str(executed_at),
            ),
            message="执行成功",
        )
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        return ResponseModel(
            code=400,
            data=FunctionTestResponse(
                success=False,
                error=str(e),
                execution_time=execution_time,
                executed_at=str(executed_at),
            ),
            message="执行失败",
        )


@router.get(
    "/{function_id}",
    summary="获取函数详情",
    response_model=ResponseModel[FunctionResponse],
)
async def get_function_detail(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
    function_id: int,
    project_id: int,
) -> ResponseModel[FunctionResponse]:
    """
    获取函数详情

    返回函数的完整信息，包括代码
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取函数
    func = await global_function.get(db, id=function_id)
    if not func:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="函数不存在",
        )

    # 转换为响应格式
    response_data = FunctionResponse(
        id=func.id,
        project_id=func.project_id,
        name=func.name,
        display_name=func.display_name,
        language=func.language,
        code=func.code,
        description=func.description,
        params=func.params if isinstance(func.params, list) else [],
        return_type=func.return_type,
        example=func.example,
        is_built_in=func.is_built_in,
        is_active=func.is_active,
        created_by=func.created_by,
        created_at=func.created_at.isoformat() if func.created_at else "",
        updated_at=func.updated_at.isoformat() if func.updated_at else "",
    )

    return ResponseModel(data=response_data)


@router.post(
    "",
    summary="创建函数",
    response_model=ResponseModel[dict],
)
async def create_function(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:create"))
    ],
    obj_in: FunctionCreate,
    project_id: int,
) -> ResponseModel[dict]:
    """
    创建自定义函数

    - **name**: 函数名称
    - **display_name**: 函数显示名称
    - **language**: 编程语言（python/javascript）
    - **code**: 函数代码
    - **description**: 函数描述
    - **params**: 参数说明
    - **return_type**: 返回值类型
    - **example**: 使用示例
    - **is_active**: 是否启用
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    try:
        func = await FunctionService.create_function(
            db,
            obj_in=obj_in,
            project_id=project_id,
            created_by=current_user.id,
        )
        return ResponseModel(
            data={"id": func.id, "name": func.name},
            message="创建成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


_logger = logging.getLogger(__name__)

_AI_GENERATE_SYSTEM_PROMPT = """你是一个专业的 Python 工具函数生成专家，为测试场景生成辅助工具函数。

生成规则：
1. 函数名使用 snake_case 命名，简短且含义明确
2. 代码必须是完整的 Python 函数定义，可直接 exec 执行，不含 markdown 代码块标记
3. 函数入参要有类型注解，函数体内用简短注释说明关键逻辑
4. 妥善处理边界值和异常情况，确保函数健壮可靠
5. 如果faker模块有可用的方法，优先使用faker中的方法，faker中没有才使用随机数生成

可用库（以下库已预加载到执行环境，可直接使用，无需 import）：
{libraries}

输出要求（非常重要）：
- 必须且只能返回一个合法的 JSON 对象，不要包含任何其他说明文字
- 不要使用 markdown 代码块（不要 ```json 或 ``` 标记）
- 直接以 {{ 开头，以 }} 结尾
- JSON 结构如下：
{{
  "name": "函数名(snake_case)",
  "display_name": "函数中文显示名称",
  "code": "完整的Python函数定义代码字符串",
  "description": "函数功能描述",
  "params": [{{"name":"参数名","type":"参数类型","description":"描述","required":true,"default":null}}],
  "return_type": "返回值类型",
  "example": "调用示例"
}}
"""


def _build_ai_generate_prompt() -> str:
    from app.utils.script_runtime.script_env import get_libraries_description

    return _AI_GENERATE_SYSTEM_PROMPT.format(libraries=get_libraries_description())


def _extract_json_from_llm_response(text: str) -> dict:
    """从 LLM 响应中提取 JSON，兼容思维链模型（<think> 标签）和 markdown 代码块包裹"""
    # 去掉 <think>...</think> 思维链内容
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # 去掉 markdown 代码块标记
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "").strip()
    # 提取最外层 {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"响应中未找到有效的 JSON 对象，原始内容：{text[:200]}")
    return json.loads(text[start : end + 1])


@router.post(
    "/ai-generate",
    summary="AI 生成全局函数",
    response_model=ResponseModel[FunctionResponse],
)
async def ai_generate_function(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:create"))
    ],
    _llm: Annotated[object, Depends(deps.get_user_llm)],
    obj_in: FunctionAIGenerateRequest,
    project_id: int,
) -> ResponseModel[FunctionResponse]:
    """
    AI 生成全局函数

    根据自然语言需求描述，调用 LLM 生成 Python 工具函数并保存到项目全局函数表。

    - **requirement**: 自然语言描述的函数需求
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    import asyncio

    messages = [
        SystemMessage(content=_build_ai_generate_prompt()),
        HumanMessage(content=f"请根据以下需求生成工具函数：\n{obj_in.requirement}"),
    ]
    try:
        response = await asyncio.to_thread(get_current_llm().invoke, messages)
        raw_data = _extract_json_from_llm_response(response.content)
        result = _GeneratedFunction(**raw_data)
    except ConnectionError:
        _logger.warning("AI 生成函数时 LLM 连接失败")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务连接失败，请稍后重试",
        )
    except Exception as e:
        _logger.exception("AI 生成函数失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 生成失败：{str(e)}",
        )

    # 验证生成的代码可以正常编译执行
    if _compile_db_function(result.name, result.code) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI 生成的函数代码无法编译，请重试或调整需求描述",
        )

    try:
        func_create = FunctionCreate(
            name=result.name,
            display_name=result.display_name,
            language="python",
            code=result.code,
            description=result.description,
            params=[
                FunctionParam(
                    name=p.name,
                    type=p.type,
                    description=p.description or "",
                    required=p.required,
                    default=p.default,
                )
                for p in (result.params or [])
            ],
            return_type=result.return_type or "str",
            example=result.example or "",
            is_active=True,
        )
    except Exception as e:
        _logger.exception("AI 生成的函数数据校验失败")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"AI 生成的函数数据格式不正确：{str(e)}",
        )

    try:
        func = await FunctionService.create_function(
            db,
            obj_in=func_create,
            project_id=project_id,
            created_by=current_user.id,
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    return ResponseModel(
        data=FunctionResponse(
            id=func.id,
            project_id=func.project_id,
            name=func.name,
            display_name=func.display_name,
            language=func.language,
            code=func.code,
            description=func.description,
            params=func.params if isinstance(func.params, list) else [],
            return_type=func.return_type,
            example=func.example,
            is_built_in=func.is_built_in,
            is_active=func.is_active,
            created_by=func.created_by,
            created_at=func.created_at.isoformat() if func.created_at else "",
            updated_at=func.updated_at.isoformat() if func.updated_at else "",
        ),
        message="AI 生成成功",
    )


@router.put(
    "/{function_id}",
    summary="更新函数",
    response_model=ResponseModel[dict],
)
async def update_function(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:edit"))],
    function_id: int,
    obj_in: FunctionUpdate,
    project_id: int,
) -> ResponseModel[dict]:
    """
    更新函数

    可以更新函数的部分或全部字段
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取函数
    func = await global_function.get(db, id=function_id)
    if not func:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="函数不存在",
        )

    try:
        updated_func = await FunctionService.update_function(
            db, db_obj=func, obj_in=obj_in
        )
        return ResponseModel(
            data={"id": updated_func.id, "display_name": updated_func.display_name},
            message="更新成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/{function_id}/test",
    summary="测试函数",
    response_model=ResponseModel[FunctionTestResponse],
)
async def test_function(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
    function_id: int,
    test_request: FunctionTestRequest,
    project_id: int,
) -> ResponseModel[FunctionTestResponse]:
    """
    测试函数执行

    执行函数并返回执行结果

    - **params**: 函数参数
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取函数
    func = await global_function.get(db, id=function_id)
    if not func:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="函数不存在",
        )

    # 测试函数
    result = await FunctionService.test_function(
        db, db_obj=func, params=test_request.params
    )

    # 根据执行结果返回不同的状态码和消息
    if result.success:
        return ResponseModel(data=result, message="执行成功")
    else:
        return ResponseModel(code=400, data=result, message="执行失败")


@router.put(
    "/{function_id}/status",
    summary="启用/禁用函数",
    response_model=ResponseModel[dict],
)
async def update_function_status(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:edit"))],
    function_id: int,
    status_update: FunctionStatusUpdate,
    project_id: int,
) -> ResponseModel[dict]:
    """
    启用/禁用函数

    - **is_active**: 是否启用
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取函数
    func = await global_function.get(db, id=function_id)
    if not func:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="函数不存在",
        )

    # 更新状态
    updated_func = await FunctionService.update_function_status(
        db, db_obj=func, is_active=status_update.is_active
    )

    return ResponseModel(
        data={"id": updated_func.id, "is_active": updated_func.is_active},
        message="状态更新成功",
    )


@router.delete(
    "/{function_id}",
    summary="删除函数",
    response_model=ResponseModel[None],
)
async def delete_function(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:delete"))
    ],
    function_id: int,
    project_id: int,
) -> ResponseModel[None]:
    """
    删除函数

    注意：不能删除内置函数
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    try:
        await FunctionService.delete_function(db, func_id=function_id)
        return ResponseModel(message="删除成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )
