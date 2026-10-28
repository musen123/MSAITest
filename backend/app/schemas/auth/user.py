"""
用户信息 Schema
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_serializer


class RoleInfo(BaseModel):
    """
    角色信息模型
    """

    id: int = Field(..., description="角色ID")
    code: str = Field(..., description="角色编码")
    name: str = Field(..., description="角色名称")

    class Config:
        """Pydantic 配置"""

        from_attributes = True


class UserInfoResponse(BaseModel):
    """
    用户信息响应模型
    """

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    real_name: str | None = Field(None, description="真实姓名")
    avatar: str | None = Field(None, description="头像URL")
    status: str = Field(..., description="状态：active/disabled/locked")
    bio: str | None = Field(None, description="个人简介")
    roles: list[RoleInfo] = Field(default_factory=list, description="角色列表")
    created_at: datetime = Field(..., description="创建时间")
    last_login_at: datetime | None = Field(None, description="最后登录时间")

    @field_serializer("avatar")
    def serialize_avatar(self, value: str | None) -> str | None:
        if not value:
            return value
        from app.utils.file import get_avatar_url
        return get_avatar_url(value)

    class Config:
        """Pydantic 配置"""

        from_attributes = True

        json_schema_extra = {
            "examples": [
                {
                    "id": 1,
                    "username": "testuser",
                    "email": "test@example.com",
                    "phone": "13800138000",
                    "real_name": "测试用户",
                    "avatar": "https://cdn.example.com/avatar/default.png",
                    "status": "active",
                    "bio": "这是个人简介",
                    "roles": [
                        {
                            "id": 2,
                            "code": "tester",
                            "name": "测试人员",
                        }
                    ],
                    "created_at": "2025-01-01T00:00:00Z",
                    "last_login_at": "2025-02-04T10:30:00Z",
                }
            ]
        }
