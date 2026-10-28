"""项目知识库服务（自研版，设计文档《知识库自研-总体设计方案》）

自研后的职责边界：
  - 上传/插文本 = 原件落 storage（可重建性根基，修掉旧版原件不落地的债）
    → 建 kb_document → embed 首绑（趁早失败，不浪费任务队列）→ 提交 kb_ingest 任务
  - 删除/清空 = 单事务「置 deleted + 取消在途任务 + 物理删 chunk + bump 原子计数」
    ——堵「删除 vs 在途入库」竞态（§6.1）
  - 统计 = 本地真实口径重算（终结 LightRAG 时代全局求和错账）

LightRAG 已随 P1b 全面下线（代理/客户端/配置项均已删除），知识库全自研。
"""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.runtime import event_bus
from app.core.exceptions import BusinessException
from app.crud.knowledge import crud_kb_chunk, crud_kb_document, crud_knowledge_base
from app.models.knowledge.document import (
    KbDocSourceType,
    KbDocType,
    KbDocument,
    KbDocumentStatus,
    KbDocValidity,
)
from app.models.knowledge.knowledge_base import (
    KnowledgeBaseStatus,
    ProjectKnowledgeBase,
)
from app.services.knowledge import embed_binding
from app.utils.storage_utils import save_bytes

# 知识库可解析格式（与 kb_parse_service 路由能力对齐；xls/ppt 能传不能解析的
# 旧坑在入口就拦掉）
KB_ALLOWED_EXTS = {
    ".pdf", ".doc", ".docx", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
}
KB_DOC_TYPES = {t.value for t in KbDocType}


async def ensure_knowledge_base(
    db: AsyncSession, *, project_id: int
) -> ProjectKnowledgeBase:
    return await crud_knowledge_base.get_or_create(db, project_id=project_id)


def _build_storage_key(project_id: int, file_ext: str) -> str:
    now = datetime.now()
    ext = file_ext if file_ext.startswith(".") else f".{file_ext}"
    return f"projects/{project_id}/kb/{now.year}/{now.month:02d}/{uuid.uuid4().hex}{ext}"


def _norm_doc_type(doc_type: str | None) -> str:
    dt = (doc_type or "").strip().lower()
    return dt if dt in KB_DOC_TYPES else KbDocType.OTHER.value


async def _submit_ingest(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    doc: KbDocument,
    auto_extract: bool = True,
    scanned_pdf: bool = False,
) -> int:
    """提交 kb_ingest 统一任务（复用平台六步提交模式），返回 ai_task_id。

    投递失败时文档标 failed（补偿），用户可重试。
    auto_extract=False 抑制入库后的图谱自动派发（回灌路径专用，P1b TB2.5）。
    scanned_pdf=True 对无文本层 PDF 走逐页 VLM 转写（显式开关，成本高）。
    """
    from app.ai_core.chat_agent.tools.base import submit_unified_task

    async def compensate(db_: AsyncSession) -> None:
        await crud_kb_document.update_status(
            db_, doc=doc, status=KbDocumentStatus.FAILED.value,
            error_message="任务投递失败（broker 不可用），请重试",
        )

    result = await submit_unified_task(
        db,
        project_id=project_id,
        user_id=user_id,
        task_type="kb_ingest",
        biz_ref_type="kb_document",
        biz_ref_id=doc.id,
        title=f"知识库入库：{doc.file_name}",
        input_params={
            "kb_document_id": doc.id,
            "file_name": doc.file_name,
            "auto_extract": auto_extract,
            "scanned_pdf": scanned_pdf,
        },
        compensate=compensate,
    )
    if not result.get("ok"):
        # 同文档已有进行中任务（幂等语义）：直接返回既有任务
        existing_id = result.get("ai_task_id")
        if existing_id:
            return int(existing_id)
        raise BusinessException(result.get("error") or "任务提交失败", code=400)

    task_id = int(result["ai_task_id"])
    doc.ai_task_id = task_id
    db.add(doc)
    await db.commit()
    # updated_at 是 SQL 表达式 onupdate（服务端算值），flush 后被标过期——
    # expire_on_commit=False 不覆盖这种逐属性过期。不 refresh 的话，端点随后
    # model_validate(doc) 的同步 getattr 会在异步引擎上触发懒加载 → MissingGreenlet 500
    await db.refresh(doc)
    return task_id


