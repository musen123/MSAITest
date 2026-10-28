"""
Bug AI 智能分析 Pydantic Schema
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AiAnalysisTrigger(BaseModel):
    """触发 AI 分析请求 Schema"""

    custom_prompt: Optional[str] = Field(default=None, description="自定义分析提示词")


class AiAnalysisStatusResponse(BaseModel):
    """AI 分析状态响应 Schema"""

    analysis_id: str
    analysis_status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AiAnalysisResponse(BaseModel):
    """AI 分析完整结果响应 Schema"""

    analysis_id: str
    analysis_status: str
    root_cause_analysis: Optional[dict[str, Any]] = None
    solution_recommendation: Optional[dict[str, Any]] = None
    similar_bugs: Optional[list[Any]] = None
    severity_assessment: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
