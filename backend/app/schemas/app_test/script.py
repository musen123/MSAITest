"""
APP 自动化用例 / 执行记录 / 录制操作台 Schema

用例载体 = Midscene YAML（tasks 段为回放输入）；录制单步 = 一句自然语言，
响应带执行结果 + 回收的即时动作步骤（沉淀进用例草稿）。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

# ==================== 用例 ====================


class AppScriptCreate(BaseModel):
    """创建用例请求"""

    name: str = Field(..., min_length=1, max_length=128, description="用例名称")
    yaml_content: str = Field(..., min_length=1, description="Midscene YAML 内容")
    platform: str = Field("android", description="平台：android/harmony/ios")
    target_app: Optional[str] = Field(None, max_length=128, description="目标应用包名/名称")
    description: Optional[str] = Field(None, max_length=500, description="用例描述")
    status: str = Field("draft", description="状态：draft/active/disabled")


class AppScriptUpdate(BaseModel):
    """更新用例请求（全部可选）"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    yaml_content: Optional[str] = Field(None, min_length=1)
    platform: Optional[str] = Field(None, description="平台：android/harmony/ios")
    target_app: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, description="draft/active/disabled")


class AppScriptOut(BaseModel):
    """用例响应"""

    id: int
    project_id: int
    name: str
    platform: str
    target_app: Optional[str] = None
    description: Optional[str] = None
    yaml_content: str
    status: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ==================== 执行记录 ====================


class AppExecutionOut(BaseModel):
    """执行记录响应"""

    id: int
    script_id: int
    script_name: Optional[str] = Field(None, description="用例名称（列表 JOIN）")
    script_platform: Optional[str] = Field(
        None, description="用例平台 android/harmony/ios（列表 JOIN）"
    )
    ai_task_id: Optional[str] = None
    device_udid: str
    device_name: Optional[str] = Field(
        None, description="设备型号（左连 app_device；设备已删则缺省）"
    )
    device_platform: Optional[str] = Field(
        None, description="实际执行平台（左连 app_device；跨平台强制回放时以此为准）"
    )
    status: str
    steps_summary: Optional[dict[str, Any]] = None
    report_path: Optional[str] = None
    duration_ms: Optional[int] = None
    retry_index: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ==================== 录制操作台（单步） ====================


class AutomationSessionRef(BaseModel):
    """仅引用会话的请求体（abort / end 用）"""

    session_id: str = Field(..., min_length=1, max_length=64, description="控制会话ID")


class AutomationStepIn(BaseModel):
    """录制单步请求：一句自然语言（Agent 侧 aiAct 内部多轮规划都算这一步）"""

    session_id: str = Field(..., min_length=1, max_length=64, description="控制会话ID（同投屏锁）")
    instruction: str = Field(..., min_length=1, max_length=2000, description="自然语言指令")
    act_context: Optional[str] = Field(
        None, max_length=2000, description="aiAct 全局上下文提示（可选）"
    )


class RecoveredStepOut(BaseModel):
    """回收的即时动作步骤（沉淀进用例）"""

    action: str = Field(..., description="动作：aiTap/aiInput/… 或无定位动作 AndroidHomeButton/Swipe/sleep/…")
    locate: Optional[str] = Field(None, description="定位描述（自然语言）；无定位动作缺省")
    value: Optional[str] = Field(None, description="aiInput 输入值 / launch 包名")
    params: Optional[dict[str, Any]] = Field(
        None, description="无定位动作的回放参数（Swipe 的 direction/distance、sleep 的 timeMs 等）"
    )


class AutomationStepOut(BaseModel):
    """录制单步响应：执行结果 + 回收步骤 + YAML flow 片段"""

    session_id: str
    status: str = Field(..., description="ok/error")
    summary: Optional[str] = Field(None, description="aiAct 文字总结")
    steps: list[RecoveredStepOut] = Field(default_factory=list)
    yaml_flow: str = Field("", description="回收步骤拼好的 YAML flow 片段")
    error: Optional[str] = Field(None, description="失败原因")


# ==================== 探索式生成（P3） ====================


class ExploreIn(BaseModel):
    """探索式生成请求：一句目标 → 自动探索 → 沉淀可回放用例（任务化）"""

    device_udid: str = Field(..., min_length=1, max_length=128, description="目标设备 UDID")
    goal: str = Field(..., min_length=4, max_length=2000, description="自然语言探索目标")
    script_name: Optional[str] = Field(
        None, max_length=128, description="用例名（缺省按目标截断生成）"
    )
    app_hint: Optional[str] = Field(
        None, max_length=2000, description="应用上下文提示（aiActContext，如「设置类应用，权限弹窗一律允许」）"
    )
    verify: bool = Field(True, description="生成后立即回放验证（通过则用例转 active）")
    suggest_asserts: bool = Field(True, description="用 TEXT 模型追加 aiAssert 断言建议")
