"""P2 WP-C3 RERANK 单测：客户端契约 + 深度模式三级回退链

客户端:完整置换/部分返回补尾/垃圾载荷 None/HTTP 错误 None;
集成:有配置走 API(reranked=True 且顺序生效)/无配置回退 listwise/都无回 RRF 原序。
"""

import httpx
import pytest

import app.services.knowledge.rerank_client as rc
import app.services.knowledge.retrieval_service as rs

pytestmark = pytest.mark.unit


class _Cfg:
    base_url = "http://rerank.local/v1"
    model = "bge-reranker-v2-m3"
    api_key = "sk-test"
    is_active = True


_RealAsyncClient = httpx.AsyncClient  # patch 前捕获,防工厂递归调用被替换的符号


def _client_with(handler):
    """monkeypatch httpx.AsyncClient 构造为 MockTransport 版本"""
    def factory(*args, **kwargs):
        return _RealAsyncClient(
            transport=httpx.MockTransport(handler), timeout=5
        )
    return factory


class TestRerankClient:
    async def test_full_permutation(self, monkeypatch):
        def handler(request):
            assert request.url.path.endswith("/rerank")
            assert request.headers["authorization"] == "Bearer sk-test"
            return httpx.Response(200, json={"results": [
                {"index": 2, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.5},
                {"index": 1, "relevance_score": 0.1},
            ]})

        monkeypatch.setattr(rc.httpx, "AsyncClient", _client_with(handler))
        order = await rc.api_rerank(_Cfg(), query="q", documents=["a", "b", "c"])
        assert order == [2, 0, 1]

    async def test_partial_results_pad_tail(self, monkeypatch):
        def handler(request):
            return httpx.Response(200, json={"results": [{"index": 1, "relevance_score": 0.9}]})

        monkeypatch.setattr(rc.httpx, "AsyncClient", _client_with(handler))
        order = await rc.api_rerank(_Cfg(), query="q", documents=["a", "b", "c"])
        assert order == [1, 0, 2]  # 缺失下标按原序补尾

    async def test_garbage_and_http_error(self, monkeypatch):
        monkeypatch.setattr(
            rc.httpx, "AsyncClient",
            _client_with(lambda r: httpx.Response(200, json={"results": "垃圾"})),
        )
        assert await rc.api_rerank(_Cfg(), query="q", documents=["a"]) is None
        monkeypatch.setattr(
            rc.httpx, "AsyncClient",
            _client_with(lambda r: httpx.Response(500, json={})),
        )
        assert await rc.api_rerank(_Cfg(), query="q", documents=["a"]) is None

    async def test_out_of_range_index_dropped(self, monkeypatch):
        def handler(request):
            return httpx.Response(200, json={"results": [
                {"index": 9}, {"index": 0}, {"index": 0},
            ]})

        monkeypatch.setattr(rc.httpx, "AsyncClient", _client_with(handler))
        order = await rc.api_rerank(_Cfg(), query="q", documents=["a", "b"])
        assert order == [0, 1]  # 越界丢弃、重复去重、补尾


class TestDeepFallbackChain:
    """search() 深度重排三级回退（打桩 _api_rerank_channel/_listwise_rerank 观测选路）"""

    @pytest.fixture()
    async def seeded(self, db):
        from app.models.knowledge.chunk import KbChunk
        from app.models.knowledge.document import KbDocument
        from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

        pid = 406
        db.add(ProjectKnowledgeBase(project_id=pid, status="ready", index_version=1))
        doc = KbDocument(project_id=pid, file_name="d.md", file_size=1, file_ext=".md",
                         doc_type="requirement", source_type="text", status="ready",
                         uploaded_by=1)
        db.add(doc)
        await db.flush()
        ids = []
        for i in range(3):
            c = KbChunk(project_id=pid, document_id=doc.id, seq=i, chunk_type="text",
                        heading_path="", content=f"内容{i}", char_len=3, token_len=3,
                        content_hash=str(i), embedding=b"\x00" * 8)
            db.add(c)
            await db.flush()
            ids.append(c.id)
        await db.commit()
        return pid, ids

    @pytest.fixture(autouse=True)
    def stub_recalls(self, monkeypatch):
        async def fake_vec(db_, *, kb, query, prefer_user_id=None):
            return []

        monkeypatch.setattr(rs, "_vector_recall", fake_vec)
        monkeypatch.setattr(
            rs, "_fulltext_recall",
            lambda *, project_id, query, doc_types=None: self._ft(),
        )

    async def _ft(self):
        return list(self._ft_hits)

    async def test_api_channel_wins(self, db, seeded, monkeypatch):
        pid, ids = seeded
        self._ft_hits = [(ids[0], 1.0), (ids[1], 0.9), (ids[2], 0.8)]

        async def fake_api(db_, **kw):
            return [(ids[2], 1.0), (ids[0], 0.9), (ids[1], 0.8)], True

        async def fail_listwise(*a, **kw):
            raise AssertionError("API 通道成功时不应触发 listwise")

        monkeypatch.setattr(rs, "_api_rerank_channel", fake_api)
        monkeypatch.setattr(rs, "_listwise_rerank", fail_listwise)
        data = await rs.search(db, project_id=pid, query="查询词", deep=True)
        assert data.reranked is True
        assert [h.chunk_id for h in data.hits][:3] == [ids[2], ids[0], ids[1]]

    async def test_fallback_to_listwise(self, db, seeded, monkeypatch):
        pid, ids = seeded
        self._ft_hits = [(ids[0], 1.0), (ids[1], 0.9), (ids[2], 0.8)]

        async def fake_api(db_, **kw):
            return None  # 无 RERANK 配置

        async def fake_listwise(text_llm, query, fused, chunk_map):
            return list(reversed(fused)), True

        monkeypatch.setattr(rs, "_api_rerank_channel", fake_api)
        monkeypatch.setattr(rs, "_listwise_rerank", fake_listwise)
        data = await rs.search(db, project_id=pid, query="查询词", deep=True,
                               text_llm=object())
        assert data.reranked is True
        assert [h.chunk_id for h in data.hits][0] == ids[2]

    async def test_no_channel_keeps_rrf_order(self, db, seeded, monkeypatch):
        pid, ids = seeded
        self._ft_hits = [(ids[0], 1.0), (ids[1], 0.9)]

        async def fake_api(db_, **kw):
            return None

        monkeypatch.setattr(rs, "_api_rerank_channel", fake_api)
        data = await rs.search(db, project_id=pid, query="查询词", deep=True)
        assert data.reranked is False
        assert [h.chunk_id for h in data.hits] == [ids[0], ids[1]]
