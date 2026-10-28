"""
测试环境管理 API 端点

处理测试环境的 CRUD、设置默认、克隆等操作
"""

import json
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel
from app.crud.project import project as project_crud
from app.crud.test_environment import environment
from app.models.auth.user import User
from app.schemas.test_environment.environment import (
    EnvironmentCloneRequest,
    EnvironmentCloneResponse,
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
    SutPrometheusTestRequest,
)
from app.services.test_environment.environment_service import EnvironmentService

router = APIRouter()


async def check_project_access(db: AsyncSession, project_id: int, user_id: int) -> bool:
    """
    检查用户是否有项目访问权限

    系统管理员可以访问所有项目
    """
    project_obj = await project_crud.get(db, id=project_id)
    if not project_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    from app.services.project.project_service import ProjectService

    if await ProjectService._is_super_admin(db, user_id):
        return True
    from app.crud.project import project_member

    return await project_member.is_member(db, project_id=project_id, user_id=user_id)


@router.get(
    "", summary="获取环境列表", response_model=ResponseModel[list[EnvironmentResponse]]
)
async def get_environments(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
    project_id: int,
    is_global: bool | None = Query(default=None, description="是否仅获取全局环境"),
    env_type: int | None = Query(
        default=None, description="环境类型: 1=接口测试 2=UI测试"
    ),
    keyword: str | None = Query(default=None, description="搜索关键词"),
) -> ResponseModel[list[EnvironmentResponse]]:
    """
    获取测试环境列表

    支持按全局环境筛选和关键词搜索

    - **is_global**: 是否仅获取全局环境
    - **keyword**: 搜索环境名称或描述
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    envs, _ = await environment.get_multi_by_project(
        db,
        project_id=project_id,
        is_global=is_global,
        env_type=env_type,
        keyword=keyword,
    )
    items = []
    for env in envs:
        var_count = await environment.count_variables(db, env_id=env.id)
        pre_script_data = None
        post_script_data = None
        items.append(
            EnvironmentResponse(
                id=env.id,
                project_id=env.project_id,
                name=env.name,
                base_url=env.base_url,
                description=env.description,
                env_type=env.env_type,
                is_default=env.is_default,
                is_global=env.is_global,
                proxy_url=env.proxy_url,
                timeout=env.timeout,
                verify_ssl=bool(env.verify_ssl),
                allow_redirects=bool(env.allow_redirects),
                keep_cookies=bool(env.keep_cookies),
                retry_times=env.retry_times,
                pre_script=pre_script_data,
                post_script=post_script_data,
                variable_count=var_count,
                created_at=env.created_at.isoformat() if env.created_at else "",
                updated_at=env.updated_at.isoformat() if env.updated_at else "",
            )
        )
    return ResponseModel(data=items)


@router.get("/{env_id}", summary="获取环境详情", response_model=ResponseModel[dict])
async def get_environment_detail(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:view"))],
    project_id: int,
    env_id: int,
) -> ResponseModel[dict]:
    """
    获取测试环境详情

    包含环境的变量列表
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    try:
        env_detail = await EnvironmentService.get_environment_detail(db, env_id=env_id)
        return ResponseModel(data=env_detail)
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.post(
    "/{env_id}/debug-script",
    summary="调试运行前后置脚本",
    response_model=ResponseModel[dict],
)
async def debug_script(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:edit"))],
    env_id: int,
    project_id: int,
    script_type: str = Query(..., description="脚本类型: pre / post"),
) -> ResponseModel[dict]:
    """
    在沙箱中调试运行环境的前置或后置脚本，返回执行结果和环境变量快照。

    不会修改数据库中的环境变量，仅用于验证脚本是否正确。
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIRONMENT, detail="无权限访问该项目"
        )
    env = await environment.get_with_variables(db, env_id=env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="测试环境不存在"
        )
    if script_type == "pre":
        raw = env.pre_script
        script_code = json.loads(raw).get("code", "") if raw else ""
    elif script_type == "post":
        raw = env.post_script
        script_code = json.loads(raw).get("code", "") if raw else ""
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="script_type 仅支持 pre / post",
        )
    if not script_code or not script_code.strip():
        return ResponseModel(
            data={"success": True, "output": "脚本为空，无需执行", "env_data": {}},
            message="脚本为空",
        )
    test_env_data = {
        "base_url": env.base_url,
        "proxy_url": env.proxy_url,
        "timeout": env.timeout or 30,
    }
    if env.variables:
        for var in env.variables:
            if var.is_active:
                test_env_data[var.name] = var.value
    from app.utils.script_runtime.script_env import build_script_globals
    from app.crud.test_environment import global_function as crud_global_function
    from app.utils.script_runtime.global_function_builder import (
        build_runtime_global_function,
    )
    from io import StringIO
    import sys

    if project_id:
        db_funcs, _ = await crud_global_function.get_multi_by_project(
            db, project_id=project_id, language="python", is_active=True, limit=10000
        )
        runtime_gf = build_runtime_global_function(db_funcs)
    else:
        runtime_gf = None
    script_globals = (
        build_script_globals(global_function=runtime_gf)
        if runtime_gf
        else build_script_globals()
    )
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_output = StringIO()
    sys.stdout = captured_output
    sys.stderr = captured_output
    try:
        exec(script_code, script_globals, {"env_data": test_env_data})
        output = captured_output.getvalue()
        env_snapshot = {
            k: v
            for (k, v) in test_env_data.items()
            if not k.startswith("_") and (not k.startswith("__"))
        }
        return ResponseModel(
            data={
                "success": True,
                "output": output or "脚本执行成功，无输出",
                "env_data": env_snapshot,
            },
            message="脚本调试执行成功",
        )
    except Exception as e:
        output = captured_output.getvalue()
        import traceback

        tb = traceback.format_exc()
        return ResponseModel(
            data={"success": False, "output": output, "error": str(e), "traceback": tb},
            message="脚本调试执行失败",
        )
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


@router.post("", summary="创建环境", response_model=ResponseModel[dict])
async def create_environment(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:create"))
    ],
    obj_in: EnvironmentCreate,
    project_id: int,
) -> ResponseModel[dict]:
    """
    创建测试环境

    - **name**: 环境名称
    - **base_url**: 环境基础URL
    - **description**: 环境描述
    - **is_default**: 是否默认环境
    - **is_global**: 是否全局环境
    - **proxy_url**: 代理URL
    - **timeout**: 超时时间（秒）
    - **pre_script**: 前置脚本
    - **post_script**: 后置脚本
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    try:
        env = await EnvironmentService.create_environment(
            db, obj_in=obj_in, project_id=project_id
        )
        return ResponseModel(data={"id": env.id, "name": env.name}, message="创建成功")
    except BusinessException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.put("/{env_id}", summary="更新环境", response_model=ResponseModel[dict])