async def upload_document_to_kb(
    db: AsyncSession,
    *,
    project_id: int,
    file_content: bytes,
    file_name: str,
    file_ext: str,
    file_size: int,
    content_type: str,  # 兼容旧签名，自研解析按扩展名路由
    uploaded_by: int,
    doc_type: str | None = None,
) -> tuple[KbDocument, int]:
    """上传文档入库：落 storage → 建行 → embed 首绑 → 提交 kb_ingest。

    返回 (doc, ai_task_id)。
    """
    ext = file_ext.lower() if file_ext.startswith(".") else f".{file_ext.lower()}"
    if ext not in KB_ALLOWED_EXTS:
        raise BusinessException(
            f"知识库暂不支持 {ext} 格式（支持：{'/'.join(sorted(e.lstrip('.') for e in KB_ALLOWED_EXTS))}）",
            code=400,
        )
    if not file_content:
        raise BusinessException("上传文件为空", code=400)

    kb = await ensure_knowledge_base(db, project_id=project_id)
    # embed 首绑前置：未配 EMBED 模型在这里就 400，不产生半途文档行
    await embed_binding.pin_on_first_ingest(db, kb=kb, user_id=uploaded_by)

    # 内容级幂等（双击双传线上实锤）：同项目同原始字节指纹的未删除文档直接复用。
    # 指纹先落原始字节 sha256（provisional），parse 节点会覆写为 sha256(content_md)
    # ——双击窗口内（parse 前）全格式命中；md/txt 长期也基本命中（raw≈content_md）
    # 双击/并行同传的 TOCTOU 竞态:hash 查重与建行之间必须持有项目级锁
    # （kb 行 FOR UPDATE,与入库 index 事务同一把锁;crud.create 的 commit 即释放）
    await db.execute(
        select(ProjectKnowledgeBase)
        .where(ProjectKnowledgeBase.project_id == project_id)
        .with_for_update()
    )
    raw_hash = hashlib.sha256(file_content).hexdigest()
    existing = await crud_kb_document.get_by_content_hash(
        db, project_id=project_id, content_hash=raw_hash
    )
    if existing is not None:
        return await _reuse_existing_doc(
            db, project_id=project_id, user_id=uploaded_by, doc=existing
        )

    storage_key = _build_storage_key(project_id, ext)
    save_bytes(file_content, storage_key)

    doc = await crud_kb_document.create(
        db,
        project_id=project_id,
        file_name=file_name,
        file_size=file_size,
        file_ext=ext,
        uploaded_by=uploaded_by,
        storage_key=storage_key,
        doc_type=_norm_doc_type(doc_type),
        source_type=KbDocSourceType.UPLOAD.value,
        content_hash=raw_hash,
        status=KbDocumentStatus.PENDING.value,
    )
    task_id = await _submit_ingest(db, project_id=project_id, user_id=uploaded_by, doc=doc)
    return doc, task_id


async def _reuse_existing_doc(
    db: AsyncSession, *, project_id: int, user_id: int, doc: KbDocument
) -> tuple[KbDocument, int]:
    """幂等复用已存在的同内容文档：failed 行顺手重提任务,其余返回既有任务。"""
    if doc.status == KbDocumentStatus.FAILED.value:
        doc.status = KbDocumentStatus.PENDING.value
        doc.error_message = None
        db.add(doc)
        await db.commit()
        task_id = await _submit_ingest(db, project_id=project_id, user_id=user_id, doc=doc)
        return doc, task_id
    if doc.ai_task_id:
        return doc, doc.ai_task_id
    task_id = await _submit_ingest(db, project_id=project_id, user_id=user_id, doc=doc)
    return doc, task_id


async def insert_text_to_kb(
    db: AsyncSession,
    *,
    project_id: int,
    title: str,
    content: str,
    uploaded_by: int,
    doc_type: str | None = None,
) -> tuple[KbDocument, int]:
    """纯文本直插：content 即 content_md（parse 节点跳过），统一走 kb_ingest 单管线"""
    if not (content or "").strip():
        raise BusinessException("文本内容为空", code=400)

    kb = await ensure_knowledge_base(db, project_id=project_id)
    await embed_binding.pin_on_first_ingest(db, kb=kb, user_id=uploaded_by)

    # 内容级幂等（同上传路径,含 TOCTOU 锁）
    # 双击/并行同传的 TOCTOU 竞态:hash 查重与建行之间必须持有项目级锁
    # （kb 行 FOR UPDATE,与入库 index 事务同一把锁;crud.create 的 commit 即释放）
    await db.execute(
        select(ProjectKnowledgeBase)
        .where(ProjectKnowledgeBase.project_id == project_id)
        .with_for_update()
    )
    text_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = await crud_kb_document.get_by_content_hash(
        db, project_id=project_id, content_hash=text_hash
    )
    if existing is not None:
        return await _reuse_existing_doc(
            db, project_id=project_id, user_id=uploaded_by, doc=existing
        )

    doc = await crud_kb_document.create(
        db,
        project_id=project_id,
        file_name=title,
        file_size=len(content.encode("utf-8")),
        file_ext=".md",
        uploaded_by=uploaded_by,
        doc_type=_norm_doc_type(doc_type),
        source_type=KbDocSourceType.TEXT.value,
        content_md=content,
        content_hash=text_hash,
        status=KbDocumentStatus.PENDING.value,
    )
    task_id = await _submit_ingest(db, project_id=project_id, user_id=uploaded_by, doc=doc)
    return doc, task_id


