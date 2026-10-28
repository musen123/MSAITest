"""跨项目隔离 + 幂等（MySQL integration，P0 DoD 第一条固化进 CI）

真 MySQL 行为：FULLTEXT ngram NATURAL LANGUAGE MODE 召回、kb_ingest 图
单事务落库、bump 原子计数。dev/CI 的 MySQL 不可达时整文件 skip。

验收语义（设计文档 §DoD①）：项目 A 入库含唯一标识串的文档，项目 B 在
向量路 / 全文路 / 混合 search 三条路径上对该标识串**零命中**。
"""

import hashlib
import uuid

import numpy as np
import pytest
from sqlalchemy import text

import app.services.knowledge.embed_binding as eb
from app.services.knowledge import retrieval_service

pytestmark = pytest.mark.integration

DIM = 64
MARKER = f"唯一标识串{uuid.uuid4().hex[:12]}"


def _bigram_vec(t: str):
    v = np.zeros(DIM, dtype="<f4")
    t = "".join(t.split())
    for i in range(len(t) - 1):
        v[int(hashlib.md5(t[i : i + 2].encode()).hexdigest(), 16) % DIM] += 1.0
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()


class BigramEmbeddings:
    async def aembed_query(self, t):
        return _bigram_vec(t)

    async def aembed_documents(self, ts):
        return [_bigram_vec(t) for t in ts]


@pytest.fixture
async def two_projects(monkeypatch, tmp_path):
    """在真实库上准备两个项目：A 项目入库带标识串的文档（经 kb_ingest 图），
    B 项目为对照。全部数据 finally 清理。

    ⚠ 全局 engine 的连接池会把连接绑到首个使用它的事件循环；pytest-asyncio
    每测试新 loop，进出各 dispose 一次丢弃旧池，否则「attached to a
    different loop」。MySQL 不可达时 skip（CI 无库场景）。"""
    from app.core.config import settings
    from app.db.session import async_session_maker, engine

    await engine.dispose()  # 丢弃可能绑定旧 loop 的连接池
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MySQL 不可达，跳过 integration：{exc}")

    monkeypatch.setattr(eb, "build_llm_from_config", lambda cfg: BigramEmbeddings())
    monkeypatch.setattr(settings, "KB_VECTOR_DIR", str(tmp_path / "kb_vec"))
    # 进程内向量 LRU 清空（其它测试/进程遗留）
    from app.services.knowledge import vector_cache

    vector_cache._lru.clear()

    import app.ai_core.graphs  # noqa: F401 注册副作用
    from app.ai_core.runtime import registry
    from app.ai_core.runtime.context import TaskContext
    from app.models.auth.user_llm_config import UserLlmConfig
    from app.models.knowledge import KbDocument

    created: dict = {}
    async with async_session_maker() as db:
        rows = (await db.execute(text("SELECT id FROM tb_project ORDER BY id LIMIT 2"))).fetchall()
        if len(rows) < 2:
            pytest.skip("dev 库项目数 < 2，无法做跨项目隔离验收")
        pid_a, pid_b = rows[0][0], rows[1][0]
        uid = (await db.execute(text("SELECT id FROM sys_user ORDER BY id LIMIT 1"))).scalar()

        cfg = UserLlmConfig(user_id=uid, model_type="embed", name="_iso_probe",
                            provider="openai", model="_iso_model", api_key="sk",
                            base_url="https://iso.local/v1", is_active=True, is_default=False)
        db.add(cfg)
        for pid in (pid_a, pid_b):
            await db.execute(text(
                "INSERT INTO kb_project_knowledge_base (project_id, status, embed_provider, embed_model, "
                "embed_base_url, embed_dim, embed_bound_by, embed_status, index_version, total_documents, "
                "total_chunks, total_nodes, total_edges, created_at, updated_at) "
                "VALUES (:p, 'empty', 'openai', '_iso_model', 'https://iso.local/v1', :d, :u, 'active', 0, 0, 0, 0, 0, NOW(), NOW()) "
                "ON DUPLICATE KEY UPDATE embed_provider='openai', embed_model='_iso_model', "
                "embed_base_url='https://iso.local/v1', embed_dim=:d, embed_bound_by=:u, embed_status='active'"),
                {"p": pid, "d": DIM, "u": uid})
        doc = KbDocument(project_id=pid_a, file_name="_iso_probe.md", file_ext="md",
                         doc_type="requirement", source_type="text", status="pending",
                         uploaded_by=uid,
                         content_md=f"# 隔离验收\n\n本文包含{MARKER},用于验证项目隔离。" * 3)
        db.add(doc)
        await db.commit()
        created = {"pid_a": pid_a, "pid_b": pid_b, "uid": uid, "doc_id": doc.id}

    spec = registry.get("kb_ingest")
    ctx = TaskContext(task_id=980001, project_id=pid_a, user_id=created["uid"])
    graph = spec.build_graph({}, ctx)
    await graph.ainvoke(spec.build_input({"kb_document_id": created["doc_id"]}))
    created["spec"] = spec

    try:
        yield created
    finally:
        async with async_session_maker() as db:
            await db.execute(text("DELETE FROM kb_document WHERE file_name='_iso_probe.md'"))
            await db.execute(text("DELETE FROM sys_user_llm_config WHERE name='_iso_probe'"))
            for pid in (created["pid_a"], created["pid_b"]):
                await db.execute(text(
                    "UPDATE kb_project_knowledge_base SET embed_provider=NULL, embed_model=NULL, "
                    "embed_base_url=NULL, embed_dim=NULL, embed_bound_by=NULL, embed_status='active' "
                    "WHERE project_id=:p"), {"p": pid})
            await db.execute(text(
                "DELETE FROM ai_task WHERE task_type='kb_ingest' AND biz_ref_id=:d"),
                {"d": created["doc_id"]})
            await db.commit()
        await engine.dispose()  # 本测试 loop 的池不留给下个 loop


