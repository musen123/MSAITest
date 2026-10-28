"""
认证授权模块 API

用户注册、登录、登出、Token刷新等认证相关接口
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.auth.user_token import TokenType, UserToken
from app.crud.auth import user_crud
from app.models.auth.user import User, UserStatus
from app.schemas.auth.login import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    UserInfo,
)
from app.schemas.auth.register import RegisterRequest, RegisterResponse
from app.schemas.auth.token import RefreshTokenRequest, RefreshTokenResponse, Token
from app.services.auth import auth_service, login_throttle
from app.services.auth.captcha import captcha_service

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP

    生产部署在 nginx 反向代理之后，优先取 X-Forwarded-For 的第一个 IP；
    无该头时回退 request.client.host；都不可用时返回 "-"（与中间件惯例一致）。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "-"


@router.post(
    "/register",
    summary="用户注册",
    response_model=ResponseModel[RegisterResponse],
)
async def register(
    obj_in: RegisterRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> ResponseModel[RegisterResponse]:
    """
    用户注册

    支持通过用户名、邮箱、手机号注册新用户

    - **用户名**: 4-20个字符，字母、数字、下划线，不能以数字开头
    - **密码**: 8-20个字符，必须包含字母和数字
    - **邮箱**: 必须填写，格式正确
    - **手机号**: 可选，11位数字
    """
    result = await auth_service.register(db, obj_in=obj_in)
    return ResponseModel(data=result, message="注册成功")


@router.post(
    "/login",
    summary="用户登录",
    response_model=ResponseModel[LoginResponse],
)
async def login(
    obj_in: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> ResponseModel[LoginResponse]:
    """
    用户登录

    支持用户名或邮箱登录

    - **account**: 用户名或邮箱
    - **password**: 密码
    - **captcha_code**: 验证码
    - **captcha_key**: 验证码Key
    - **remember_me**: 记住登录状态

    返回 access_token 和 refresh_token，access_token 有效期为7天
    """
    result = await auth_service.login(
        db, obj_in=obj_in, client_ip=_get_client_ip(request)
    )
    return ResponseModel(data=result, message="登录成功")


@router.post(
    "/logout",
    summary="用户登出",
    response_model=ResponseModel[None],
)
async def logout(
    obj_in: LogoutRequest,
    current_user: Annotated[User, Depends(deps.get_current_user)],
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> ResponseModel[None]:
    """
    用户登出

    需要认证，撤销当前的 refresh_token（可选）。
    若不传 refresh_token，服务端仅清除会话上下文，由前端自行清理本地存储。
    """
    await auth_service.logout(
        db, user=current_user, refresh_token=obj_in.refresh_token
    )
    return ResponseModel(message="登出成功")


@router.post(
    "/refresh",
    summary="刷新Token",
    response_model=ResponseModel[RefreshTokenResponse],
)
async def refresh_token(
    refresh_token: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> ResponseModel[RefreshTokenResponse]:
    """
    刷新访问令牌

    使用 refresh_token 获取新的 access_token
    """
    access_token, new_refresh_token = await auth_service.refresh_token(
        db, refresh_token=refresh_token.refresh_token
    )
    return ResponseModel(
        data=RefreshTokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=7 * 24 * 60 * 60,
        ),
        message="刷新成功",
    )


@router.get(
    "/me",
    summary="获取当前用户信息",
    response_model=ResponseModel[UserInfo],
)
async def get_current_user(
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> ResponseModel[UserInfo]:
    """
    获取当前用户信息

    需要认证，返回当前登录用户的基本信息
    """
    user_info = UserInfo(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        real_name=current_user.real_name,
        avatar=current_user.avatar,
        roles=current_user.role_codes,
        permissions=current_user.permissions,
    )
    return ResponseModel(data=user_info)


@router.get(
    "/captcha",
    summary="获取验证码",
    response_model=ResponseModel[dict],
)
async def get_captcha() -> ResponseModel[dict]:
    """
    获取图形验证码

    返回验证码图片（base64编码）和验证码Key
    """
    captcha_key, captcha_image = captcha_service.generate()

    return ResponseModel(
        data={
            "captcha_key": captcha_key,
            "captcha_image": captcha_image,
        },
        message="验证码生成成功",
    )


@router.post(
    "/token",
    summary="OAuth2 认证获取 Token（用于 Swagger 文档）",
    response_model=Token,
)
async def login_for_swagger(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> Token:
    """
    OAuth2 密码模式认证接口

    专门用于 FastAPI Swagger 文档的 "Authorize" 功能。
    使用 form-data 格式提交用户名和密码。

    - **username**: 用户名或邮箱
    - **password**: 密码

    返回标准的 OAuth2 Token 响应，可用于 Swagger 文档中其他需要认证的接口。
    """
    # IP 维度限流（该端点不走 auth_service.login，单独套前置限流，不引入账号锁）
    client_ip = _get_client_ip(request)
    await login_throttle.check_allowed(client_ip, form_data.username)
    await login_throttle.record_attempt(client_ip)

    # 查找用户（支持用户名或邮箱登录）
    user = await user_crud.get_by_account(db, account=form_data.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查账户状态
    if user.status == UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被锁定",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证密码
    if not verify_password(form_data.password, user.password_hash):
        # 记录失败（IP+账号 维度计数，供 check_allowed 限流；本端点不锁账号）
        await login_throttle.record_failure(client_ip, form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 生成 Token
    access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))
    db.add(
        UserToken(
            user_id=user.id,
            token_type=TokenType.REFRESH,
            token=new_refresh_token,
            expires_at=int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        )
    )
    await db.commit()

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=7 * 24 * 60 * 60,  # 7 天
        refresh_token=new_refresh_token,
    )
