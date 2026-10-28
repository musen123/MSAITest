"""知识库文档入库（统一 AI 任务图，设计文档 §5 入库管线 / 任务拆解 T3.3）

图结构（5 节点）：
    load    取文档+归属校验铁律+确保 embed 已钉定+来源路由（func_doc/text 直取现成文本）
    parse   upload 源解析（md/txt 直读、docx 补表格、PDF 分片规整、图片 VLM）→ 回写 content_md
    chunk   结构感知父子块分块（chunker 纯函数）+ 软/硬红线检查
    embed   child 块批量向量化（库钉定配置 + 每批维度断言 + 指数退避重试 3 次）
    index   单事务落库：FOR UPDATE 复核存活（堵删除竞态）→ 删旧插新 → 文档 ready
            → bump_index_version 原子计数 → kb 状态翻转

失败语义：任一节点异常 → 文档 status=failed + error_message，**不打坏已 ready 的
旧版本 chunk**（旧 chunk 只在 index 事务内被替换，事务失败自动回滚）。

幂等（task_acks_late 重投安全）：index 先删后插 + uq(document_id, seq)
+ 提交去重锁（spec.dedupe），三层对齐框架纪律。
"""

import asyncio
import hashlib
from datetime import datetime
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.ai_core.llm_context import get_current_llm, get_current_vision_llm
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.llm import load_user_llms
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.knowledge import crud_kb_chunk, crud_kb_document, crud_knowledge_base
from app.db.session import async_session_maker
from app.models.knowledge.chunk import KbChunk, KbChunkType
from app.models.knowledge.document import (
    KbDocSourceType,
    KbDocument,
    KbDocumentStatus,
    KbParseMode,
)
from app.models.knowledge.knowledge_base import (
    KnowledgeBaseStatus,
    ProjectKnowledgeBase,
)
from app.services.knowledge import embed_binding
from app.services.knowledge.chunker import ChunkDraft, build_index_text, chunk_markdown
from app.services.knowledge.kb_parse_service import parse_file_for_kb

# —— 锁定常量（任务拆解冻结） ——
KB_CHUNK_SOFT_LIMIT = 10_000  # 单项目软红线：告警
KB_CHUNK_HARD_LIMIT = 20_000  # 单项目硬红线：入库报错
_EMBED_MAX_RETRY = 3
_EMBED_BACKOFF_BASE_S = 1.5
_IMAGE_EXT_SET = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_INDEX_LOCK_RETRY = 3  # index 事务死锁/锁超时重试次数（1213/1205 是并发常态）
_INDEX_LOCK_BACKOFF_S = 0.4


def _is_lock_conflict(exc: BaseException) -> bool:
    """MySQL 1213 死锁 / 1205 锁等待超时——事务已整体回滚,重试安全。

    同项目并发入库的 index 事务会在 kb_chunk uq(document_id,seq) 相邻间隙上
    互踩 gap 锁（线上实锤:两 worker 并发上传→1213）。
    """
    orig = getattr(exc, "orig", None)
    args = getattr(orig, "args", None) or ()
    return bool(args) and args[0] in (1213, 1205)


class KbIngestState(TypedDict, total=False):
    kb_document_id: int
    markdown: str
    parse_mode: str
    truncated: bool
    was_ready: bool  # 入库前文档是否已 ready（total_documents 增量判定）
    drafts: list[dict]  # ChunkDraft 序列化（LangGraph state 走 dict）
    embeddings: dict  # child draft seq -> packed bytes


async def _set_doc_status(doc_id: int, status: str, error: Optional[str] = None) -> None:
    async with async_session_maker() as db:
        doc = await crud_kb_document.get(db, doc_id)
        if doc is None or doc.status == KbDocumentStatus.DELETED.value:
            return  # 已删除的文档不再改状态（删除竞态下让位）
        doc.status = status
        if error is not None:
            doc.error_message = error[:2000]
        db.add(doc)
        await db.commit()


