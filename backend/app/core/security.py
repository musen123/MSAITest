"""
安全相关功能

包含密码哈希、JWT Token 生成和验证等安全功能
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(
    schemes=settings.PASSWORD_HASH_SCHEMES,
    deprecated=settings.PASSWORD_HASH_DEPRECATED,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希

    Args:
        password: 明文密码

    Returns:
        str: 哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    创建 JWT Access Token

    Args:
        subject: Token 主题（通常是用户 ID 或用户名）
        expires_delta: 过期时间增量
        additional_claims: 额外的声明

    Returns:
        str: JWT Token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    # 添加额外的声明
    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 JWT Refresh Token

    Args:
        subject: Token 主题（通常是用户 ID）
        expires_delta: 过期时间增量

    Returns:
        str: JWT Refresh Token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Refresh Token 有效期更长（30 天）
        expire = datetime.now(timezone.utc) + timedelta(days=30)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        # 同一用户在同一秒签发/轮换时也必须得到不同 token。
        "jti": uuid4().hex,
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """
    解码 JWT Token

    Args:
        token: JWT Token

    Returns:
        Optional[dict]: 解码后的 Token 数据，解码失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """
    验证 JWT Token

    Args:
        token: JWT Token
        token_type: Token 类型（access 或 refresh）

    Returns:
        Optional[str]: Token 主题（用户 ID），验证失败返回 None
    """
    payload = decode_token(token)
    if payload is None:
        return None

    # 检查 Token 类型
    if payload.get("type") != token_type:
        return None

    # 检查是否过期
    exp = payload.get("exp")
    if exp is None:
        return None

    return payload.get("sub")
