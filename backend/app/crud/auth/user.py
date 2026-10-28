"""
用户 CRUD 操作
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.auth.role import Role
from app.models.auth.role_permission import RolePermission
from app.models.auth.user import User, UserStatus
from app.models.auth.user_role import UserRole
from app.schemas.auth.user_manage import CreateUserRequest, UpdateUserRequest


class CRUDUser(CRUDBase[User, CreateUserRequest, UpdateUserRequest]):
    """
    用户 CRUD 操作类
    """

    async def get_by_username(
        self,
        db: AsyncSession,
        *,
        username: str,
    ) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            db: 数据库会话
            username: 用户名

        Returns:
            Optional[User]: 用户实例，不存在返回 None
        """
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        db: AsyncSession,
        *,
        email: str,
    ) -> Optional[User]:
        """
        根据邮箱获取用户

        Args:
            db: 数据库会话
            email: 邮箱

        Returns:
            Optional[User]: 用户实例，不存在返回 None
        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(
        self,
        db: AsyncSession,
        *,
        phone: str,
    ) -> Optional[User]:
        """
        根据手机号获取用户

        Args:
            db: 数据库会话
            phone: 手机号

        Returns:
            Optional[User]: 用户实例，不存在返回 None
        """
        stmt = select(User).where(User.phone == phone)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_account(
        self,
        db: AsyncSession,
        *,
        account: str,
    ) -> Optional[User]:
        """
        根据账号（用户名或邮箱）获取用户

        Args:
            db: 数据库会话
            account: 用户名或邮箱

        Returns:
            Optional[User]: 用户实例，不存在返回 None
        """
        # 预加载完整的关系链：User -> UserRole -> Role -> RolePermission -> Permission
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(
                or_(
                    User.username == account,
                    User.email == account,
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_relations(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> Optional[User]:
        """
        根据 ID 获取用户（包含角色和权限关系）

        预加载完整的关系链，避免异步懒加载问题：
        User -> UserRole -> Role -> RolePermission -> Permission

        Args:
            db: 数据库会话
            user_id: 用户 ID

        Returns:
            Optional[User]: 用户实例，不存在返回 None
        """
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier(
        self,
        db: AsyncSession,
        *,
        identifier: str,
    ) -> Optional[User]:
        """
        根据标识符（用户名、邮箱或手机号）获取用户

        Args:
            db: 数据库会话
            identifier: 用户名、邮箱或手机号

        Returns:
            Optional[User]: 用户实例，不存在返回 None
        """
        stmt = select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier,
                User.phone == identifier,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateUserRequest,
        hashed_password: str,
    ) -> User:
        """
        创建用户

        Args:
            db: 数据库会话
            obj_in: 创建请求 Schema
            hashed_password: 加密后的密码

        Returns:
            User: 创建的用户实例
        """
        # 创建用户基本信息
        db_obj = User(
            username=obj_in.username,
            password_hash=hashed_password,
            email=obj_in.email,
            phone=obj_in.phone,
            real_name=obj_in.real_name,
            status=UserStatus.ACTIVE,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)

        # 处理角色关联
        role_ids = getattr(obj_in, 'role_ids', None)
        if role_ids:
            # 获取角色信息
            stmt = select(Role).where(Role.id.in_(role_ids))
            result = await db.execute(stmt)
            roles = result.scalars().all()

            # 创建用户-角色关联
            for role in roles:
                user_role = UserRole(user_id=db_obj.id, role_id=role.id)
                db.add(user_role)

            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def update_login_info(
        self,
        db: AsyncSession,
        *,
        user: User,
        ip_address: str | None = None,
    ) -> User:
        """
        更新用户登录信息

        Args:
            db: 数据库会话
            user: 用户实例
            ip_address: 登录IP

        Returns:
            User: 更新后的用户实例
        """
        # BIGINT 字段存储时间戳，需要转换为整数
        user.last_login_at = int(datetime.now(timezone.utc).timestamp())
        user.last_login_ip = ip_address
        user.login_fail_count = 0
        user.locked_until = None
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def increment_login_fail_count(
        self,
        db: AsyncSession,
        *,
        user: User,
    ) -> User:
        """
        增加登录失败次数

        Args:
            db: 数据库会话
            user: 用户实例

        Returns:
            User: 更新后的用户实例
        """
        # 在数据库内原子 +1，避免并发登录失败相互覆盖。
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(login_fail_count=func.coalesce(User.login_fail_count, 0) + 1)
        )
        await db.commit()
        await db.refresh(user)
        return user

    async def reset_login_fail_count(
        self,
        db: AsyncSession,
        *,
        user: User,
    ) -> User:
        """
        清零登录失败次数并清除锁定截止时间

        用于账号锁定过期自动解锁时，避免历史失败计数残留。

        Args:
            db: 数据库会话
            user: 用户实例

        Returns:
            User: 更新后的用户实例
        """
        user.login_fail_count = 0
        user.locked_until = None
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def lock_user(
        self,
        db: AsyncSession,
        *,
        user: User,
        lock_minutes: int = 30,
    ) -> User:
        """
        锁定用户

        Args:
            db: 数据库会话
            user: 用户实例
            lock_minutes: 锁定时长（分钟）

        Returns:
            User: 更新后的用户实例
        """
        user.status = UserStatus.LOCKED
        # BIGINT 字段存储时间戳，需要转换为整数
        lock_time = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
        user.locked_until = int(lock_time.timestamp())
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def update_password(
        self,
        db: AsyncSession,
        *,
        user: User,
        hashed_password: str,
    ) -> User:
        """
        更新用户密码

        Args:
            db: 数据库会话
            user: 用户实例
            hashed_password: 新的加密密码

        Returns:
            User: 更新后的用户实例
        """
        user.password_hash = hashed_password
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def update_status(
        self,
        db: AsyncSession,
        *,
        user: User,
        status: UserStatus,
    ) -> User:
        """
        更新用户状态

        Args:
            db: 数据库会话
            user: 用户实例
            status: 新状态

        Returns:
            User: 更新后的用户实例
        """
        user.status = status
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def search(
        self,
        db: AsyncSession,
        *,
        keyword: str | None = None,
        status: UserStatus | None = None,
        role_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """
        搜索用户

        Args:
            db: 数据库会话
            keyword: 搜索关键词（用户名/邮箱/手机号/真实姓名）
            status: 状态筛选
            role_id: 角色筛选
            skip: 跳过数量
            limit: 限制数量

        Returns:
            list[User]: 用户列表
        """
        stmt = select(User)

        if keyword:
            stmt = stmt.where(
                or_(
                    User.username.like(f"%{keyword}%"),
                    User.email.like(f"%{keyword}%"),
                    User.phone.like(f"%{keyword}%"),
                    User.real_name.like(f"%{keyword}%"),
                )
            )

        if status:
            stmt = stmt.where(User.status == status)

        if role_id is not None:
            stmt = stmt.where(
                exists().where(
                    UserRole.user_id == User.id,
                    UserRole.role_id == role_id,
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_multi_with_relations(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        keyword: str | None = None,
        status: UserStatus | None = None,
        role_id: int | None = None,
    ) -> list[User]:
        """
        获取用户列表（预加载角色关系）

        预加载角色关系，避免异步懒加载问题：
        User -> UserRole -> Role

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 限制数量
            keyword: 搜索关键词（用户名/邮箱/手机号）
            status: 状态筛选
            role_id: 角色筛选

        Returns:
            list[User]: 用户列表
        """
        stmt = select(User).options(
            selectinload(User.user_roles).selectinload(UserRole.role)
        )

        if keyword:
            stmt = stmt.where(
                or_(
                    User.username.like(f"%{keyword}%"),
                    User.email.like(f"%{keyword}%"),
                    User.phone.like(f"%{keyword}%"),
                    User.real_name.like(f"%{keyword}%"),
                )
            )

        if status:
            stmt = stmt.where(User.status == status)

        if role_id is not None:
            stmt = stmt.where(
                exists().where(
                    UserRole.user_id == User.id,
                    UserRole.role_id == role_id,
                )
            )

        stmt = stmt.order_by(User.id).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_search(
        self,
        db: AsyncSession,
        *,
        keyword: str | None = None,
        status: UserStatus | None = None,
        role_id: int | None = None,
    ) -> int:
        """
        统计搜索结果数量

        Args:
            db: 数据库会话
            keyword: 搜索关键词
            status: 状态筛选
            role_id: 角色筛选

        Returns:
            int: 用户数量
        """
        from sqlalchemy import func

        stmt = select(func.count(User.id))

        if keyword:
            stmt = stmt.where(
                or_(
                    User.username.like(f"%{keyword}%"),
                    User.email.like(f"%{keyword}%"),
                    User.phone.like(f"%{keyword}%"),
                    User.real_name.like(f"%{keyword}%"),
                )
            )

        if status:
            stmt = stmt.where(User.status == status)

        if role_id is not None:
            stmt = stmt.where(
                exists().where(
                    UserRole.user_id == User.id,
                    UserRole.role_id == role_id,
                )
            )

        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def assign_roles(
        self,
        db: AsyncSession,
        *,
        user: User,
        role_ids: list[int],
    ) -> User:
        """
        为用户分配角色（替换现有角色）

        Args:
            db: 数据库会话
            user: 用户实例
            role_ids: 角色ID列表

        Returns:
            User: 更新后的用户实例
        """
        from sqlalchemy import delete

        # 删除用户现有的所有角色关联
        delete_stmt = delete(UserRole).where(UserRole.user_id == user.id)
        await db.execute(delete_stmt)

        # 如果有新角色，创建关联
        if role_ids:
            # 获取角色信息
            stmt = select(Role).where(Role.id.in_(role_ids))
            result = await db.execute(stmt)
            roles = result.scalars().all()

            # 创建用户-角色关联
            for role in roles:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                db.add(user_role)

        await db.commit()
        await db.refresh(user)
        return user


# 创建单例实例
user_crud = CRUDUser(User)
