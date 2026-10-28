"""测试需求 Schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RequirementCreate(BaseModel):
    """创建需求请求"""

    title: str = Field(min_length=1, max_length=200)
    code: Optional[str] = Field(default=None, max_length=50)
    module_id: Optional[int] = None
    priority: str = Field(default="medium")
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    attachments: Optional[list[str]] = None


class RequirementUpdate(BaseModel):
    """更新需求请求"""

    title: Optional[str] = Field(default=None, max_length=200)
    code: Optional[str] = Field(default=None, max_length=50)
    module_id: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    understood_content: Optional[str] = None
    attachments: Optional[list[str]] = None


class RequirementReview(BaseModel):
    """需求审核请求"""

    action: str = Field(description="approve / reject")
    review_comment: Optional[str] = Field(default=None, max_length=500)


class RequirementResponse(BaseModel):
    """需求响应"""

    id: int
    project_id: int
    code: Optional[str] = None
    title: str
    module_id: Optional[int] = None
    priority: str
    status: str
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    understood_content: Optional[str] = None
    source: str
    document_id: Optional[int] = None
    attachments: Optional[list[str]] = None
    review_comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    case_count: int = 0

    model_config = {"from_attributes": True}


class RequirementListResponse(BaseModel):
    """需求列表响应"""

    total: int
    items: list[RequirementResponse] = Field(default_factory=list)


# ─── 上传附件 ─────────────────────────────────────────────


class AttachmentUploadResponse(BaseModel):
    url: str
