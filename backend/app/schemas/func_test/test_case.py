"""功能测试用例 Schemas"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CaseStepSchema(BaseModel):
    """测试步骤"""

    step_no: int
    action: str
    expected: str


class TestCaseCreate(BaseModel):
    """创建用例请求"""

    title: str = Field(..., max_length=200)
    code: Optional[str] = Field(default=None, max_length=80)
    requirement_id: Optional[int] = None
    module_id: Optional[int] = None
    priority: str = Field(default="medium")
    case_type: str = Field(default="functional")
    validation_level: str = Field(default="system")
    preconditions: Optional[str] = None
    test_data: Optional[dict] = None
    steps: Optional[list[CaseStepSchema]] = None
    expected_result: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    ui_automatable: Optional[bool] = Field(
        default=None, description="是否适合 Web UI 自动化（true/false/null=未评估）"
    )


class TestCaseUpdate(BaseModel):
    """更新用例请求"""

    title: Optional[str] = Field(default=None, max_length=200)
    code: Optional[str] = Field(default=None, max_length=80)
    requirement_id: Optional[int] = None
    module_id: Optional[int] = None
    priority: Optional[str] = None
    case_type: Optional[str] = None
    validation_level: Optional[str] = None
    status: Optional[str] = None
    preconditions: Optional[str] = None
    test_data: Optional[dict] = None
    steps: Optional[list[CaseStepSchema]] = None
    expected_result: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    ui_automatable: Optional[bool] = Field(
        default=None, description="是否适合 Web UI 自动化（true/false/null=未评估）"
    )


class TestCaseReview(BaseModel):
    """用例评审请求"""

    action: str = Field(description="approve / reject")
    review_comment: Optional[str] = Field(default=None, max_length=500)


class TestCaseBatchReview(BaseModel):
    """用例批量评审请求"""

    case_ids: list[int] = Field(min_length=1, max_length=200)
    action: str = Field(description="approve / reject")
    review_comment: Optional[str] = Field(default=None, max_length=500)


class TestCaseResponse(BaseModel):
    """用例响应"""

    id: int
    project_id: int
    code: Optional[str] = None
    title: str
    requirement_id: Optional[int] = None
    module_id: Optional[int] = None
    priority: str
    case_type: str
    validation_level: str
    status: str
    preconditions: Optional[str] = None
    test_data: Optional[dict] = None
    steps: Optional[list[Any]] = None
    expected_result: Optional[list[Any]] = None
    tags: Optional[list[Any]] = None
    ui_automatable: Optional[bool] = None
    review_info: Optional[dict] = None
    review_comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    source: str
    created_by: int
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseListResponse(BaseModel):
    """用例列表响应"""

    total: int
    items: list[TestCaseResponse] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
