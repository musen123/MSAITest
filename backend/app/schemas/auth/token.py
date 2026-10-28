"""
Token 刷新 Schema
"""

from pydantic import BaseModel, Field


class Token(BaseModel):
    """
    OAuth2 标准 Token 响应模型

    用于 FastAPI Swagger 文档认证
    """

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="Token 类型")
    expires_in: int | None = Field(None, description="过期时间（秒）")
    refresh_token: str | None = Field(None, description="刷新令牌")

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 604800,
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                }
            ]
        }


class RefreshTokenRequest(BaseModel):
    """
    刷新 Token 请求模型
    """

    refresh_token: str = Field(..., description="刷新令牌")

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                }
            ]
        }


class RefreshTokenResponse(BaseModel):
    """
    刷新 Token 响应模型
    """

    access_token: str = Field(..., description="新的访问令牌")
    refresh_token: str = Field(..., description="轮换后的刷新令牌")
    expires_in: int = Field(..., description="过期时间（秒）")

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "expires_in": 604800,
                }
            ]
        }
