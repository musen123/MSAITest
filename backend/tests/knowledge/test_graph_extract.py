"""P1b WP-B2 图谱抽取单测：质量闸纯函数矩阵 + resolve 守护语义落库

冻结规则逐条固化：name≥2/黑名单/type 归 term/批≤15/relation 端点闸/自环丢弃;
resolve:重抽替换不累积/墓碑不复活/保护位不覆写/合并沿指针/自动孤儿 GC。
"""

import pytest

from app.services.knowledge import graph_extract as gx
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import (
    KbEntity,
    KbEntityMention,
    KbRelation,
    KbRelationMention,
)

pytestmark = pytest.mark.unit

PID = 402


# ────────────────────────── 纯函数区 ──────────────────────────

class TestNormalize:
    def test_nfkc_case_whitespace(self):
        assert gx.normalize_entity_name("　Ｌｏｇｉｎ  ＡＰＩ ") == "login api"
        assert gx.normalize_entity_name("退款接口") == "退款接口"
        assert gx.normalize_entity_name("A\t\nB") == "a b"
        assert gx.normalize_entity_name("") == ""


class TestValidateBatch:
    def _payload(self, entities=None, relations=None):
        return {"entities": entities or [], "relations": relations or []}

    def test_quality_gates(self):
        ents, _ = gx.validate_batch_payload(
            self._payload(entities=[
                {"name": "系统", "type": "system"},          # 黑名单裸词
                {"name": "支", "type": "module"},            # <2 字
                {"name": "支付系统", "type": "system"},       # 合法
                {"name": "退款接口", "type": "不存在的类型"},   # type 归 term
                {"name": "退款接口", "type": "api"},          # norm 重复丢弃
                {"name": "X" * 200, "type": "term"},         # 超长名
            ]),
            known_norms=set(),
        )
        assert [(e["name"], e["type"]) for e in ents] == [
            ("支付系统", "system"), ("退款接口", "term"),
        ]

    def test_batch_cap_15(self):
        ents, _ = gx.validate_batch_payload(
            self._payload(entities=[
                {"name": f"实体编号{i:02d}", "type": "term"} for i in range(30)
            ]),
            known_norms=set(),
        )
        assert len(ents) == gx.BATCH_MAX_ENTITIES

    def test_relation_endpoint_gate_and_self_loop(self):
        _, rels = gx.validate_batch_payload(
            self._payload(
                entities=[{"name": "支付系统", "type": "system"},
                          {"name": "退款接口", "type": "api"}],
                relations=[
                    {"source": "支付系统", "target": "退款接口", "keywords": "包含"},
                    {"source": "支付系统", "target": "支付系统"},        # 自环
                    {"source": "支付系统", "target": "未抽实体"},         # 端点闸
                    {"source": "支付系统", "target": "历史实体"},         # 跨批端点(known)
                ],
            ),
            known_norms={"历史实体"},
        )
        assert [(r["source"], r["target"]) for r in rels] == [
            ("支付系统", "退款接口"), ("支付系统", "历史实体"),
        ]

    def test_garbage_payload_tolerated(self):
        ents, rels = gx.validate_batch_payload(
            {"entities": ["非字典", {"name": None}], "relations": [42]},
            known_norms=set(),
        )
        assert ents == [] and rels == []


class TestAggregation:
    def test_entity_agg_longest_desc_and_attribution(self):
        aggs: dict = {}
        batch = [{"id": 11, "text": "支付系统负责收单"}, {"id": 12, "text": "无关内容"}]
        gx.merge_entity_aggs(aggs, [{"name": "支付系统", "norm": "支付系统",
                                     "type": "system", "description": "短"}], batch)
        gx.merge_entity_aggs(aggs, [{"name": "支付系统", "norm": "支付系统",
                                     "type": "system", "description": "更长的描述"}],
                             [{"id": 13, "text": "支付系统对接银行"}])
        agg = aggs["支付系统"]
        assert agg["description"] == "更长的描述"
        assert agg["chunk_ids"] == {11, 13}

    def test_relation_agg_needs_both_names_in_chunk(self):
        eaggs: dict = {}
        batch = [{"id": 21, "text": "支付系统 调用 退款接口"}, {"id": 22, "text": "只有支付系统"}]
        for n, t in (("支付系统", "system"), ("退款接口", "api")):
            gx.merge_entity_aggs(eaggs, [{"name": n, "norm": n, "type": t,
                                          "description": ""}], batch)
        raggs: dict = {}
        gx.merge_relation_aggs(
            raggs,
            [{"source": "支付系统", "target": "退款接口", "keywords": "调用", "description": ""}],
            eaggs, batch,
        )
        assert raggs[("支付系统", "退款接口")]["chunk_ids"] == {21}


