"""
测试报告 Pydantic Schema
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReportSummary(BaseModel):
    """报告汇总统计"""

    total_executions: int = Field(default=0, description="总执行次数")
    functional_executions: int = Field(default=0, description="功能测试执行次数")
    app_executions: int = Field(default=0, description="App 自动化执行次数")
    overall_pass_rate: float = Field(default=0.0, description="综合通过率")
    functional_pass_rate: float = Field(default=0.0, description="功能测试通过率")
    app_pass_rate: float = Field(default=0.0, description="App 自动化通过率")


class ReportExecutionItem(BaseModel):
    """统一执行记录条目"""

    id: int = Field(description="执行记录 ID")
    exec_type: str = Field(description="执行类型：functional / app")
    name: str = Field(description="执行名称")
    status: str = Field(description="执行状态")
    total: int = Field(default=0, description="总用例数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    pass_rate: float = Field(default=0.0, description="通过率")
    duration_ms: int = Field(default=0, description="耗时（毫秒）")
    executor_name: Optional[str] = Field(default=None, description="执行人姓名")
    executed_at: datetime = Field(description="执行时间")


class ReportExecutionListResponse(BaseModel):
    """执行记录分页响应"""

    total: int = Field(description="总记录数")
    page: int = Field(description="当前页")
    page_size: int = Field(description="每页大小")
    items: list[ReportExecutionItem] = Field(description="记录列表")
