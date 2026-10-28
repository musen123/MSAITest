"""
全局函数相关的 Pydantic Schema
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class FunctionParam(BaseModel):
    """函数参数 Schema"""

    name: str = Field(min_length=1, max_length=100, description="参数名")
    type: str = Field(description="参数类型")
    description: Optional[str] = Field(default=None, description="参数描述")
    required: bool = Field(default=False, description="是否必填")
    default: Optional[Any] = Field(default=None, description="默认值")


class FunctionBase(BaseModel):
    """全局函数基础 Schema"""

    name: str = Field(min_length=1, max_length=100, description="函数名称")
    display_name: str = Field(min_length=1, max_length=100, description="函数显示名称")
    language: str = Field(description="编程语言：python/javascript")
    code: str = Field(min_length=1, max_length=10000, description="函数代码")
    description: Optional[str] = Field(default=None, description="函数描述")
    params: Optional[list[FunctionParam]] = Field(default=None, description="参数说明")
    return_type: Optional[str] = Field(
        default=None, max_length=50, description="返回值类型"
    )
    example: Optional[str] = Field(default=None, max_length=500, description="使用示例")
    is_active: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证函数名格式"""
        if not v:
            raise ValueError("函数名不能为空")
        if not v[0].isalpha() and v[0] != "_":
            raise ValueError("函数名必须以字母或下划线开头")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("函数名只能包含字母、数字和下划线")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """验证编程语言"""
        if v not in ("python", "javascript"):
            raise ValueError("编程语言必须是 python 或 javascript")
        return v


class FunctionCreate(FunctionBase):
    """创建函数请求 Schema"""

    pass


class FunctionUpdate(BaseModel):
    """更新函数请求 Schema"""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    language: Optional[str] = None
    code: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    description: Optional[str] = None
    params: Optional[list[FunctionParam]] = None
    return_type: Optional[str] = Field(default=None, max_length=50)
    example: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class FunctionResponse(BaseModel):
    """函数响应 Schema"""

    id: int = Field(description="函数ID")
    project_id: Optional[int] = Field(default=None, description="项目ID")
    name: str = Field(description="函数名称")
    display_name: str = Field(description="函数显示名称")
    language: str = Field(description="编程语言")
    code: str = Field(description="函数代码")
    description: Optional[str] = Field(default=None, description="函数描述")
    params: Optional[list[FunctionParam]] = Field(default=None, description="参数说明")
    return_type: Optional[str] = Field(default=None, description="返回值类型")
    example: Optional[str] = Field(default=None, description="使用示例")
    is_built_in: bool = Field(description="是否内置函数")
    is_active: bool = Field(description="是否启用")
    created_by: Optional[int] = Field(default=None, description="创建人ID")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")

    model_config = {"from_attributes": True}


class BuiltInFunctionResponse(BaseModel):
    """内置函数响应 Schema"""

    name: str = Field(description="函数名称")
    display_name: str = Field(description="函数显示名称")
    language: str = Field(default="python", description="编程语言")
    code: str = Field(default="", description="函数代码")
    description: str = Field(description="函数描述")
    params: list[FunctionParam] = Field(default_factory=list, description="参数说明")
    return_type: Optional[str] = Field(default=None, description="返回值类型")
    example: str = Field(default="", description="使用示例")
    is_built_in: bool = Field(default=True, description="是否内置函数")
    is_active: bool = Field(default=True, description="是否启用")


class FunctionListResponse(BaseModel):
    """函数列表响应 Schema"""

    built_in: list[BuiltInFunctionResponse] = Field(
        default_factory=list, description="内置函数"
    )
    custom: list[FunctionResponse] = Field(
        default_factory=list, description="自定义函数"
    )


class FunctionTestRequest(BaseModel):
    """测试函数请求 Schema"""

    params: Optional[dict[str, Any]] = Field(default=None, description="函数参数")


class FunctionTestResponse(BaseModel):
    """测试函数响应 Schema"""

    success: bool = Field(description="是否执行成功")
    result: Optional[Any] = Field(default=None, description="执行结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    execution_time: int = Field(description="执行时间（毫秒）")
    executed_at: str = Field(description="执行时间")


class FunctionStatusUpdate(BaseModel):
    """函数状态更新请求 Schema"""

    is_active: bool = Field(description="是否启用")


class FunctionAIGenerateRequest(BaseModel):
    """AI 生成函数请求 Schema"""

    requirement: str = Field(min_length=1, description="功能需求描述（自然语言）")
