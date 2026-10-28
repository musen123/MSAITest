"""用户大模型配置 Schema"""

from typing import Optional

from pydantic import BaseModel, Field

from app.models.auth.user_llm_config import ModelType


class UserLlmConfigCreate(BaseModel):
    model_type: str = Field(ModelType.TEXT, description="模型类型: text/embed/vision")
    name: Optional[str] = Field(None, description="配置别名/备注")
    provider: str = Field(..., description="模型提供商: openai/anthropic 等")
    model: str = Field(..., description="模型名称")
    api_key: str = Field(..., description="API Key")
    base_url: Optional[str] = Field(None, description="自定义 Base URL")
    model_family: Optional[str] = Field(
        None,
        max_length=32,
        description="模型家族（vision 用于 Midscene grounding，如 doubao-seed/qwen3-vl/glm-v）",
    )
    make_default: bool = Field(False, description="是否设为该类型默认配置")


class UserLlmConfigUpdate(BaseModel):
    """编辑单条配置（按 id）。字段全可选，不含 model_type（改类型会破坏默认不变量）。

    base_url / name 可显式置空，故用 ``model_fields_set`` 区分"未传"与"传了 None"。
    """

    name: Optional[str] = Field(None, description="配置别名/备注")
    provider: Optional[str] = Field(None, description="模型提供商")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, description="API Key")
    base_url: Optional[str] = Field(None, description="自定义 Base URL")
    model_family: Optional[str] = Field(None, max_length=32, description="模型家族")


class UserLlmConfigResponse(BaseModel):
    id: int
    user_id: int
    model_type: str
    name: Optional[str]
    provider: str
    model: str
    api_key: str
    base_url: Optional[str]
    model_family: Optional[str] = None
    is_active: bool
    is_default: bool

    model_config = {"from_attributes": True}

    @staticmethod
    def mask_api_key(api_key: str) -> str:
        if len(api_key) <= 8:
            return "****"
        return api_key[:4] + "****" + api_key[-4:]
