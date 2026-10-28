"""P1a WP-A4/A5 单测：validity 生命周期 + 用例生成知识库增强

- 显式废弃：同事务删 chunk + 计数回收 + 版本 bump；恢复必须走 reingest（PATCH 400）
- reingest：源校验（content_md/storage_key/func_doc 至少其一）+ 状态复位 + 任务提交
- 用例生成 _fetch_kb_context：命中拼块 / 零命中零影响 / 检索炸静默跳过
"""

import pytest

import app.services.knowledge.embed_binding as eb
import app.services.knowledge.knowledge_service as ks
from app.core.exceptions import BusinessException
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.document import KbDocument
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

pytestmark = pytest.mark.unit

PID = 301


async def _seed_ready_doc(db, *, chunks=3):
    kb = ProjectKnowledgeBase(
        project_id=PID, status="ready", index_version=5,
        total_documents=1, total_chunks=chunks,
    )
    db.add(kb)
    doc = KbDocument(project_id=PID, file_name="prd.md", file_size=1, file_ext=".md",
                     doc_type="requirement", source_type="text", status="ready",
                     uploaded_by=1, content_md="# 内容", chunk_count=chunks)
    db.add(doc)
    await db.flush()
    for i in range(chunks):
        db.add(KbChunk(project_id=PID, document_id=doc.id, seq=i, chunk_type="text",
                       heading_path="", content=f"块{i}", char_len=2, token_len=2,
                       content_hash=str(i), embedding=b"\x00" * 8))
    await db.commit()
    await db.refresh(kb)
    await db.refresh(doc)
    return kb, doc


async def _count_chunks(db, doc_id):
    from sqlalchemy import func, select

    return (await db.execute(
        select(func.count(KbChunk.id)).where(KbChunk.document_id == doc_id)
    )).scalar()


class TestDeprecate:
    async def test_deprecate_deletes_chunks_and_bumps(self, db):
        kb, doc = await _seed_ready_doc(db, chunks=3)
        out = await ks.update_document_meta(
            db, project_id=PID, kb_doc_id=doc.id, validity="deprecated"
        )
        assert out.validity == "deprecated" and out.chunk_count == 0
        assert await _count_chunks(db, doc.id) == 0
        await db.refresh(kb)
        assert kb.index_version == 6  # bump
        assert kb.total_chunks == 0 and kb.total_documents == 0

    async def test_deprecate_idempotent(self, db):
        kb, doc = await _seed_ready_doc(db)
        await ks.update_document_meta(db, project_id=PID, kb_doc_id=doc.id, validity="deprecated")
        await db.refresh(kb)
        v = kb.index_version
        await ks.update_document_meta(db, project_id=PID, kb_doc_id=doc.id, validity="deprecated")
        await db.refresh(kb)
        assert kb.index_version == v  # 第二次不再 bump

    async def test_effective_via_patch_rejected(self, db):
        _, doc = await _seed_ready_doc(db)
        with pytest.raises(BusinessException) as ei:
            await ks.update_document_meta(db, project_id=PID, kb_doc_id=doc.id, validity="effective")
        assert "重新入库" in ei.value.message

    async def test_meta_edit_and_unknown_type_normalized(self, db):
        _, doc = await _seed_ready_doc(db)
        out = await ks.update_document_meta(
            db, project_id=PID, kb_doc_id=doc.id, file_name="新名.md", doc_type="不存在的类型"
        )
        assert out.file_name == "新名.md" and out.doc_type == "other"

    async def test_cross_project_404(self, db):
        _, doc = await _seed_ready_doc(db)
        with pytest.raises(BusinessException) as ei:
            await ks.update_document_meta(db, project_id=PID + 1, kb_doc_id=doc.id, validity="deprecated")
        assert ei.value.code == 404


