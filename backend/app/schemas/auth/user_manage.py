"""
用户管理 Schema
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_serializer, field_validator


def _normalize_phone(v: str | None) -> str | None:
    """手机号规范化：空白 → None，非空再校验格式。

    DB 中 phone 为 nullable + unique：多个 NULL 合法，但多个空串 '' 会触发
    "Duplicate entry '' for key 'sys_user.phone'" 唯一约束冲突。前端未填手机号
    时会传 ''，必须落库为 NULL，否则第二个没填手机号的用户一保存就 500。
    """
    if v is not None:
        v = v.strip()
    if not v:
        return None
    if not (v.isdigit() and len(v) == 11):
        raise ValueError("手机号格式不正确")
    return v


def _blank_to_none(v: str | None) -> str | None:
    """可选文本字段空白 → None（避免存空串）。"""
    if v is not None:
        v = v.strip()
    return v or None


class UserListQuery(BaseModel):
    """
    用户列表查询参数模型
    """

    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    keyword: str | None = Field(None, description="搜索关键词（用户名/邮箱/手机号）")
    status: str | None = Field(None, description="状态筛选：active/disabled")
    role_id: int | None = Field(None, description="角色筛选")
    order_by: str = Field(
        "created_at", description="排序字段：created_at/last_login_at"
    )
    order: str = Field("desc", description="排序方向：asc/desc")

    @field_validator("order")
    @classmethod
    def validate_order(cls, v: str) -> str:
        """验证排序方向"""
        if v not in ("asc", "desc"):
            raise ValueError("排序方向必须是 asc 或 desc")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """验证状态"""
        if v and v not in ("active", "disabled", "locked"):
            raise ValueError("状态必须是 active、disabled 或 locked")
        return v


class UserListItem(BaseModel):
    """
    用户列表项模型
    """

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    real_name: str | None = Field(None, description="真实姓名")
    avatar: str | None = Field(None, description="头像URL")
    status: str = Field(..., description="状态")
    roles: list[str] = Field(default_factory=list, description="角色列表")
    created_at: datetime = Field(..., description="创建时间")
    last_login_at: datetime | None = Field(None, description="最后登录时间")

    @field_validator("roles", mode="before")
    @classmethod
    def convert_roles(cls, v: list | None) -> list[str]:
        """将 Role 对象列表转换为角色代码字符串列表"""
        if v is None:
            return []
        # 如果已经是字符串列表，直接返回
        if v and isinstance(v[0], str):
            return v
        # 否则从 Role 对象提取 code 属性
        return [role.code for role in v]

    @field_validator("created_at", "last_login_at", mode="before")
    @classmethod
    def convert_timestamp(cls, v: int | None) -> datetime | None:
        """将时间戳转换为 datetime 对象"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        # 从时间戳（BIGINT）转换
        return datetime.fromtimestamp(v, tz=timezone.utc)

    @field_serializer("avatar")
    def serialize_avatar(self, value: str | None) -> str | None:
        if not value:
            return value
        from app.utils.file import get_avatar_url
        return get_avatar_url(value)

    class Config:
        """Pydantic 配置"""

        from_attributes = True


class UserDetailResponse(BaseModel):
    """
    用户详情响应模型
    """

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    real_name: str | None = Field(None, description="真实姓名")
    avatar: str | None = Field(None, description="头像URL")
    status: str = Field(..., description="状态")
    bio: str | None = Field(None, description="个人简介")
    roles: list[dict[str, Any]] = Field(default_factory=list, description="角色列表")
    permissions: list[str] = Field(default_factory=list, description="权限列表")
    projects: list[Any] = Field(default_factory=list, description="项目列表")
    created_at: datetime = Field(..., description="创建时间")

    @field_serializer("avatar")
    def serialize_avatar(self, value: str | None) -> str | None:
        if not value:
            return value
        from app.utils.file import get_avatar_url
        return get_avatar_url(value)
    last_login_at: datetime | None = Field(None, description="最后登录时间")

    @field_validator("roles", mode="before")
    @classmethod
    def convert_roles(cls, v: list | None) -> list[dict[str, Any]]:
        """将 Role 对象列表转换为字典列表"""
        if v is None:
            return []
        # 如果已经是字典列表，直接返回
        if v and isinstance(v[0], dict):
            return v
        # 否则从 Role 对象转换为字典
        return [{"id": role.id, "code": role.code, "name": role.name} for role in v]

    @field_validator("created_at", "last_login_at", mode="before")
    @classmethod
    def convert_timestamp(cls, v: int | None) -> datetime | None:
        """将时间戳转换为 datetime 对象"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        # 从时间戳（BIGINT）转换
        return datetime.fromtimestamp(v, tz=timezone.utc)

    class Config:
        """Pydantic 配置"""

        from_attributes = True


class CreateUserRequest(BaseModel):
    """
    创建用户请求模型（管理员）
    """

    username: str = Field(..., min_length=4, max_length=20, description="用户名")
    password: str = Field(..., min_length=8, max_length=20, description="密码")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    real_name: str | None = Field(None, max_length=50, description="真实姓名")
    role_ids: list[int] = Field(default_factory=list, description="角色ID列表")

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

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        """空手机号规范化为 None，避免空串撞 phone 唯一索引。"""
        return _normalize_phone(v)

    @field_validator("real_name")
    @classmethod
    def normalize_real_name(cls, v: str | None) -> str | None:
        return _blank_to_none(v)


class UpdateUserRequest(BaseModel):
    """
    更新用户信息请求模型
    """

    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    real_name: str | None = Field(None, max_length=50, description="真实姓名")
    bio: str | None = Field(None, max_length=500, description="个人简介")

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        """空手机号规范化为 None，避免空串撞 phone 唯一索引。"""
        return _normalize_phone(v)

    @field_validator("real_name")
    @classmethod
    def normalize_real_name(cls, v: str | None) -> str | None:
        return _blank_to_none(v)


class ChangePasswordRequest(BaseModel):
    """
    修改密码请求模型
    """

    old_password: str = Field(..., description="原密码")
    new_password: str = Field(..., min_length=8, max_length=20, description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码复杂度"""
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v


class ResetPasswordRequest(BaseModel):
    """
    重置密码请求模型（管理员）
    """

    new_password: str = Field(..., min_length=8, max_length=20, description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码复杂度"""
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v


class UpdateUserStatusRequest(BaseModel):
    """
    更新用户状态请求模型
    """

    status: str = Field(..., description="状态：active/disabled")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证状态"""
        if v not in ("active", "disabled"):
            raise ValueError("状态必须是 active 或 disabled")
        return v


class AssignRoleRequest(BaseModel):
    """
    为用户分配角色请求模型
    """

    role_ids: list[int] = Field(..., description="角色ID列表")


class UploadAvatarResponse(BaseModel):
    """
    上传头像响应模型
    """

    url: str = Field(..., description="头像URL")
