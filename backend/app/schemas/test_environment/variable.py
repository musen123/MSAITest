"""
环境变量相关的 Pydantic Schema
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EnvironmentVariableBase(BaseModel):
    """环境变量基础 Schema"""

    name: str = Field(min_length=1, max_length=100, description="变量名")
    value: str = Field(min_length=1, description="变量值")
    type: str = Field(
        default="text", description="变量类型：text/password/json/dynamic"
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="变量描述"
    )
    is_active: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0, ge=0, description="排序顺序")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证变量名格式"""
        if not v:
            raise ValueError("变量名不能为空")
        if not v[0].isalpha() and v[0] != "_":
            raise ValueError("变量名必须以字母或下划线开头")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("变量名只能包含字母、数字和下划线")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证变量类型"""
        if v not in ("text", "password", "json", "dynamic"):
            raise ValueError("变量类型必须是 text/password/json/dynamic 之一")
        return v


class EnvironmentVariableCreate(EnvironmentVariableBase):
    """创建变量请求 Schema"""

    pass


class EnvironmentVariableUpdate(BaseModel):
    """更新变量请求 Schema"""

    value: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class EnvironmentVariableResponse(BaseModel):
    """变量响应 Schema"""

    id: int = Field(description="变量ID")
    env_id: int = Field(description="环境ID")
    name: str = Field(description="变量名")
    value: str = Field(description="变量值")
    type: str = Field(description="变量类型")
    description: Optional[str] = Field(default=None, description="变量描述")
    is_active: bool = Field(description="是否启用")
    sort_order: int = Field(description="排序顺序")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")

    model_config = {"from_attributes": True}


class VariableBatchUpdateItem(BaseModel):
    """批量更新变量项 Schema"""

    id: int = Field(description="变量ID")
    value: Optional[str] = None
    is_active: Optional[bool] = None


class VariableBatchUpdateRequest(BaseModel):
    """批量更新变量请求 Schema"""

    variables: list[VariableBatchUpdateItem] = Field(
        min_length=1, description="变量列表"
    )


class VariableBatchUpdateResponse(BaseModel):
    """批量更新变量响应 Schema"""

    updated_count: int = Field(description="更新数量")


class VariableExportContent(BaseModel):
    """变量导出内容 Schema"""

    environment: str = Field(description="环境名称")
    exported_at: str = Field(description="导出时间")
    variables: list[EnvironmentVariableCreate] = Field(description="变量列表")


class VariableExportResponse(BaseModel):
    """变量导出响应 Schema"""

    filename: str = Field(description="文件名")
    content: VariableExportContent = Field(description="导出内容")


class VariableImportRequest(BaseModel):
    """变量导入请求 Schema"""

    content: VariableExportContent = Field(description="导入内容")
    mode: str = Field(description="导入模式：merge/replace")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """验证导入模式"""
        if v not in ("merge", "replace"):
            raise ValueError("导入模式必须是 merge 或 replace")
        return v


class VariableImportResponse(BaseModel):
    """变量导入响应 Schema"""

    imported_count: int = Field(description="导入数量")
    skipped_count: int = Field(default=0, description="跳过数量")
    failed_count: int = Field(default=0, description="失败数量")


class VariableBatchDeleteRequest(BaseModel):
    """批量删除变量请求 Schema"""

    ids: list[int] = Field(min_length=1, description="变量ID列表")


class VariableBatchDeleteResponse(BaseModel):
    """批量删除变量响应 Schema"""

    deleted_count: int = Field(description="删除数量")
