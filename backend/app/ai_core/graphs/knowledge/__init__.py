"""知识库域 AI 任务图（自研替代 LightRAG，设计文档《知识库自研-总体设计方案》）

  - kb_ingest：文档入库（解析→分块→向量化→落库），P0
  - kb_rebuild：换 embed 模型/分块策略后全量重建，P1a
  - kb_extract：知识图谱抽取（独立于入库主流程，失败不阻塞检索），P1b
"""

from app.ai_core.graphs.knowledge import extract, ingest  # noqa: F401

__all__ = ["ingest", "extract"]
