"""数据报表中心 API（测试资产 / 缺陷质量 / AI 提效）"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.project.member import project_member
from app.models.auth.user import User
from app.services.project.project_service import ProjectService

router = APIRouter()


async def _check_access(
    db: AsyncSession, project_id: int, user: User
) -> None:
    """项目级权限：超管或项目成员（与 dashboard/statistics 同口径）"""
    if await ProjectService._is_super_admin(db, user.id):
        return
    if not await project_member.is_member(
        db, project_id=project_id, user_id=user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )


@router.get(
    "/{project_id}/report/assets",
    summary="测试资产报表",
    response_model=ResponseModel[dict],
)
async def get_assets_report(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("report:view"))
    ],
    days: int = Query(default=30, ge=7, le=90),
) -> ResponseModel[dict]:
    await _check_access(db, project_id, current_user)
    from app.services.project import report_center_service

    data = await report_center_service.get_assets_report(
        db, project_id=project_id, days=days
    )
    return success_response(data=data)


@router.get(
    "/{project_id}/report/quality",
    summary="缺陷质量报表",
    response_model=ResponseModel[dict],
)
async def get_quality_report(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("report:view"))
    ],
    days: int = Query(default=30, ge=7, le=90),
) -> ResponseModel[dict]:
    await _check_access(db, project_id, current_user)
    from app.services.project import report_center_service

    data = await report_center_service.get_quality_report(
        db, project_id=project_id, days=days
    )
    return success_response(data=data)


@router.get(
    "/{project_id}/report/execution",
    summary="执行汇总报表",
    response_model=ResponseModel[dict],
)
async def get_execution_report(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("report:view"))
    ],
    days: int = Query(default=30, ge=7, le=90),
) -> ResponseModel[dict]:
    await _check_access(db, project_id, current_user)
    from app.services.project import report_center_service

    data = await report_center_service.get_execution_report(
        db, project_id=project_id, days=days
    )
    return success_response(data=data)


@router.get(
    "/{project_id}/module-stats",
    summary="列表页全量统计",
    response_model=ResponseModel[dict],
)
async def get_module_stats(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("report:view"))
    ],
    module: str = Query(description="统计模块"),
) -> ResponseModel[dict]:
    await _check_access(db, project_id, current_user)
    from app.services.project import module_stats_service

    if module not in module_stats_service.MODULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"module 必须是 {'/'.join(module_stats_service.MODULES)}",
        )
    data = await module_stats_service.get_module_stats(
        db, project_id=project_id, module=module
    )
    return success_response(data=data)


@router.get(
    "/{project_id}/report/ai-efficiency",
    summary="AI 提效报表",
    response_model=ResponseModel[dict],
)
async def get_ai_report(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("report:view"))
    ],
    days: int = Query(default=30, ge=7, le=90),
) -> ResponseModel[dict]:
    await _check_access(db, project_id, current_user)
    from app.services.project import report_center_service

    data = await report_center_service.get_ai_report(
        db, project_id=project_id, days=days
    )
    return success_response(data=data)