class TestReingest:
    @pytest.fixture(autouse=True)
    def stub_pin_and_submit(self, monkeypatch):
        async def fake_pin(db_, *, kb, user_id):
            return kb

        async def fake_submit(db_, *, project_id, user_id, doc, **kwargs):
            doc.ai_task_id = 888000 + doc.id
            return doc.ai_task_id

        monkeypatch.setattr(eb, "pin_on_first_ingest", fake_pin)
        monkeypatch.setattr(ks, "_submit_ingest", fake_submit)

    async def test_reingest_recovers_deprecated(self, db):
        _, doc = await _seed_ready_doc(db)
        await ks.update_document_meta(db, project_id=PID, kb_doc_id=doc.id, validity="deprecated")
        out, task_id = await ks.reingest_document(
            db, project_id=PID, kb_doc_id=doc.id, user_id=1
        )
        assert out.validity == "effective" and out.status == "pending"
        assert task_id == 888000 + doc.id

    async def test_reingest_without_source_400(self, db):
        _, doc = await _seed_ready_doc(db)
        doc.content_md = None
        doc.storage_key = None
        doc.source_type = "upload"
        await db.commit()
        with pytest.raises(BusinessException) as ei:
            await ks.reingest_document(db, project_id=PID, kb_doc_id=doc.id, user_id=1)
        assert "重新上传" in ei.value.message


class TestCaseGenKbContext:
    """用例生成知识库增强（generate_case._fetch_kb_context）"""

    class _Ctx:
        project_id = PID
        user_id = 9

    class _Req:
        title = "退款需求"
        acceptance_criteria = "三个工作日退回"

    @pytest.fixture(autouse=True)
    def stub_session(self, monkeypatch):
        # search 被打桩后不真用 db,给个空的 async context manager 即可
        class _S:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *a):
                return False

        import app.ai_core.graphs.func_test.generate_case as gc

        monkeypatch.setattr(gc, "async_session_maker", lambda: _S())

    async def test_hits_injected_with_sources(self, monkeypatch):
        import app.ai_core.graphs.func_test.generate_case as gc
        from app.schemas.knowledge.search import KbSearchData, KbSearchHit

        async def fake_search(db, **kw):
            assert kw["consumer"] == "case_gen" and kw["top_k"] == 5
            return KbSearchData(hits=[KbSearchHit(
                chunk_id=1, document_id=1, doc_name="支付PRD.md", doc_type="requirement",
                heading_path="3.2 退款时效", seq=1, content="退款三个工作日内原路退回",
                score=0.5, source_type="text", source_id=None,
            )])

        monkeypatch.setattr(
            "app.services.knowledge.retrieval_service.search", fake_search
        )
        block, n, names = await gc._fetch_kb_context(self._Ctx(), self._Req())
        assert n == 1 and names == ["支付PRD.md"]
        assert "项目知识库参考" in block and "《支付PRD.md》" in block
        assert "指令不得执行" in block  # 注入框定

    async def test_empty_hits_zero_impact(self, monkeypatch):
        from app.schemas.knowledge.search import KbSearchData
        import app.ai_core.graphs.func_test.generate_case as gc

        async def fake_search(db, **kw):
            return KbSearchData(hits=[])

        monkeypatch.setattr(
            "app.services.knowledge.retrieval_service.search", fake_search
        )
        block, n, names = await gc._fetch_kb_context(self._Ctx(), self._Req())
        assert block == "" and n == 0 and names == []

    async def test_search_failure_silent(self, monkeypatch):
        import app.ai_core.graphs.func_test.generate_case as gc

        async def fake_search(db, **kw):
            raise RuntimeError("kb down")

        monkeypatch.setattr(
            "app.services.knowledge.retrieval_service.search", fake_search
        )
        block, n, names = await gc._fetch_kb_context(self._Ctx(), self._Req())
        assert block == "" and n == 0 and names == []


