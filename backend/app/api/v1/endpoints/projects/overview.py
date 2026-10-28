"""
工作台项目总览 API 端点

独立路径 /projects-overview，避免与 /projects/{project_id} 冲突。
为「我的项目」页面顶部 5 张统计卡提供真实数据与环比趋势。
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import deps
from app.core.response import ResponseModel
from app.models.auth.user import User
from app.models.bug.bug import Bug, BugStatus
from app.models.app_test.script import AppScript
from app.models.func_test.test_case import FuncTestCase
from app.models.project.member import ProjectMember
from app.models.project.module import ProjectModule
from app.models.project.project import Project, ProjectStatus

router = APIRouter()


class OverviewMetric(BaseModel):
    """单项指标（数值 + 环比）"""

    value: int = Field(description="当前值")
    trend: float = Field(description="较上一窗口变化百分比（正=上升，负=下降）")
    compare_window: str = Field(description="比较窗口：week | month")


class ProjectsOverview(BaseModel):
    """工作台项目总览"""

    project_count: OverviewMetric = Field(description="活跃项目总数")
    member_count: OverviewMetric = Field(description="团队成员总数（去重）")
    module_count: OverviewMetric = Field(description="模块总数")
    case_count: OverviewMetric = Field(description="用例总数（功能+接口+Web+App+压测）")
    bug_count: OverviewMetric = Field(description="未关闭缺陷总数")
    generated_at: str = Field(description="数据快照时间（ISO 8601）")


def _compute_trend(current: int, previous: int) -> float:
    """
    计算环比百分比

    - 上一窗口值为 0 且当前也为 0：0%
    - 上一窗口值为 0 但当前 > 0：+100%（视为翻倍）
    - 否则：(current - previous) / previous * 100，保留 1 位小数
    """
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


def _build_metric(current: int, previous: int, window: str) -> OverviewMetric:
    return OverviewMetric(
        value=current, trend=_compute_trend(current, previous), compare_window=window
    )


async def _get_visible_project_ids(db: AsyncSession, current_user: User) -> list[int]:
    """
    获取当前用户可见的「活跃」项目 ID 列表

    规则：
    - 系统管理员（super_admin）→ 所有 active 项目
    - 其他用户 → 仅自己创建 OR 自己是成员（tb_project_member.user_id = me）的 active 项目
    """
    is_super_admin = "super_admin" in (current_user.role_codes or [])
    if is_super_admin:
        stmt = select(Project.id).where(Project.status == ProjectStatus.ACTIVE)
    else:
        member_subq = select(ProjectMember.project_id).where(
            ProjectMember.user_id == current_user.id
        )
        stmt = select(Project.id).where(
            and_(
                Project.status == ProjectStatus.ACTIVE,
                or_(
                    Project.created_by_id == current_user.id,
                    Project.id.in_(member_subq),
                ),
            )
        )
    result = await db.execute(stmt)
    return [row[0] for row in result.fetchall()]


@router.get(
    "",
    summary="工作台项目总览（5 张统计卡真实数据）",
    response_model=ResponseModel[ProjectsOverview],
)
async def get_projects_overview(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("project:view"))],
    compare_window: Literal["week", "month"] = Query(
        default="week", description="环比窗口：week=上周同期；month=上月同期"
    ),
) -> ResponseModel[ProjectsOverview]:
    """
    获取当前用户可见项目的 5 项聚合指标与环比。

    - **project_count**    活跃项目总数
    - **member_count**     团队成员数（按 user_id 去重）
    - **module_count**     模块总数
    - **case_count**       用例总数（功能 + 接口 + Web + App + 压测）
    - **bug_count**        未关闭的缺陷数（new/assigned/in_progress/resolved）
    """
    window_days = 7 if compare_window == "week" else 30
    now = datetime.now(timezone.utc)
    prev_threshold = now - timedelta(days=window_days)
    visible_project_ids = await _get_visible_project_ids(db, current_user)
    if not visible_project_ids:
        empty = _build_metric(0, 0, compare_window)
        return ResponseModel(
            data=ProjectsOverview(
                project_count=empty,
                member_count=empty.model_copy(),
                module_count=empty.model_copy(),
                case_count=empty.model_copy(),
                bug_count=empty.model_copy(),
                generated_at=now.isoformat(),
            )
        )
    project_count_current = len(visible_project_ids)
    project_count_prev_stmt = select(func.count(Project.id)).where(
        Project.id.in_(visible_project_ids), Project.created_at < prev_threshold
    )
    project_count_prev = (await db.execute(project_count_prev_stmt)).scalar_one() or 0
    member_count_current_stmt = select(
        func.count(distinct(ProjectMember.user_id))
    ).where(ProjectMember.project_id.in_(visible_project_ids))
    member_count_current = (
        await db.execute(member_count_current_stmt)
    ).scalar_one() or 0
    member_count_prev_stmt = select(func.count(distinct(ProjectMember.user_id))).where(
        ProjectMember.project_id.in_(visible_project_ids),
        ProjectMember.created_at < prev_threshold,
    )
    member_count_prev = (await db.execute(member_count_prev_stmt)).scalar_one() or 0
    module_count_current_stmt = select(func.count(ProjectModule.id)).where(
        ProjectModule.project_id.in_(visible_project_ids)
    )
    module_count_current = (
        await db.execute(module_count_current_stmt)
    ).scalar_one() or 0
    module_count_prev_stmt = select(func.count(ProjectModule.id)).where(
        ProjectModule.project_id.in_(visible_project_ids),
        ProjectModule.created_at < prev_threshold,
    )
    module_count_prev = (await db.execute(module_count_prev_stmt)).scalar_one() or 0
    case_count_current = 0
    case_count_prev = 0
    for cm in (FuncTestCase, AppScript):
        case_count_current += (
            await db.execute(
                select(func.count(cm.id)).where(cm.project_id.in_(visible_project_ids))
            )
        ).scalar_one() or 0
        case_count_prev += (
            await db.execute(
                select(func.count(cm.id)).where(
                    cm.project_id.in_(visible_project_ids),
                    cm.created_at < prev_threshold,
                )
            )
        ).scalar_one() or 0
    open_statuses = [
        BugStatus.NEW.value,
        BugStatus.ASSIGNED.value,
        BugStatus.IN_PROGRESS.value,
        BugStatus.RESOLVED.value,
        BugStatus.VERIFIED.value,
    ]
    bug_count_current_stmt = select(func.count(Bug.id)).where(
        Bug.project_id.in_(visible_project_ids),
        Bug.status.in_(open_statuses),
        Bug.is_archived.is_(False),
    )
    bug_count_current = (await db.execute(bug_count_current_stmt)).scalar_one() or 0
    bug_count_prev_stmt = select(func.count(Bug.id)).where(
        Bug.project_id.in_(visible_project_ids),
        Bug.status.in_(open_statuses),
        Bug.is_archived.is_(False),
        Bug.created_at < prev_threshold,
    )
    bug_count_prev = (await db.execute(bug_count_prev_stmt)).scalar_one() or 0
    overview = ProjectsOverview(
        project_count=_build_metric(
            project_count_current, project_count_prev, compare_window
        ),
        member_count=_build_metric(
            member_count_current, member_count_prev, compare_window
        ),
        module_count=_build_metric(
            module_count_current, module_count_prev, compare_window
        ),
        case_count=_build_metric(case_count_current, case_count_prev, compare_window),
        bug_count=_build_metric(bug_count_current, bug_count_prev, compare_window),
        generated_at=now.isoformat(),
    )
    return ResponseModel(data=overview, message="success")
