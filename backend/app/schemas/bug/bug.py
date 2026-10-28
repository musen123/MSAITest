"""
Bug 管理 Pydantic Schema
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BugCreate(BaseModel):
    """创建 Bug 请求 Schema"""

    title: str = Field(min_length=1, max_length=255, description="Bug 标题")
    description: str = Field(min_length=1, description="Bug 详细描述")
    severity: str = Field(description="严重程度：critical/major/moderate/minor/trivial")
    priority: str = Field(description="优先级：urgent/high/medium/low")
    module_id: Optional[int] = Field(default=None, description="关联模块 ID")
    test_case_id: Optional[int] = Field(default=None, description="关联测试用例 ID")
    test_case_type: Optional[str] = Field(
        default=None, description="用例类型：functional/api/web"
    )
    assigned_to: Optional[int] = Field(default=None, description="指派给用户 ID")
    environment: Optional[str] = Field(
        default=None, max_length=100, description="发现环境描述"
    )
    reproduction_steps: Optional[str] = Field(default=None, description="复现步骤")
    expected_result: Optional[str] = Field(default=None, description="预期结果")
    actual_result: Optional[str] = Field(default=None, description="实际结果")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    external_bug_key: Optional[str] = Field(
        default=None, max_length=100, description="外部系统 Bug 编号"
    )


class BugUpdate(BaseModel):
    """更新 Bug 请求 Schema（所有字段可选）"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, min_length=1)
    severity: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    module_id: Optional[int] = Field(default=None)
    test_case_id: Optional[int] = Field(default=None)
    test_case_type: Optional[str] = Field(default=None)
    environment: Optional[str] = Field(default=None, max_length=100)
    reproduction_steps: Optional[str] = Field(default=None)
    expected_result: Optional[str] = Field(default=None)
    actual_result: Optional[str] = Field(default=None)
    tags: Optional[list[str]] = Field(default=None)
    external_bug_key: Optional[str] = Field(default=None, max_length=100)


class BugListItem(BaseModel):
    """Bug 列表项 Schema（简略信息）"""

    id: int
    bug_key: str
    title: str
    severity: str
    priority: str
    status: str
    module_id: Optional[int]
    module_name: Optional[str] = None
    assigned_to: Optional[int]
    assignee_name: Optional[str] = None
    created_by: int
    creator_name: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BugResponse(BaseModel):
    """Bug 详情响应 Schema"""

    id: int
    bug_key: str
    project_id: int
    title: str
    description: str
    severity: str
    priority: str
    status: str
    module_id: Optional[int]
    module_name: Optional[str] = None
    test_case_id: Optional[int]
    test_case_type: Optional[str]
    assigned_to: Optional[int]
    assignee_name: Optional[str] = None
    environment: Optional[str]
    reproduction_steps: Optional[str]
    expected_result: Optional[str]
    actual_result: Optional[str]
    tags: Optional[list[str]]
    external_bug_key: Optional[str]
    is_archived: bool
    has_ai_analysis: bool = False
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BugListResponse(BaseModel):
    """Bug 列表响应 Schema"""

    total: int
    page: int
    page_size: int
    items: list[BugListItem] = Field(default_factory=list)

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。
