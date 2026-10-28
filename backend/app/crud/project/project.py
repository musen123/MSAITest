"""
项目 CRUD 操作
"""

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.project import Project, ProjectStatus
from app.schemas.project import ProjectCreate, ProjectUpdate


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    """
    项目 CRUD 操作类
    """

    async def get_by_code(
        self,
        db: AsyncSession,
        *,
        code: str,
    ) -> Optional[Project]:
        """
        根据项目标识获取项目

        Args:
            db: 数据库会话
            code: 项目标识

        Returns:
            Optional[Project]: 项目实例
        """
        stmt = select(Project).where(
            Project.code == code,
            Project.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str,
    ) -> Optional[Project]:
        """
        根据项目名称获取项目

        Args:
            db: 数据库会话
            name: 项目名称

        Returns:
            Optional[Project]: 项目实例
        """
        stmt = select(Project).where(
            Project.name == name,
            Project.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_details(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> Optional[Project]:
        """
        获取项目详情（包含关联数据）

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            Optional[Project]: 项目实例
        """
        stmt = (
            select(Project)
            .where(
                Project.id == project_id,
                Project.is_deleted.is_(False),
            )
            .options(
                selectinload(Project.created_by),
                selectinload(Project.members),
                selectinload(Project.modules),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_projects(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None,
        status: Optional[ProjectStatus] = None,
        is_public: Optional[bool] = None,
        member_id: Optional[int] = None,
        accessible_by: Optional[int] = None,
        order_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[Project], int]:
        """
        获取项目列表

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 限制数量
            keyword: 搜索关键词
            status: 项目状态
            is_public: 是否公开
            member_id: 成员ID筛选（精确到「参与」，供管理员按用户筛选）
            accessible_by: 可见性约束——返回该用户「参与 OR 公开」的项目
                （非管理员看列表用；公开项目对非成员也可见）
            order_by: 排序字段
            order: 排序方向

        Returns:
            tuple[list[Project], int]: 项目列表和总数
        """
        # 构建查询
        stmt = select(Project).where(Project.is_deleted.is_(False))
        count_stmt = select(func.count(Project.id)).where(Project.is_deleted.is_(False))

        # 关键词搜索
        if keyword:
            search_filter = or_(
                Project.name.like(f"%{keyword}%"),
                Project.description.like(f"%{keyword}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # 状态筛选
        if status:
            stmt = stmt.where(Project.status == status)
            count_stmt = count_stmt.where(Project.status == status)

        # 公开状态筛选
        if is_public is not None:
            stmt = stmt.where(Project.is_public == is_public)
            count_stmt = count_stmt.where(Project.is_public == is_public)

        # 成员筛选（需要关联查询）
        if member_id:
            from app.models.project import ProjectMember

            stmt = (
                stmt.join(ProjectMember, Project.id == ProjectMember.project_id)
                .where(ProjectMember.user_id == member_id)
                .distinct()
            )
            count_stmt = (
                count_stmt.join(ProjectMember, Project.id == ProjectMember.project_id)
                .where(ProjectMember.user_id == member_id)
                .distinct()
            )

        # 可见性约束：非管理员看列表时传入——返回「本人参与 OR 项目公开」，
        # 修复公开项目对非成员不可见的问题（与项目详情接口 is_public 放行同口径）。
        if accessible_by is not None:
            from app.models.project import ProjectMember

            member_subq = select(ProjectMember.project_id).where(
                ProjectMember.user_id == accessible_by
            )
            visible_cond = or_(
                Project.is_public.is_(True),
                Project.id.in_(member_subq),
            )
            stmt = stmt.where(visible_cond)
            count_stmt = count_stmt.where(visible_cond)

        # 排序
        order_column = getattr(Project, order_by, Project.created_at)
        if order.lower() == "desc":
            stmt = stmt.order_by(order_column.desc())
        else:
            stmt = stmt.order_by(order_column.asc())

        # 分页
        stmt = stmt.offset(skip).limit(limit)

        # 预加载关联数据
        stmt = stmt.options(selectinload(Project.created_by))

        # 执行查询
        result = await db.execute(stmt)
        projects = list(result.scalars().all())

        # 获取总数
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one() or 0

        return projects, total

    async def code_exists(
        self,
        db: AsyncSession,
        *,
        code: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查项目标识是否存在

        Args:
            db: 数据库会话
            code: 项目标识
            exclude_id: 排除的项目ID

        Returns:
            bool: 是否存在
        """
        stmt = select(Project).where(
            Project.code == code,
            Project.is_deleted.is_(False),
        )

        if exclude_id:
            stmt = stmt.where(Project.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def name_exists(
        self,
        db: AsyncSession,
        *,
        name: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查项目名称是否存在

        Args:
            db: 数据库会话
            name: 项目名称
            exclude_id: 排除的项目ID

        Returns:
            bool: 是否存在
        """
        stmt = select(Project).where(
            Project.name == name,
            Project.is_deleted.is_(False),
        )

        if exclude_id:
            stmt = stmt.where(Project.id != exclude_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def update_status(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        status: ProjectStatus,
    ) -> Optional[Project]:
        """
        更新项目状态

        Args:
            db: 数据库会话
            project_id: 项目ID
            status: 新状态

        Returns:
            Optional[Project]: 更新后的项目实例
        """
        project = await self.get(db, id=project_id)
        if project:
            project.status = status
            db.add(project)
            await db.commit()
            await db.refresh(project)
            return project
        return None

    async def soft_delete(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> bool:
        """
        软删除项目

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            bool: 是否删除成功
        """
        project = await self.get(db, id=project_id)
        if project:
            project.is_deleted = True
            project.status = ProjectStatus.DELETED
            db.add(project)
            await db.commit()
            return True
        return False


# 创建实例
project = CRUDProject(Project)