async def _writeback_func_bridge(doc_id: int, *, success: bool) -> None:
    """func_doc 源的桥接状态回写（kb_status 由任务事件驱动，§4.4）。best-effort。"""
    try:
        async with async_session_maker() as db:
            kb_doc = await crud_kb_document.get(db, doc_id)
            if (
                kb_doc is None
                or kb_doc.source_type != KbDocSourceType.FUNC_DOC.value
                or not kb_doc.source_id
            ):
                return
            from app.crud.func_test.document import crud_document as crud_func_doc
            from app.models.func_test.document import DocumentKbStatus

            func_doc = await crud_func_doc.get(db, kb_doc.source_id)
            if func_doc is None:
                return
            if success:
                func_doc.kb_status = DocumentKbStatus.INGESTED.value
                func_doc.kb_document_id = kb_doc.id
                func_doc.kb_ingested_at = datetime.now()
            else:
                func_doc.kb_status = DocumentKbStatus.INGEST_FAILED.value
            db.add(func_doc)
            await db.commit()
    except Exception:  # noqa: BLE001 —— 桥接回写失败不影响入库结果本身
        pass


async def _mark_failed(doc_id: int, error: str) -> None:
    await _set_doc_status(doc_id, KbDocumentStatus.FAILED.value, error)
    await _writeback_func_bridge(doc_id, success=False)


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def load(state: KbIngestState) -> dict:
        ctx.stage("加载文档", index=1, total=5)
        ctx.progress(5)
        doc_id = state["kb_document_id"]
        try:
            async with async_session_maker() as db:
                doc = await crud_kb_document.get(db, doc_id)
                if doc is None:
                    raise ValueError(f"知识库文档不存在：{doc_id}")
                # 归属校验铁律（照 generate_case.py:66 先例）
                if doc.project_id != ctx.project_id:
                    raise ValueError(f"文档不属于该项目：{doc_id}")
                if doc.status == KbDocumentStatus.DELETED.value:
                    raise ValueError("文档已被删除，取消入库")

                was_ready = doc.status == KbDocumentStatus.READY.value
                kb = await crud_knowledge_base.get_or_create(db, project_id=ctx.project_id)
                # embed 钉定兜底复查（正常在上传端点完成；直插/回灌路径兜底）
                await embed_binding.pin_on_first_ingest(db, kb=kb, user_id=ctx.user_id)

                doc.status = KbDocumentStatus.PARSING.value
                doc.error_message = None
                doc.ai_task_id = ctx.task_id
                db.add(doc)
                await db.commit()

                source_type = doc.source_type
                source_id = doc.source_id
                content_md = doc.content_md
                file_name = doc.file_name

            out: dict = {"was_ready": was_ready}
            if source_type == KbDocSourceType.FUNC_DOC.value:
                # 桥接源：直取 func 文档 AI 解析产物，零重复解析零 token
                async with async_session_maker() as db:
                    from app.crud.func_test.document import crud_document as crud_func_doc

                    func_doc = await crud_func_doc.get(db, source_id)
                    if func_doc is None or func_doc.project_id != ctx.project_id:
                        raise ValueError(f"来源功能测试文档不存在或跨项目：{source_id}")
                    if not (func_doc.parsed_content or "").strip():
                        raise ValueError("来源功能测试文档尚未解析（parsed_content 为空），请先解析")
                    out["markdown"] = func_doc.parsed_content
                    out["parse_mode"] = KbParseMode.LLM_NORMALIZED.value
                    out["truncated"] = False
                ctx.log(f"「{file_name}」来源 func_doc#{source_id}，直取解析产物（零 token）")
            elif source_type == KbDocSourceType.TEXT.value:
                if not (content_md or "").strip():
                    raise ValueError("文本文档内容为空")
                out["markdown"] = content_md
                out["parse_mode"] = KbParseMode.RAW.value
                out["truncated"] = False
                ctx.log(f"「{file_name}」纯文本直插，跳过解析")
            else:
                ctx.log(f"「{file_name}」上传文件，进入解析")
            return out
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise

    async def parse(state: KbIngestState) -> dict:
        ctx.stage("解析文档", index=2, total=5)
        ctx.progress(18)
        doc_id = state["kb_document_id"]
        try:
            markdown = state.get("markdown")
            parse_mode = state.get("parse_mode")
            truncated = bool(state.get("truncated"))

            if not markdown:
                async with async_session_maker() as db:
                    doc = await crud_kb_document.get(db, doc_id)
                    storage_key, file_ext, file_name = doc.storage_key, doc.file_ext, doc.file_name
                if not storage_key:
                    raise ValueError("文档缺少原件（storage_key 为空），无法解析——请重新上传")

                ext = file_ext.lower() if file_ext.startswith(".") else f".{file_ext.lower()}"
                vision_llm = None
                if ext in _IMAGE_EXT_SET:
                    # 图片按需加载提交者 VISION（照 parse_document.py 节点内加载先例）
                    await load_user_llms(ctx.user_id, kind="vision")
                    vision_llm = get_current_vision_llm()
                    ctx.log("图片文档，调用视觉模型识别")
                elif ext in (".pdf", ".doc", ".docx"):
                    # 内嵌图片按需加载（未配置 → 优雅降级为纯文本，不阻断解析）
                    try:
                        await load_user_llms(ctx.user_id, kind="vision")
                        vision_llm = get_current_vision_llm()
                    except Exception:  # noqa: BLE001
                        ctx.log(
                            "未配置 VISION 模型，文档内嵌图片将跳过", level="warning"
                        )

                async def on_slice(done: int, total: int) -> None:
                    ctx.progress(18 + int(20 * done / max(total, 1)))
                    ctx.log(f"PDF 规整分片 {done}/{total}")

                scanned_pdf = bool(params.get("scanned_pdf"))
                if scanned_pdf:
                    ctx.log("扫描件解析已开启（逐页 VLM 转写）")
                result = await parse_file_for_kb(
                    storage_key=storage_key,
                    file_ext=file_ext,
                    file_name=file_name,
                    text_llm=get_current_llm(),
                    vision_llm=vision_llm,
                    scanned_pdf=scanned_pdf,
                    on_slice=on_slice,
                )
                markdown, parse_mode, truncated = result.markdown, result.parse_mode, result.truncated
                if result.media_note:
                    ctx.log(f"内嵌图片：{result.media_note}")
                if truncated:
                    ctx.log(f"⚠ 文档超长已截断至 {len(markdown)} 字符（truncated 标记用户可见）")

            content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            async with async_session_maker() as db:
                doc = await crud_kb_document.get(db, doc_id)
                if doc is None or doc.status == KbDocumentStatus.DELETED.value:
                    raise ValueError("文档已被删除，取消入库")
                doc.content_md = markdown
                doc.content_hash = content_hash
                doc.parse_mode = parse_mode
                doc.truncated = truncated
                doc.status = KbDocumentStatus.CHUNKING.value
                db.add(doc)
                await db.commit()

            ctx.log(f"解析完成：{len(markdown)} 字符，parse_mode={parse_mode}")
            return {"markdown": markdown, "parse_mode": parse_mode, "truncated": truncated}
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise

    async def chunk(state: KbIngestState) -> dict:
        ctx.stage("结构感知分块", index=3, total=5)
        ctx.progress(42)
        doc_id = state["kb_document_id"]
        try:
            async with async_session_maker() as db:
                doc = await crud_kb_document.get(db, doc_id)
                doc_type = doc.doc_type if doc else "other"
                old_total = await crud_kb_chunk.count_by_project(db, project_id=ctx.project_id)
                old_doc_chunks = doc.chunk_count if doc else 0

            drafts = chunk_markdown(state["markdown"], doc_type=doc_type)
            if not drafts:
                raise ValueError("分块结果为空（解析产物无有效内容）")

            projected = old_total - old_doc_chunks + len(drafts)
            if projected > KB_CHUNK_HARD_LIMIT:
                raise ValueError(
                    f"入库后项目 chunk 总量将达 {projected}，超过硬红线 {KB_CHUNK_HARD_LIMIT}"
                    "——请归档清理旧文档，或联系管理员评估 P2 规模方案"
                )
            if projected > KB_CHUNK_SOFT_LIMIT:
                ctx.log(f"⚠ 项目 chunk 总量将达 {projected}（软红线 {KB_CHUNK_SOFT_LIMIT}），建议关注规模")

            parents = sum(1 for d in drafts if d.chunk_type == KbChunkType.PARENT.value)
            ctx.log(f"分块完成：{len(drafts)} 块（parent {parents} / child {len(drafts) - parents}）")
            await _set_doc_status(doc_id, KbDocumentStatus.EMBEDDING.value)
            return {"drafts": [d.__dict__ for d in drafts]}
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise

    async def embed(state: KbIngestState) -> dict:
        ctx.stage("向量化", index=4, total=5)
        ctx.progress(50)
        doc_id = state["kb_document_id"]
        try:
            drafts = [ChunkDraft(**d) for d in state["drafts"]]
            children = [d for d in drafts if d.chunk_type != KbChunkType.PARENT.value]
            texts = [build_index_text(d.heading_path, d.content) for d in children]

            async with async_session_maker() as db:
                kb = await crud_knowledge_base.get_by_project(db, project_id=ctx.project_id)
                embedder = await embed_binding.resolve_embedder(
                    db, kb=kb, prefer_user_id=ctx.user_id
                )

                embeddings: dict[int, bytes] = {}
                batch_size = embed_binding.KB_EMBED_BATCH_SIZE
                total_batches = (len(texts) + batch_size - 1) // batch_size
                for bi in range(total_batches):
                    batch = texts[bi * batch_size : (bi + 1) * batch_size]
                    last_exc: Optional[Exception] = None
                    for attempt in range(_EMBED_MAX_RETRY):
                        try:
                            blobs = await embedder.embed_texts(batch)
                            last_exc = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            from app.core.exceptions import BusinessException

                            if isinstance(exc, BusinessException):
                                raise  # 维度断言/配置失效不重试，fail-fast
                            last_exc = exc
                            wait = _EMBED_BACKOFF_BASE_S ** (attempt + 1)
                            ctx.log(f"embedding 批 {bi + 1}/{total_batches} 失败重试 {attempt + 1}/{_EMBED_MAX_RETRY}（{wait:.1f}s 后）：{exc}")
                            await asyncio.sleep(wait)
                    if last_exc is not None:
                        raise ValueError(f"embedding 批量调用连续 {_EMBED_MAX_RETRY} 次失败：{last_exc}") from last_exc
                    for j, blob in enumerate(blobs):
                        embeddings[children[bi * batch_size + j].seq] = blob
                    ctx.progress(50 + int(38 * (bi + 1) / total_batches))

            ctx.log(f"向量化完成：{len(embeddings)} 个 child 块（批大小 {batch_size}）")
            return {"embeddings": embeddings}
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise

    async def index(state: KbIngestState) -> dict:
        ctx.stage("落库建索引", index=5, total=5)
        ctx.progress(90)
        doc_id = state["kb_document_id"]
        try:
            drafts = [ChunkDraft(**d) for d in state["drafts"]]
            embeddings: dict[int, bytes] = state.get("embeddings", {})

            deleted_mid_flight = False
            for lock_attempt in range(_INDEX_LOCK_RETRY):
                try:
                    async with async_session_maker() as db:
                        # 单事务：FOR UPDATE 复核存活（用户删文档/清库与在途任务的竞态，§6.1）
                        doc = (
                            await db.execute(
                                select(KbDocument)
                                .where(KbDocument.id == doc_id)
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if doc is None or doc.status == KbDocumentStatus.DELETED.value:
                            deleted_mid_flight = True
                            break

                        # 项目级写序列化（统一 doc→kb 加锁序）：同项目并发入库先在
                        # kb 行排队,再进 kb_chunk 删插——否则两事务在 uq(document_id,
                        # seq) 相邻间隙互踩 gap 锁,MySQL 1213（并发上传线上实锤）
                        await db.execute(
                            select(ProjectKnowledgeBase)
                            .where(ProjectKnowledgeBase.project_id == ctx.project_id)
                            .with_for_update()
                        )

                        old_count = await crud_kb_chunk.delete_by_document(
                            db, document_id=doc_id
                        )

                        # 先插 parent 拿 id，再回填 child.parent_chunk_id
                        seq_to_row: dict[int, KbChunk] = {}
                        parent_rows = []
                        for d in drafts:
                            if d.chunk_type == KbChunkType.PARENT.value:
                                row = KbChunk(
                                    project_id=ctx.project_id,
                                    document_id=doc_id,
                                    seq=d.seq,
                                    chunk_type=d.chunk_type,
                                    heading_path=d.heading_path,
                                    content=d.content,
                                    char_len=d.char_len,
                                    token_len=d.token_len,
                                    content_hash=d.content_hash,
                                    embedding=None,
                                )
                                seq_to_row[d.seq] = row
                                parent_rows.append(row)
                        if parent_rows:
                            await crud_kb_chunk.bulk_add(db, chunks=parent_rows)

                        child_rows = []
                        for d in drafts:
                            if d.chunk_type == KbChunkType.PARENT.value:
                                continue
                            parent_row = (
                                seq_to_row.get(d.parent_seq)
                                if d.parent_seq is not None
                                else None
                            )
                            child_rows.append(
                                KbChunk(
                                    project_id=ctx.project_id,
                                    document_id=doc_id,
                                    seq=d.seq,
                                    chunk_type=d.chunk_type,
                                    heading_path=d.heading_path,
                                    content=d.content,
                                    char_len=d.char_len,
                                    token_len=d.token_len,
                                    content_hash=d.content_hash,
                                    parent_chunk_id=parent_row.id if parent_row else None,
                                    embedding=embeddings.get(d.seq),
                                )
                            )
                        if child_rows:
                            await crud_kb_chunk.bulk_add(db, chunks=child_rows)

                        doc.status = KbDocumentStatus.READY.value
                        doc.chunk_count = len(drafts)
                        doc.error_message = None
                        doc.processed_at = datetime.now()
                        db.add(doc)

                        await crud_knowledge_base.bump_index_version(
                            db,
                            project_id=ctx.project_id,
                            delta_chunks=len(drafts) - old_count,
                            delta_documents=0 if state.get("was_ready") else 1,
                        )
                        kb = await crud_knowledge_base.get_by_project(
                            db, project_id=ctx.project_id
                        )
                        if kb and kb.status in (
                            KnowledgeBaseStatus.EMPTY.value,
                            KnowledgeBaseStatus.ERROR.value,
                        ):
                            kb.status = KnowledgeBaseStatus.READY.value
                            kb.last_built_at = datetime.now()
                            db.add(kb)
                        await db.commit()
                    break  # 事务成功
                except OperationalError as exc:
                    if (
                        lock_attempt < _INDEX_LOCK_RETRY - 1
                        and _is_lock_conflict(exc)
                    ):
                        wait = _INDEX_LOCK_BACKOFF_S * (lock_attempt + 1)
                        ctx.log(
                            f"落库遇数据库锁冲突（死锁/锁超时,并发入库常态），"
                            f"{wait:.1f}s 后重试 {lock_attempt + 1}/{_INDEX_LOCK_RETRY - 1}"
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise

            if deleted_mid_flight:
                ctx.log("文档已在入库期间被删除，放弃落库（不产生幽灵 chunk）")
                ctx.set_result(
                    summary={"metrics": [{"label": "结果", "value": "已删除，跳过落库"}]},
                    ref={"kind": "kb_document", "doc_id": doc_id},
                )
                return {}

            await _writeback_func_bridge(doc_id, success=True)

            # 图谱自动派发（P1b TB2.5）：commit 之后、try/except 全吞——派发失败
            # 不影响入库结果;回灌路径传 auto_extract=False 抑制（避免切换日集中烧 token）
            if params.get("auto_extract", True):
                try:
                    from app.services.knowledge import graph_extract

                    async with async_session_maker() as db:
                        doc_row = await crud_kb_document.get(db, doc_id)
                        if doc_row is not None:
                            extract_task_id = await graph_extract.auto_dispatch_after_ingest(
                                db,
                                project_id=ctx.project_id,
                                user_id=ctx.user_id,
                                doc=doc_row,
                            )
                            if extract_task_id:
                                ctx.log(f"已自动派发图谱抽取任务 #{extract_task_id}")
                except Exception as exc:  # noqa: BLE001
                    ctx.log(f"图谱抽取派发失败（不影响入库）：{exc}", level="warning")

            parents = sum(1 for d in drafts if d.chunk_type == KbChunkType.PARENT.value)
            ctx.progress(100)
            ctx.set_result(
                summary={
                    "metrics": [
                        {"label": "分块数", "value": len(drafts), "highlight": True},
                        {"label": "父块/子块", "value": f"{parents}/{len(drafts) - parents}"},
                        {"label": "解析模式", "value": state.get("parse_mode", "-")},
                        {"label": "截断", "value": "是" if state.get("truncated") else "否"},
                    ],
                    "chunks": len(drafts),
                },
                ref={"kind": "kb_document", "doc_id": doc_id},
            )
            return {}
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise

    graph = StateGraph(KbIngestState)
    graph.add_node("load", load)
    graph.add_node("parse", parse)
    graph.add_node("chunk", chunk)
    graph.add_node("embed", embed)
    graph.add_node("index", index)
    graph.add_edge(START, "load")
    graph.add_edge("load", "parse")
    graph.add_edge("parse", "chunk")
    graph.add_edge("chunk", "embed")
    graph.add_edge("embed", "index")
    graph.add_edge("index", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {"kb_document_id": int(params["kb_document_id"])}


def title(params: dict) -> str:
    name = params.get("file_name")
    return f"知识库入库：{name}" if name else "知识库入库"


register(
    TaskSpec(
        task_type="kb_ingest",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",  # PDF 规整用；图片在节点内按需加载 vision；embedding 由库钉定配置节点内自建
        dedupe=True,
    )
)
