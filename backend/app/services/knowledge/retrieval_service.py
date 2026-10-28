"""知识库混合检索服务（设计文档 §3#3/#4，任务拆解 T4.2）

流水线：向量召回 ∥ 全文召回（各 top30，并行、**各自独立会话**——同一 AsyncSession
不可并发使用）→ RRF 融合（k=60）→ 区间去重（同 parent 上卷合并 / 同文档 cap 3 /
上下文 8000 token 封顶）→ chunk 引用列表。

可用性铁律（§8 R2）：检索**永不 502**——
  - 向量路失败（库未钉定 / embed_status=invalid / key 失效 / 外呼超时 10s）
    → 纯全文单路继续服务，degraded.vector=true 明示
  - 全文路失败 → 向量单路，degraded.fulltext=true
  - 双路全失败 → 空结果 + 双 degraded 标志，仍是 200

返回契约 = chunk 列表 + 引用溯源（非合成答案）：合成下放消费方
（Chat agent 用自己的对话模型 / /answer 端点用查询者 TEXT 模型）。
"""

import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

from app.core.exceptions import BusinessException
from app.crud.knowledge import crud_kb_chunk, crud_knowledge_base
from app.db.session import async_session_maker
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.document import KbDocumentStatus, KbDocValidity
from app.models.knowledge.knowledge_base import KbEmbedStatus, ProjectKnowledgeBase
from app.schemas.knowledge.search import (
    KbSearchData,
    KbSearchDegraded,
    KbSearchHit,
)
from app.services.knowledge import embed_binding, vector_cache

logger = logging.getLogger(__name__)

# —— 锁定常量（任务拆解冻结） ——
RECALL_K = 30  # 每路召回条数
RRF_K = 60  # RRF 平滑常数
SAME_DOC_CAP = 3  # 单文档进入 top_k 的命中上限
CONTEXT_TOKEN_BUDGET = 8_000  # 父块扩展后的总 token 封顶
RERANK_CANDIDATES = 20  # 深度模式 listwise 重排候选数
RERANK_SNIPPET_CHARS = 300  # 重排候选片段截断
LOG_RETENTION_DAYS = 90  # 检索日志保留期
LOG_CLEANUP_MODULO = 200  # 每 N 条日志顺手清理一次过期行（免 beat 任务）

# —— 图增强检索第三路（P2 WP-C2,库级开关 settings.graph_channel 默认关） ——
GRAPH_CHANNEL_ENTITY_POOL = 2000  # 参与子串匹配的热门实体池上限
GRAPH_CHANNEL_MAX_SEEDS = 5  # 查询命中实体取前 N（按 ref_count）
GRAPH_CHANNEL_MAX_CHUNKS = 30  # 图路产出 chunk 上限


async def _vector_recall(
    db: AsyncSession,
    *,
    kb: ProjectKnowledgeBase,
    query: str,
    prefer_user_id: Optional[int],
) -> list[tuple[int, float]]:
    """向量路：库钉定配置向量化 query（带缓存/超时）→ memmap 矩阵 topk"""
    if not kb.embed_model or not kb.embed_dim:
        raise BusinessException("知识库未钉定 EMBED 模型", code=400)
    if kb.embed_status == KbEmbedStatus.INVALID.value:
        raise BusinessException("embed 配置失效（invalid）", code=400)
    qvec = await embed_binding.embed_query_cached(
        db, kb=kb, query=query, prefer_user_id=prefer_user_id
    )
    return await vector_cache.vector_topk(
        db,
        project_id=kb.project_id,
        index_version=kb.index_version,
        dim=kb.embed_dim,
        query_vec=qvec,
        k=RECALL_K,
    )


async def _fulltext_recall(
    *, project_id: int, query: str, doc_types: Optional[Sequence[str]]
) -> list[tuple[int, float]]:
    """全文路（独立会话，供 gather 并行）：≥2 字符走 ngram NL 模式，否则 LIKE 兜底"""
    async with async_session_maker() as db2:
        q = query.strip()
        if len(q) >= 2:
            return await crud_kb_chunk.fulltext_search(
                db2, project_id=project_id, query=q, limit=RECALL_K, doc_types=doc_types
            )
        return await crud_kb_chunk.like_search(
            db2, project_id=project_id, query=q, limit=RECALL_K
        )


