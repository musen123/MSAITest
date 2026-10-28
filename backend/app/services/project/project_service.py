"""
项目业务服务层

处理项目相关的业务逻辑
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import BusinessException
from app.crud.project import project
from app.crud.project import project_config as config_crud
from app.crud.project import project_member as member_crud
from app.crud.project.member import ProjectRoleCode
from app.models.auth.user import User
from app.models.auth.user_role import UserRole
from app.models.project import Project, ProjectStatus
from app.models.func_test.case_execution import (
    FuncCaseExecution as CaseExecution,
    CaseExecuteResult as ExecuteStatus,
)
from app.models.app_test.script import AppScript
from app.services.func_test.statistics_service import (
    get_case_count as get_func_case_count,
)
from app.services.bug.statistics_service import get_bug_stats
from app.services.project.dashboard_service import _exec_window_agg
from app.schemas.project import (
    BugStatistics,
    CaseStatistics,
    ExecutionTrendItem,
    ProjectCreate,
    ProjectStatisticsResponse,
    ProjectUpdate,
)


class ProjectService:
    """
    项目业务服务类
    """

    @staticmethod
    async def _is_super_admin(db: AsyncSession, user_id: int) -> bool:
        """
        检查用户是否是系统管理员

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            bool: 是否是系统管理员
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
        for user_role in user.user_roles:
            if user_role.role.code == "super_admin":
                return True
        return False

    @staticmethod
    async def create_project(
        db: AsyncSession, *, obj_in: ProjectCreate, creator_id: int
    ) -> Project:
        """
        创建项目

        Args:
            db: 数据库会话
            obj_in: 创建数据
            creator_id: 创建者ID

        Returns:
            Project: 创建的项目

        Raises:
            BusinessException: 项目名称或标识已存在
        """
        if await project.name_exists(db, name=obj_in.name):
            raise BusinessException("项目名称已存在")
        if await project.code_exists(db, code=obj_in.code):
            raise BusinessException("项目标识已存在")
        project_data = obj_in.model_dump()
        project_data["created_by_id"] = creator_id
        project_data["status"] = ProjectStatus.ACTIVE
        db_obj = await project.create(db, obj_in=project_data)
        await member_crud.add_members(
            db,
            project_id=db_obj.id,
            user_ids=[creator_id],
            project_role_code=ProjectRoleCode.OWNER,
        )
        await config_crud.get_or_create(db, project_id=db_obj.id)
        return db_obj

    @staticmethod
    async def update_project(
        db: AsyncSession, *, db_obj: Project, obj_in: ProjectUpdate
    ) -> Project:
        """
        更新项目

        Args:
            db: 数据库会话
            db_obj: 数据库中的项目
            obj_in: 更新数据

        Returns:
            Project: 更新后的项目

        Raises:
            BusinessException: 项目名称已存在
        """
        if obj_in.name and obj_in.name != db_obj.name:
            if await project.name_exists(db, name=obj_in.name, exclude_id=db_obj.id):
                raise BusinessException("项目名称已存在")
        return await project.update(db, db_obj=db_obj, obj_in=obj_in)

    @staticmethod
    async def archive_project(db: AsyncSession, *, project_id: int) -> Project:
        """
        归档项目

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            Project: 归档后的项目

        Raises:
            BusinessException: 项目不存在或已归档
        """
        db_obj = await project.get_with_details(db, project_id=project_id)
        if not db_obj:
            raise BusinessException("项目不存在")
        if db_obj.status == ProjectStatus.ARCHIVED:
            raise BusinessException("项目已归档")
        return await project.update_status(
            db, project_id=project_id, status=ProjectStatus.ARCHIVED
        )

    @staticmethod
    async def restore_project(db: AsyncSession, *, project_id: int) -> Project:
        """
        恢复项目

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            Project: 恢复后的项目

        Raises:
            BusinessException: 项目不存在或未归档
        """
        db_obj = await project.get(db, id=project_id)
        if not db_obj:
            raise BusinessException("项目不存在")
        if db_obj.status != ProjectStatus.ARCHIVED:
            raise BusinessException("只能恢复已归档的项目")
        return await project.update_status(
            db, project_id=project_id, status=ProjectStatus.ACTIVE
        )

    @staticmethod
    async def delete_project(db: AsyncSession, *, project_id: int) -> bool:
        """
        删除项目

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            bool: 是否删除成功

        Raises:
            BusinessException: 项目不存在或有关联数据
        """
        db_obj = await project.get(db, id=project_id)
        if not db_obj:
            raise BusinessException("项目不存在")
        return await project.soft_delete(db, project_id=project_id)

    @staticmethod
    async def get_project_statistics(
        db: AsyncSession,
        *,
        project_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ProjectStatisticsResponse:
        """
        获取项目统计数据

        Args:
            db: 数据库会话
            project_id: 项目ID
            start_date: 统计开始日期
            end_date: 统计结束日期

        Returns:
            ProjectStatisticsResponse: 项目统计数据
        """
        case_stats = await ProjectService._calc_case_statistics(
            db, project_id=project_id
        )
        bug_stats = await ProjectService._calc_bug_statistics(db, project_id=project_id)
        trend = await ProjectService._calc_execution_trend(
            db, project_id=project_id, start_date=start_date, end_date=end_date
        )
        return ProjectStatisticsResponse(
            case_statistics=case_stats,
            bug_statistics=bug_stats,
            execution_trend=trend,
            member_statistics=[],
        )

    @staticmethod
    async def _calc_case_statistics(
        db: AsyncSession, *, project_id: int
    ) -> CaseStatistics:
        from app.services.project.dashboard_service import _case_counts

        by_type = await _case_counts(db, project_id)
        total = sum(by_type.values())
        stats = await _exec_window_agg(db, project_id, None, None)
        done = stats["passed"] + stats["failed"]
        return CaseStatistics(
            total=total,
            executed=stats["total"],
            passed=stats["passed"],
            failed=stats["failed"],
            blocked=0,
            pass_rate=round(stats["passed"] / done * 100, 1) if done else 0.0,
            execution_rate=round(stats["total"] / total * 100, 1) if total else 0.0,
            automation_rate=round(by_type["app"] / total * 100, 1) if total else 0.0,
            by_type=by_type,
        )

    @staticmethod
    async def _calc_bug_statistics(
        db: AsyncSession, *, project_id: int
    ) -> BugStatistics:
        """统计 Bug 总数、各状态数量、各严重程度数量及修复率。"""
        from sqlalchemy import select, func as sql_func
        from app.models.bug.bug import Bug

        stats = await get_bug_stats(db, project_id=project_id)
        by_status = stats["by_status"]
        total = stats["total"]
        resolved = by_status.get("resolved", 0)
        closed = by_status.get("closed", 0)
        resolution_rate = stats["resolution_rate"]
        sev_rows = await db.execute(
            select(Bug.severity, sql_func.count().label("cnt"))
            .where(Bug.project_id == project_id, Bug.is_deleted == 0)
            .group_by(Bug.severity)
        )
        by_severity: dict[str, int] = {row.severity: row.cnt for row in sev_rows}
        return BugStatistics(
            total=total,
            new=by_status.get("new", 0),
            resolved=resolved,
            closed=closed,
            resolution_rate=resolution_rate,
            by_severity=by_severity,
            by_status=by_status,
        )

    @staticmethod
    async def _calc_execution_trend(
        db: AsyncSession,
        *,
        project_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[ExecutionTrendItem]:
        """按日期统计执行趋势（默认最近30天）。"""
        today = datetime.utcnow().date()
        if not end_date:
            end_date = today
        if not start_date:
            start_date = today - timedelta(days=29)
        start_dt = datetime(start_date.year, start_date.month, start_date.day)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
        rows = await db.execute(
            select(
                func.date(CaseExecution.created_at).label("exec_date"),
                func.count().label("cnt"),
                func.sum(
                    case(
                        (CaseExecution.execute_result == ExecuteStatus.PASSED.value, 1),
                        else_=0,
                    )
                ).label("passed"),
                func.sum(
                    case(
                        (CaseExecution.execute_result == ExecuteStatus.FAILED.value, 1),
                        else_=0,
                    )
                ).label("failed"),
            )
            .where(
                CaseExecution.project_id == project_id,
                CaseExecution.created_at >= start_dt,
                CaseExecution.created_at <= end_dt,
            )
            .group_by(func.date(CaseExecution.created_at))
            .order_by(func.date(CaseExecution.created_at))
        )
        data_map: dict[str, dict] = {
            (
                row.exec_date.isoformat()
                if hasattr(row.exec_date, "isoformat")
                else str(row.exec_date)
            ): {
                "count": row.cnt,
                "passed": int(row.passed or 0),
                "failed": int(row.failed or 0),
            }
            for row in rows
        }
        trend: list[ExecutionTrendItem] = []
        cursor = start_date
        while cursor <= end_date:
            ds = cursor.isoformat()
            item = data_map.get(ds, {"count": 0, "passed": 0, "failed": 0})
            trend.append(
                ExecutionTrendItem(
                    date=ds,
                    count=item["count"],
                    passed=item["passed"],
                    failed=item["failed"],
                )
            )
            cursor += timedelta(days=1)
        return trend

    @staticmethod
    async def check_permission(
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
        required_role: Optional[str] = None,
    ) -> bool:
        """
        检查用户是否有项目权限

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID
            required_role: 需要的角色代码

        Returns:
            bool: 是否有权限

        权限规则：
        - 系统管理员（super_admin）拥有所有项目的所有权限
        - 项目成员根据角色级别判断权限
        - 非项目成员没有权限

        角色级别：
        - project_owner: 100（项目负责人，可管理项目）
        - project_member: 80（项目成员）
        """
        if await ProjectService._is_super_admin(db, user_id):
            return True
        member = await member_crud.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        if not member:
            return False
        if required_role:
            member_level = await member_crud.get_member_role_level(
                db, project_id=project_id, user_id=user_id
            )
            role_levels = {ProjectRoleCode.OWNER: 100, ProjectRoleCode.MEMBER: 80}
            required_level = role_levels.get(required_role, 0)
            return member_level >= required_level
        return True

    @staticmethod
    async def is_owner(db: AsyncSession, *, project_id: int, user_id: int) -> bool:
        """
        检查用户是否是项目负责人

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否是负责人

        注：系统管理员被视为所有项目的负责人
        """
        if await ProjectService._is_super_admin(db, user_id):
            return True
        role = await member_crud.get_member_role(
            db, project_id=project_id, user_id=user_id
        )
        return role == ProjectRoleCode.OWNER

    @staticmethod
    async def can_edit_project(
        db: AsyncSession, *, project_id: int, user_id: int
    ) -> bool:
        """
        检查用户是否可以编辑项目

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否可以编辑
        """
        return await ProjectService.check_permission(
            db,
            project_id=project_id,
            user_id=user_id,
            required_role=ProjectRoleCode.OWNER,
        )

    @staticmethod
    async def can_manage_members(
        db: AsyncSession, *, project_id: int, user_id: int
    ) -> bool:
        """
        检查用户是否可以管理成员

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否可以管理成员
        """
        return await ProjectService.check_permission(
            db,
            project_id=project_id,
            user_id=user_id,
            required_role=ProjectRoleCode.OWNER,
        )

    @staticmethod
    async def get_user_permissions(
        db: AsyncSession, *, project_id: int, user_id: int
    ) -> dict[str, Any]:
        """
        获取用户在项目中的权限信息

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            dict: 权限信息

        权限规则：
        - 系统管理员拥有所有项目的所有权限
        - 项目成员根据角色返回对应权限
        - 非项目成员返回空权限
        """
        if await ProjectService._is_super_admin(db, user_id):
            return {
                "project_role": "super_admin",
                "permissions": [
                    "project:view",
                    "project:edit",
                    "project:delete",
                    "project:archive",
                    "member:view",
                    "member:add",
                    "member:remove",
                    "member:edit_role",
                    "module:view",
                    "module:add",
                    "module:edit",
                    "module:delete",
                    "config:view",
                    "config:edit",
                    "test_case:*",
                    "bug:*",
                ],
                "can_edit_project": True,
                "can_manage_members": True,
                "can_delete_project": True,
            }
        role = await member_crud.get_member_role(
            db, project_id=project_id, user_id=user_id
        )
        if not role:
            return {
                "project_role": None,
                "permissions": [],
                "can_edit_project": False,
                "can_manage_members": False,
                "can_delete_project": False,
            }
        permissions_map = {
            ProjectRoleCode.OWNER: [
                "project:view",
                "project:edit",
                "project:delete",
                "project:archive",
                "member:view",
                "member:add",
                "member:remove",
                "member:edit_role",
                "module:view",
                "module:add",
                "module:edit",
                "module:delete",
                "config:view",
                "config:edit",
                "test_case:*",
                "bug:*",
            ],
            ProjectRoleCode.MEMBER: ["project:view", "member:view", "module:view"],
        }
        permissions = permissions_map.get(role, [])
        return {
            "project_role": role,
            "permissions": permissions,
            "can_edit_project": role == ProjectRoleCode.OWNER,
            "can_manage_members": role == ProjectRoleCode.OWNER,
            "can_delete_project": role == ProjectRoleCode.OWNER,
        }


project_service = ProjectService()
