"""
操作日志相关的数据模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OperationLogResponse(BaseModel):
    """操作日志响应模型"""

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    module: str
    action: str
    description: Optional[str] = None
    request_method: Optional[str] = None
    request_url: Optional[str] = None
    request_params: Optional[str] = None
    response_status: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    execution_time: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OperationLogListResponse(BaseModel):
    """操作日志列表响应模型"""

    items: list[OperationLogResponse]
    total: int
    page: int
    page_size: int


class OperationLogStatsResponse(BaseModel):
    """操作日志聚合统计响应模型

    用于前端"今日统计"卡片：
    - total / users / actions / abnormal：当前区间的真实指标
    - prev_*：与当前区间等长的上一窗口指标，用于计算环比百分比（前端展示"较昨日 ↑X%"）
    """

    total: int = Field(default=0, description="操作总数")
    users: int = Field(default=0, description="不重复的操作用户数")
    actions: int = Field(default=0, description="不重复的操作类型数")
    abnormal: int = Field(default=0, description="异常操作数（response_status >= 400）")

    prev_total: int | None = Field(default=None, description="上一区间操作总数")
    prev_users: int | None = Field(default=None, description="上一区间不重复操作用户数")
    prev_actions: int | None = Field(default=None, description="上一区间不重复操作类型数")
    prev_abnormal: int | None = Field(default=None, description="上一区间异常操作数")