def _rrf_fuse(
    lists: Sequence[Sequence[tuple[int, float]]], *, k: int = RRF_K
) -> list[tuple[int, float]]:
    """RRF：score(c) = Σ 1/(k + rank_i)。免调参、量纲无关、单路噪声被稀释。"""
    scores: dict[int, float] = {}
    for ranked in lists:
        for rank, (cid, _s) in enumerate(ranked):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


async def _graph_recall(
    db: AsyncSession, *, project_id: int, query: str
) -> list[tuple[int, float]]:
    """图增强第三路（P2 WP-C2）：查询串包含实体名 → 1-hop 邻居 → mention 关联 chunk。

    排序键 = (命中种子实体数 DESC, 关联实体 ref_count 合计 DESC)——直接提及查询
    实体的块排在仅邻居提及的块之前。增强路无损降级：调用方 try/except，
    失败/空图/无命中一律返回空列表，不进 degraded 标志。
    """
    from app.crud.knowledge.graph import crud_kb_graph
    from app.models.knowledge.graph import KbEntityMention

    q = query.strip()
    if len(q) < 2:
        return []
    pool = await crud_kb_graph.list_popular_entities(
        db, project_id=project_id, limit=GRAPH_CHANNEL_ENTITY_POOL
    )
    if not pool:
        return []
    matched = [e for e in pool if len(e.name) >= 2 and e.name in q]
    if not matched:
        return []
    matched.sort(key=lambda e: (-(e.ref_count or 0), e.id))
    seeds = matched[:GRAPH_CHANNEL_MAX_SEEDS]
    seed_ids = {e.id for e in seeds}

    entity_ids = set(seed_ids)
    rels = await crud_kb_graph.list_relations_touching(
        db, project_id=project_id, entity_ids=list(seed_ids)
    )
    for r in rels:
        entity_ids.add(r.source_entity_id)
        entity_ids.add(r.target_entity_id)

    rows = (
        await db.execute(
            select(KbEntityMention.chunk_id, KbEntityMention.entity_id).where(
                KbEntityMention.project_id == project_id,
                KbEntityMention.entity_id.in_(entity_ids),
                KbEntityMention.chunk_id > 0,
            )
        )
    ).all()
    if not rows:
        return []

    ref_by_id = {e.id: (e.ref_count or 0) for e in pool}
    chunk_entities: dict[int, set[int]] = {}
    for chunk_id, entity_id in rows:
        chunk_entities.setdefault(int(chunk_id), set()).add(int(entity_id))

    scored = [
        (cid, len(eids & seed_ids), sum(ref_by_id.get(i, 0) for i in eids))
        for cid, eids in chunk_entities.items()
    ]
    scored.sort(key=lambda t: (-t[1], -t[2], t[0]))
    return [
        (cid, float(seed_hits))
        for cid, seed_hits, _w in scored[:GRAPH_CHANNEL_MAX_CHUNKS]
    ]


async def _api_rerank_channel(
    db: AsyncSession,
    *,
    user_id: Optional[int],
    query: str,
    fused: list[tuple[int, float]],
    chunk_map: dict[int, "KbChunk"],
) -> Optional[tuple[list[tuple[int, float]], bool]]:
    """RERANK 模型重排（P2 WP-C3，深度模式一级通道）。

    查询用户配置了激活的 RERANK 模型才启用（top20 候选,片段截 300 字）;
    无配置/调用失败返回 None,回退 listwise LLM。比 listwise 快 300-500ms。
    """
    if not user_id:
        return None
    try:
        from app.crud.auth.user_llm_config import crud_user_llm_config
        from app.models.auth.user_llm_config import ModelType
        from app.services.knowledge import rerank_client

        cfg = await crud_user_llm_config.get_default(
            db, user_id=user_id, model_type=ModelType.RERANK
        )
        if cfg is None or not cfg.is_active:
            return None
        cand = fused[:RERANK_CANDIDATES]
        docs = [
            (chunk_map[cid].content or "")[:RERANK_SNIPPET_CHARS]
            for cid, _ in cand
            if cid in chunk_map
        ]
        if len(docs) != len(cand):
            return None
        order = await rerank_client.api_rerank(cfg, query=query, documents=docs)
        if not order:
            return None
        reordered = [cand[i] for i in order] + fused[RERANK_CANDIDATES:]
        return reordered, True
    except Exception as exc:  # noqa: BLE001 —— 增强路失败静默回退
        logger.info("kb rerank API 通道失败(回退 listwise): %s", exc)
        return None


# ────────────────────────── 深度模式（TA3：改写 + listwise 重排，全部静默回退） ──────────────────────────

