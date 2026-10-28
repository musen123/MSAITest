"""
项目相关的 Pydantic Schema
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.models.project import ProjectStatus


class UserSimple(BaseModel):
    """用户简要信息"""

    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    real_name: Optional[str] = Field(default=None, description="真实姓名")
    avatar: Optional[str] = Field(default=None, description="头像URL")

    model_config = {"from_attributes": True}

    @field_serializer("avatar")
    def serialize_avatar(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        from app.utils.file import get_avatar_url
        return get_avatar_url(value)


# ==================== 项目 Schema ====================


class ProjectBase(BaseModel):
    """项目基础 Schema"""

    name: str = Field(min_length=2, max_length=100, description="项目名称")
    code: str = Field(
        min_length=2,
        max_length=50,
        pattern="^[a-zA-Z][a-zA-Z0-9_-]*$",
        description="项目标识（字母开头，仅支持字母、数字、下划线、中划线）",
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="项目描述"
    )
    avatar: Optional[str] = Field(
        default=None, max_length=255, description="项目图标URL"
    )
    start_date: Optional[date] = Field(default=None, description="计划开始日期")
    end_date: Optional[date] = Field(default=None, description="计划结束日期")
    is_public: bool = Field(default=False, description="是否公开项目")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[date], info) -> Optional[date]:
        """验证结束日期必须大于开始日期"""
        if v is not None and "start_date" in info.data:
            start_date = info.data.get("start_date")
            if start_date is not None and v < start_date:
                raise ValueError("结束日期必须大于或等于开始日期")
        return v


class ProjectCreate(ProjectBase):
    """创建项目请求 Schema"""

    pass


class ProjectUpdate(BaseModel):
    """更新项目请求 Schema"""

    name: Optional[str] = Field(
        default=None, min_length=2, max_length=100, description="项目名称"
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="项目描述"
    )
    avatar: Optional[str] = Field(
        default=None, max_length=255, description="项目图标URL"
    )
    start_date: Optional[date] = Field(default=None, description="计划开始日期")
    end_date: Optional[date] = Field(default=None, description="计划结束日期")
    is_public: Optional[bool] = Field(default=None, description="是否公开项目")
    status: Optional[ProjectStatus] = Field(default=None, description="项目状态")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[date], info) -> Optional[date]:
        """验证结束日期必须大于开始日期"""
        if v is not None and "start_date" in info.data:
            start_date = info.data.get("start_date")
            if start_date is not None and v < start_date:
                raise ValueError("结束日期必须大于或等于开始日期")
        return v


class ProjectResponse(BaseModel):
    """项目响应 Schema"""

    id: int = Field(description="项目ID")
    name: str = Field(description="项目名称")
    code: str = Field(description="项目标识")
    description: Optional[str] = Field(default=None, description="项目描述")
    avatar: Optional[str] = Field(default=None, description="项目图标URL")
    status: ProjectStatus = Field(description="项目状态")
    is_public: bool = Field(description="是否公开项目")
    start_date: Optional[date] = Field(default=None, description="计划开始日期")
    end_date: Optional[date] = Field(default=None, description="计划结束日期")
    member_count: int = Field(default=0, description="成员数量")
    module_count: int = Field(default=0, description="模块数量")
    case_count: int = Field(default=0, description="用例数量")
    bug_count: int = Field(default=0, description="Bug数量")
    created_by: Optional[UserSimple] = Field(default=None, description="创建者信息")
    owner: Optional[UserSimple] = Field(default=None, description="项目负责人信息")

    model_config = {"from_attributes": True}

    @field_serializer("avatar")
    def serialize_avatar(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        from app.utils.storage_utils import get_access_url
        from app.utils.file import _extract_storage_key
        return get_access_url(_extract_storage_key(value))


class ProjectDetailResponse(BaseModel):
    """项目详情响应 Schema"""

    id: int = Field(description="项目ID")
    name: str = Field(description="项目名称")
    code: str = Field(description="项目标识")
    description: Optional[str] = Field(default=None, description="项目描述")
    avatar: Optional[str] = Field(default=None, description="项目图标URL")
    status: ProjectStatus = Field(description="项目状态")
    is_public: bool = Field(description="是否公开项目")
    start_date: Optional[date] = Field(default=None, description="计划开始日期")
    end_date: Optional[date] = Field(default=None, description="计划结束日期")
    owner: Optional[UserSimple] = Field(default=None, description="项目负责人")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")

    model_config = {"from_attributes": True}

    @field_serializer("avatar")
    def serialize_avatar(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        from app.utils.storage_utils import get_access_url
        from app.utils.file import _extract_storage_key
        return get_access_url(_extract_storage_key(value))


# ==================== 项目列表查询 Schema ====================


class ProjectListQuery(BaseModel):
    """项目列表查询 Schema"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(default=None, description="搜索关键词（名称/描述）")
    status: Optional[ProjectStatus] = Field(default=None, description="状态筛选")
    is_public: Optional[bool] = Field(default=None, description="是否公开")
    member_id: Optional[int] = Field(default=None, description="筛选某用户参与的项目")
    order_by: str = Field(
        default="created_at",
        description="排序字段：created_at/updated_at/name",
    )
    order: str = Field(default="desc", pattern="^(asc|desc)$", description="排序方向")

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, v: str) -> str:
        """验证排序字段"""
        allowed_fields = {"created_at", "updated_at", "name"}
        if v not in allowed_fields:
            raise ValueError(f"排序字段必须是以下之一: {', '.join(allowed_fields)}")
        return v