async def _delete_doc_in_tx(db: AsyncSession, *, doc: KbDocument) -> int:
    """单事务删除一份文档：置 deleted → 删 chunk → bump → 图谱 GC（调用方 commit）。

    返回删除的 chunk 数。取消在途任务在事务外做（Redis 标志，best-effort）。
    """
    was_ready = doc.status == KbDocumentStatus.READY.value
    doc.status = KbDocumentStatus.DELETED.value
    db.add(doc)
    deleted = await crud_kb_chunk.delete_by_document(db, document_id=doc.id)
    await crud_knowledge_base.bump_index_version(
        db,
        project_id=doc.project_id,
        delta_chunks=-deleted,
        delta_documents=-1 if was_ready else 0,
    )
    # 图谱 GC（P1b TB3.2）：清本文档台账贡献,自动孤儿删行,同事务原子
    from app.services.knowledge import graph_service

    await graph_service.gc_for_document(
        db, project_id=doc.project_id, document_id=doc.id
    )
    return deleted


async def delete_document_from_kb(
    db: AsyncSession, *, project_id: int, kb_doc_id: int
) -> None:
    """删除单文档（含在途任务取消 + chunk 物理删除 + 计数回收）"""
    doc = await crud_kb_document.get(db, kb_doc_id)
    if not doc or doc.project_id != project_id:
        raise BusinessException("文档不存在", code=404)
    if doc.status == KbDocumentStatus.DELETED.value:
        return

    # 先发取消标志（在途 kb_ingest 的 index 节点 FOR UPDATE 复核会看到 deleted）
    if doc.ai_task_id:
        try:
            await event_bus.request_cancel(doc.ai_task_id)
        except Exception:  # noqa: BLE001 —— 取消是 best-effort，事务复核兜底
            pass

    await _delete_doc_in_tx(db, doc=doc)
    await db.commit()


async def clear_documents_from_kb(
    db: AsyncSession, *, project_id: int
) -> dict[str, int]:
    """清空本项目全部文档（逐份同一事务语义，最后统一重算状态）"""
    stmt = select(KbDocument).where(
        KbDocument.project_id == project_id,
        KbDocument.status != KbDocumentStatus.DELETED.value,
    )
    docs = list((await db.execute(stmt)).scalars().all())
    deleted_docs = 0
    deleted_chunks = 0
    for doc in docs:
        if doc.ai_task_id:
            try:
                await event_bus.request_cancel(doc.ai_task_id)
            except Exception:  # noqa: BLE001
                pass
        deleted_chunks += await _delete_doc_in_tx(db, doc=doc)
        deleted_docs += 1

    kb = await crud_knowledge_base.get_by_project(db, project_id=project_id)
    if kb:
        kb.status = KnowledgeBaseStatus.EMPTY.value
        db.add(kb)
    await db.commit()
    return {"deleted": deleted_docs, "chunks": deleted_chunks}


