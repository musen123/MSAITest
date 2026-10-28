"""知识库检索日志数据模型（P1a 反馈闭环的数据底座）

对应数据库表：kb_retrieval_log

价值（评审嫁接自产品派方案）：没有检索日志与采纳反馈,「检索质量好不好」
永远只有一次性人工评测——本表是 P2 重排决策、jieba 引入与质量回归的
唯一实测数据源。需求页点选 chunk / 答案页赞踩 即采纳信号。

保留期（评审补漏:无界增长）：写入时按 id 取模概率触发清理 90 天前的行,
不新增 beat 任务(小表小平台,顺手清理足够)。
"""

from enum import Enum
from typing import Any, Optional

from sqlalchemy import Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, JSON, TINYINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class KbRetrievalConsumer(str, Enum):
    """检索消费方（口径统一,质量看板按此分维）"""

    SEARCH = "search"  # 检索页纯检索
    ANSWER = "answer"  # 检索页问答合成
    CHAT = "chat"  # Chat 智能体工具
    REQUIREMENT = "requirement"  # 需求页 RAG 辅助
    CASE_GEN = "case_gen"  # 用例生成图自动检索


class KbRetrievalLog(Base, IDMixin, TimestampMixin):
    """知识库检索日志"""

    __tablename__ = "kb_retrieval_log"

    project_id: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="项目ID（硬隔离列）"
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT, nullable=True, comment="查询用户ID"
    )
    consumer: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default=KbRetrievalConsumer.SEARCH.value,
        comment="消费方：search/answer/chat/requirement/case_gen",
    )
    query: Mapped[str] = mapped_column(
        VARCHAR(500), nullable=False, comment="查询文本（截断 500）"
    )
    top_k: Mapped[int] = mapped_column(INTEGER, nullable=False, default=10)
    doc_types: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="类型过滤"
    )
    deep: Mapped[bool] = mapped_column(
        TINYINT(1), nullable=False, default=False, comment="是否深度模式（改写+重排）"
    )
    hits: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True, comment="命中 [{chunk_id, document_id, score}]"
    )
    degraded: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="降级标志 {vector, fulltext}"
    )
    latency_ms: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="检索耗时（毫秒,不含合成）"
    )
    adopted_chunk_ids: Mapped[Optional[list[int]]] = mapped_column(
        JSON, nullable=True, comment="被采纳的 chunk（需求页点选/引用展开回写）"
    )
    feedback: Mapped[Optional[int]] = mapped_column(
        TINYINT, nullable=True, comment="用户反馈：1 赞 / -1 踩 / NULL 未反馈"
    )

    __table_args__ = (
        Index("idx_kb_rlog_project_time", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<KbRetrievalLog(id={self.id}, project_id={self.project_id}, consumer='{self.consumer}')>"
