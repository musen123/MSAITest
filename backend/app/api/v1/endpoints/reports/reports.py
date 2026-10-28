"""
测试报告 API 端点

实时聚合功能和 App 两类测试执行数据（功能/App），提供汇总统计和执行记录列表。
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.project.member import project_member
from app.models.auth.user import User
from app.schemas.report import (
    ReportExecutionListResponse,
    ReportSummary,
)
from app.services.project.project_service import ProjectService
from app.services.report import ReportService

router = APIRouter()


async def _check_access(db: AsyncSession, project_id: int, user_id: int) -> None:
    """验证项目访问权限，无权限抛出 403。"""
    is_admin = await ProjectService._is_super_admin(db, user_id)
    if not is_admin:
        if not await project_member.is_member(
            db, project_id=project_id, user_id=user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问该项目",
            )


@router.get(
    "/summary",
    summary="获取报告汇总统计",
    response_model=ResponseModel[ReportSummary],
)
async def get_report_summary(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("report:view"))],
    start_date: Optional[datetime] = Query(default=None, description="开始时间"),
    end_date: Optional[datetime] = Query(default=None, description="结束时间"),
) -> ResponseModel[ReportSummary]:
    """
    汇总功能和 App 两类测试执行数据。

    - **start_date / end_date**：不传则默认最近 30 天
    """
    await _check_access(db, project_id, current_user.id)
    summary = await ReportService.get_summary(
        db,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ResponseModel(data=summary)


@router.get(
    "/executions",
    summary="获取执行记录列表",
    response_model=ResponseModel[ReportExecutionListResponse],
)
async def get_executions(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("report:view"))],
    exec_type: Optional[str] = Query(
        default=None,
        description="执行类型：functional / app，不传返回全部",
    ),
    start_date: Optional[datetime] = Query(default=None, description="开始时间"),
    end_date: Optional[datetime] = Query(default=None, description="结束时间"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> ResponseModel[ReportExecutionListResponse]:
    """
    分页获取功能和 App 两类执行记录，按执行时间倒序排列。

    - **exec_type**：functional / app，不传则返回全部类型
    - **start_date / end_date**：不传则默认最近 30 天
    """
    await _check_access(db, project_id, current_user.id)

    if exec_type and exec_type not in ("functional", "app"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="exec_type 仅支持 functional / app",
        )

    result = await ReportService.get_executions(
        db,
        project_id=project_id,
        exec_type=exec_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data=result)
