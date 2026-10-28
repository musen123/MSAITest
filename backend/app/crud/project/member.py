"""
项目成员 CRUD 操作
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.auth.role import Role
from app.models.project import ProjectMember
from app.schemas.project import MemberCreate, MemberRoleUpdate


# 项目角色代码常量
class ProjectRoleCode:
    """项目角色代码常量（仅 负责人/成员 两种）"""

    OWNER = "project_owner"  # 项目负责人（可管理项目）
    MEMBER = "project_member"  # 项目成员


class CRUDProjectMember(CRUDBase[ProjectMember, MemberCreate, MemberRoleUpdate]):
    """
    项目成员 CRUD 操作类
    """

    async def _get_role_by_code(
        self,
        db: AsyncSession,
        *,
        code: str,
    ) -> Optional[Role]:
        """
        根据角色代码获取角色

        Args:
            db: 数据库会话
            code: 角色代码

        Returns:
            Optional[Role]: 角色对象
        """
        stmt = select(Role).where(Role.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_project_and_user(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> Optional[ProjectMember]:
        """
        根据项目ID和用户ID获取成员记录

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            Optional[ProjectMember]: 成员记录
        """
        stmt = (
            select(ProjectMember)
            .options(selectinload(ProjectMember.project_role_obj))
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_members_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        role: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> list[ProjectMember]:
        """
        获取项目的成员列表

        Args:
            db: 数据库会话
            project_id: 项目ID
            role: 角色筛选（角色代码）
            keyword: 关键词搜索（用户名/姓名）

        Returns:
            list[ProjectMember]: 成员列表
        """
        from app.models.auth import User
        from app.models.auth.user_role import UserRole

        # 构建查询
        stmt = (
            select(ProjectMember)
            .join(User, ProjectMember.user_id == User.id)
            .join(Role, ProjectMember.project_role_id == Role.id)
            .where(ProjectMember.project_id == project_id)
        )

        # 角色筛选
        if role:
            stmt = stmt.where(Role.code == role)

        # 关键词搜索
        if keyword:
            search_filter = or_(
                User.username.like(f"%{keyword}%"),
                User.real_name.like(f"%{keyword}%"),
            )
            stmt = stmt.where(search_filter)

        # 预加载关联数据（含用户的系统角色，供前端展示「用户角色」）
        stmt = stmt.options(
            selectinload(ProjectMember.user)
            .selectinload(User.user_roles)
            .selectinload(UserRole.role),
            selectinload(ProjectMember.project_role_obj),
        )

        # 排序
        stmt = stmt.order_by(ProjectMember.created_at.asc())

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_projects_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[ProjectMember]:
        """
        获取用户参与的项目列表

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            list[ProjectMember]: 项目成员列表
        """
        stmt = (
            select(ProjectMember)
            .where(ProjectMember.user_id == user_id)
            .options(
                selectinload(ProjectMember.project),
                selectinload(ProjectMember.project_role_obj),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> int:
        """
        统计项目成员数量

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            int: 成员数量
        """
        stmt = select(func.count(ProjectMember.id)).where(
            ProjectMember.project_id == project_id
        )
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def count_by_role(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        role_code: str,
    ) -> int:
        """
        统计项目中指定角色的成员数量

        Args:
            db: 数据库会话
            project_id: 项目ID
            role_code: 项目角色代码

        Returns:
            int: 成员数量
        """
        stmt = (
            select(func.count(ProjectMember.id))
            .join(Role, ProjectMember.project_role_id == Role.id)
            .where(
                ProjectMember.project_id == project_id,
                Role.code == role_code,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def is_member(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> bool:
        """
        检查用户是否是项目成员

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否是成员
        """
        return (
            await self.get_by_project_and_user(
                db, project_id=project_id, user_id=user_id
            )
            is not None
        )

    async def get_member_role(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> Optional[str]:
        """
        获取用户在项目中的角色代码

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            Optional[str]: 项目角色代码
        """
        member = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        return member.project_role if member else None

    async def get_member_role_level(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> int:
        """
        获取用户在项目中的角色级别

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            int: 角色级别（数字越大权限越高）
        """
        member = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        if member and member.project_role_obj:
            # 从 sys_role 表的 sort_order 获取级别
            return member.project_role_obj.sort_order or 0
        return 0

    async def add_members(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_ids: list[int],
        project_role_code: str,
    ) -> list[ProjectMember]:
        """
        批量添加项目成员

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_ids: 用户ID列表
            project_role_code: 项目角色代码

        Returns:
            list[ProjectMember]: 添加的成员列表

        Raises:
            ValueError: 用户不存在
        """
        from app.models.auth import User

        # 获取角色
        role = await self._get_role_by_code(db, code=project_role_code)
        if not role:
            # 如果角色不存在，使用默认角色（项目成员）
            role = await self._get_role_by_code(db, code=ProjectRoleCode.MEMBER)
        if not role:
            raise ValueError(f"项目角色 '{project_role_code}' 不存在")

        current_time = datetime.now(timezone.utc)
        members = []

        for user_id in user_ids:
            # 检查用户是否存在
            user_stmt = select(User).where(User.id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError(f"用户 ID {user_id} 不存在")

            # 检查是否已是成员
            existing = await self.get_by_project_and_user(
                db, project_id=project_id, user_id=user_id
            )
            if existing:
                continue

            # 创建成员记录
            member = ProjectMember(
                project_id=project_id,
                user_id=user_id,
                project_role_id=role.id,
                last_active_at=current_time,
            )
            db.add(member)
            members.append(member)

        await db.commit()

        # 刷新所有成员
        for member in members:
            await db.refresh(member)

        return members

    async def remove_member(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> bool:
        """
        移除项目成员

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否移除成功
        """
        member = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        if member:
            await db.delete(member)
            await db.commit()
            return True
        return False

    async def update_member_role(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
        new_role_code: str,
    ) -> Optional[ProjectMember]:
        """
        更新成员角色

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID
            new_role_code: 新角色代码

        Returns:
            Optional[ProjectMember]: 更新后的成员记录
        """
        # 获取新角色
        new_role = await self._get_role_by_code(db, code=new_role_code)
        if not new_role:
            raise ValueError(f"项目角色 '{new_role_code}' 不存在")

        member = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        if member:
            member.project_role_id = new_role.id
            db.add(member)
            await db.commit()
            await db.refresh(member)
            return member
        return None

    async def update_last_active(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> bool:
        """
        更新成员最后活跃时间

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否更新成功
        """
        member = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        if member:
            member.last_active_at = datetime.now(timezone.utc)
            db.add(member)
            await db.commit()
            return True
        return False

    async def get_owner(
        self,
        db: AsyncSession,
        *,
        project_id: int,
    ) -> Optional[ProjectMember]:
        """
        获取项目的负责人（owner）

        Args:
            db: 数据库会话
            project_id: 项目ID

        Returns:
            Optional[ProjectMember]: 负责人成员记录
        """
        stmt = (
            select(ProjectMember)
            .join(Role, ProjectMember.project_role_id == Role.id)
            .where(
                ProjectMember.project_id == project_id,
                Role.code == ProjectRoleCode.OWNER,
            )
            .options(selectinload(ProjectMember.user))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def can_manage_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> bool:
        """
        检查用户是否可以管理项目（编辑、删除、管理成员等）

        只有项目负责人可以管理项目

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否可以管理项目
        """
        member = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        return member and member.project_role == ProjectRoleCode.OWNER

    async def has_owner(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        exclude_user_id: Optional[int] = None,
    ) -> bool:
        """
        检查项目是否有负责人（可排除指定用户）

        Args:
            db: 数据库会话
            project_id: 项目ID
            exclude_user_id: 排除的用户ID

        Returns:
            bool: 是否有负责人
        """
        stmt = (
            select(func.count(ProjectMember.id))
            .join(Role, ProjectMember.project_role_id == Role.id)
            .where(
                ProjectMember.project_id == project_id,
                Role.code == ProjectRoleCode.OWNER,
            )
        )

        if exclude_user_id:
            stmt = stmt.where(ProjectMember.user_id != exclude_user_id)

        result = await db.execute(stmt)
        count = result.scalar_one() or 0
        return count > 0

    async def transfer_ownership(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        from_user_id: int,
        to_user_id: int,
    ) -> dict:
        """
        转让项目所有权

        Args:
            db: 数据库会话
            project_id: 项目ID
            from_user_id: 当前负责人ID
            to_user_id: 新负责人ID

        Returns:
            dict: 转让结果，包含用户ID和新角色

        Raises:
            ValueError: 用户不存在、角色不存在、接收人不是项目成员
        """
        from app.models.auth import User

        # 验证两个用户都存在
        for uid, role_name in [(from_user_id, "转让人"), (to_user_id, "接收人")]:
            user_stmt = select(User).where(User.id == uid)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError(f"{role_name}用户 ID {uid} 不存在")

        # 获取角色
        owner_role = await self._get_role_by_code(db, code=ProjectRoleCode.OWNER)
        member_role = await self._get_role_by_code(db, code=ProjectRoleCode.MEMBER)

        if not owner_role:
            raise ValueError(f"项目负责人角色 '{ProjectRoleCode.OWNER}' 不存在")
        if not member_role:
            raise ValueError(f"项目成员角色 '{ProjectRoleCode.MEMBER}' 不存在")

        # 获取当前负责人
        current_owner = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=from_user_id
        )
        if not current_owner or current_owner.project_role != ProjectRoleCode.OWNER:
            raise ValueError("当前用户不是项目负责人")

        # 获取新负责人
        new_owner = await self.get_by_project_and_user(
            db, project_id=project_id, user_id=to_user_id
        )
        if not new_owner:
            raise ValueError("接收人不是项目成员")

        # 交换角色：原负责人降为项目成员，接收人升为项目负责人
        current_owner.project_role_id = member_role.id
        new_owner.project_role_id = owner_role.id

        db.add(current_owner)
        db.add(new_owner)
        await db.commit()

        # 刷新以获取最新数据
        await db.refresh(current_owner)
        await db.refresh(new_owner)

        return {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "from_user_new_role": ProjectRoleCode.MEMBER,
            "to_user_new_role": ProjectRoleCode.OWNER,
        }


# 创建实例
project_member = CRUDProjectMember(ProjectMember)
