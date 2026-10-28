"""
项目成员相关的 Pydantic Schema
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# 项目角色代码常量（与 CRUD 层保持一致）
class ProjectRoleCode:
    """项目角色代码常量（单层 RBAC：仅 负责人/成员 两种，仅作组织标签）"""

    OWNER = "project_owner"  # 项目负责人（可管理项目）
    MEMBER = "project_member"  # 项目成员

    # 所有有效的项目角色代码
    ALL = {OWNER, MEMBER}


# ==================== 成员 Schema ====================


class RoleBrief(BaseModel):
    """角色简要信息（用于展示用户的系统角色）"""

    code: str = Field(description="角色代码")
    name: str = Field(description="角色名称")

    model_config = {"from_attributes": True}


class UserInProject(BaseModel):
    """项目中的用户信息 Schema"""

    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    real_name: Optional[str] = Field(default=None, description="真实姓名")
    email: Optional[str] = Field(default=None, description="邮箱")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    # 用户的系统角色（决定其实际操作权限；项目角色仅作组织标签）
    roles: List[RoleBrief] = Field(default_factory=list, description="用户的系统角色")

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    """成员响应 Schema"""

    id: int = Field(description="成员记录ID")
    user: UserInProject = Field(description="用户信息")
    project_role: str = Field(description="项目角色代码")
    joined_at: Optional[str] = Field(default=None, description="加入时间")
    last_active_at: Optional[str] = Field(default=None, description="最后活跃时间")

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    """添加成员请求 Schema"""

    user_ids: List[int] = Field(min_length=1, description="用户ID列表")
    project_role: str = Field(description="项目角色代码")

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, v: List[int]) -> List[int]:
        """验证用户ID列表"""
        if not v:
            raise ValueError("用户ID列表不能为空")
        # 去重
        return list(set(v))

    @field_validator("project_role")
    @classmethod
    def validate_project_role(cls, v: str) -> str:
        """验证项目角色代码"""
        if v not in ProjectRoleCode.ALL:
            raise ValueError(
                f"无效的项目角色代码: {v}。"
                f"有效值为: {', '.join(ProjectRoleCode.ALL)}"
            )
        return v


class MemberRoleUpdate(BaseModel):
    """成员角色更新请求 Schema"""

    project_role: str = Field(description="新项目角色代码")

    @field_validator("project_role")
    @classmethod
    def validate_project_role(cls, v: str) -> str:
        """验证项目角色代码"""
        if v not in ProjectRoleCode.ALL:
            raise ValueError(
                f"无效的项目角色代码: {v}。"
                f"有效值为: {', '.join(ProjectRoleCode.ALL)}"
            )
        return v


class MemberPermissionsResponse(BaseModel):
    """成员权限响应 Schema"""

    project_role: Optional[str] = Field(default=None, description="项目角色代码")
    permissions: List[str] = Field(default_factory=list, description="权限列表")
    can_edit_project: bool = Field(default=False, description="是否可以编辑项目")
    can_manage_members: bool = Field(default=False, description="是否可以管理成员")
    can_delete_project: bool = Field(default=False, description="是否可以删除项目")

    model_config = {"from_attributes": True}


# ==================== 成员查询 Schema ====================


class MemberListQuery(BaseModel):
    """成员列表查询 Schema"""

    role: Optional[str] = Field(default=None, description="角色筛选（角色代码）")
    keyword: Optional[str] = Field(
        default=None, description="搜索关键词（用户名/姓名）"
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """验证项目角色代码"""
        if v is not None and v not in ProjectRoleCode.ALL:
            raise ValueError(
                f"无效的项目角色代码: {v}。"
                f"有效值为: {', '.join(ProjectRoleCode.ALL)}"
            )
        return v


# ==================== 项目转让 Schema ====================


class ProjectTransferRequest(BaseModel):
    """项目转让请求 Schema"""

    to_user_id: int = Field(description="接收人用户ID")

    @field_validator("to_user_id")
    @classmethod
    def validate_to_user_id(cls, v: int) -> int:
        """验证接收人用户ID"""
        if v <= 0:
            raise ValueError("接收人用户ID必须大于0")
        return v


class ProjectTransferResponse(BaseModel):
    """项目转让响应 Schema"""

    from_user_id: int = Field(description="转让人用户ID")
    to_user_id: int = Field(description="接收人用户ID")
    from_user_new_role: str = Field(description="转让人新角色")
    to_user_new_role: str = Field(description="接收人新角色")

    model_config = {"from_attributes": True}
