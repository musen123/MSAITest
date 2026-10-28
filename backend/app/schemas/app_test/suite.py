"""
APP 自动化套件 / 套件执行汇总 Schema（P4）

编排采用全量替换语义：PUT cases 提交有序数组，sort_order = 数组下标——
前端拖拽排序后整单保存，增/删/排序一个入口（比 web 先例三端点更省）。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ==================== 套件 ====================


class AppSuiteCreate(BaseModel):
    """创建套件请求"""

    name: str = Field(..., min_length=1, max_length=128, description="套件名称")
    description: Optional[str] = Field(None, max_length=500, description="套件描述")
    device_udid: Optional[str] = Field(
        None, max_length=160, description="默认执行设备（定时触发用；手动可覆盖）"
    )
    failure_strategy: str = Field(
        "continue", description="失败策略：continue/stop"
    )


class AppSuiteUpdate(BaseModel):
    """更新套件请求（全部可选）"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    device_udid: Optional[str] = Field(None, max_length=160)
    failure_strategy: Optional[str] = Field(None, description="continue/stop")


class AppSuiteCaseItem(BaseModel):
    """套件内用例条目（出参，JOIN 用例名/状态）"""

    id: int = Field(..., description="关联行 ID（app_suite_case.id）")
    script_id: int
    script_name: str = Field("", description="用例名称")
    script_status: str = Field("", description="用例状态：draft/active/disabled")
    script_platform: str = Field("android", description="用例平台：android/harmony/ios")
    sort_order: int = 0
    enabled: bool = True


class AppSuiteOut(BaseModel):
    """套件列表项响应"""

    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    device_udid: Optional[str] = None
    failure_strategy: str = "continue"
    case_count: int = Field(0, description="编排用例数")
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AppSuiteDetailOut(AppSuiteOut):
    """套件详情响应（含编排）"""

    cases: list[AppSuiteCaseItem] = Field(default_factory=list)


class AppSuiteCasesReplaceItem(BaseModel):
    """编排条目（入参）"""

    script_id: int = Field(..., description="用例 ID")
    enabled: bool = Field(True, description="是否参与执行")


class AppSuiteCasesReplaceIn(BaseModel):
    """全量替换编排：数组顺序即执行顺序"""

    items: list[AppSuiteCasesReplaceItem] = Field(
        default_factory=list, max_length=200, description="有序用例数组（空=清空编排）"
    )


class AppSuiteRunIn(BaseModel):
    """手动执行套件请求"""

    device_udid: Optional[str] = Field(
        None, max_length=160, description="执行设备（缺省用套件默认设备）"
    )
    force: bool = Field(
        False, description="强制执行（跳过用例↔设备平台不匹配的软拦截）"
    )


# ==================== 套件执行汇总 ====================


class AppSuiteExecutionOut(BaseModel):
    """套件执行汇总响应"""

    id: int
    suite_id: int
    project_id: int
    suite_name: Optional[str] = Field(None, description="套件名称（列表 JOIN）")
    ai_task_id: Optional[str] = None
    device_udid: str
    device_name: Optional[str] = Field(
        None, description="设备型号（左连 app_device；设备已删则缺省）"
    )
    device_platform: Optional[str] = Field(
        None, description="设备平台 android/harmony/ios（左连 app_device）"
    )
    trigger_type: str = "manual"
    status: str
    total_cases: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