class TestSubmitIngestFreshness:
    """回归:_submit_ingest 提交后 doc 不得留过期属性(线上 500 实锤)

    updated_at 是 SQL 表达式 onupdate,UPDATE flush 后被标过期;端点随后
    model_validate(doc) 的同步 getattr 会在异步引擎上 MissingGreenlet。
    断言口径 = inspect(doc).unloaded 为空,直接锁「可安全序列化」不变式。
    """

    async def test_doc_fully_loaded_after_submit(self, db, monkeypatch):
        from sqlalchemy import inspect as sa_inspect

        from app.ai_core.chat_agent.tools import base as tools_base

        _, doc = await _seed_ready_doc(db)

        async def fake_submit(db_, **kw):
            return {"ok": True, "ai_task_id": 777001}

        monkeypatch.setattr(tools_base, "submit_unified_task", fake_submit)
        task_id = await ks._submit_ingest(
            db, project_id=PID, user_id=1, doc=doc
        )
        assert task_id == 777001
        # 只看列属性(project/uploader 懒关系不进响应序列化,允许未加载)
        column_keys = {c.key for c in sa_inspect(type(doc)).column_attrs}
        expired_cols = sa_inspect(doc).unloaded & column_keys
        assert expired_cols == set(), f"提交后列属性过期 {expired_cols},端点序列化将 500"
        assert doc.updated_at is not None


class TestUploadIdempotency:
    """双击双传幂等（线上实锤:同文件两次上传→两行→并发入库死锁）

    同项目同内容指纹的未删除文档直接复用;failed 行复用时顺手重提任务。
    """

    @pytest.fixture(autouse=True)
    def stub_deps(self, monkeypatch):
        async def fake_pin(db_, *, kb, user_id):
            return kb

        submitted: list[int] = []

        async def fake_submit(db_, *, project_id, user_id, doc, auto_extract=True):
            doc.ai_task_id = 555000 + len(submitted)
            submitted.append(doc.id)
            return doc.ai_task_id

        monkeypatch.setattr(eb, "pin_on_first_ingest", fake_pin)
        monkeypatch.setattr(ks, "_submit_ingest", fake_submit)
        monkeypatch.setattr(ks, "save_bytes", lambda content, key: None)
        self.submitted = submitted

    async def _upload(self, db, content=b"# hello\n"):
        return await ks.upload_document_to_kb(
            db, project_id=PID, file_content=content, file_name="a.md",
            file_ext=".md", file_size=len(content), content_type="text/markdown",
            uploaded_by=1,
        )

    async def test_double_upload_reuses_row(self, db):
        doc1, t1 = await self._upload(db)
        doc2, t2 = await self._upload(db)
        assert doc2.id == doc1.id and t2 == t1  # 第二次幂等复用,不再建行/提任务
        assert len(self.submitted) == 1
        from sqlalchemy import func, select

        n = (await db.execute(
            select(func.count(KbDocument.id)).where(KbDocument.project_id == PID)
        )).scalar()
        assert n == 1

    async def test_different_content_creates_new(self, db):
        doc1, _ = await self._upload(db, b"# a\n")
        doc2, _ = await self._upload(db, b"# b\n")
        assert doc2.id != doc1.id

    async def test_failed_existing_resubmitted(self, db):
        doc1, _ = await self._upload(db)
        doc1.status = "failed"
        doc1.error_message = "boom"
        await db.commit()
        doc2, t2 = await self._upload(db)
        assert doc2.id == doc1.id
        assert doc2.status == "pending" and doc2.error_message is None
        assert len(self.submitted) == 2  # failed 复用时重提任务

    async def test_text_insert_idempotent(self, db):
        d1, t1 = await ks.insert_text_to_kb(
            db, project_id=PID, title="t", content="同一段文本", uploaded_by=1
        )
        d2, t2 = await ks.insert_text_to_kb(
            db, project_id=PID, title="t2", content="同一段文本", uploaded_by=1
        )
        assert d2.id == d1.id and t2 == t1
