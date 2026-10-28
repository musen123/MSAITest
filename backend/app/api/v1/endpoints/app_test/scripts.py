"""APP 自动化用例 CRUD 端点（项目域，P2）

/projects/{project_id}/app/scripts：列表 / 创建 / 详情 / 更新 / 删除。
用例载体 = Midscene YAML（tasks 段为回放输入），录制操作台把回收的
YAML flow 存进来；执行记录列表也挂本前缀（经 script 归属项目）。

两层门禁（RBAC）：require_permission(app_test:*)（系统级）+
require_project_access（项目二元门禁）+ 归属断言（防 IDOR，同 web_test 先例）。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, page_response, success_response
from app.crud.app_test import crud_app_execution, crud_app_script
from app.models.auth.user import User
from app.schemas.app_test import (
    AppExecutionOut,
    AppScriptCreate,
    AppScriptOut,
    AppScriptUpdate,
)
from app.utils.project_permission import require_project_access

router = APIRouter()

_ALLOWED_STATUS = {"draft", "active", "disabled"}
_ALLOWED_PLATFORM = {"android", "harmony", "ios"}


async def _ensure_script_in_project(
    db: AsyncSession, *, project_id: int, script_id: int, user_id: int
):
    """项目成员校验 + 用例归属断言（防跨项目 IDOR，不符按 404）。"""
    await require_project_access(db, project_id, user_id)
    script = await crud_app_script.get_in_project(db, project_id, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用例不存在")
    return script


@router.get("", summary="用例列表")
async def list_scripts(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
    keyword: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    platform: Optional[str] = Query(None, description="android/harmony/ios"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    await require_project_access(db, project_id, current_user.id)
    items, total = await crud_app_script.get_list(
        db,
        project_id,
        keyword=keyword,
        status=status_filter,
        platform=platform if platform in _ALLOWED_PLATFORM else None,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return page_response(
        items=[AppScriptOut.model_validate(s).model_dump(mode="json") for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    summary="创建用例",
    response_model=ResponseModel[AppScriptOut],
)
async def create_script(
    project_id: int,
    body: AppScriptCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:create"))],
):
    await require_project_access(db, project_id, current_user.id)
    if body.status not in _ALLOWED_STATUS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="status 只支持 draft/active/disabled"
        )
    if body.platform not in _ALLOWED_PLATFORM:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="platform 只支持 android/harmony/ios"
        )
    script = await crud_app_script.create(
        db,
        project_id=project_id,
        name=body.name,
        yaml_content=body.yaml_content,
        platform=body.platform,
        target_app=body.target_app,
        description=body.description,
        status=body.status,
        created_by=current_user.id,
    )
    return ResponseModel(data=AppScriptOut.model_validate(script), message="用例已创建")


@router.get(
    "/{script_id}",
    summary="用例详情",
    response_model=ResponseModel[AppScriptOut],
)
async def get_script(
    project_id: int,
    script_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
):
    script = await _ensure_script_in_project(
        db, project_id=project_id, script_id=script_id, user_id=current_user.id
    )
    return ResponseModel(data=AppScriptOut.model_validate(script))


@router.put(
    "/{script_id}",
    summary="更新用例",
    response_model=ResponseModel[AppScriptOut],
)
async def update_script(
    project_id: int,
    script_id: int,
    body: AppScriptUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:edit"))],
):
    script = await _ensure_script_in_project(
        db, project_id=project_id, script_id=script_id, user_id=current_user.id
    )
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in _ALLOWED_STATUS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="status 只支持 draft/active/disabled"
        )
    if "platform" in changes and changes["platform"] not in _ALLOWED_PLATFORM:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="platform 只支持 android/harmony/ios"
        )
    script = await crud_app_script.update(db, script, changes)
    return ResponseModel(data=AppScriptOut.model_validate(script), message="用例已更新")


@router.delete(
    "/{script_id}",
    summary="删除用例",
    response_model=ResponseModel[dict],
)
async def delete_script(
    project_id: int,
    script_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:delete"))],
):
    script = await _ensure_script_in_project(
        db, project_id=project_id, script_id=script_id, user_id=current_user.id
    )
    await crud_app_script.remove(db, script)
    return success_response(data={"deleted": True}, message="用例已删除")


# ==================== 回放提交 ====================


@router.post(
    "/{script_id}/run",
    summary="回放用例（提交 run_app_script 任务，契约 §3.2）",
    response_model=ResponseModel[dict],
)
async def run_script(
    project_id: int,
    script_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:execute"))],
):
    """提交回放：预创建 app_execution → 立 ai_task → 投递 app_tasks 队列。

    body: {device_udid, force?}。同用例活跃任务去重；投递失败立即标失败不留
    running 残骸。用例↔设备平台不匹配软拦截（force=true 跳过——语义步骤
    aiTap/aiInput 跨平台其实可回放，launch/runAdbShell 类步骤才必失败）。
    """
    from app.crud.ai.ai_task import crud_ai_task
    from app.crud.app_device.device import crud_app_device
    from app.tasks.ai_task import safe_dispatch

    device_udid = str((body or {}).get("device_udid") or "")
    if not device_udid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="缺 device_udid")

    script = await _ensure_script_in_project(
        db, project_id=project_id, script_id=script_id, user_id=current_user.id
    )
    device = await crud_app_device.get_by_udid(db, device_udid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="设备不存在")

    script_platform = script.platform or "android"
    device_platform = device.platform or "android"
    if script_platform != device_platform and not bool((body or {}).get("force")):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"平台不匹配：用例为 {script_platform}，所选设备为 {device_platform}；"
                "确认要跨平台回放请带 force=true 重新提交"
            ),
        )

    # 去重按 (用例, 设备)：同一用例可在不同设备并行回放（单 Agent 多设备并行）
    existing = await crud_ai_task.find_active(
        db,
        project_id=project_id,
        task_type="run_app_script",
        biz_ref_id=script_id,
        device_udid=device_udid,
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"该用例在此设备上已有进行中的回放任务（task_id={existing.id}）",
        )

    # 先立账：预创建执行记录，前端立即可查
    execution = await crud_app_execution.create(
        db, script_id=script_id, device_udid=device_udid, status="pending"
    )
    task = await crud_ai_task.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        task_type="run_app_script",
        title=f"App 回放：{script.name}",
        input_params={
            "script_id": script_id,
            "execution_id": execution.id,
            "device_udid": device_udid,
            "platform": device_platform,  # 任务中心观战直播选解码器
            "script_name": script.name,
        },
        biz_ref_type="app_script",
        biz_ref_id=script_id,
    )
    await crud_app_execution.update(db, execution, {"ai_task_id": str(task.id)})

    async_result = safe_dispatch("run_app_script", task.id)
    if async_result is None:
        await crud_app_execution.update(db, execution, {"status": "failed"})
        await crud_ai_task.set_failed(
            db, task_id=task.id, error_message="任务投递失败（broker 不可用）"
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务投递失败，请检查 Celery/Redis 服务",
        )
    return ResponseModel(
        data={"execution_id": execution.id, "task_id": task.id},
        message="回放任务已提交",
    )


# ==================== 执行记录（读侧，经 script 归属项目） ====================


@router.get("/{script_id}/executions", summary="用例的执行记录列表")
async def list_script_executions(
    project_id: int,
    script_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    await _ensure_script_in_project(
        db, project_id=project_id, script_id=script_id, user_id=current_user.id
    )
    rows, total = await crud_app_execution.get_list(
        db,
        project_id,
        script_id=script_id,
        status=status_filter,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = []
    for execution, script_name, script_platform, device_model, device_platform in rows:
        out = AppExecutionOut.model_validate(execution)
        out.script_name = script_name
        out.script_platform = script_platform
        out.device_name = device_model
        out.device_platform = device_platform
        items.append(out.model_dump(mode="json"))
    return page_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