async def update_environment(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:edit"))],
    env_id: int,
    obj_in: EnvironmentUpdate,
    project_id: int,
) -> ResponseModel[dict]:
    """
    更新测试环境

    可以更新环境的部分或全部字段
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    env = await environment.get(db, id=env_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="环境不存在")
    try:
        updated_env = await EnvironmentService.update_environment(
            db, db_obj=env, obj_in=obj_in
        )
        return ResponseModel(
            data={"id": updated_env.id, "name": updated_env.name}, message="更新成功"
        )
    except BusinessException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/{env_id}/set-default", summary="设置默认环境", response_model=ResponseModel[dict]
)
async def set_default_environment(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("environment:edit"))],
    env_id: int,
    project_id: int,
) -> ResponseModel[dict]:
    """
    设置默认环境

    将指定环境设置为项目的默认环境，会自动取消其他环境的默认状态
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    try:
        env = await EnvironmentService.set_default_environment(
            db, project_id=project_id, env_id=env_id
        )
        return ResponseModel(
            data={"id": env.id, "is_default": True}, message="设置成功"
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.post(
    "/{env_id}/clone",
    summary="克隆环境",
    response_model=ResponseModel[EnvironmentCloneResponse],
)
async def clone_environment(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:create"))
    ],
    env_id: int,
    clone_data: EnvironmentCloneRequest,
    project_id: int,
) -> ResponseModel[EnvironmentCloneResponse]:
    """
    克隆测试环境

    复制环境及其所有变量到新环境

    - **name**: 新环境的名称
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    source_env = await environment.get(db, id=env_id)
    if not source_env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="环境不存在")
    try:
        result = await EnvironmentService.clone_environment(
            db, source_env=source_env, clone_data=clone_data
        )
        return ResponseModel(data=result, message="克隆成功")
    except BusinessException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete("/{env_id}", summary="删除环境", response_model=ResponseModel[None])
async def delete_environment(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:delete"))
    ],
    env_id: int,
    project_id: int,
) -> ResponseModel[None]:
    """
    删除测试环境

    注意：不能删除默认环境
    """
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )
    try:
        await EnvironmentService.delete_environment(db, env_id=env_id)
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
