"""检索编排单测：RRF 融合 + 区间去重 + 降级（sqlite，召回路 monkeypatch）

FULLTEXT/向量真召回是 MySQL/numpy 行为（integration 覆盖）；本文件测 search()
的编排正确性：融合序、父块上卷、同 parent 去重、同文档 cap、token 预算、
类型过滤兜底向量路、单路失败降级不 502、非 ready/已废弃文档过滤。
"""

import pytest

import app.services.knowledge.retrieval_service as rs
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.document import KbDocument
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

pytestmark = pytest.mark.unit

PID = 201


async def _seed(db):
    """两份文档：doc1 一个 parent 带两个 child + 一个独立小 child；doc2 一个 child"""
    kb = ProjectKnowledgeBase(
        project_id=PID, status="ready",
        embed_provider="openai", embed_model="m", embed_base_url="u",
        embed_dim=8, embed_status="active", index_version=3,
    )
    db.add(kb)
    doc1 = KbDocument(project_id=PID, file_name="PRD.md", file_size=1, file_ext=".md",
                      doc_type="requirement", source_type="text", status="ready",
                      uploaded_by=1)
    doc2 = KbDocument(project_id=PID, file_name="API.md", file_size=1, file_ext=".md",
                      doc_type="api_doc", source_type="text", status="ready",
                      uploaded_by=1)
    db.add_all([doc1, doc2])
    await db.flush()

    parent = KbChunk(project_id=PID, document_id=doc1.id, seq=0, chunk_type="parent",
                     heading_path="3.2 退款时效", content="父块完整上下文" * 50,
                     char_len=350, token_len=350, content_hash="p")
    db.add(parent)
    await db.flush()
    c1 = KbChunk(project_id=PID, document_id=doc1.id, seq=1, chunk_type="text",
                 parent_chunk_id=parent.id, heading_path="3.2 退款时效",
                 content="child甲", char_len=6, token_len=6, content_hash="a",
                 embedding=b"\x00" * 32)
    c2 = KbChunk(project_id=PID, document_id=doc1.id, seq=2, chunk_type="text",
                 parent_chunk_id=parent.id, heading_path="3.2 退款时效",
                 content="child乙", char_len=6, token_len=6, content_hash="b",
                 embedding=b"\x00" * 32)
    c3 = KbChunk(project_id=PID, document_id=doc1.id, seq=3, chunk_type="text",
                 parent_chunk_id=None, heading_path="4 附则",
                 content="独立小节child", char_len=8, token_len=8, content_hash="c",
                 embedding=b"\x00" * 32)
    c4 = KbChunk(project_id=PID, document_id=doc2.id, seq=0, chunk_type="text",
                 parent_chunk_id=None, heading_path="登录接口",
                 content="接口文档child", char_len=8, token_len=8, content_hash="d",
                 embedding=b"\x00" * 32)
    db.add_all([c1, c2, c3, c4])
    await db.commit()
    return {"kb": kb, "doc1": doc1, "doc2": doc2, "parent": parent,
            "c1": c1, "c2": c2, "c3": c3, "c4": c4}


def _patch_recalls(monkeypatch, vector, fulltext):
    async def _vec(db, *, kb, query, prefer_user_id):
        if isinstance(vector, Exception):
            raise vector
        return vector

    async def _ft(*, project_id, query, doc_types):
        if isinstance(fulltext, Exception):
            raise fulltext
        return fulltext

    monkeypatch.setattr(rs, "_vector_recall", _vec)
    monkeypatch.setattr(rs, "_fulltext_recall", _ft)


class TestRrfFuse:
    def test_both_path_hit_ranks_first(self):
        fused = rs._rrf_fuse([[(1, 0.9), (2, 0.8)], [(2, 5.0), (3, 4.0)]])
        assert fused[0][0] == 2  # 双路同现者置顶

    def test_empty_paths(self):
        assert rs._rrf_fuse([[], []]) == []


