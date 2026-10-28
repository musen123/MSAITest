"""测试文档 → 项目知识库 桥接服务（自研版）

数据流（设计文档 §4.4）：
  测试文档（func_project_document，须 parse_status='parsed'）
    → 建/复用 kb_document（source_type='func_doc', source_id=doc.id）
    → 提交 kb_ingest 统一任务（图的 load 节点直取 parsed_content，**零重复解析零 token**）
    → 任务侧回写 kb_status = ingested / ingest_failed + kb_ingested_at
      （见 ai_core/graphs/knowledge/ingest.py 的 func 桥回写）

幂等：同 func 文档重复入库 = 复用同一 kb_document 行重新提交任务（先删后插
chunk 由图保证），不再有 LightRAG 时代「全量拉取按 file_source 反查删旧」的
O(n) 扫描。撤回 = 删除 kb_document（级联 chunk + 计数回收）。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.crud.knowledge import crud_kb_document
from app.models.func_test.document import (
    DocumentKbStatus,
    DocumentParseStatus,
    ProjectDocument,
)
from app.models.knowledge.document import (
    KbDocSourceType,
    KbDocType,
    KbDocumentStatus,
)
from app.services.knowledge import embed_binding
from app.services.knowledge.knowledge_service import (
    _submit_ingest,
    delete_document_from_kb,
    ensure_knowledge_base,
)

# func 文档类型 → 知识库 doc_type（func: requirement/prototype/db_dict/other）
_DOC_TYPE_MAP = {
    "requirement": KbDocType.REQUIREMENT.value,
    "prototype": KbDocType.DESIGN.value,
    "db_dict": KbDocType.DESIGN.value,
}


async def ingest_document_to_kb(
    db: AsyncSession, *, doc: ProjectDocument, user_id: int, auto_extract: bool = True
) -> dict:
    """把测试文档的解析结果导入自研知识库（任务式，异步入库）

    前置条件：``doc.parse_status == parsed`` 且 ``parsed_content`` 非空。
    返回 {doc_id, kb_status, kb_document_id, ai_task_id}。
    auto_extract=False 抑制入库后图谱自动派发（回灌专用——切换日不集中烧 token）。
    """
    if doc.parse_status != DocumentParseStatus.PARSED.value:
        raise BusinessException("文档尚未完成 AI 解析，请先点击「AI 解析」", code=400)
    if not (doc.parsed_content or "").strip():
        raise BusinessException("解析后的内容为空，无法入库", code=400)

    kb = await ensure_knowledge_base(db, project_id=doc.project_id)
    # embed 首绑前置（未配 EMBED 在这里就 400）
    await embed_binding.pin_on_first_ingest(db, kb=kb, user_id=user_id)

    # 幂等：同源复用 kb_document 行
    kb_doc = await crud_kb_document.get_by_source(
        db,
        project_id=doc.project_id,
        source_type=KbDocSourceType.FUNC_DOC.value,
        source_id=doc.id,
    )
    doc_type = _DOC_TYPE_MAP.get(doc.doc_type or "", KbDocType.OTHER.value)
    if kb_doc is None:
        kb_doc = await crud_kb_document.create(
            db,
            project_id=doc.project_id,
            file_name=doc.name,
            file_size=len((doc.parsed_content or "").encode("utf-8")),
            file_ext=".md",
            uploaded_by=user_id,
            doc_type=doc_type,
            source_type=KbDocSourceType.FUNC_DOC.value,
            source_id=doc.id,
            status=KbDocumentStatus.PENDING.value,
        )
    else:
        kb_doc.file_name = doc.name
        kb_doc.doc_type = doc_type
        kb_doc.status = KbDocumentStatus.PENDING.value
        kb_doc.error_message = None
        db.add(kb_doc)
        await db.commit()
        await db.refresh(kb_doc)

    # 桥接状态：ingesting（终态由 kb_ingest 图回写）
    doc.kb_status = DocumentKbStatus.INGESTING.value
    doc.kb_document_id = kb_doc.id
    db.add(doc)
    await db.commit()
    # updated_at 是 SQL onupdate 服务端算值列，flush 后被逐属性标过期（expire_on_commit=False
    # 管不到）。不 refresh 的话，端点随后 model_validate(doc) 的同步 getattr 会在异步引擎上
    # 触发懒加载 → MissingGreenlet 500（入库其实已成功，用户看到报错）——与 _submit_ingest
    # refresh kb_doc 同源，此处补的是 func 文档本身。
    await db.refresh(doc)

    task_id = await _submit_ingest(
        db,
        project_id=doc.project_id,
        user_id=user_id,
        doc=kb_doc,
        auto_extract=auto_extract,
    )
    return {
        "doc_id": doc.id,
        "kb_status": doc.kb_status,
        "kb_document_id": kb_doc.id,
        "ai_task_id": task_id,
    }


async def remove_document_from_kb(
    db: AsyncSession, *, doc: ProjectDocument
) -> dict:
    """把测试文档从知识库撤回（删除 kb_document：级联 chunk + 计数回收）。幂等。"""
    kb_doc = None
    if doc.kb_document_id:
        kb_doc = await crud_kb_document.get(db, doc.kb_document_id)
    if kb_doc is None:
        kb_doc = await crud_kb_document.get_by_source(
            db,
            project_id=doc.project_id,
            source_type=KbDocSourceType.FUNC_DOC.value,
            source_id=doc.id,
        )
    if kb_doc is not None and kb_doc.status != KbDocumentStatus.DELETED.value:
        await delete_document_from_kb(
            db, project_id=doc.project_id, kb_doc_id=kb_doc.id
        )

    doc.kb_status = DocumentKbStatus.NOT_INGESTED.value
    doc.kb_document_id = None
    doc.kb_ingested_at = None
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"doc_id": doc.id, "kb_status": doc.kb_status}
