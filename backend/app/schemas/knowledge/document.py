"""知识库文档 Schemas（自研版）"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class KbDocumentResponse(BaseModel):
    """知识库文档响应"""

    id: int
    project_id: int
    file_name: str
    file_size: int
    file_ext: str
    doc_type: str = "other"
    source_type: str = "upload"
    source_id: Optional[int] = None
    storage_key: Optional[str] = None
    version: int = 1
    validity: str = "effective"
    parse_mode: Optional[str] = None
    truncated: bool = False
    chunk_count: int = 0
    ai_task_id: Optional[int] = None
    # 图谱抽取（P1b：与主 status 独立的状态面）
    graph_status: str = "none"
    graph_task_id: Optional[int] = None
    entity_count: int = 0
    status: str
    error_message: Optional[str] = None
    uploaded_by: int
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class KbDocumentListResponse(BaseModel):
    total: int
    items: list[KbDocumentResponse] = Field(default_factory=list)
    status_counts: dict[str, int] = Field(
        default_factory=dict, description="各状态文档数（本地 GROUP BY，替代 LightRAG 全局口径）"
    )


class KbDocumentUploadResponse(BaseModel):
    """上传/插文本响应：文档行 + 入库任务（前端跳任务详情/订阅 SSE）"""

    document: KbDocumentResponse
    ai_task_id: int


class KbInsertTextRequest(BaseModel):
    """直接插入文本到知识库"""

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    doc_type: Optional[str] = Field(
        default=None,
        description="文档类型：requirement/api_doc/design/test_case/bug_review/meeting/other",
    )


class KbDocumentPatchRequest(BaseModel):
    """文档元信息编辑（P1a：validity 只收 deprecated,恢复走 reingest）"""

    file_name: Optional[str] = Field(default=None, max_length=255)
    doc_type: Optional[str] = None
    validity: Optional[str] = Field(
        default=None, description="仅支持 'deprecated'（废弃即删分块,检索即时不可见）"
    )


class KbClearResponse(BaseModel):
    deleted: int
    chunks: int
