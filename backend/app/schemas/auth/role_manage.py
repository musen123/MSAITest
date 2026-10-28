"""
角色管理 Schema
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RoleListItem(BaseModel):
    """
    角色列表项模型
    """

    id: int = Field(..., description="角色ID")
    code: str = Field(..., description="角色编码")
    name: str = Field(..., description="角色名称")
    description: str | None = Field(None, description="角色描述")
    is_system: bool = Field(..., description="是否系统预定义角色")
    permissions: list[str] = Field(default_factory=list, description="权限列表")
    created_at: datetime = Field(..., description="创建时间")

    @field_validator("permissions", mode="before")
    @classmethod
    def convert_permissions(cls, v: list | None) -> list[str]:
        """将 Permission 对象列表转换为权限代码字符串列表"""
        if v is None:
            return []
        # 如果已经是字符串列表，直接返回
        if v and isinstance(v[0], str):
            return v
        # 否则从 Permission 对象提取 code 属性
        return [perm.code for perm in v]

    @field_validator("created_at", mode="before")
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


class RoleDetailResponse(BaseModel):
    """
    角色详情响应模型
    """

    id: int = Field(..., description="角色ID")
    code: str = Field(..., description="角色编码")
    name: str = Field(..., description="角色名称")
    description: str | None = Field(None, description="角色描述")
    is_system: bool = Field(..., description="是否系统预定义角色")
    permissions: list[str] = Field(default_factory=list, description="权限列表")
    users: list[Any] = Field(default_factory=list, description="拥有此角色的用户列表")
    created_at: datetime = Field(..., description="创建时间")

    @field_validator("permissions", mode="before")
    @classmethod
    def convert_permissions(cls, v: list | None) -> list[str]:
        """将 Permission 对象列表转换为权限代码字符串列表"""
        if v is None:
            return []
        # 如果已经是字符串列表，直接返回
        if v and isinstance(v[0], str):
            return v
        # 否则从 Permission 对象提取 code 属性
        return [perm.code for perm in v]

    @field_validator("created_at", mode="before")
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


class CreateRoleRequest(BaseModel):
    """
    创建角色请求模型
    """

    code: str = Field(..., min_length=1, max_length=50, description="角色编码")
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=200, description="角色描述")
    permissions: list[str] = Field(default_factory=list, description="权限编码列表")


class UpdateRoleRequest(BaseModel):
    """
    更新角色请求模型
    """

    name: str | None = Field(None, min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=200, description="角色描述")
    permissions: list[str] | None = Field(None, description="权限编码列表")


class PermissionListItem(BaseModel):
    """
    权限列表项模型
    """

    code: str = Field(..., description="权限编码")
    name: str = Field(..., description="权限名称")


class PermissionModule(BaseModel):
    """
    权限模块模型
    """

    module: str = Field(..., description="模块名称")
    permissions: list[PermissionListItem] = Field(
        default_factory=list, description="权限列表"
    )


class PermissionsResponse(BaseModel):
    """
    所有权限列表响应模型
    """

    data: list[PermissionModule] = Field(..., description="权限模块列表")


class UserPermissionsResponse(BaseModel):
    """
    用户权限响应模型
    """

    roles: list[Any] = Field(default_factory=list, description="角色列表")
    permissions: list[str] = Field(default_factory=list, description="权限列表")
