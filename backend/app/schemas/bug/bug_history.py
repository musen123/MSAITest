"""
Bug 操作历史 Pydantic Schema
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BugHistoryResponse(BaseModel):
    """Bug 操作历史响应 Schema"""

    id: int
    action: str
    from_value: Optional[str]
    to_value: Optional[str]
    comment: Optional[str]
    operated_by: int
    operator_name: Optional[str] = None
    operated_at: datetime

    model_config = {"from_attributes": True}
