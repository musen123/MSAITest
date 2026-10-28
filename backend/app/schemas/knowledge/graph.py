"""知识图谱 Schemas（P1b WP-B4）

返回契约（GraphView 消费）：节点带 entity_type/ref_count（前端映射颜色/大小），
边带 weight（映射边宽）；子图带 is_truncated（预算截断明示）。
"""

from typing import Optional

from pydantic import BaseModel, Field


class KbGraphNode(BaseModel):
    id: int
    name: str
    entity_type: str
    description: Optional[str] = None
    ref_count: int = 0
    doc_count: int = 0
    human_edited: bool = False


class KbGraphEdge(BaseModel):
    id: int
    source: int
    target: int
    keywords: str = ""
    description: Optional[str] = None
    weight: float = 1.0
    ref_count: int = 0
    human_edited: bool = False


class KbSubgraphData(BaseModel):
    nodes: list[KbGraphNode] = Field(default_factory=list)
    edges: list[KbGraphEdge] = Field(default_factory=list)
    is_truncated: bool = False


class KbGraphLabelsData(BaseModel):
    labels: list[str] = Field(default_factory=list)


class KbEntityMentionItem(BaseModel):
    document_id: int
    doc_name: str
    chunk_id: Optional[int] = None
    heading_path: str = ""


class KbEntityRelationItem(KbGraphEdge):
    source_name: str = ""
    target_name: str = ""


class KbEntityDetailData(KbGraphNode):
    created_by: Optional[int] = None
    mentions: list[KbEntityMentionItem] = Field(default_factory=list)
    relations: list[KbEntityRelationItem] = Field(default_factory=list)


class KbEntityCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    entity_type: str = Field(default="term", max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)


class KbEntityPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    entity_type: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)


class KbEntityMergeRequest(BaseModel):
    source_id: int = Field(description="败者（并入方，留重定向指针）")
    target_id: int = Field(description="胜者")


class KbRelationPatchRequest(BaseModel):
    keywords: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class KbGraphStatsData(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    doc_graph_status: dict[str, int] = Field(default_factory=dict)


class KbExtractSubmitData(BaseModel):
    ai_task_id: int


class KbExtractBatchData(BaseModel):
    dispatched: int = 0
    remaining: int = 0
    task_ids: list[int] = Field(default_factory=list)