class TestSearchOrchestration:
    async def test_parent_upconvert_and_same_parent_dedup(self, db, monkeypatch):
        s = await _seed(db)
        # 同 parent 两个 child 都命中 → 只保留一条，content 为父块
        _patch_recalls(monkeypatch,
                       vector=[(s["c1"].id, 0.9), (s["c2"].id, 0.8)],
                       fulltext=[(s["c2"].id, 3.0)])
        r = await rs.search(db, project_id=PID, query="退款时效")
        assert len(r.hits) == 1
        assert r.hits[0].content.startswith("父块完整上下文")
        assert not r.degraded.vector and not r.degraded.fulltext
        assert r.index_version == 3

    async def test_doc_cap_limits_same_document(self, db, monkeypatch):
        s = await _seed(db)
        # doc1 三个不同代表(parent组/c3) + doc2 —— cap=3 内 doc1 全进
        _patch_recalls(monkeypatch,
                       vector=[(s["c1"].id, 0.9), (s["c3"].id, 0.8), (s["c4"].id, 0.7)],
                       fulltext=[])
        r = await rs.search(db, project_id=PID, query="q", top_k=10)
        assert len(r.hits) == 3
        assert {h.document_id for h in r.hits} == {s["doc1"].id, s["doc2"].id}

    async def test_doc_types_filter_covers_vector_path(self, db, monkeypatch):
        s = await _seed(db)
        # 向量路命中 requirement 的 chunk，但过滤只要 api_doc → 被组装层兜住
        _patch_recalls(monkeypatch,
                       vector=[(s["c1"].id, 0.9), (s["c4"].id, 0.5)],
                       fulltext=[])
        r = await rs.search(db, project_id=PID, query="q", doc_types=["api_doc"])
        assert [h.doc_type for h in r.hits] == ["api_doc"]

    async def test_vector_failure_degrades_not_500(self, db, monkeypatch):
        s = await _seed(db)
        _patch_recalls(monkeypatch,
                       vector=RuntimeError("embed api down"),
                       fulltext=[(s["c4"].id, 2.0)])
        r = await rs.search(db, project_id=PID, query="q")
        assert r.degraded.vector and not r.degraded.fulltext
        assert len(r.hits) == 1  # 全文单路仍服务

    async def test_both_fail_returns_empty_200_semantics(self, db, monkeypatch):
        await _seed(db)
        _patch_recalls(monkeypatch,
                       vector=RuntimeError("x"), fulltext=RuntimeError("y"))
        r = await rs.search(db, project_id=PID, query="q")
        assert r.hits == []
        assert r.degraded.vector and r.degraded.fulltext

    async def test_deprecated_doc_filtered(self, db, monkeypatch):
        s = await _seed(db)
        s["doc2"].validity = "deprecated"
        await db.commit()
        _patch_recalls(monkeypatch, vector=[(s["c4"].id, 0.9)], fulltext=[])
        r = await rs.search(db, project_id=PID, query="q")
        assert r.hits == []

    async def test_token_budget_skips_oversized_after_first(self, db, monkeypatch):
        s = await _seed(db)
        # 把父块 token 拉爆预算：首条不受限保底，后续大块被跳过
        s["parent"].token_len = rs.CONTEXT_TOKEN_BUDGET + 100
        await db.commit()
        _patch_recalls(monkeypatch,
                       vector=[(s["c3"].id, 0.9), (s["c1"].id, 0.8), (s["c4"].id, 0.7)],
                       fulltext=[])
        r = await rs.search(db, project_id=PID, query="q", top_k=10)
        contents = [h.content for h in r.hits]
        assert "独立小节child" in contents[0]
        assert all(not c.startswith("父块完整上下文") for c in contents)  # 超预算父块被跳过
        assert any("接口文档child" in c for c in contents)  # 继续找小块

    async def test_unknown_project_empty(self, db, monkeypatch):
        await _seed(db)
        _patch_recalls(monkeypatch, vector=[], fulltext=[])
        r = await rs.search(db, project_id=999999, query="q")
        assert r.hits == [] and r.index_version == 0


