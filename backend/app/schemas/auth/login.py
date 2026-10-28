"""
用户登录 Schema
"""

from pydantic import BaseModel, Field, field_serializer


class LoginRequest(BaseModel):
    """
    用户登录请求模型

    验证码字段已废弃（前端 UI 已移除验证码输入），保留以做兼容。
    新版请勿传递 captcha_code / captcha_key。
    """

    account: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")
    captcha_code: str | None = Field(default=None, description="[已废弃] 验证码")
    captcha_key: str | None = Field(default=None, description="[已废弃] 验证码Key")
    remember_me: bool = Field(False, description="记住登录状态")

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {
            "examples": [
                {
                    "account": "testuser",
                    "password": "Test123456",
                    "remember_me": False,
                }
            ]
        }


class LogoutRequest(BaseModel):
    """
    用户登出请求模型

    refresh_token 可选：登录态过期或纯前端清除场景下，
    服务端仅清除会话，前端自行清理本地存储即可。
    """

    refresh_token: str | None = Field(
        default=None, description="要撤销的刷新令牌（可选）"
    )


class UserInfo(BaseModel):
    """
    用户信息模型
    """

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    real_name: str | None = Field(None, description="真实姓名")
    avatar: str | None = Field(None, description="头像URL")
    roles: list[str] = Field(default_factory=list, description="角色列表")
    permissions: list[str] = Field(default_factory=list, description="权限列表")

    @field_serializer("avatar")
    def serialize_avatar(self, value: str | None) -> str | None:
        if not value:
            return value
        from app.utils.file import get_avatar_url
        return get_avatar_url(value)

    class Config:
        """Pydantic 配置"""

        from_attributes = True


class LoginResponse(BaseModel):
    """
    用户登录响应模型
    """

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    expires_in: int = Field(..., description="过期时间（秒）")
    user_info: UserInfo = Field(..., description="用户信息")

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "expires_in": 604800,
                    "user_info": {
                        "id": 1,
                        "username": "testuser",
                        "email": "test@example.com",
                        "real_name": "测试用户",
                        "avatar": "https://cdn.example.com/avatar/default.png",
                        "roles": ["tester"],
                        "permissions": ["test_case:view", "test_case:execute"],
                    },
                }
            ]
        }


class LogoutResponse(BaseModel):
    """
    用户登出响应模型
    """

    class Config:
        """Pydantic 配置"""

        json_schema_extra = {"examples": [{"message": "登出成功"}]}
