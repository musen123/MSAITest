"""项目知识库 Schemas（自研版）"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class KnowledgeBaseResponse(BaseModel):
    """项目知识库元信息响应（含 embed 钉定信息与索引版本，统计为项目真实口径）"""

    model_config = {"from_attributes": True}

    id: int
    project_id: int
    status: str
    # —— embedding 库级钉定（§3#5） ——
    embed_provider: Optional[str] = None
    embed_model: Optional[str] = None
    embed_dim: Optional[int] = None
    embed_bound_by: Optional[int] = None
    embed_bound_at: Optional[datetime] = None
    embed_status: str = "active"
    index_version: int = 0
    # —— 库级设置（P2：图谱白名单 + 图增强检索开关） ——
    graph_doc_types: str = "requirement,design,api_doc"
    settings: Optional[dict[str, Any]] = None
    total_documents: int
    total_chunks: int
    total_nodes: int
    total_edges: int
    project_summary: Optional[str] = None
    error_message: Optional[str] = None
    last_built_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
