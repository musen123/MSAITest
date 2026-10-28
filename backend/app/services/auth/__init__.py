"""
认证授权模块 - 服务

本模块包含认证授权相关的业务服务：
- 验证码服务
- 用户认证服务
"""

from app.services.auth.auth_service import AuthService, auth_service
from app.services.auth.captcha import (
    CaptchaService,
    RedisCaptchaService,
    captcha_service,
)

__all__ = [
    "AuthService",
    "auth_service",
    "CaptchaService",
    "RedisCaptchaService",
    "captcha_service",
]
