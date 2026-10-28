"""
Celery worker / 队列监控 API（系统级，非项目）。

只读快照：worker 存活/并发/正在跑、队列积压、无人消费告警、beat 计划。
权限 `system:monitor`。数据源全原生（inspect + broker LLEN），见 services/celery_monitor.py。
"""

from typing import Annotated

from app.core import deps
from app.core.response import ResponseModel
from app.models.auth.user import User
from app.services import celery_monitor
from fastapi import APIRouter, Depends, Query

router = APIRouter()


@router.get(
    "/celery/monitor",
    summary="Celery worker/队列 监控快照",
    response_model=ResponseModel[dict],
)
async def get_celery_monitor(
    current_user: Annotated[
        User, Depends(deps.require_permission("system:monitor"))
    ],
    force: bool = Query(default=False, description="跳过数秒缓存强制刷新"),
) -> ResponseModel[dict]:
    """一份 worker/队列/beat 监控快照（默认数秒缓存，force=true 强刷）。"""
    data = await celery_monitor.get_snapshot(force=force)
    return ResponseModel(data=data)