async def _deep_rewrite(text_llm, query: str) -> tuple[Optional[str], list[str]]:
    """查询改写：返回 (语义改写, 关键词)。任何失败 → (None, []) 回退原句。"""
    from app.ai_core.prompts.kb_prompts import (
        build_deep_rewrite_messages,
        parse_llm_json_loose,
    )

    try:
        resp = await asyncio.wait_for(
            text_llm.ainvoke(build_deep_rewrite_messages(query)), timeout=20
        )
        data = parse_llm_json_loose(getattr(resp, "content", ""))
        rewrite = str(data.get("rewrite") or "").strip() or None
        keywords = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:5]
        if rewrite == query.strip():
            rewrite = None
        return rewrite, keywords
    except Exception as exc:  # noqa: BLE001
        logger.info("kb deep rewrite 回退原句: %s", exc)
        return None, []


async def _listwise_rerank(
    text_llm, query: str, ordered: list[tuple[int, float]], chunk_map: dict
) -> tuple[list[tuple[int, float]], bool]:
    """LLM listwise 重排 RRF top-N。失败/超时/输出不合法 → 原序 + reranked=False。"""
    from app.ai_core.prompts.kb_prompts import build_rerank_messages, parse_llm_json_loose

    head = ordered[:RERANK_CANDIDATES]
    tail = ordered[RERANK_CANDIDATES:]
    candidates = []
    for i, (cid, _s) in enumerate(head):
        ch = chunk_map.get(cid)
        if ch is None:
            continue
        snippet = f"{ch.heading_path} | {ch.content}"[:RERANK_SNIPPET_CHARS]
        candidates.append((i, snippet))
    if len(candidates) < 2:
        return ordered, False
    try:
        resp = await asyncio.wait_for(
            text_llm.ainvoke(build_rerank_messages(query, candidates)), timeout=30
        )
        data = parse_llm_json_loose(getattr(resp, "content", ""))
        order = [int(i) for i in (data.get("order") or [])]
        valid = [i for i in order if 0 <= i < len(head)]
        if not valid:
            return ordered, False
        seen = set(valid)
        reordered = [head[i] for i in valid] + [
            h for i, h in enumerate(head) if i not in seen
        ]
        return reordered + tail, True
    except Exception as exc:  # noqa: BLE001
        logger.info("kb rerank 回退 RRF 序: %s", exc)
        return ordered, False


# ────────────────────────── 检索日志（TA1.2：反馈闭环数据底座） ──────────────────────────

