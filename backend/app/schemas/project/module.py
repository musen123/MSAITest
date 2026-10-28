"""
项目模块相关的 Pydantic Schema
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.project import ModuleType

# ==================== 模块 Schema ====================


class ModuleBase(BaseModel):
    """模块基础 Schema"""

    name: str = Field(min_length=1, max_length=100, description="模块名称")
    parent_id: Optional[int] = Field(default=None, description="父模块ID")
    sort_order: int = Field(default=0, ge=0, description="排序顺序")
    description: Optional[str] = Field(default=None, description="模块描述")


class ModuleCreate(ModuleBase):
    """创建模块请求 Schema"""

    module_type: Optional[ModuleType] = Field(
        default=ModuleType.FEATURE, description="模块类型"
    )

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, v: Optional[int]) -> Optional[int]:
        """验证父模块ID"""
        if v is not None and v <= 0:
            raise ValueError("父模块ID必须大于0")
        return v


class ModuleUpdate(BaseModel):
    """更新模块请求 Schema"""

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=100, description="模块名称"
    )
    sort_order: Optional[int] = Field(default=None, ge=0, description="排序顺序")
    description: Optional[str] = Field(default=None, description="模块描述")


class ModuleMove(BaseModel):
    """移动模块请求 Schema"""

    parent_id: Optional[int] = Field(default=None, description="新父模块ID")
    sort_order: int = Field(default=0, ge=0, description="新排序顺序")


class ModuleResponse(BaseModel):
    """模块响应 Schema"""

    id: int = Field(description="模块ID")
    name: str = Field(description="模块名称")
    parent_id: Optional[int] = Field(default=None, description="父模块ID")
    sort_order: int = Field(description="排序顺序")
    description: Optional[str] = Field(default=None, description="模块描述")
    path: Optional[str] = Field(default=None, description="模块路径")
    case_count: int = Field(default=0, description="用例数量")
    children_count: int = Field(default=0, description="子模块数量")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")

    model_config = {"from_attributes": True}


class ModuleTreeNode(BaseModel):
    """模块树节点 Schema"""

    id: int = Field(description="模块ID")
    name: str = Field(description="模块名称")
    parent_id: Optional[int] = Field(default=None, description="父模块ID")
    sort_order: int = Field(description="排序顺序")
    description: Optional[str] = Field(default=None, description="模块描述")
    case_count: int = Field(default=0, description="用例数量")
    level: int = Field(default=1, description="层级深度")
    children: List["ModuleTreeNode"] = Field(default_factory=list, description="子模块")

    model_config = {"from_attributes": True}


# 更新前向引用
ModuleTreeNode.model_rebuild()
