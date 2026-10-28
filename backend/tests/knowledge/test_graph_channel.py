"""P2 WP-C2 图增强检索第三路单测

铁律验证:开关关=与既有结果完全一致(零影响);开=图路 chunk 进入融合且
graph_boosted=true;直接命中种子的块排在仅邻居提及的块之前;墓碑/合并行不参与;
图路失败静默(不进 degraded)。
"""

import pytest

import app.services.knowledge.retrieval_service as rs
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import KbEntity, KbEntityMention, KbRelation
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

pytestmark = pytest.mark.unit

PID = 405


async def _seed_base(db, *, graph_channel: bool):
    kb = ProjectKnowledgeBase(
        project_id=PID, status="ready", index_version=1,
        settings={"graph_channel": graph_channel} if graph_channel else None,
    )
    db.add(kb)
    doc = KbDocument(project_id=PID, file_name="prd.md", file_size=1, file_ext=".md",
                     doc_type="requirement", source_type="text", status="ready",
                     uploaded_by=1)
    db.add(doc)
    await db.flush()
    chunks = []
    for i, content in enumerate(["支付相关内容", "退款接口说明", "无关的登录内容"]):
        c = KbChunk(project_id=PID, document_id=doc.id, seq=i, chunk_type="text",
                    heading_path="", content=content, char_len=len(content),
                    token_len=10, content_hash=str(i), embedding=b"\x00" * 8)
        db.add(c)
        chunks.append(c)
    await db.flush()
    return kb, doc, chunks


async def _seed_graph(db, doc, chunks):
    """实体:支付系统(种子候选,mention→chunk0)——邻居:退款接口(mention→chunk1)"""
    pay = KbEntity(project_id=PID, name="支付系统", name_norm="支付系统",
                   entity_type="system", ref_count=3)
    refund = KbEntity(project_id=PID, name="退款接口", name_norm="退款接口",
                      entity_type="api", ref_count=1)
    tomb = KbEntity(project_id=PID, name="支付系统旧名", name_norm="支付系统旧名",
                    is_deleted=True, ref_count=99)
    db.add_all([pay, refund, tomb])
    await db.flush()
    db.add(KbRelation(project_id=PID, source_entity_id=pay.id,
                      target_entity_id=refund.id, keywords="包含"))
    db.add(KbEntityMention(project_id=PID, entity_id=pay.id,
                           document_id=doc.id, chunk_id=chunks[0].id))
    db.add(KbEntityMention(project_id=PID, entity_id=refund.id,
                           document_id=doc.id, chunk_id=chunks[1].id))
    await db.flush()
    return pay, refund


class TestGraphRecall:
    async def test_empty_graph_returns_empty(self, db):
        await _seed_base(db, graph_channel=True)
        assert await rs._graph_recall(db, project_id=PID, query="支付系统的退款") == []

    async def test_seed_chunk_ranks_before_neighbor_chunk(self, db):
        _, doc, chunks = await _seed_base(db, graph_channel=True)
        await _seed_graph(db, doc, chunks)
        hits = await rs._graph_recall(db, project_id=PID, query="支付系统的退款时效是什么")
        ids = [cid for cid, _ in hits]
        assert ids[0] == chunks[0].id  # 直接命中种子实体的块在前
        assert chunks[1].id in ids  # 1-hop 邻居的块也进入
        assert chunks[2].id not in ids  # 无 mention 的块不出现

    async def test_no_entity_match_in_query(self, db):
        _, doc, chunks = await _seed_base(db, graph_channel=True)
        await _seed_graph(db, doc, chunks)
        assert await rs._graph_recall(db, project_id=PID, query="登录锁定策略") == []

    async def test_tombstone_not_matched(self, db):
        _, doc, chunks = await _seed_base(db, graph_channel=True)
        await _seed_graph(db, doc, chunks)
        hits = await rs._graph_recall(db, project_id=PID, query="支付系统旧名 相关")
        # 「支付系统旧名」含「支付系统」子串→种子仍是活跃实体;墓碑行(ref=99)不参与
        assert all(cid != chunks[2].id for cid, _ in hits)


class TestSearchIntegration:
    @pytest.fixture(autouse=True)
    def stub_recalls(self, monkeypatch):
        async def fake_vec(db_, *, kb, query, prefer_user_id=None):
            return []

        async def fake_ft(*, project_id, query, doc_types=None):
            return list(self._ft_hits)

        monkeypatch.setattr(rs, "_vector_recall", fake_vec)
        monkeypatch.setattr(rs, "_fulltext_recall", fake_ft)
        self._ft_hits = []

    async def test_switch_off_zero_impact(self, db):
        _, doc, chunks = await _seed_base(db, graph_channel=False)
        await _seed_graph(db, doc, chunks)
        self._ft_hits = [(chunks[2].id, 1.0)]
        data = await rs.search(db, project_id=PID, query="支付系统的退款")
        assert data.graph_boosted is False
        assert [h.chunk_id for h in data.hits] == [chunks[2].id]  # 仅全文路结果

    async def test_switch_on_graph_chunks_fused(self, db):
        _, doc, chunks = await _seed_base(db, graph_channel=True)
        await _seed_graph(db, doc, chunks)
        self._ft_hits = [(chunks[2].id, 1.0)]
        data = await rs.search(db, project_id=PID, query="支付系统的退款")
        assert data.graph_boosted is True
        got = {h.chunk_id for h in data.hits}
        assert chunks[0].id in got and chunks[1].id in got  # 图路块进入结果

    async def test_graph_failure_silent(self, db, monkeypatch):
        _, doc, chunks = await _seed_base(db, graph_channel=True)
        await _seed_graph(db, doc, chunks)
        self._ft_hits = [(chunks[2].id, 1.0)]

        async def boom(db_, *, project_id, query):
            raise RuntimeError("graph down")

        monkeypatch.setattr(rs, "_graph_recall", boom)
        data = await rs.search(db, project_id=PID, query="支付系统的退款")
        assert data.graph_boosted is False
        assert data.degraded.fulltext is False  # 增强路失败不进 degraded
        assert [h.chunk_id for h in data.hits] == [chunks[2].id]
