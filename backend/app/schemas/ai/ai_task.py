"""统一 AI 任务 Pydantic Schemas"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AiTaskCreate(BaseModel):
    """提交 AI 任务"""

    task_type: str = Field(..., description="任务类型（registry key）")
    params: dict[str, Any] = Field(
        default_factory=dict, description="任务输入参数"
    )
    biz_ref_type: Optional[str] = Field(default=None, description="业务关联类型")
    biz_ref_id: Optional[int] = Field(default=None, description="业务关联ID")
    title: Optional[str] = Field(default=None, description="任务展示名（可选）")


class AiTaskResponse(BaseModel):
    """AI 任务（列表/主体）"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_by: int
    task_type: str
    title: str
    biz_ref_type: Optional[str] = None
    biz_ref_id: Optional[int] = None
    status: str
    progress: int
    current_stage: Optional[str] = None
    stage_index: Optional[int] = None
    total_stages: Optional[int] = None
    ai_model: Optional[str] = None
    result_summary: Optional[dict] = None
    result_ref: Optional[dict] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AiTaskListResponse(BaseModel):
    """AI 任务列表"""

    total: int
    items: list[AiTaskResponse] = Field(default_factory=list)


class AiTaskStatsResponse(BaseModel):
    """AI 任务状态统计（任务中心统计卡）"""

    total: int = 0
    pending: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    canceled: int = 0


class AiTaskEventResponse(BaseModel):
    """AI 任务事件"""

    model_config = ConfigDict(from_attributes=True)

    seq: int
    event_type: str
    payload: Optional[dict] = None
    created_at: Optional[datetime] = None


class AiTaskDetailResponse(AiTaskResponse):
    """AI 任务详情（含输入参数与已落库事件）"""

    input_params: Optional[dict] = None
    events: list[AiTaskEventResponse] = Field(default_factory=list)