async def update_document_meta(
    db: AsyncSession,
    *,
    project_id: int,
    kb_doc_id: int,
    file_name: str | None = None,
    doc_type: str | None = None,
    validity: str | None = None,
) -> KbDocument:
    """文档元信息编辑 + 显式废弃（P1a WP-A4）。

    validity 只接受 'deprecated'：置废弃时**同事务**物理删 chunk + bump
    （检索即时不可见，无 stale 向量滞留——评审裁决）;content_md 保留供恢复。
    恢复生效必须走 reingest_document（重建 chunk），不允许 PATCH 空翻状态。
    """
    doc = await crud_kb_document.get(db, kb_doc_id)
    if not doc or doc.project_id != project_id or doc.status == KbDocumentStatus.DELETED.value:
        raise BusinessException("文档不存在", code=404)

    if file_name is not None:
        name = file_name.strip()
        if not name:
            raise BusinessException("文件名不能为空", code=400)
        doc.file_name = name[:255]
    if doc_type is not None:
        doc.doc_type = _norm_doc_type(doc_type)

    if validity is not None:
        if validity == KbDocValidity.EFFECTIVE.value:
            raise BusinessException(
                "恢复生效请使用「重新入库」（需重建分块索引），不支持直接改状态", code=400
            )
        if validity != KbDocValidity.DEPRECATED.value:
            raise BusinessException(f"不支持的 validity：{validity}", code=400)
        if doc.validity != KbDocValidity.DEPRECATED.value:
            was_ready = doc.status == KbDocumentStatus.READY.value
            deleted = await crud_kb_chunk.delete_by_document(db, document_id=doc.id)
            await crud_knowledge_base.bump_index_version(
                db,
                project_id=project_id,
                delta_chunks=-deleted,
                delta_documents=-1 if was_ready else 0,
            )
            doc.validity = KbDocValidity.DEPRECATED.value
            doc.chunk_count = 0
            # 废弃同时撤回图谱贡献（P1b TB3.2）,graph_status 复位
            from app.services.knowledge import graph_service

            await graph_service.gc_for_document(
                db, project_id=project_id, document_id=doc.id
            )
            doc.graph_status = "none"
            doc.entity_count = 0

    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def reingest_document(
    db: AsyncSession,
    *,
    project_id: int,
    kb_doc_id: int,
    user_id: int,
    scanned_pdf: bool = False,
) -> tuple[KbDocument, int]:
    """重新入库（P1a WP-A4）：废弃恢复 / 失败重试 / 分块策略升级后重建单文档。

    数据源优先级由 kb_ingest 图决定（func_doc 直取 parsed_content /
    content_md 跳解析 / storage_key 重新解析），此处只校验至少有一个源。
    """
    doc = await crud_kb_document.get(db, kb_doc_id)
    if not doc or doc.project_id != project_id or doc.status == KbDocumentStatus.DELETED.value:
        raise BusinessException("文档不存在", code=404)
    has_source = bool(
        (doc.content_md or "").strip()
        or doc.storage_key
        or (doc.source_type == KbDocSourceType.FUNC_DOC.value and doc.source_id)
    )
    if not has_source:
        raise BusinessException(
            "该文档无可重入库的数据源（LightRAG 时代原件未落盘），请重新上传", code=400
        )

    kb = await ensure_knowledge_base(db, project_id=project_id)
    await embed_binding.pin_on_first_ingest(db, kb=kb, user_id=user_id)

    # 重入库前撤回旧内容的图谱贡献（P1b TB3.2）：新内容入库后由自动派发重抽
    from app.services.knowledge import graph_service

    await graph_service.gc_for_document(db, project_id=project_id, document_id=doc.id)
    doc.graph_status = "none"
    doc.graph_source_hash = None
    doc.entity_count = 0

    doc.validity = KbDocValidity.EFFECTIVE.value
    doc.status = KbDocumentStatus.PENDING.value
    doc.error_message = None
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    task_id = await _submit_ingest(
        db, project_id=project_id, user_id=user_id, doc=doc, scanned_pdf=scanned_pdf
    )
    return doc, task_id


async def recount_stats(
    db: AsyncSession, *, project_id: int
) -> ProjectKnowledgeBase:
    """本地真实口径重算统计（替代旧 sync_kb_stats 的 LightRAG 全局求和错账）。

    正常路径下计数由 bump_index_version 增量维护，本函数是显式校准入口
    （/sync 端点语义保留，数据源改为本地）。
    """
    kb = await ensure_knowledge_base(db, project_id=project_id)
    total_documents = await crud_kb_document.count_active(db, project_id=project_id)
    total_chunks = await crud_kb_chunk.count_by_project(db, project_id=project_id)
    kb.total_documents = total_documents
    kb.total_chunks = total_chunks
    if kb.status not in (KnowledgeBaseStatus.REBUILDING.value,):
        kb.status = (
            KnowledgeBaseStatus.READY.value
            if total_documents > 0
            else KnowledgeBaseStatus.EMPTY.value
        )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


# 旧名兼容：knowledge_base 端点 import 的 sync_kb_stats（语义已改为本地重算）
sync_kb_stats = recount_stats
