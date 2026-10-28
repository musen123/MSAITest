"""
依赖注入

FastAPI 依赖注入函数，用于获取当前用户、数据库会话、权限检查等
"""

from typing import AsyncGenerator, Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.crud.auth import user_crud
from app.db.session import async_session
from app.models.auth.user import User

# OAuth2 密码模式
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话

    Yields:
        AsyncSession: 数据库会话
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
) -> str:
    """
    获取当前用户 ID

    Args:
        token: JWT Token

    Returns:
        str: 用户 ID

    Raises:
        HTTPException: Token 无效或过期
    """
    user_id = verify_token(token, token_type="access")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


# 可选的认证依赖（允许匿名访问）
async def get_optional_user_id(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """
    获取当前用户 ID（可选）

    如果未提供 Token 或 Token 无效，返回 None

    Args:
        token: JWT Token（可选）

    Returns:
        Optional[str]: 用户 ID 或 None
    """
    if token is None:
        return None

    user_id = verify_token(token, token_type="access")
    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前用户对象

    使用 get_with_relations 预加载角色和权限关系，
    避免异步 SQLAlchemy 的懒加载问题（MissingGreenlet 错误）

    Args:
        user_id: 用户 ID（从 Token 中解析）
        db: 数据库会话

    Returns:
        User: 用户对象

    Raises:
        HTTPException: 用户不存在或状态异常
    """
    user = await user_crud.get_with_relations(db, user_id=int(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户

    Returns:
        User: 活跃用户对象

    Raises:
        HTTPException: 用户未激活
    """
    if current_user.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户已被{current_user.status.value}",
        )
    return current_user


async def get_user_llm(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户配置的文本 LLM，并注入 ContextVar"""
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.ai_core.llm_client import build_llm_from_config
    from app.ai_core.llm_context import set_current_llm
    from app.models.auth.user_llm_config import ModelType

    config = await crud_user_llm_config.get_default(
        db, user_id=current_user.id, model_type=ModelType.TEXT
    )
    if not config or not config.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置文本大模型，再使用 AI 功能",
        )
    llm = build_llm_from_config(config)
    set_current_llm(llm)
    return llm


async def get_user_embed_llm(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户配置的嵌入模型，并注入 ContextVar"""
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.ai_core.llm_client import build_llm_from_config
    from app.ai_core.llm_context import set_current_embed_llm
    from app.models.auth.user_llm_config import ModelType

    config = await crud_user_llm_config.get_default(
        db, user_id=current_user.id, model_type=ModelType.EMBED
    )
    if not config or not config.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置嵌入模型，再使用该功能",
        )
    llm = build_llm_from_config(config)
    set_current_embed_llm(llm)
    return llm


async def get_user_vision_llm(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户配置的视觉模型，并注入 ContextVar"""
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.ai_core.llm_client import build_llm_from_config
    from app.ai_core.llm_context import set_current_vision_llm
    from app.models.auth.user_llm_config import ModelType

    config = await crud_user_llm_config.get_default(
        db, user_id=current_user.id, model_type=ModelType.VISION
    )
    if not config or not config.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置视觉模型，再使用该功能",
        )
    llm = build_llm_from_config(config)
    set_current_vision_llm(llm)
    return llm


def require_permission(*permissions: str) -> Callable:
    """
    权限检查装饰器工厂

    用于检查当前用户是否拥有指定的权限

    Args:
        *permissions: 需要的权限列表（满足其一即可）

    Returns:
        Callable: 依赖注入函数

    Examples:
        ```python
        @router.get("/users")
        async def get_users(
            current_user: User = Depends(require_permission("user:view")),
        ):
            return {"users": []}
        ```
    """

    async def check_permission(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        """
        检查用户权限

        Args:
            current_user: 当前用户

        Returns:
            User: 用户对象

        Raises:
            HTTPException: 用户权限不足
        """
        # 超级管理员拥有所有权限
        if "super_admin" in current_user.role_codes:
            return current_user

        # 获取用户所有权限
        user_permissions = current_user.permissions

        # 检查是否拥有所需权限
        if not any(perm in user_permissions for perm in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="抱歉，你没有执行该操作的权限",
            )

        return current_user

    return check_permission


def require_role(*roles: str) -> Callable:
    """
    角色检查装饰器工厂

    用于检查当前用户是否拥有指定的角色

    Args:
        *roles: 需要的角色列表（满足其一即可）

    Returns:
        Callable: 依赖注入函数

    Examples:
        ```python
        @router.get("/admin")
        async def admin_page(
            current_user: User = Depends(require_role("admin", "super_admin")),
        ):
            return {"message": "Welcome admin"}
        ```
    """

    async def check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        """
        检查用户角色

        Args:
            current_user: 当前用户

        Returns:
            User: 用户对象

        Raises:
            HTTPException: 用户角色不足
        """
        user_roles = current_user.role_codes

        # 超级管理员拥有所有角色
        if "super_admin" in user_roles:
            return current_user

        # 检查是否拥有所需角色
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="抱歉，你没有执行该操作所需的角色权限",
            )

        return current_user

    return check_role
