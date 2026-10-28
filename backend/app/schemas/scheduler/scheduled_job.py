"""定时计划 Schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScheduledJobCreate(BaseModel):
    """创建定时计划"""

    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    job_type: str = Field(description="app_suite")
    target_id: int
    params: Optional[dict] = Field(default=None, description="{device_udid}")
    schedule_type: str = Field(default="cron", description="cron / interval")
    cron_expr: Optional[str] = Field(default=None, max_length=100)
    interval_seconds: Optional[int] = Field(default=None, ge=60)
    enabled: bool = True
    allow_overlap: bool = False


class ScheduledJobUpdate(BaseModel):
    """更新定时计划"""

    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    job_type: Optional[str] = None
    target_id: Optional[int] = None
    params: Optional[dict] = None
    schedule_type: Optional[str] = None
    cron_expr: Optional[str] = Field(default=None, max_length=100)
    interval_seconds: Optional[int] = Field(default=None, ge=60)
    enabled: Optional[bool] = None
    allow_overlap: Optional[bool] = None


class ScheduledJobResponse(BaseModel):
    """定时计划响应"""

    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    job_type: str
    target_id: int
    target_name: Optional[str] = None
    params: Optional[dict] = None
    schedule_type: str
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: bool
    allow_overlap: bool
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_task_id: Optional[int] = None
    total_runs: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobListResponse(BaseModel):
    total: int
    items: list[ScheduledJobResponse] = Field(default_factory=list)


class ScheduledJobRunResponse(BaseModel):
    """派发流水响应（含回链 ai_task 终态）"""

    id: int
    job_id: int
    ai_task_id: Optional[int] = None
    fired_at: datetime
    status: str
    note: Optional[str] = None
    task_status: Optional[str] = None

    model_config = {"from_attributes": True}


class ScheduledJobRunListResponse(BaseModel):
    total: int
    items: list[ScheduledJobRunResponse] = Field(default_factory=list)


class CronValidateRequest(BaseModel):
    cron_expr: str = Field(max_length=100)


class CronValidateResponse(BaseModel):
    valid: bool
    next_runs: list[str] = Field(default_factory=list)
