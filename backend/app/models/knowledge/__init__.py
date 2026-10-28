"""项目知识库数据模型（自研版，设计文档《知识库自研-总体设计方案》§4.1/§4.2）

存放：
  - ProjectKnowledgeBase：项目级知识库元信息（embed 库级钉定 + index_version）
  - KbDocument：知识库文档元数据（doc_type 类型体系 + 任务事件驱动状态机）
  - KbChunk：分块（父子块 + FULLTEXT ngram + embedding BLOB，检索核心资产）
  - KbEntity/KbRelation/KbEntityMention/KbRelationMention：知识图谱四表（P1b）
  - KbRetrievalLog：检索日志（反馈闭环）
"""

from app.models.knowledge.chunk import (
    KbChunk,
    KbChunkType,
)
from app.models.knowledge.document import (
    KbDocSourceType,
    KbDocType,
    KbDocument,
    KbDocumentStatus,
    KbDocValidity,
    KbParseMode,
)
from app.models.knowledge.graph import (
    KbEntity,
    KbEntityMention,
    KbEntityType,
    KbGraphStatus,
    KbRelation,
    KbRelationMention,
)
from app.models.knowledge.knowledge_base import (
    KbEmbedStatus,
    KnowledgeBaseStatus,
    ProjectKnowledgeBase,
)
from app.models.knowledge.retrieval_log import (
    KbRetrievalConsumer,
    KbRetrievalLog,
)

__all__ = [
    "ProjectKnowledgeBase",
    "KnowledgeBaseStatus",
    "KbEmbedStatus",
    "KbDocument",
    "KbDocumentStatus",
    "KbDocType",
    "KbDocSourceType",
    "KbDocValidity",
    "KbParseMode",
    "KbChunk",
    "KbChunkType",
    "KbEntity",
    "KbEntityMention",
    "KbEntityType",
    "KbGraphStatus",
    "KbRelation",
    "KbRelationMention",
    "KbRetrievalLog",
    "KbRetrievalConsumer",
]
