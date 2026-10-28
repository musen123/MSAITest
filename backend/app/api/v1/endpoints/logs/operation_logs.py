"""
操作日志API

提供操作日志的查询和管理接口
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.auth.operation_log import operation_log_crud
from app.models.auth.operation_log import OperationLog
from app.schemas.auth.operation_log import (
    OperationLogResponse,
    OperationLogListResponse,
    OperationLogStatsResponse,
)

router = APIRouter()

# 操作类型选项（与 OperationLog.Action 枚举对齐：login/logout/create/update/delete/query/export/import）
ACTION_OPTIONS = [
    {"label": "查询", "value": "query"},
    {"label": "创建", "value": "create"},
    {"label": "更新", "value": "update"},
    {"label": "删除", "value": "delete"},
    {"label": "登录", "value": "login"},
    {"label": "登出", "value": "logout"},
    {"label": "导出", "value": "export"},
    {"label": "导入", "value": "import"},
]


@router.get(
    "/operation-logs/options",
    summary="获取操作日志筛选选项",
)
async def get_operation_log_options(
    current_user: Annotated[
        OperationLog, Depends(deps.require_permission("system:log"))
    ],
) -> ResponseModel[dict]:
    """获取操作类型和模块的筛选选项"""
    return ResponseModel(
        data={"actions": ACTION_OPTIONS},
        message="获取筛选选项成功",
    )


@router.get(
    "/operation-logs",
    summary="获取操作日志列表",
)
async def get_operation_logs(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        OperationLog, Depends(deps.require_permission("system:log"))
    ],
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    module: str | None = Query(None, description="操作模块"),
    action: str | None = Query(None, description="操作类型"),
    start_time: int | None = Query(None, description="开始时间戳"),
    end_time: int | None = Query(None, description="结束时间戳"),
) -> ResponseModel[OperationLogListResponse]:
    """
    获取操作日志列表

    支持按模块、操作类型、时间范围等条件筛选
    """
    filter_kwargs: dict = {}
    if module:
        filter_kwargs["module"] = module
    if action:
        filter_kwargs["action"] = action
    if start_time:
        filter_kwargs["created_at__gte"] = start_time
    if end_time:
        filter_kwargs["created_at__lte"] = end_time

    logs, total = await operation_log_crud.get_multi(
        db,
        skip=(page - 1) * page_size,
        limit=page_size,
        **filter_kwargs,
    )

    items = [OperationLogResponse.model_validate(log) for log in logs]

    return ResponseModel(
        data=OperationLogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        ),
        message="获取操作日志列表成功",
    )


@router.get(
    "/operation-logs/stats",
    summary="获取操作日志聚合统计",
)
async def get_operation_log_stats(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        OperationLog, Depends(deps.require_permission("system:log"))
    ],
    start_time: int | None = Query(
        None, description="起始时间戳（Unix 秒），不传默认为今日 0 点"
    ),
    end_time: int | None = Query(
        None, description="结束时间戳（Unix 秒），不传默认为当前时间"
    ),
    include_prev: bool = Query(
        True, description="是否同时计算上一区间指标（用于趋势）"
    ),
) -> ResponseModel[OperationLogStatsResponse]:
    """获取操作日志聚合统计指标

    用于前端"今日统计"卡片，包含：
      - total: 操作总数
      - users: 不重复的操作用户数
      - actions: 不重复的操作类型数
      - abnormal: 异常操作数（response_status >= 400）
      - prev_*: 上一窗口的同样指标（前端用于计算"较昨日 ↑X%"）
    """
    now = int(datetime.now().timestamp())
    if end_time is None:
        end_time = now
    if start_time is None:
        # 默认今日 0 点
        start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = int(start_dt.timestamp())

    stats = await operation_log_crud.get_stats(
        db,
        start_time=start_time,
        end_time=end_time,
        include_prev=include_prev,
    )

    return ResponseModel(
        data=OperationLogStatsResponse(**stats),
        message="获取操作日志统计成功",
    )


@router.get(
    "/operation-logs/{log_id}",
    summary="获取操作日志详情",
)
async def get_operation_log_detail(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        OperationLog, Depends(deps.require_permission("system:log"))
    ],
    log_id: int,
) -> ResponseModel[OperationLogResponse]:
    """获取操作日志详情"""
    log = await operation_log_crud.get(db, id=log_id)

    if not log:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="操作日志不存在",
        )

    return ResponseModel(
        data=OperationLogResponse.model_validate(log),
        message="获取操作日志详情成功",
    )
