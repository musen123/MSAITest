"""项目文档 Schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentUpdate(BaseModel):
    """文档更新请求"""

    name: Optional[str] = Field(default=None, max_length=200)
    doc_type: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None, max_length=500)
    version: Optional[str] = Field(default=None, max_length=50)


class DocumentResponse(BaseModel):
    """文档响应"""

    id: int
    project_id: int
    name: str
    doc_type: str
    file_name: str
    file_path: str
    file_size: int
    file_ext: str
    description: Optional[str] = None
    version: Optional[str] = None
    status: str
    uploaded_by: int
    created_at: datetime
    updated_at: datetime
    download_url: Optional[str] = None

    # AI 解析 + 知识库入库
    parse_status: str = "pending"
    parsed_content: Optional[str] = None
    parsed_at: Optional[datetime] = None
    parse_error_message: Optional[str] = None
    kb_status: str = "not_ingested"
    kb_ingested_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    total: int
    items: list[DocumentResponse] = Field(default_factory=list)


class DocumentParseRequest(BaseModel):
    """触发 AI 解析的请求体"""

    custom_prompt: Optional[str] = Field(
        default=None, max_length=2000, description="附加给 LLM 的自定义提示"
    )


class DocumentPreviewResponse(BaseModel):
    """文档预览响应

    根据 ``preview_type`` 决定前端如何渲染：
      - ``url``       → 直接 iframe/img/object 嵌入（PDF/原型图）
      - ``html``      → 渲染 ``content`` 为 HTML（Word 已转换）
      - ``markdown``  → 渲染 ``content`` 为 Markdown
      - ``text``      → 纯文本
      - ``unsupported`` → 不支持，仅给下载链接
    """

    preview_type: str
    file_ext: str
    file_name: str
    url: Optional[str] = None
    content: Optional[str] = None
    parsed_content: Optional[str] = None  # AI 解析后的 Markdown
