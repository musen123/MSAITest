"""用例执行记录 Schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CaseExecutionCreate(BaseModel):
    """提交执行结果请求"""

    execute_result: str = Field(description="passed/failed/blocked/skipped")
    environment_id: Optional[int] = None
    notes: Optional[str] = None
    duration: Optional[int] = Field(default=None, description="耗时（秒）")
    executed_at: Optional[datetime] = None


class CaseExecutionResponse(BaseModel):
    id: int
    test_case_id: int
    project_id: int
    environment_id: Optional[int] = None
    execute_result: str
    executor_id: int
    notes: Optional[str] = None
    executed_at: datetime
    duration: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseExecutionListResponse(BaseModel):
    total: int
    items: list[CaseExecutionResponse] = Field(default_factory=list)
