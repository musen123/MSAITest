"""智能体对话 Schemas"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default="新对话", max_length=255)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = None


class ConversationResponse(BaseModel):
    id: int
    project_id: int
    title: str
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    tool_calls: Optional[list[Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    total: int
    items: list[ConversationResponse] = Field(default_factory=list)
