"""
项目配置相关的 Pydantic Schema
"""

from typing import Optional

from pydantic import BaseModel, Field

# ==================== 配置 Schema ====================


class ConfigBase(BaseModel):
    """配置基础 Schema"""

    default_env_id: Optional[int] = Field(default=None, description="默认测试环境ID")
    bug_auto_assign: bool = Field(default=True, description="Bug是否自动分配给创建者")
    bug_severity_default: str = Field(
        default="medium",
        description="Bug默认严重程度：critical/high/medium/low/trivial",
    )
    test_case_priority_default: str = Field(
        default="medium",
        description="用例默认优先级：critical/high/medium/low",
    )
    allow_public_report: bool = Field(
        default=False, description="是否允许公开查看测试报告"
    )
    retention_days: int = Field(
        default=90, ge=1, le=3650, description="数据保留天数（归档后）"
    )


class ConfigCreate(ConfigBase):
    """创建配置请求 Schema"""

    pass


class ConfigUpdate(BaseModel):
    """更新配置请求 Schema"""

    default_env_id: Optional[int] = Field(default=None, description="默认测试环境ID")
    bug_auto_assign: Optional[bool] = Field(
        default=None, description="Bug是否自动分配给创建者"
    )
    bug_severity_default: Optional[str] = Field(
        default=None,
        description="Bug默认严重程度：critical/high/medium/low/trivial",
    )
    test_case_priority_default: Optional[str] = Field(
        default=None,
        description="用例默认优先级：critical/high/medium/low",
    )
    allow_public_report: Optional[bool] = Field(
        default=None, description="是否允许公开查看测试报告"
    )
    retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=3650,
        description="数据保留天数（归档后）",
    )


class ConfigResponse(ConfigBase):
    """配置响应 Schema"""

    id: int = Field(description="配置ID")
    project_id: int = Field(description="项目ID")

    model_config = {"from_attributes": True}
