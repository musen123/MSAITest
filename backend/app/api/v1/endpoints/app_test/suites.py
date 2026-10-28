"""APP 自动化套件端点（项目域，P4）

/projects/{project_id}/app/suites：套件 CRUD + 编排（全量替换）+ 手动执行。
套件 = 有序用例编组，run_app_suite 图在同一设备一锁贯穿顺序回放。

两层门禁同 scripts.py：require_permission(app_test:*) + require_project_access
+ 归属断言（防 IDOR）。权限码复用 app_test:*（套件即用例编组，无新码——
避免登录快照失效坑）。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, page_response, success_response
from app.crud.app_test import (
    crud_app_script,
    crud_app_suite,
    crud_app_suite_execution,
)
from app.models.auth.user import User
from app.schemas.app_test import (
    AppSuiteCaseItem,
    AppSuiteCasesReplaceIn,
    AppSuiteCreate,
    AppSuiteDetailOut,
    AppSuiteOut,
    AppSuiteRunIn,
    AppSuiteUpdate,
)
from app.utils.project_permission import require_project_access

router = APIRouter()

_ALLOWED_STRATEGY = {"continue", "stop"}


async def _ensure_suite_in_project(
    db: AsyncSession, *, project_id: int, suite_id: int, user_id: int
):
    """项目成员校验 + 套件归属断言（防跨项目 IDOR，不符按 404）。"""
    await require_project_access(db, project_id, user_id)
    suite = await crud_app_suite.get_in_project(db, project_id, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="套件不存在")
    return suite


async def _suite_detail(db: AsyncSession, suite) -> AppSuiteDetailOut:
    rows = await crud_app_suite.get_cases_with_script(db, suite.id)
    # 先按基类校验（不含 cases 字段，避免 Pydantic 去读 ORM 的 suite.cases
    # 关系——那是裸 AppSuiteCase 对象、不带 script_name，会校验失败），
    # 再补编排明细构造 detail。
    base = AppSuiteOut.model_validate(suite).model_dump()
    base["case_count"] = len(rows)
    return AppSuiteDetailOut(
        **base,
        cases=[
            AppSuiteCaseItem(
                id=c.id,
                script_id=s.id,
                script_name=s.name,
                script_status=s.status,
                script_platform=s.platform or "android",
                sort_order=c.sort_order,
                enabled=c.enabled,
            )
            for c, s in rows
        ],
    )


@router.get("", summary="套件列表")
async def list_suites(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    await require_project_access(db, project_id, current_user.id)
    rows, total = await crud_app_suite.get_list(
        db,
        project_id,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = []
    for suite, case_count in rows:
        out = AppSuiteOut.model_validate(suite)
        out.case_count = case_count
        items.append(out.model_dump(mode="json"))
    return page_response(items=items, total=total, page=page, page_size=page_size)


@router.post("", summary="创建套件", response_model=ResponseModel[AppSuiteOut])
async def create_suite(
    project_id: int,
    body: AppSuiteCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:create"))],
):
    await require_project_access(db, project_id, current_user.id)
    if body.failure_strategy not in _ALLOWED_STRATEGY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="failure_strategy 只支持 continue/stop"
        )
    suite = await crud_app_suite.create(
        db,
        project_id=project_id,
        name=body.name,
        description=body.description,
        device_udid=body.device_udid,
        failure_strategy=body.failure_strategy,
        created_by=current_user.id,
    )
    return ResponseModel(data=AppSuiteOut.model_validate(suite), message="套件已创建")


@router.get(
    "/{suite_id}", summary="套件详情（含编排）", response_model=ResponseModel[AppSuiteDetailOut]
)
async def get_suite(
    project_id: int,
    suite_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
):
    suite = await _ensure_suite_in_project(
        db, project_id=project_id, suite_id=suite_id, user_id=current_user.id
    )
    return ResponseModel(data=await _suite_detail(db, suite))


@router.put(
    "/{suite_id}", summary="更新套件", response_model=ResponseModel[AppSuiteOut]
)
async def update_suite(
    project_id: int,
    suite_id: int,
    body: AppSuiteUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:edit"))],
):
    suite = await _ensure_suite_in_project(
        db, project_id=project_id, suite_id=suite_id, user_id=current_user.id
    )
    changes = body.model_dump(exclude_unset=True)
    if (
        "failure_strategy" in changes
        and changes["failure_strategy"] not in _ALLOWED_STRATEGY
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="failure_strategy 只支持 continue/stop"
        )
    suite = await crud_app_suite.update(db, suite, changes)
    return ResponseModel(data=AppSuiteOut.model_validate(suite), message="套件已更新")


@router.delete(
    "/{suite_id}", summary="删除套件", response_model=ResponseModel[dict]
)
async def delete_suite(
    project_id: int,
    suite_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:delete"))],
):
    suite = await _ensure_suite_in_project(
        db, project_id=project_id, suite_id=suite_id, user_id=current_user.id
    )
    await crud_app_suite.remove(db, suite)
    return success_response(data={"deleted": True}, message="套件已删除")


@router.put(
    "/{suite_id}/cases",
    summary="全量替换编排（数组顺序即执行顺序）",
    response_model=ResponseModel[AppSuiteDetailOut],
)
async def replace_suite_cases(
    project_id: int,
    suite_id: int,
    body: AppSuiteCasesReplaceIn,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:edit"))],
):
    suite = await _ensure_suite_in_project(
        db, project_id=project_id, suite_id=suite_id, user_id=current_user.id
    )
    # 归属断言：所有 script_id 必须在本项目（防跨项目挂靠 IDOR）
    for item in body.items:
        script = await crud_app_script.get_in_project(db, project_id, item.script_id)
        if script is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"用例不存在：{item.script_id}"
            )
    await crud_app_suite.replace_cases(
        db, suite_id, [item.model_dump() for item in body.items]
    )
    return ResponseModel(data=await _suite_detail(db, suite), message="编排已保存")


# ==================== 手动执行提交 ====================


@router.post(
    "/{suite_id}/run",
    summary="批量执行套件（提交 run_app_suite 任务）",
    response_model=ResponseModel[dict],
)
async def run_suite(
    project_id: int,
    suite_id: int,
    body: AppSuiteRunIn,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:execute"))],
):
    """提交批量回放：预创建 app_suite_execution → 立 ai_task → 投递 app_tasks 队列。

    设备优先级：body.device_udid > 套件默认设备；同套件活跃任务去重。
    """
    from app.crud.ai.ai_task import crud_ai_task
    from app.crud.app_device.device import crud_app_device
    from app.tasks.ai_task import safe_dispatch

    suite = await _ensure_suite_in_project(
        db, project_id=project_id, suite_id=suite_id, user_id=current_user.id
    )
    device_udid = body.device_udid or suite.device_udid or ""
    if not device_udid:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="缺执行设备：请求未带 device_udid 且套件未配默认设备",
        )
    device = await crud_app_device.get_by_udid(db, device_udid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="设备不存在")

    enabled_cases = [
        (c, s)
        for c, s in await crud_app_suite.get_cases_with_script(db, suite_id)
        if c.enabled
    ]
    if not enabled_cases:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="套件没有启用的用例，无法执行"
        )

    # 平台不匹配软拦截（force=true 跳过）：套件在一台设备上串行回放，
    # 混入异平台用例大概率静默失败在 launch/shell 步骤，先拦下来让用户确认
    device_platform = device.platform or "android"
    mismatched = [s.name for _, s in enabled_cases if (s.platform or "android") != device_platform]
    if mismatched and not body.force:
        preview = "、".join(mismatched[:3]) + ("…" if len(mismatched) > 3 else "")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"平台不匹配：{len(mismatched)} 条启用用例（{preview}）与设备平台 "
                f"{device_platform} 不一致；确认要执行请带 force=true 重新提交"
            ),
        )

    # 去重按 (套件, 设备)：同一套件可在不同设备并行执行（单 Agent 多设备并行）
    existing = await crud_ai_task.find_active(
        db,
        project_id=project_id,
        task_type="run_app_suite",
        biz_ref_id=suite_id,
        device_udid=device_udid,
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"该套件在此设备上已有进行中的执行任务（task_id={existing.id}）",
        )

    # 先立账：预创建执行汇总，前端立即可查
    execution = await crud_app_suite_execution.create(
        db,
        suite_id=suite_id,
        project_id=project_id,
        device_udid=device_udid,
        trigger_type="manual",
        status="pending",
        created_by=current_user.id,
    )
    task = await crud_ai_task.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        task_type="run_app_suite",
        title=f"App 套件执行：{suite.name}",
        input_params={
            "suite_id": suite_id,
            "suite_execution_id": execution.id,
            "device_udid": device_udid,
            "platform": device_platform,  # 任务中心观战直播选解码器
            "suite_name": suite.name,
            "trigger_type": "manual",
        },
        biz_ref_type="app_suite",
        biz_ref_id=suite_id,
    )
    await crud_app_suite_execution.update(db, execution, {"ai_task_id": str(task.id)})

    async_result = safe_dispatch("run_app_suite", task.id)
    if async_result is None:
        await crud_app_suite_execution.update(db, execution, {"status": "failed"})
        await crud_ai_task.set_failed(
            db, task_id=task.id, error_message="任务投递失败（broker 不可用）"
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务投递失败，请检查 Celery/Redis 服务",
        )
    return ResponseModel(
        data={"suite_execution_id": execution.id, "task_id": task.id},
        message="套件执行任务已提交",
    )
