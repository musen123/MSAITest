"""知识图谱抽取（统一 AI 任务图，P1b WP-B2）

图结构（4 节点，与 kb_ingest 完全解耦——失败隔离铁律）：
    load      文档归属/ready 校验 + graph_source_hash 短路（内容未变直接 skipped）
              + child chunk 分批打包（~3000 字/批）
    extract   提交者 TEXT 模型逐批抽取（10 类受控词表 prompt-JSON，禁
              with_structured_output;批失败重试 1 次再跳过;单文档 ≤200 实体截停）
    resolve   单事务落库（graph_extract.resolve_and_persist:清旧台账→墓碑/重定向/
              保护位 resolve→mention→recount→孤儿 GC）
    finalize  total_nodes/edges 重算 + graph_status=extracted + hash/entity_count
              回写 + 1 万实体软红线告警

失败语义：任一节点异常 → 文档 graph_status=failed,**主 status 与 chunk 不受任何
影响**（检索照常）。部分批失败仍算 extracted;全部批失败按整体失败处理。
幂等：resolve 先清本文档旧 mention 再落新（重投/重抽=替换,不累积）+ 提交去重锁。
"""

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.ai_core.llm_context import get_current_llm
from app.ai_core.prompts.kb_prompts import (
    build_kb_extract_messages,
    parse_llm_json_loose,
)
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.knowledge import crud_kb_document
from app.crud.knowledge.graph import crud_kb_graph
from app.db.session import async_session_maker
from app.models.knowledge.chunk import KbChunk, KbChunkType
from app.models.knowledge.document import KbDocumentStatus
from app.models.knowledge.graph import KbGraphStatus
from app.services.knowledge import graph_extract as gx


class KbExtractState(TypedDict, total=False):
    kb_document_id: int
    skipped: bool  # hash 未变短路（后续节点全部直通）
    doc_type: str
    source_hash: str
    batches: list[list[dict]]  # [[{id, text}...] ...]
    entity_aggs: dict  # norm -> {name,type,description,chunk_ids(list)}
    relation_aggs: list  # [{source,target,keywords,description,chunk_ids(list)}]
    failed_batches: int
    total_batches: int
    stats: dict