# ────────────────────────── resolve 落库（守护语义） ──────────────────────────

async def _seed_doc(db, name="prd.md"):
    doc = KbDocument(project_id=PID, file_name=name, file_size=1, file_ext=".md",
                     doc_type="requirement", source_type="text", status="ready",
                     uploaded_by=1)
    db.add(doc)
    await db.flush()
    return doc


def _eagg(name, etype="term", desc="", chunk_ids=None):
    return {"name": name, "type": etype, "description": desc,
            "chunk_ids": set(chunk_ids or [])}


async def _get_entity_by_norm(db, norm):
    from sqlalchemy import select

    return (await db.execute(
        select(KbEntity).where(KbEntity.project_id == PID, KbEntity.name_norm == norm)
    )).scalar_one_or_none()


async def _count(db, model, **where):
    from sqlalchemy import func, select

    stmt = select(func.count(model.id))
    for k, v in where.items():
        stmt = stmt.where(getattr(model, k) == v)
    return (await db.execute(stmt)).scalar()


class TestResolvePersist:
    async def test_fresh_insert_full_chain(self, db):
        doc = await _seed_doc(db)
        stats = await gx.resolve_and_persist(
            db, project_id=PID, document_id=doc.id,
            entity_aggs={
                "支付系统": _eagg("支付系统", "system", "收单系统", [101, 102]),
                "退款接口": _eagg("退款接口", "api", "", []),  # 无归因→文档级 0
            },
            relation_aggs={("支付系统", "退款接口"): {
                "keywords": "包含", "description": "", "chunk_ids": {101}}},
        )
        await db.commit()
        assert stats["entities"] == 2 and stats["created"] == 2
        assert stats["relations"] == 1 and stats["relations_created"] == 1
        e = await _get_entity_by_norm(db, "支付系统")
        assert e.ref_count == 2 and e.doc_count == 1
        e2 = await _get_entity_by_norm(db, "退款接口")
        assert e2.ref_count == 1  # chunk_id=0 文档级出处
        assert await _count(db, KbRelationMention) == 1

    async def test_reextract_replaces_not_accumulates(self, db):
        doc = await _seed_doc(db)
        aggs = {"支付系统": _eagg("支付系统", "system", "", [1])}
        rels = {}
        await gx.resolve_and_persist(db, project_id=PID, document_id=doc.id,
                                     entity_aggs=aggs, relation_aggs=rels)
        await db.commit()
        await gx.resolve_and_persist(db, project_id=PID, document_id=doc.id,
                                     entity_aggs=aggs, relation_aggs=rels)
        await db.commit()
        e = await _get_entity_by_norm(db, "支付系统")
        assert e.ref_count == 1  # mention 不翻倍
        assert await _count(db, KbEntityMention, document_id=doc.id) == 1

    async def test_relation_weight_increment_across_docs(self, db):
        d1 = await _seed_doc(db, "a.md")
        d2 = await _seed_doc(db, "b.md")
        aggs = {"支付系统": _eagg("支付系统", "system"),
                "退款接口": _eagg("退款接口", "api")}
        rel = {("支付系统", "退款接口"): {"keywords": "调用", "description": "", "chunk_ids": set()}}
        await gx.resolve_and_persist(db, project_id=PID, document_id=d1.id,
                                     entity_aggs=aggs, relation_aggs=rel)
        await db.commit()
        await gx.resolve_and_persist(db, project_id=PID, document_id=d2.id,
                                     entity_aggs=aggs, relation_aggs=rel)
        await db.commit()
        from sqlalchemy import select

        r = (await db.execute(select(KbRelation).where(KbRelation.project_id == PID))
             ).scalar_one()
        assert r.weight == 2.0 and r.ref_count == 2

    async def test_tombstone_blocks_revival(self, db):
        doc = await _seed_doc(db)
        db.add(KbEntity(project_id=PID, name="已删实体", name_norm="已删实体",
                        is_deleted=True))
        await db.flush()
        stats = await gx.resolve_and_persist(
            db, project_id=PID, document_id=doc.id,
            entity_aggs={
                "已删实体": _eagg("已删实体"),
                "存活实体": _eagg("存活实体"),
            },
            relation_aggs={("存活实体", "已删实体"): {
                "keywords": "", "description": "", "chunk_ids": set()}},
        )
        await db.commit()
        assert stats["tombstone_skipped"] == 1
        assert stats["dropped_endpoints"] == 1  # 端点被墓碑拦
        tomb = await _get_entity_by_norm(db, "已删实体")
        assert tomb.is_deleted and tomb.ref_count == 0
        assert await _count(db, KbEntityMention, entity_id=tomb.id) == 0

    async def test_human_edited_not_overwritten(self, db):
        doc = await _seed_doc(db)
        db.add(KbEntity(project_id=PID, name="人工实体", name_norm="人工实体",
                        entity_type="module", description="人工描述", human_edited=True))
        await db.flush()
        stats = await gx.resolve_and_persist(
            db, project_id=PID, document_id=doc.id,
            entity_aggs={"人工实体": _eagg("人工实体", "term", "自动新描述", [7])},
            relation_aggs={},
        )
        await db.commit()
        assert stats["mention_only"] == 1
        e = await _get_entity_by_norm(db, "人工实体")
        assert e.entity_type == "module" and e.description == "人工描述"
        assert e.ref_count == 1  # mention 照加

    async def test_merged_redirect_lands_on_winner(self, db):
        doc = await _seed_doc(db)
        winner = KbEntity(project_id=PID, name="登录接口", name_norm="登录接口",
                          entity_type="api")
        db.add(winner)
        await db.flush()
        db.add(KbEntity(project_id=PID, name="登陆接口", name_norm="登陆接口",
                        merged_into_id=winner.id))
        await db.flush()
        await gx.resolve_and_persist(
            db, project_id=PID, document_id=doc.id,
            entity_aggs={"登陆接口": _eagg("登陆接口", "api", "旧名再现", [3])},
            relation_aggs={},
        )
        await db.commit()
        await db.refresh(winner)
        assert winner.ref_count == 1  # mention 落在胜者
        loser = await _get_entity_by_norm(db, "登陆接口")
        assert loser.ref_count == 0

    async def test_auto_orphan_gc_on_reextract(self, db):
        doc = await _seed_doc(db)
        await gx.resolve_and_persist(
            db, project_id=PID, document_id=doc.id,
            entity_aggs={"旧实体": _eagg("旧实体"), "常驻实体": _eagg("常驻实体")},
            relation_aggs={},
        )
        await db.commit()
        stats = await gx.resolve_and_persist(
            db, project_id=PID, document_id=doc.id,
            entity_aggs={"常驻实体": _eagg("常驻实体")},
            relation_aggs={},
        )
        await db.commit()
        assert stats["gc_entities"] == 1
        assert await _get_entity_by_norm(db, "旧实体") is None
        assert (await _get_entity_by_norm(db, "常驻实体")).ref_count == 1


class TestRegistry:
    def test_kb_extract_registered(self):
        import app.ai_core.graphs.knowledge  # noqa: F401 —— 触发包导入注册

        from app.ai_core.runtime import registry

        spec = registry.get("kb_extract")
        assert spec is not None and spec.llm_kind == "text" and spec.dedupe
