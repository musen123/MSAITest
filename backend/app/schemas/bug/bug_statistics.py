"""
Bug 统计分析 Pydantic Schema
"""

from typing import Optional

from pydantic import BaseModel, Field


class BugStatistics(BaseModel):
    """Bug 统计概览 Schema"""

    total: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_priority: dict[str, int]
    resolution_rate: float = Field(description="解决率（百分比）")
    avg_resolution_hours: Optional[float] = Field(
        default=None, description="平均解决时长（小时）"
    )


class BugTrends(BaseModel):
    """Bug 趋势分析 Schema"""

    dates: list[str]
    created: list[int]
    resolved: list[int]
    closed: list[int]

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。