class FakeTextLlm:
    """可编程假 TEXT 模型：按调用序返回预设内容"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        class R:  # noqa: N801
            content = self.responses.pop(0) if self.responses else "{}"
        return R()


class TestDeepMode:
    async def test_rewrite_merges_keywords_into_fulltext(self, db, monkeypatch):
        s = await _seed(db)
        captured = {}

        async def _vec(db_, *, kb, query, prefer_user_id):
            captured.setdefault("vec_queries", []).append(query)
            return [(s["c4"].id, 0.9)]

        async def _ft(*, project_id, query, doc_types):
            captured["ft_query"] = query
            return []

        monkeypatch.setattr(rs, "_vector_recall", _vec)
        monkeypatch.setattr(rs, "_fulltext_recall", _ft)
        llm = FakeTextLlm(['{"rewrite": "登录失败几次会被锁", "keywords": ["锁定", "AUTH_LOCKED"]}'])
        r = await rs.search(db, project_id=PID, query="登录锁定规则", deep=True, text_llm=llm)
        assert "锁定" in captured["ft_query"] and "AUTH_LOCKED" in captured["ft_query"]
        assert captured["vec_queries"] == ["登录锁定规则", "登录失败几次会被锁"]  # 原句+改写双路
        assert r.hits

    async def test_rerank_reorders_and_flags(self, db, monkeypatch):
        s = await _seed(db)
        _patch_recalls(monkeypatch,
                       vector=[(s["c3"].id, 0.9), (s["c4"].id, 0.8)],
                       fulltext=[])
        # 改写失败(垃圾) + 重排把第 1 位(编号1=c4)提到最前
        llm = FakeTextLlm(["not json at all", '{"order": [1, 0]}'])
        r = await rs.search(db, project_id=PID, query="q", deep=True, text_llm=llm)
        assert r.reranked is True
        assert "接口文档child" in r.hits[0].content  # c4 被重排到首位

    async def test_rerank_garbage_falls_back_to_rrf(self, db, monkeypatch):
        s = await _seed(db)
        _patch_recalls(monkeypatch,
                       vector=[(s["c3"].id, 0.9), (s["c4"].id, 0.8)],
                       fulltext=[])
        llm = FakeTextLlm(["garbage", "also garbage"])
        r = await rs.search(db, project_id=PID, query="q", deep=True, text_llm=llm)
        assert r.reranked is False
        assert "独立小节child" in r.hits[0].content  # RRF 原序保持

    async def test_no_text_llm_deep_noop(self, db, monkeypatch):
        s = await _seed(db)
        _patch_recalls(monkeypatch, vector=[(s["c3"].id, 0.9)], fulltext=[])
        r = await rs.search(db, project_id=PID, query="q", deep=True, text_llm=None)
        assert r.hits and r.reranked is False


class TestRetrievalLog:
    async def test_log_written_and_id_returned(self, db, monkeypatch):
        s = await _seed(db)
        _patch_recalls(monkeypatch, vector=[(s["c4"].id, 0.9)], fulltext=[])
        r = await rs.search(db, project_id=PID, query="登录", consumer="chat", prefer_user_id=7)
        assert r.log_id is not None
        from app.models.knowledge.retrieval_log import KbRetrievalLog
        row = await db.get(KbRetrievalLog, r.log_id)
        assert row.consumer == "chat" and row.user_id == 7 and row.project_id == PID
        assert row.hits and row.hits[0]["chunk_id"] == s["c4"].id
        assert row.latency_ms >= 0

    async def test_empty_result_also_logged(self, db, monkeypatch):
        await _seed(db)
        _patch_recalls(monkeypatch, vector=[], fulltext=[])
        r = await rs.search(db, project_id=PID, query="无命中查询")
        assert r.log_id is not None


class TestFormatForLlm:
    async def test_citation_header_format(self, db, monkeypatch):
        s = await _seed(db)
        _patch_recalls(monkeypatch, vector=[(s["c4"].id, 0.9)], fulltext=[])
        r = await rs.search(db, project_id=PID, query="q")
        text = rs.format_hits_for_llm(r.hits)
        assert text.startswith("[1]《API.md》 › 登录接口")
        assert rs.format_hits_for_llm([]) == ""