async def _mark_graph_failed(doc_id: int) -> None:
    """抽取失败只落 graph_status=failed——不碰主 status/error_message（隔离铁律）"""
    try:
        async with async_session_maker() as db:
            doc = await crud_kb_document.get(db, doc_id)
            if doc is None or doc.status == KbDocumentStatus.DELETED.value:
                return
            doc.graph_status = KbGraphStatus.FAILED.value
            db.add(doc)
            await db.commit()
    except Exception:  # noqa: BLE001 —— 状态回写失败不掩盖原始异常
        pass


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def load(state: KbExtractState) -> dict:
        ctx.stage("加载与分批", index=1, total=4)
        ctx.progress(5)
        doc_id = state["kb_document_id"]
        try:
            async with async_session_maker() as db:
                doc = await crud_kb_document.get(db, doc_id)
                if doc is None:
                    raise ValueError(f"知识库文档不存在：{doc_id}")
                if doc.project_id != ctx.project_id:
                    raise ValueError(f"文档不属于该项目：{doc_id}")
                if doc.status != KbDocumentStatus.READY.value:
                    raise ValueError(
                        f"文档尚未入库完成（status={doc.status}），无法抽取图谱"
                    )
                if not (doc.content_md or "").strip():
                    raise ValueError("文档 content_md 为空，无法抽取")

                source_hash = gx.source_hash_of(doc.content_md)
                if (
                    doc.graph_status == KbGraphStatus.EXTRACTED.value
                    and doc.graph_source_hash == source_hash
                ):
                    ctx.log("内容未变化（hash 命中），跳过重复抽取")
                    ctx.progress(100)
                    ctx.set_result(
                        summary={
                            "metrics": [
                                {"label": "结果", "value": "内容未变，跳过", "highlight": True},
                                {"label": "实体贡献", "value": doc.entity_count},
                            ]
                        },
                        ref={"kind": "kb_document", "doc_id": doc_id},
                    )
                    return {"skipped": True}

                doc.graph_status = KbGraphStatus.EXTRACTING.value
                doc.graph_task_id = ctx.task_id
                db.add(doc)
                await db.commit()
                doc_type = doc.doc_type
                file_name = doc.file_name

                rows = (
                    await db.execute(
                        select(KbChunk.id, KbChunk.heading_path, KbChunk.content)
                        .where(
                            KbChunk.document_id == doc_id,
                            KbChunk.chunk_type != KbChunkType.PARENT.value,
                        )
                        .order_by(KbChunk.seq)
                    )
                ).all()

            batches: list[list[dict]] = []
            cur: list[dict] = []
            cur_len = 0
            for cid, heading, content in rows:
                text = (content or "")[: gx.CHUNK_PROMPT_MAX_CHARS]
                piece = f"[{heading}]\n{text}" if heading else text
                if cur and cur_len + len(piece) > gx.BATCH_TARGET_CHARS:
                    batches.append(cur)
                    cur, cur_len = [], 0
                cur.append({"id": cid, "text": piece})
                cur_len += len(piece)
            if cur:
                batches.append(cur)

            ctx.log(f"「{file_name}」共 {len(rows)} 块 → {len(batches)} 批")
            return {
                "doc_type": doc_type,
                "source_hash": source_hash,
                "batches": batches,
                "total_batches": len(batches),
            }
        except Exception:
            await _mark_graph_failed(doc_id)
            raise

    async def extract(state: KbExtractState) -> dict:
        if state.get("skipped"):
            return {}
        ctx.stage("LLM 抽取", index=2, total=4)
        ctx.progress(15)
        doc_id = state["kb_document_id"]
        try:
            llm = get_current_llm()
            if llm is None:
                raise ValueError("未加载 TEXT 模型，无法抽取（请配置文本模型后重试）")

            batches = state.get("batches") or []
            doc_type = state.get("doc_type") or "other"
            entity_aggs: dict[str, dict] = {}
            relation_aggs: dict[tuple[str, str], dict] = {}
            failed = 0
            succeeded = 0

            for bi, batch in enumerate(batches):
                if len(entity_aggs) >= gx.DOC_MAX_ENTITIES:
                    ctx.log(
                        f"⚠ 实体数已达单文档上限 {gx.DOC_MAX_ENTITIES}，"
                        f"剩余 {len(batches) - bi} 批不再抽取"
                    )
                    break
                batch_text = "\n\n".join(c["text"] for c in batch)
                payload: Optional[dict] = None
                for attempt in range(2):  # 失败重试 1 次（冻结规则）
                    try:
                        resp = await llm.ainvoke(
                            build_kb_extract_messages(batch_text, doc_type)
                        )
                        payload = parse_llm_json_loose(getattr(resp, "content", resp))
                        break
                    except Exception as exc:  # noqa: BLE001
                        if attempt == 0:
                            ctx.log(f"批 {bi + 1}/{len(batches)} 解析失败，重试：{exc}")
                if payload is None:
                    failed += 1
                    ctx.log(f"⚠ 批 {bi + 1}/{len(batches)} 连续失败，跳过（部分成功仍算完成）")
                    continue

                ents, rels = gx.validate_batch_payload(
                    payload, known_norms=set(entity_aggs)
                )
                gx.merge_entity_aggs(entity_aggs, ents, batch)
                gx.merge_relation_aggs(relation_aggs, rels, entity_aggs, batch)
                succeeded += 1
                ctx.log(
                    f"批 {bi + 1}/{len(batches)}：实体 +{len(ents)} 关系 +{len(rels)}"
                    f"（累计 {len(entity_aggs)}/{len(relation_aggs)}）"
                )
                ctx.progress(15 + int(55 * (bi + 1) / max(len(batches), 1)))

            if batches and succeeded == 0:
                raise ValueError(f"全部 {len(batches)} 批抽取失败，请检查文本模型后重试")

            # LangGraph state 走可序列化结构：set→list、tuple 键→字段
            ea = {
                norm: {**agg, "chunk_ids": sorted(agg["chunk_ids"])}
                for norm, agg in entity_aggs.items()
            }
            ra = [
                {
                    "source": s,
                    "target": t,
                    "keywords": agg["keywords"],
                    "description": agg["description"],
                    "chunk_ids": sorted(agg["chunk_ids"]),
                }
                for (s, t), agg in relation_aggs.items()
            ]
            return {"entity_aggs": ea, "relation_aggs": ra, "failed_batches": failed}
        except Exception:
            await _mark_graph_failed(doc_id)
            raise

    async def resolve(state: KbExtractState) -> dict:
        if state.get("skipped"):
            return {}
        ctx.stage("实体消解落库", index=3, total=4)
        ctx.progress(75)
        doc_id = state["kb_document_id"]
        try:
            entity_aggs = {
                norm: {**agg, "chunk_ids": set(agg["chunk_ids"])}
                for norm, agg in (state.get("entity_aggs") or {}).items()
            }
            relation_aggs = {
                (r["source"], r["target"]): {
                    "keywords": r["keywords"],
                    "description": r["description"],
                    "chunk_ids": set(r["chunk_ids"]),
                }
                for r in (state.get("relation_aggs") or [])
            }
            async with async_session_maker() as db:
                stats = await gx.resolve_and_persist(
                    db,
                    project_id=ctx.project_id,
                    document_id=doc_id,
                    entity_aggs=entity_aggs,
                    relation_aggs=relation_aggs,
                )
                await db.commit()
            ctx.log(
                f"落库：实体 {stats['entities']}（新建 {stats['created']}"
                f"/更新 {stats['updated']}/仅出处 {stats['mention_only']}"
                f"/墓碑拦 {stats['tombstone_skipped']}），关系 {stats['relations']}"
                f"，GC {stats['gc_entities']}+{stats['gc_relations']}"
            )
            return {"stats": stats}
        except Exception:
            await _mark_graph_failed(doc_id)
            raise

    async def finalize(state: KbExtractState) -> dict:
        if state.get("skipped"):
            return {}
        ctx.stage("统计收口", index=4, total=4)
        ctx.progress(92)
        doc_id = state["kb_document_id"]
        try:
            stats = state.get("stats") or {}
            async with async_session_maker() as db:
                nodes, edges = await crud_kb_graph.recount_totals(
                    db, project_id=ctx.project_id
                )
                doc = await crud_kb_document.get(db, doc_id)
                if doc is not None and doc.status != KbDocumentStatus.DELETED.value:
                    doc.graph_status = KbGraphStatus.EXTRACTED.value
                    doc.graph_source_hash = state.get("source_hash")
                    doc.entity_count = int(stats.get("entities") or 0)
                    db.add(doc)
                await db.commit()

            if nodes > gx.NODES_SOFT_LIMIT:
                ctx.log(f"⚠ 项目实体总数 {nodes} 超软红线 {gx.NODES_SOFT_LIMIT}，建议人工修编/清理")
            failed_batches = int(state.get("failed_batches") or 0)
            if failed_batches:
                ctx.log(f"⚠ {failed_batches} 批抽取失败被跳过（部分成功口径）", level="warning")

            ctx.progress(100)
            ctx.set_result(
                summary={
                    "metrics": [
                        {"label": "文档实体", "value": stats.get("entities", 0), "highlight": True},
                        {"label": "新建/更新", "value": f"{stats.get('created', 0)}/{stats.get('updated', 0)}"},
                        {"label": "关系", "value": stats.get("relations", 0)},
                        {
                            "label": "失败批",
                            "value": failed_batches,
                            "color": "warning" if failed_batches else None,
                        },
                        {"label": "项目图谱", "value": f"{nodes} 点 / {edges} 边"},
                    ],
                    **stats,
                },
                ref={"kind": "kb_document", "doc_id": doc_id},
            )
            return {}
        except Exception:
            await _mark_graph_failed(doc_id)
            raise

    graph = StateGraph(KbExtractState)
    graph.add_node("load", load)
    graph.add_node("extract", extract)
    graph.add_node("resolve", resolve)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "load")
    graph.add_edge("load", "extract")
    graph.add_edge("extract", "resolve")
    graph.add_edge("resolve", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {"kb_document_id": int(params["kb_document_id"])}


def title(params: dict) -> str:
    name = params.get("file_name")
    return f"图谱抽取：{name}" if name else "知识图谱抽取"


register(
    TaskSpec(
        task_type="kb_extract",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",  # 提交者 TEXT 模型（抽取产物是文本三元组，无同空间约束）
        dedupe=True,
    )
)
