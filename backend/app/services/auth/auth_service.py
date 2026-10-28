"""
用户认证服务

处理用户登录、注册、登出等认证逻辑
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.crud.auth import user_crud
from app.models.auth.role import Role
from app.models.auth.user import User, UserStatus
from app.models.auth.user_role import UserRole
from app.models.auth.user_token import TokenType, UserToken
from app.schemas.auth.login import LoginRequest, LoginResponse, UserInfo
from app.schemas.auth.register import RegisterRequest, RegisterResponse
from app.services.auth import login_throttle


class AuthService:
    """
    用户认证服务类
    """

    async def register(
        self,
        db: AsyncSession,
        *,
        obj_in: RegisterRequest,
    ) -> RegisterResponse:
        """
        用户注册

        Args:
            db: 数据库会话
            obj_in: 注册请求

        Returns:
            RegisterResponse: 注册响应

        Raises:
            HTTPException: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        if await user_crud.get_by_username(db, username=obj_in.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在",
            )

        # 检查邮箱是否已存在
        if await user_crud.get_by_email(db, email=obj_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已被注册",
            )

        # 检查手机号是否已存在
        if obj_in.phone and await user_crud.get_by_phone(db, phone=obj_in.phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="手机号已被注册",
            )

        # 加密密码
        hashed_password = get_password_hash(obj_in.password)

        # 创建用户
        user = await user_crud.create(
            db,
            obj_in=obj_in,
            hashed_password=hashed_password,
        )

        # 自动分配默认"普通用户"角色
        default_role_result = await db.execute(
            select(Role).where(Role.code == "user", Role.deleted_at.is_(None))
        )
        default_role = default_role_result.scalar_one_or_none()
        if default_role:
            db.add(UserRole(user_id=user.id, role_id=default_role.id))
            await db.commit()

        return RegisterResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        )

    async def login(
        self,
        db: AsyncSession,
        *,
        obj_in: LoginRequest,
        client_ip: str = "-",
    ) -> LoginResponse:
        """
        用户登录

        Args:
            db: 数据库会话
            obj_in: 登录请求
            client_ip: 客户端 IP（用于限流与分布式攻击检测）

        Returns:
            LoginResponse: 登录响应

        Raises:
            HTTPException: 登录失败（用户不存在、密码错误、账户被锁定、限流等）
        """
        # 登录前置限流：IP 尝试次数 / IP+账号 失败次数超限直接 429（fail-open）
        await login_throttle.check_allowed(client_ip, obj_in.account)
        await login_throttle.record_attempt(client_ip)

        # 查找用户
        user = await user_crud.get_by_account(db, account=obj_in.account)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账号或密码错误",
            )

        # 检查账户状态
        if user.status == UserStatus.DISABLED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用",
            )

        if user.status == UserStatus.LOCKED:
            # 检查锁定是否已过期。locked_until 实为 int Unix 时间戳(见 crud lock_user:
            # `int(lock_time.timestamp())`,列 bigint),必须按时间戳比较,不能与 datetime 直接比
            # （否则 int > datetime 报 TypeError → 锁定用户每次登录都 500）。
            if user.locked_until and user.locked_until > int(datetime.now(timezone.utc).timestamp()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="账户已被锁定，请稍后再试",
                )
            else:
                # 锁定已过期，解锁用户并清零历史失败计数
                await user_crud.update_status(db, user=user, status=UserStatus.ACTIVE)
                await user_crud.reset_login_fail_count(db, user=user)

        # 验证密码
        if not verify_password(obj_in.password, user.password_hash):
            # 增加登录失败次数
            await user_crud.increment_login_fail_count(db, user=user)

            # 防武器化：仅当失败来源达到多个不同 IP（分布式攻击）才全局锁定账号；
            # 单一 IP 反复输错只会被 login_throttle 的 pair 维度限流 429，
            # 不会把账号锁掉（防止攻击者故意输错密码锁定他人账号）。
            distributed_attack = await login_throttle.record_failure(
                client_ip, obj_in.account
            )
            if distributed_attack:
                await user_crud.lock_user(db, user=user)

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账号或密码错误",
            )

        # 验证成功，清理限流状态并更新登录信息
        await login_throttle.clear(client_ip, obj_in.account)
        await user_crud.update_login_info(db, user=user, ip_address=client_ip)

        # 生成 Token
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        # 单元测试替身允许 db=None；真实 API 始终传入 AsyncSession。
        if db is not None:
            db.add(
                UserToken(
                    user_id=user.id,
                    token_type=TokenType.REFRESH,
                    token=refresh_token,
                    expires_at=int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                )
            )
            await db.commit()

        # 构建响应
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=7 * 24 * 60 * 60,  # 7 天
            user_info=UserInfo(
                id=user.id,
                username=user.username,
                email=user.email,
                real_name=user.real_name,
                avatar=user.avatar,
                roles=user.role_codes,
                permissions=user.permissions,
            ),
        )

    async def logout(
        self,
        db: AsyncSession,
        *,
        user: User,
        refresh_token: str | None = None,
    ) -> None:
        """
        用户登出

        Args:
            db: 数据库会话
            user: 当前用户
            refresh_token: 刷新令牌（可选）。不传时仅清理会话上下文。

        Raises:
            HTTPException: 登出失败
        """
        if not refresh_token:
            return
        result = await db.execute(
            select(UserToken).where(
                UserToken.token == refresh_token,
                UserToken.user_id == user.id,
                UserToken.token_type == TokenType.REFRESH,
            ).with_for_update()
        )
        stored = result.scalar_one_or_none()
        if stored and not stored.revoked:
            stored.revoked = True
            stored.revoked_at = int(datetime.now(timezone.utc).timestamp())
            await db.commit()

    async def refresh_token(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> tuple[str, str]:
        """
        刷新访问令牌

        Args:
            db: 数据库会话
            refresh_token: 刷新令牌

        Returns:
            tuple[str, str]: (新的访问令牌, 新的刷新令牌)

        Raises:
            HTTPException: Token 无效或已撤销
        """
        from app.core.security import verify_token

        # 验证 refresh token
        user_id = verify_token(refresh_token, token_type="refresh")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌",
            )

        token_result = await db.execute(
            select(UserToken)
            .where(
                UserToken.token == refresh_token,
                UserToken.token_type == TokenType.REFRESH,
            )
            .with_for_update()
        )
        stored = token_result.scalar_one_or_none()
        if not stored or stored.user_id != int(user_id) or not stored.is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌已失效或已撤销",
            )

        # 检查用户是否存在且状态正常
        user = await user_crud.get(db, id=int(user_id))

        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或状态异常",
            )

        # 生成新的 Token
        new_access_token = create_access_token(subject=user_id)
        new_refresh_token = create_refresh_token(subject=user_id)

        now_ts = int(datetime.now(timezone.utc).timestamp())
        stored.revoked = True
        stored.revoked_at = now_ts
        db.add(
            UserToken(
                user_id=int(user_id),
                token_type=TokenType.REFRESH,
                token=new_refresh_token,
                expires_at=now_ts + 30 * 24 * 60 * 60,
            )
        )
        await db.commit()

        return new_access_token, new_refresh_token

    async def get_current_user_info(
        self,
        *,
        user: User,
    ) -> UserInfo:
        """
        获取当前用户信息

        Args:
            user: 用户对象

        Returns:
            UserInfo: 用户信息
        """
        return UserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            real_name=user.real_name,
            avatar=user.avatar,
            roles=user.role_codes,
            permissions=user.permissions,
        )


# 创建单例实例
auth_service = AuthService()