async def _write_log(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: Optional[int],
    consumer: str,
    query: str,
    top_k: int,
    doc_types: Optional[Sequence[str]],
    deep: bool,
    hits: list[KbSearchHit],
    degraded: KbSearchDegraded,
    latency_ms: int,
) -> Optional[int]:
    """落检索日志；失败静默（日志永不阻断检索）。顺手按取模清理过期行。"""
    from app.models.knowledge.retrieval_log import KbRetrievalLog

    try:
        row = KbRetrievalLog(
            project_id=project_id,
            user_id=user_id,
            consumer=consumer,
            query=query.strip()[:500],
            top_k=top_k,
            doc_types=list(doc_types) if doc_types else None,
            deep=deep,
            hits=[
                {"chunk_id": h.chunk_id, "document_id": h.document_id, "score": h.score}
                for h in hits
            ],
            degraded={"vector": degraded.vector, "fulltext": degraded.fulltext},
            latency_ms=latency_ms,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        if row.id % LOG_CLEANUP_MODULO == 0:
            from datetime import datetime, timedelta

            from sqlalchemy import delete as sa_delete

            cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
            await db.execute(
                sa_delete(KbRetrievalLog).where(KbRetrievalLog.created_at < cutoff)
            )
            await db.commit()
        return row.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb 检索日志写入失败(不阻断): %s", exc)
        return None


async def search(
    db: AsyncSession,
    *,
    project_id: int,
    query: str,
    top_k: int = 10,
    doc_types: Optional[Sequence[str]] = None,
    prefer_user_id: Optional[int] = None,
    consumer: str = "search",
    deep: bool = False,
    text_llm=None,
) -> KbSearchData:
    """混合检索主入口（API /search、/answer、Chat kb_search 工具、需求页、用例生成共用）。

    deep=True 且提供 text_llm 时启用深度模式：查询改写（原句+改写双跑向量路、
    关键词并入全文 query）+ listwise 重排——每个增强环节失败都静默回退，
    深度模式永远不比快速模式更不可用。
    """
    import time

    started = time.perf_counter()
    degraded = KbSearchDegraded()
    kb = await crud_knowledge_base.get_by_project(db, project_id=project_id)
    if kb is None:
        return KbSearchData(hits=[], degraded=degraded, index_version=0)

    # ── 深度模式:查询改写（失败回退原句） ──
    rewrite: Optional[str] = None
    keywords: list[str] = []
    if deep and text_llm is not None:
        rewrite, keywords = await _deep_rewrite(text_llm, query)
    ft_query = f"{query} {' '.join(keywords)}".strip() if keywords else query

    # ── 双路并行召回（全文路独立会话；任何一路失败降级而非 502） ──
    vec_task = asyncio.create_task(
        _vector_recall(db, kb=kb, query=query, prefer_user_id=prefer_user_id)
    )
    ft_task = asyncio.create_task(
        _fulltext_recall(project_id=project_id, query=ft_query, doc_types=doc_types)
    )
    vec_res, ft_res = await asyncio.gather(vec_task, ft_task, return_exceptions=True)

    vector_hits: list[tuple[int, float]] = []
    fulltext_hits: list[tuple[int, float]] = []
    if isinstance(vec_res, Exception):
        degraded.vector = True
        logger.warning("kb search 向量路降级 project=%s: %s", project_id, vec_res)
    else:
        vector_hits = vec_res
    if isinstance(ft_res, Exception):
        degraded.fulltext = True
        logger.warning("kb search 全文路降级 project=%s: %s", project_id, ft_res)
    else:
        fulltext_hits = ft_res

    # 改写句第二路向量召回（串行——共用请求会话,且 qvec 缓存使多数情况极快）
    rewrite_hits: list[tuple[int, float]] = []
    if rewrite and not degraded.vector:
        try:
            rewrite_hits = await _vector_recall(
                db, kb=kb, query=rewrite, prefer_user_id=prefer_user_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("kb deep 改写路召回失败(忽略): %s", exc)

    # 图增强第三路（库级开关默认关;增强路无损降级——失败静默,不进 degraded）
    graph_hits: list[tuple[int, float]] = []
    if bool((kb.settings or {}).get("graph_channel")):
        try:
            graph_hits = await _graph_recall(db, project_id=project_id, query=query)
        except Exception as exc:  # noqa: BLE001
            logger.info("kb graph 路召回失败(忽略): %s", exc)
    # ── 融合：向量/改写/全文等权 RRF；图增强只补召回、绝不重排 ──
    # 图路曾以等权进 RRF，会把「邻居实体块」顶到精确命中之上（kb_eval gate 实测
    # 2 条从 #1 掉到 #2）。修正语义：图路作为纯召回补充——只把其它路都没召回到的
    # 图路块追加到融合结果尾部，永不改变已召回块的相对次序（保证 gate 回退=0，
    # 其价值 = 捞回文本/向量漏掉的关系相邻块，而非重排）。
    recall_lists: list[Sequence[tuple[int, float]]] = [vector_hits]
    if rewrite_hits:
        recall_lists.append(rewrite_hits)
    recall_lists.append(fulltext_hits)
    fused = _rrf_fuse(recall_lists)

    graph_boosted = False
    if graph_hits:
        base_ids = {cid for cid, _ in fused}
        tail_score = min((s for _, s in fused), default=1.0 / (RRF_K + 1))
        extra = [(cid, s) for cid, s in graph_hits if cid not in base_ids]
        # 追加分严格小于基集最小分且随图路名次递减 → 只落尾部、不动已有排序
        for i, (cid, _s) in enumerate(extra):
            fused.append((cid, tail_score * 0.5 / (i + 1)))
        graph_boosted = bool(extra)
    if not fused:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_id = await _write_log(
            db, project_id=project_id, user_id=prefer_user_id, consumer=consumer,
            query=query, top_k=top_k, doc_types=doc_types, deep=deep,
            hits=[], degraded=degraded, latency_ms=latency_ms,
        )
        return KbSearchData(
            hits=[], degraded=degraded, index_version=kb.index_version,
            log_id=log_id, graph_boosted=graph_boosted,
        )

    # ── 取候选块（带文档预加载），过滤 + 组装 ──
    candidate_ids = [cid for cid, _ in fused]
    chunks = await crud_kb_chunk.get_by_ids_with_doc(
        db, project_id=project_id, chunk_ids=candidate_ids
    )
    chunk_map: dict[int, KbChunk] = {c.id: c for c in chunks}
    allow_types = set(doc_types) if doc_types else None

    def _visible(ch: KbChunk) -> bool:
        doc = ch.document
        if doc is None or doc.status != KbDocumentStatus.READY.value:
            return False
        if doc.validity != KbDocValidity.EFFECTIVE.value:
            return False
        if allow_types and doc.doc_type not in allow_types:
            return False  # 向量路无 SQL 过滤，在此兜住类型过滤
        return True

    # ── 深度模式重排（三级回退:RERANK API → listwise LLM → RRF 原序） ──
    reranked = False
    if deep:
        visible_fused = [(cid, s) for cid, s in fused
                         if (c := chunk_map.get(cid)) is not None and _visible(c)]
        if len(visible_fused) >= 2:
            api_result = await _api_rerank_channel(
                db, user_id=prefer_user_id, query=query,
                fused=visible_fused, chunk_map=chunk_map,
            )
            if api_result is not None:
                fused, reranked = api_result
            elif text_llm is not None:
                visible_fused, reranked = await _listwise_rerank(
                    text_llm, query, visible_fused, chunk_map
                )
                fused = visible_fused

    # 父块预取（child 命中上卷为 parent 上下文）
    parent_ids = {
        c.parent_chunk_id
        for c in chunks
        if c.parent_chunk_id is not None and _visible(c)
    }
    parents = await crud_kb_chunk.get_by_ids(
        db, project_id=project_id, chunk_ids=list(parent_ids)
    )
    parent_map: dict[int, KbChunk] = {p.id: p for p in parents}

    # ── 区间去重：同 parent 上卷合并 / 同文档 cap / token 预算（§3#4 评审点名环节） ──
    hits: list[KbSearchHit] = []
    seen_rep: set[int] = set()
    doc_counts: dict[int, int] = {}
    tokens_used = 0

    for cid, score in fused:
        ch = chunk_map.get(cid)
        if ch is None or not _visible(ch):
            continue
        rep_key = ch.parent_chunk_id or ch.id
        if rep_key in seen_rep:
            continue  # 同 parent 的多 child 命中只保留最高名次一份
        if doc_counts.get(ch.document_id, 0) >= SAME_DOC_CAP:
            continue

        context_row = parent_map.get(ch.parent_chunk_id) if ch.parent_chunk_id else None
        content_row = context_row or ch
        tok = content_row.token_len or len(content_row.content)
        if hits and tokens_used + tok > CONTEXT_TOKEN_BUDGET:
            continue  # 预算内装不下大块，跳过继续找小块（首条不受限，保底有结果）

        doc = ch.document
        hits.append(
            KbSearchHit(
                chunk_id=ch.id,
                document_id=ch.document_id,
                doc_name=doc.file_name,
                doc_type=doc.doc_type,
                heading_path=ch.heading_path,
                seq=ch.seq,
                content=content_row.content,
                score=round(score, 6),
                source_type=doc.source_type,
                source_id=doc.source_id,
                parse_mode=doc.parse_mode,
            )
        )
        seen_rep.add(rep_key)
        doc_counts[ch.document_id] = doc_counts.get(ch.document_id, 0) + 1
        tokens_used += tok
        if len(hits) >= top_k:
            break

    latency_ms = int((time.perf_counter() - started) * 1000)
    log_id = await _write_log(
        db, project_id=project_id, user_id=prefer_user_id, consumer=consumer,
        query=query, top_k=top_k, doc_types=doc_types, deep=deep,
        hits=hits, degraded=degraded, latency_ms=latency_ms,
    )
    return KbSearchData(
        hits=hits, degraded=degraded, index_version=kb.index_version,
        log_id=log_id, reranked=reranked, graph_boosted=graph_boosted,
    )


def format_hits_for_llm(hits: Sequence[KbSearchHit]) -> str:
    """把命中格式化为带溯源头的上下文文本（Chat 工具 / /answer 合成共用）。

    形如：
        [1]《支付系统PRD》› 3 退款 › 3.2 退款时效
        用户发起退款后……
    """
    if not hits:
        return ""
    blocks: list[str] = []
    for i, h in enumerate(hits, 1):
        head = f"[{i}]《{h.doc_name}》"
        if h.heading_path:
            head += f" › {h.heading_path}"
        blocks.append(f"{head}\n{h.content}")
    return "\n\n".join(blocks)
