"""
用户注册 Schema
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    """
    用户注册请求模型
    """

    username: str = Field(..., min_length=4, max_length=20, description="用户名")
    password: str = Field(..., min_length=8, max_length=20, description="密码")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    real_name: str | None = Field(None, max_length=50, description="真实姓名")
    captcha_code: str = Field(..., description="验证码")
    captcha_key: str = Field(..., description="验证码Key")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        if not v.isalnum() and "_" not in v:
            raise ValueError("用户名只能包含字母、数字和下划线")
        if v[0].isdigit():
            raise ValueError("用户名不能以数字开头")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码复杂度"""
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """验证邮箱格式"""
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """验证手机号格式；空白规范化为 None（避免空串撞 phone 唯一索引）"""
        if v is not None:
            v = v.strip()
        if not v:
            return None
        if not (v.isdigit() and len(v) == 11):
            raise ValueError("手机号格式不正确")
        return v

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {
            "examples": [
                {
                    "username": "testuser",
                    "password": "Test123456",
                    "email": "test@example.com",
                    "phone": "13800138000",
                    "real_name": "测试用户",
                    "captcha_code": "1234",
                    "captcha_key": "captcha_key_from_session",
                }
            ]
        }


class RegisterResponse(BaseModel):
    """
    用户注册响应模型
    """

    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        """Pydantic 配置"""

        from_attributes = True

        json_schema_extra = {
            "examples": [
                {
                    "user_id": 1,
                    "username": "testuser",
                    "email": "test@example.com",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ]
        }
