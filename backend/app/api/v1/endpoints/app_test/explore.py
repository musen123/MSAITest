"""APP 探索式生成提交端点（项目域，P3）

POST /projects/{project_id}/app/automation/explore：一句自然语言目标 →
提交 explore_app_script 统一任务（app_tasks 队列）→ 返回 task_id，前端经
统一任务 SSE（/ai-tasks/{id}/stream）看进度。

独立挂 /app/automation 前缀（不进 /app/scripts——与 /scripts/{script_id}
同段数会被参数路由抢匹配，FastAPI 靠注册顺序不靠类型，见项目路由顺序坑）。

设备并发由 Redis 设备锁天然防重：探索图抢锁失败即任务失败，报错明确，
不做 find_active 去重。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.app_device.device import crud_app_device
from app.models.auth.user import User
from app.schemas.app_test import ExploreIn
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.post(
    "/explore",
    summary="探索式生成：一句目标 → 自动探索 → 沉淀可回放用例（P3）",
    response_model=ResponseModel[dict],
)
async def submit_explore(
    project_id: int,
    body: ExploreIn,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:create"))],
):
    """校设备在线 → 立统一任务（explore_app_script）→ 投递 app_tasks 队列。"""
    from app.crud.ai.ai_task import crud_ai_task
    from app.tasks.ai_task import safe_dispatch

    await require_project_access(db, project_id, current_user.id)

    device = await crud_app_device.get_by_udid(db, body.device_udid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="设备不存在")
    # 廉价预检（库字段）；Agent 是否真在线由探索图首个 RPC 快速失败给出明确报错
    if device.state != "device":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"设备状态异常（{device.state}），无法探索"
        )

    goal = body.goal.strip()
    task = await crud_ai_task.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        task_type="explore_app_script",
        title=f"App 探索生成：{goal[:30]}",
        input_params={
            "device_udid": body.device_udid,
            "platform": device.platform or "android",  # 任务中心观战直播选解码器
            "goal": goal,
            "script_name": (body.script_name or "").strip(),
            "app_hint": (body.app_hint or "").strip(),
            "verify": body.verify,
            "suggest_asserts": body.suggest_asserts,
        },
        biz_ref_type="app_explore",
    )

    async_result = safe_dispatch("explore_app_script", task.id)
    if async_result is None:
        await crud_ai_task.set_failed(
            db, task_id=task.id, error_message="任务投递失败（broker 不可用）"
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务投递失败，请检查 Celery/Redis 服务",
        )
    return ResponseModel(data={"task_id": task.id}, message="探索任务已提交")
