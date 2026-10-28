"""
认证授权模块 - Schema

本模块包含认证授权相关的所有 Pydantic Schema：
- 注册/登录相关 Schema
- Token 相关 Schema
- 用户信息 Schema
- 用户管理 Schema
- 角色管理 Schema
"""

from app.schemas.auth.login import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)
from app.schemas.auth.register import RegisterRequest, RegisterResponse
from app.schemas.auth.role_manage import (
    CreateRoleRequest,
    PermissionListItem,
    PermissionModule,
    PermissionsResponse,
    RoleDetailResponse,
    RoleListItem,
    UpdateRoleRequest,
    UserPermissionsResponse,
)
from app.schemas.auth.token import RefreshTokenRequest, RefreshTokenResponse
from app.schemas.auth.user import UserInfoResponse
from app.schemas.auth.user_manage import (
    ChangePasswordRequest,
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UpdateUserStatusRequest,
    UploadAvatarResponse,
    UserDetailResponse,
    UserListItem,
    UserListQuery,
)

__all__ = [
    "RegisterRequest",
    "RegisterResponse",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "UserInfoResponse",
    "UserListQuery",
    "UserListItem",
    "UserDetailResponse",
    "CreateUserRequest",
    "UpdateUserRequest",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "UpdateUserStatusRequest",
    "UploadAvatarResponse",
    "RoleListItem",
    "RoleDetailResponse",
    "CreateRoleRequest",
    "UpdateRoleRequest",
    "PermissionsResponse",
    "UserPermissionsResponse",
    "PermissionListItem",
    "PermissionModule",
]