# ==================== 项目操作 Schema ====================


class ProjectStatusUpdate(BaseModel):
    """项目状态更新 Schema"""

    status: ProjectStatus = Field(description="项目状态")


# ==================== 项目统计 Schema ====================


class CaseStatistics(BaseModel):
    """用例统计 Schema"""

    total: int = Field(default=0, description="用例总数")
    executed: int = Field(default=0, description="已执行数量")
    passed: int = Field(default=0, description="通过数量")
    failed: int = Field(default=0, description="失败数量")
    blocked: int = Field(default=0, description="阻塞数量")
    pass_rate: float = Field(default=0.0, description="通过率")
    execution_rate: float = Field(default=0.0, description="执行率")
    automation_rate: float = Field(default=0.0, description="自动化率")
    by_type: dict = Field(default_factory=dict, description="按类型统计")

    model_config = {"from_attributes": True}


class BugStatistics(BaseModel):
    """Bug 统计 Schema"""

    total: int = Field(default=0, description="Bug总数")
    new: int = Field(default=0, description="新增")
    resolved: int = Field(default=0, description="已解决")
    closed: int = Field(default=0, description="已关闭")
    resolution_rate: float = Field(default=0.0, description="解决率")
    by_severity: dict = Field(default_factory=dict, description="按严重程度统计")
    by_status: dict = Field(default_factory=dict, description="按状态统计")

    model_config = {"from_attributes": True}


class ExecutionTrendItem(BaseModel):
    """执行趋势项 Schema"""

    date: str = Field(description="日期")
    count: int = Field(description="执行数量")
    passed: int = Field(description="通过数量")
    failed: int = Field(description="失败数量")


class MemberStatisticsItem(BaseModel):
    """成员统计项 Schema"""

    user_id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    real_name: Optional[str] = Field(default=None, description="真实姓名")
    case_executed: int = Field(default=0, description="执行用例数")
    bug_found: int = Field(default=0, description="发现Bug数")
    active_days: int = Field(default=0, description="活跃天数")


class ProjectStatisticsResponse(BaseModel):
    """项目统计响应 Schema"""

    case_statistics: CaseStatistics = Field(description="用例统计")
    bug_statistics: BugStatistics = Field(description="Bug统计")
    execution_trend: list[ExecutionTrendItem] = Field(
        default_factory=list, description="执行趋势"
    )
    member_statistics: list[MemberStatisticsItem] = Field(
        default_factory=list, description="成员统计"
    )

    model_config = {"from_attributes": True}
