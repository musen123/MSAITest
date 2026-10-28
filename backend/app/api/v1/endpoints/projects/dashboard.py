"""项目概览仪表盘 API"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.project.member import project_member
from app.models.auth.user import User
from app.services.project.project_service import ProjectService

router = APIRouter()


@router.get(
    "/{project_id}/dashboard",
    summary="项目概览仪表盘聚合统计",
    response_model=ResponseModel[dict],
)
async def get_project_dashboard(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:view"))
    ],
    days: int = Query(default=7, ge=1, le=30, description="时间窗口天数"),
) -> ResponseModel[dict]:
    # 项目级权限：超管或项目成员（与 /{project_id}/statistics 口径一致）
    is_super_admin = await ProjectService._is_super_admin(db, current_user.id)
    if not is_super_admin:
        if not await project_member.is_member(
            db, project_id=project_id, user_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问该项目",
            )

    from app.services.project import dashboard_service

    data = await dashboard_service.get_dashboard(
        db, project_id=project_id, days=days
    )
    return success_response(data=data)
