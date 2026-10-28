"""P1b WP-B1 图谱 crud 单测：台账重算 / 孤儿 GC 守护 / 热门序 / 文档级清台账

计数纪律验证：ref_count/doc_count/total_nodes/total_edges 永远从台账与存活行重算,
不做增量加减——这里固化「重算正确 + GC 只碰自动行」两条地基。
"""

import pytest

from app.crud.knowledge.graph import crud_kb_graph
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import (
    KbEntity,
    KbEntityMention,
    KbRelation,
    KbRelationMention,
)
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

pytestmark = pytest.mark.unit

PID = 401


async def _seed_doc(db, name="prd.md"):
    doc = KbDocument(
        project_id=PID, file_name=name, file_size=1, file_ext=".md",
        doc_type="requirement", source_type="text", status="ready", uploaded_by=1,
    )
    db.add(doc)
    await db.flush()
    return doc


def _entity(name, **kw):
    return KbEntity(project_id=PID, name=name, name_norm=name.lower(), **kw)


class TestRecount:
    async def test_ref_and_doc_count_from_ledger(self, db):
        d1 = await _seed_doc(db, "a.md")
        d2 = await _seed_doc(db, "b.md")
        e = _entity("退款接口", entity_type="api")
        db.add(e)
        await db.flush()
        db.add_all([
            KbEntityMention(project_id=PID, entity_id=e.id, document_id=d1.id, chunk_id=1),
            KbEntityMention(project_id=PID, entity_id=e.id, document_id=d1.id, chunk_id=2),
            KbEntityMention(project_id=PID, entity_id=e.id, document_id=d2.id, chunk_id=0),
        ])
        await db.flush()
        await crud_kb_graph.recount_entities(db, entity_ids=[e.id])
        await db.refresh(e)
        assert e.ref_count == 3 and e.doc_count == 2

    async def test_totals_exclude_tombstone_and_merged(self, db):
        db.add(ProjectKnowledgeBase(project_id=PID, status="ready"))
        alive = _entity("支付模块", entity_type="module")
        tomb = _entity("废弃实体", is_deleted=True)
        merged = _entity("旧名", merged_into_id=999)
        db.add_all([alive, tomb, merged])
        await db.flush()
        db.add(KbRelation(project_id=PID, source_entity_id=alive.id,
                          target_entity_id=tomb.id))
        db.add(KbRelation(project_id=PID, source_entity_id=tomb.id,
                          target_entity_id=alive.id, is_deleted=True))
        await db.flush()
        nodes, edges = await crud_kb_graph.recount_totals(db, project_id=PID)
        assert nodes == 1 and edges == 1


class TestDocumentLedgerGC:
    async def test_delete_mentions_returns_affected(self, db):
        doc = await _seed_doc(db)
        e = _entity("登录页")
        db.add(e)
        await db.flush()
        r = KbRelation(project_id=PID, source_entity_id=e.id, target_entity_id=e.id)
        db.add(r)
        await db.flush()
        db.add(KbEntityMention(project_id=PID, entity_id=e.id, document_id=doc.id))
        db.add(KbRelationMention(project_id=PID, relation_id=r.id, document_id=doc.id))
        await db.flush()
        ent_ids, rel_ids = await crud_kb_graph.delete_mentions_by_document(
            db, document_id=doc.id
        )
        assert ent_ids == [e.id] and rel_ids == [r.id]
        ent_ids2, rel_ids2 = await crud_kb_graph.delete_mentions_by_document(
            db, document_id=doc.id
        )
        assert ent_ids2 == [] and rel_ids2 == []


class TestOrphanGC:
    async def test_gc_only_touches_automatic_rows(self, db):
        plain = _entity("自动孤儿")
        human = _entity("人工编辑过", human_edited=True)
        manual = _entity("手工创建", created_by=9)
        tomb = _entity("墓碑", is_deleted=True)
        merged = _entity("被合并", merged_into_id=1)
        db.add_all([plain, human, manual, tomb, merged])
        await db.flush()
        ids = [plain.id, human.id, manual.id, tomb.id, merged.id]
        deleted_rel, deleted_ent = await crud_kb_graph.delete_orphans(
            db, project_id=PID, entity_ids=ids, relation_ids=[]
        )
        assert deleted_ent == 1
        survivors = await crud_kb_graph.get_entities_by_ids(
            db, project_id=PID, entity_ids=ids
        )
        assert {e.name for e in survivors} == {"人工编辑过", "手工创建", "墓碑", "被合并"}

    async def test_gc_skips_referenced_rows(self, db):
        doc = await _seed_doc(db)
        e = _entity("仍被引用")
        db.add(e)
        await db.flush()
        db.add(KbEntityMention(project_id=PID, entity_id=e.id, document_id=doc.id))
        await db.flush()
        await crud_kb_graph.recount_entities(db, entity_ids=[e.id])
        _, deleted = await crud_kb_graph.delete_orphans(
            db, project_id=PID, entity_ids=[e.id], relation_ids=[]
        )
        assert deleted == 0


class TestQueries:
    async def test_popular_orders_by_ref_and_hides_dead(self, db):
        hot = _entity("热门", ref_count=9)
        cold = _entity("冷门", ref_count=1)
        dead = _entity("死行", ref_count=99, is_deleted=True)
        db.add_all([hot, cold, dead])
        await db.flush()
        rows = await crud_kb_graph.list_popular_entities(db, project_id=PID, limit=10)
        assert [e.name for e in rows] == ["热门", "冷门"]

    async def test_cross_project_invisible(self, db):
        e = _entity("本项目")
        db.add(e)
        await db.flush()
        assert await crud_kb_graph.get_entity(db, project_id=PID + 1, entity_id=e.id) is None
        assert await crud_kb_graph.get_entities_by_norms(
            db, project_id=PID + 1, name_norms=["本项目"]
        ) == []

    async def test_relations_touching_both_directions(self, db):
        a, b, c = _entity("A"), _entity("B"), _entity("C")
        db.add_all([a, b, c])
        await db.flush()
        db.add_all([
            KbRelation(project_id=PID, source_entity_id=a.id, target_entity_id=b.id),
            KbRelation(project_id=PID, source_entity_id=c.id, target_entity_id=a.id),
            KbRelation(project_id=PID, source_entity_id=b.id, target_entity_id=c.id,
                       is_deleted=True),
        ])
        await db.flush()
        rows = await crud_kb_graph.list_relations_touching(
            db, project_id=PID, entity_ids=[a.id]
        )
        assert len(rows) == 2  # 出边 A→B + 入边 C→A;墓碑边不出现
