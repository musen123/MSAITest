"""知识库检索 Schemas（自研混合检索，设计文档 §3#4）

返回契约是「chunk 列表 + 引用溯源 + 降级标志」而非合成答案——
合成下放给各消费方自己的 TEXT 模型（Chat agent 在环 / /answer 端点流式）。
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# 锁定常量（任务拆解文档冻结；改动=改设计文档）
KB_SEARCH_DEFAULT_TOP_K = 10
KB_SEARCH_MAX_TOP_K = 30


class KbSearchRequest(BaseModel):
    """混合检索请求"""

    query: str = Field(min_length=1, max_length=2000, description="查询文本（Chat 工具契约：多轮对话须先改写为自包含问句）")
    top_k: int = Field(
        default=KB_SEARCH_DEFAULT_TOP_K, ge=1, le=KB_SEARCH_MAX_TOP_K, description="返回条数"
    )
    doc_types: Optional[list[str]] = Field(
        default=None, description="按文档类型过滤（requirement/api_doc/design/test_case/bug_review/meeting/other）"
    )
    deep: bool = Field(
        default=False,
        description="深度模式：LLM 查询改写 + listwise 重排（需 TEXT 模型；失败静默回退 RRF 序）",
    )
    consumer: Literal["search", "requirement"] = Field(
        default="search",
        description="消费方标注（检索日志分维；chat/answer/case_gen 由服务端注入不可伪装）",
    )


class KbSearchHit(BaseModel):
    """单条命中（chunk 级引用溯源：文档名 + 章节面包屑，两跳可达原文）"""

    chunk_id: int
    document_id: int
    doc_name: str
    doc_type: str
    heading_path: str = ""
    seq: int
    content: str
    score: float = Field(description="RRF 融合分（仅同一次检索内可比，非绝对相似度）")
    source_type: str = Field(description="upload/text/func_doc/entity——func_doc 可回跳平台实体")
    source_id: Optional[int] = None
    parse_mode: Optional[str] = Field(
        default=None, description="raw=原文确定性提取 / llm_normalized=LLM 规整产物（忠实性标注）"
    )


class KbSearchDegraded(BaseModel):
    """降级标志（检索永不 502：embed 外呼失败退纯全文单路，明示而非静默）"""

    vector: bool = Field(default=False, description="向量路是否降级（embed 失效/超时）")
    fulltext: bool = Field(default=False, description="全文路是否降级")


class KbSearchData(BaseModel):
    """检索响应 data 体（外层由 core/response.py 包 {code,message,data} 壳）"""

    hits: list[KbSearchHit] = Field(default_factory=list)
    degraded: KbSearchDegraded = Field(default_factory=KbSearchDegraded)
    index_version: int = Field(default=0, description="命中时的索引版本（调试/一致性排查用）")
    log_id: Optional[int] = Field(default=None, description="检索日志ID（反馈/采纳回写凭据）")
    reranked: bool = Field(default=False, description="深度模式下 LLM 重排是否实际生效（失败回退时为 false）")
    graph_boosted: bool = Field(
        default=False,
        description="图增强第三路是否实际参与融合（库级开关 settings.graph_channel 且查询命中实体）",
    )


class KbFeedbackRequest(BaseModel):
    """检索反馈回写（需求页点选采纳 / 答案页赞踩）"""

    log_id: int
    adopted_chunk_ids: Optional[list[int]] = Field(default=None, description="本次采纳的 chunk（增量合并）")
    feedback: Optional[Literal[1, -1]] = Field(default=None, description="1 赞 / -1 踩")
