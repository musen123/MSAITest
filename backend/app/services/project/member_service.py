"""
项目成员业务服务层

处理项目成员相关的业务逻辑
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessException
from app.crud.project import (
    project,
)
from app.crud.project import project_member as member_crud
from app.crud.project.member import ProjectRoleCode
from app.models.auth.user import User
from app.models.auth.user_role import UserRole
from app.models.project import ProjectMember
from app.schemas.project import MemberCreate, MemberRoleUpdate


class MemberService:
    """
    项目成员业务服务类
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

        # 检查是否有 super_admin 角色
        for user_role in user.user_roles:
            if user_role.role.code == "super_admin":
                return True
        return False

    @staticmethod
    async def add_members(
        db: AsyncSession,
        *,
        project_id: int,
        obj_in: MemberCreate,
        operator_id: int,
    ) -> list[ProjectMember]:
        """
        添加项目成员

        Args:
            db: 数据库会话
            project_id: 项目ID
            obj_in: 添加成员数据
            operator_id: 操作者ID

        Returns:
            list[ProjectMember]: 添加的成员列表

        Raises:
            BusinessException: 项目不存在、用户不存在、用户已是成员
        """
        # 检查项目是否存在
        project_obj = await project.get(db, id=project_id)
        if not project_obj:
            raise BusinessException("项目不存在")

        # 系统管理员可以直接添加成员
        if await MemberService._is_super_admin(db, operator_id):
            pass  # 系统管理员跳过权限检查
        else:
            # 检查操作者是否是项目负责人
            role = await member_crud.get_member_role(
                db, project_id=project_id, user_id=operator_id
            )
            is_owner = role == ProjectRoleCode.OWNER

            if not is_owner:
                raise BusinessException("只有项目负责人可以添加成员")

        # 添加成员
        try:
            members = await member_crud.add_members(
                db,
                project_id=project_id,
                user_ids=obj_in.user_ids,
                project_role_code=obj_in.project_role,
            )
        except ValueError as e:
            raise BusinessException(str(e))

        return members

    @staticmethod
    async def update_member_role(
        db: AsyncSession,
        *,
        project_id: int,
        member_id: int,
        obj_in: MemberRoleUpdate,
        operator_id: int,
    ) -> ProjectMember:
        """
        修改成员角色

        Args:
            db: 数据库会话
            project_id: 项目ID
            member_id: 成员ID
            obj_in: 角色更新数据
            operator_id: 操作者ID

        Returns:
            ProjectMember: 更新后的成员

        Raises:
            BusinessException: 成员不存在、无权限修改
        """
        # 获取成员记录
        member = await member_crud.get(db, id=member_id)
        if not member or member.project_id != project_id:
            raise BusinessException("成员不存在")

        # 系统管理员可以直接修改成员角色
        if await MemberService._is_super_admin(db, operator_id):
            pass  # 系统管理员跳过权限检查
        else:
            # 检查操作者是否是项目负责人
            role = await member_crud.get_member_role(
                db, project_id=project_id, user_id=operator_id
            )
            is_owner = role == ProjectRoleCode.OWNER

            if not is_owner:
                raise BusinessException("只有项目负责人可以修改成员角色")

        # 如果修改的是owner角色，检查是否有其他owner
        if member.project_role == ProjectRoleCode.OWNER:
            if not await member_crud.has_owner(
                db, project_id=project_id, exclude_user_id=member.user_id
            ):
                raise BusinessException("项目必须有至少一个负责人")

        # 更新角色
        return await member_crud.update_member_role(
            db,
            project_id=project_id,
            user_id=member.user_id,
            new_role_code=obj_in.project_role,
        )

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        *,
        project_id: int,
        member_id: int,
        operator_id: int,
    ) -> bool:
        """
        移除项目成员

        Args:
            db: 数据库会话
            project_id: 项目ID
            member_id: 成员ID
            operator_id: 操作者ID

        Returns:
            bool: 是否移除成功

        Raises:
            BusinessException: 成员不存在、无权限移除、最后一位负责人
        """
        # 获取成员记录
        member = await member_crud.get(db, id=member_id)
        if not member or member.project_id != project_id:
            raise BusinessException("成员不存在")

        # 如果操作者不是被移除的成员，需要检查权限
        if member.user_id != operator_id:
            # 系统管理员可以直接移除成员
            if await MemberService._is_super_admin(db, operator_id):
                pass  # 系统管理员跳过权限检查
            else:
                # 检查操作者是否是项目负责人
                role = await member_crud.get_member_role(
                    db, project_id=project_id, user_id=operator_id
                )
                is_owner = role == ProjectRoleCode.OWNER

                if not is_owner:
                    raise BusinessException("只有项目负责人可以移除成员")

            # 如果移除的是owner，检查是否有其他owner
            if member.project_role == ProjectRoleCode.OWNER:
                if not await member_crud.has_owner(
                    db, project_id=project_id, exclude_user_id=member.user_id
                ):
                    raise BusinessException("项目必须有至少一个负责人")
        else:
            # 自己退出，检查是否是owner
            if member.project_role == ProjectRoleCode.OWNER:
                raise BusinessException("项目负责人不能退出项目，请先转让负责人")

        # 移除成员
        return await member_crud.remove_member(
            db, project_id=project_id, user_id=member.user_id
        )

    @staticmethod
    async def quit_project(
        db: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> bool:
        """
        退出项目

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            bool: 是否退出成功

        Raises:
            BusinessException: 用户不是成员、是项目负责人
        """
        # 获取成员记录
        member = await member_crud.get_by_project_and_user(
            db, project_id=project_id, user_id=user_id
        )
        if not member:
            raise BusinessException("您不是该项目的成员")

        # 检查是否是owner
        if member.project_role == ProjectRoleCode.OWNER:
            raise BusinessException("项目负责人不能退出项目，请先转让负责人")

        # 移除成员
        return await member_crud.remove_member(
            db, project_id=project_id, user_id=user_id
        )

    @staticmethod
    async def transfer_ownership(
        db: AsyncSession,
        *,
        project_id: int,
        to_user_id: int,
        from_user_id: int,
    ) -> dict:
        """
        转让项目所有权

        Args:
            db: 数据库会话
            project_id: 项目ID
            to_user_id: 接收者ID
            from_user_id: 转让者ID

        Returns:
            dict: 转让结果

        Raises:
            BusinessException: 接收者不是成员、转让者不是负责人
        """
        try:
            # 执行转让
            return await member_crud.transfer_ownership(
                db,
                project_id=project_id,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
            )
        except ValueError as e:
            raise BusinessException(str(e))


# 创建服务实例
member_service = MemberService()