class TestCrossProjectZeroLeak:
    """零泄漏口径：B 项目的结果**绝不含 A 播种的文档**。

    不能断言「B 零命中」——dev 真库 B 项目可能有真实业务文档,NATURAL LANGUAGE
    MODE 对中文查询天然给模糊命中（环境实锤:用户上传真数据后旧断言假红）。
    """

    async def test_project_a_hits_project_b_zero(self, two_projects):
        from app.db.session import async_session_maker

        pid_a, pid_b = two_projects["pid_a"], two_projects["pid_b"]
        marker_doc = two_projects["doc_id"]
        async with async_session_maker() as db:
            # A 项目可命中播种文档
            ra = await retrieval_service.search(db, project_id=pid_a, query=MARKER, top_k=5)
            assert marker_doc in {h.document_id for h in ra.hits}, "A 项目应命中标识文档"
            assert not ra.degraded.vector and not ra.degraded.fulltext

            # B 项目绝不含 A 的播种文档（向量+全文融合后的 search 主路径）
            rb = await retrieval_service.search(db, project_id=pid_b, query=MARKER, top_k=5)
            leaked = [h for h in rb.hits if h.document_id == marker_doc or MARKER in h.content]
            assert leaked == [], f"跨项目泄漏！B 命中 {[(h.doc_name, h.content[:30]) for h in leaked]}"
            assert all(h.document_id != marker_doc for h in rb.hits)

    async def test_fulltext_path_isolated(self, two_projects):
        from app.crud.knowledge import crud_kb_chunk
        from app.db.session import async_session_maker

        async with async_session_maker() as db:
            hits_a = await crud_kb_chunk.fulltext_search(
                db, project_id=two_projects["pid_a"], query=MARKER, limit=10)
            hits_b = await crud_kb_chunk.fulltext_search(
                db, project_id=two_projects["pid_b"], query=MARKER, limit=10)
            a_ids = [cid for cid, _ in hits_a]
            b_ids = [cid for cid, _ in hits_b]
            marker_chunks = set((await db.execute(text(
                "SELECT id FROM kb_chunk WHERE document_id=:d"),
                {"d": two_projects["doc_id"]})).scalars())
        assert marker_chunks & set(a_ids), "A 全文路应命中播种 chunk"
        assert not (marker_chunks & set(b_ids)), "跨项目泄漏:B 全文路命中 A 播种 chunk"

    async def test_chat_tool_path_isolated(self, two_projects):
        """Chat 工具与 /search 共用 retrieval_service.search——工具层 project_id
        来自会话上下文闭包，此处验证 B 项目域调用不含 A 播种内容即等价覆盖"""
        from app.db.session import async_session_maker

        async with async_session_maker() as db:
            rb = await retrieval_service.search(
                db, project_id=two_projects["pid_b"], query=MARKER, top_k=6)
        ctx_text = retrieval_service.format_hits_for_llm(rb.hits)
        assert MARKER not in ctx_text, "跨项目泄漏:B 域上下文含 A 标识串"


class TestIngestIdempotent:
    async def test_rerun_no_duplicate_chunks(self, two_projects):
        """acks_late 重投语义：同文档重跑图，chunk 不重复、计数不虚涨、版本 +1"""
        from app.ai_core.runtime.context import TaskContext
        from app.db.session import async_session_maker

        doc_id = two_projects["doc_id"]
        pid_a = two_projects["pid_a"]
        async with async_session_maker() as db:
            before = (await db.execute(text(
                "SELECT COUNT(*), (SELECT index_version FROM kb_project_knowledge_base WHERE project_id=:p), "
                "(SELECT total_chunks FROM kb_project_knowledge_base WHERE project_id=:p) "
                "FROM kb_chunk WHERE document_id=:d"), {"p": pid_a, "d": doc_id})).fetchone()

        ctx = TaskContext(task_id=980002, project_id=pid_a, user_id=two_projects["uid"])
        spec = two_projects["spec"]
        graph = spec.build_graph({}, ctx)
        await graph.ainvoke(spec.build_input({"kb_document_id": doc_id}))

        async with async_session_maker() as db:
            after = (await db.execute(text(
                "SELECT COUNT(*), (SELECT index_version FROM kb_project_knowledge_base WHERE project_id=:p), "
                "(SELECT total_chunks FROM kb_project_knowledge_base WHERE project_id=:p) "
                "FROM kb_chunk WHERE document_id=:d"), {"p": pid_a, "d": doc_id})).fetchone()
            dup = (await db.execute(text(
                "SELECT document_id, seq, COUNT(*) c FROM kb_chunk WHERE document_id=:d "
                "GROUP BY document_id, seq HAVING c > 1"), {"d": doc_id})).fetchall()

        assert dup == []
        assert after[0] == before[0]  # 块数不变
        assert after[1] == before[1] + 1  # 版本 +1
        assert after[2] == before[2]  # 计数不虚涨
