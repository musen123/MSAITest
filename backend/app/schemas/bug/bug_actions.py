"""
Bug 操作动作 Schema（状态流转、指派、归档等）
"""

from typing import Optional

from pydantic import BaseModel, Field


class BugStatusChange(BaseModel):
    """变更 Bug 状态请求 Schema"""

    status: str = Field(description="目标状态枚举值")
    comment: Optional[str] = Field(default=None, description="操作备注")


class BugAssign(BaseModel):
    """指派 Bug 请求 Schema"""

    assigned_to: int = Field(description="指派给用户的 ID")
    comment: Optional[str] = Field(default=None, description="操作备注")


class BugResolve(BaseModel):
    """解决 / 关闭 / 重开 Bug 请求 Schema"""

    action: str = Field(description="操作类型：resolve / close / reopen")
    comment: Optional[str] = Field(default=None, description="操作备注")


class BugArchive(BaseModel):
    """归档 / 取消归档 Bug 请求 Schema"""

    is_archived: bool = Field(description="true=归档，false=取消归档")


class BugStatusResponse(BaseModel):
    """状态变更响应 Schema"""

    id: int
    status: str
    updated_at: str


class BugAssignResponse(BaseModel):
    """指派响应 Schema"""

    id: int
    assigned_to: Optional[int]
    assignee_name: Optional[str]
    status: str
    updated_at: str

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。
