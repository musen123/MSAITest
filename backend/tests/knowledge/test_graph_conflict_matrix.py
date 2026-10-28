"""P1b TB3.3 图谱冲突矩阵（验收①固化）

人工维护 × 自动重抽的全部冲突面：
  编辑后重抽不回退 / 改名后重抽不分裂(旧名重定向) / 删除后重抽不复活 /
  合并后重抽不分裂 / 关系编辑不回退 / 关系删除不复活 /
  文档 GC 不伤手工与人工编辑行 / 合并后删文档重定向行存活。
"""

import pytest
from sqlalchemy import func, select

from app.core.exceptions import BusinessException
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import KbEntity, KbEntityMention, KbRelation
from app.services.knowledge import graph_extract as gx
from app.services.knowledge import graph_service as gs
from app.services.knowledge import knowledge_service as ks
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase

pytestmark = pytest.mark.unit

PID = 403


async def _seed_doc(db, name="prd.md"):
    kb = (await db.execute(
        select(ProjectKnowledgeBase).where(ProjectKnowledgeBase.project_id == PID)
    )).scalar_one_or_none()
    if kb is None:
        db.add(ProjectKnowledgeBase(project_id=PID, status="ready"))
    doc = KbDocument(project_id=PID, file_name=name, file_size=1, file_ext=".md",
                     doc_type="requirement", source_type="text", status="ready",
                     uploaded_by=1, content_md="# 内容")
    db.add(doc)
    await db.flush()
    return doc


def _eagg(name, etype="term", desc="", chunk_ids=None):
    return {"name": name, "type": etype, "description": desc,
            "chunk_ids": set(chunk_ids or [])}


async def _extract(db, doc, names, relations=None):
    """模拟一次自动抽取落库（names: [(name, type, desc)]）"""
    aggs = {gx.normalize_entity_name(n): _eagg(n, t, d) for n, t, d in names}
    rels = {}
    for s, t in (relations or []):
        rels[(gx.normalize_entity_name(s), gx.normalize_entity_name(t))] = {
            "keywords": "关联", "description": "", "chunk_ids": set()}
    stats = await gx.resolve_and_persist(
        db, project_id=PID, document_id=doc.id, entity_aggs=aggs, relation_aggs=rels)
    await db.commit()
    return stats


async def _entity(db, norm):
    return (await db.execute(
        select(KbEntity).where(KbEntity.project_id == PID, KbEntity.name_norm == norm)
    )).scalar_one_or_none()


async def _entity_rows(db, norm):
    return list((await db.execute(
        select(KbEntity).where(KbEntity.project_id == PID, KbEntity.name_norm == norm)
    )).scalars())


class TestEditThenReextract:
    async def test_edit_type_desc_not_reverted(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("退款接口", "term", "自动描述")])
        e = await _entity(db, "退款接口")
        await gs.update_entity(db, project_id=PID, entity_id=e.id,
                               entity_type="api", description="人工校正的描述")
        # 自动重抽给出相反的 type/desc
        await _extract(db, doc, [("退款接口", "term", "又一个自动描述")])
        await db.refresh(e)
        assert e.entity_type == "api" and e.description == "人工校正的描述"
        assert e.human_edited and e.ref_count == 1  # mention 照常,不翻倍

    async def test_rename_leaves_redirect_no_split(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("登陆接口", "api", "")])
        e = await _entity(db, "登陆接口")
        await gs.update_entity(db, project_id=PID, entity_id=e.id, name="登录接口")
        # 重抽命中旧名 → 沿重定向落到改名后的实体,不分裂
        await _extract(db, doc, [("登陆接口", "api", "")])
        await db.refresh(e)
        assert e.name == "登录接口" and e.ref_count == 1
        old_rows = await _entity_rows(db, "登陆接口")
        assert len(old_rows) == 1 and old_rows[0].merged_into_id == e.id

    async def test_rename_conflict_409(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("支付系统", "system", ""), ("收银系统", "system", "")])
        e = await _entity(db, "收银系统")
        with pytest.raises(BusinessException) as ei:
            await gs.update_entity(db, project_id=PID, entity_id=e.id, name="支付系统")
        assert ei.value.code == 409


class TestDeleteThenReextract:
    async def test_tombstone_not_revived(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("废弃概念", "term", "")],)
        e = await _entity(db, "废弃概念")
        await gs.delete_entity(db, project_id=PID, entity_id=e.id)
        stats = await _extract(db, doc, [("废弃概念", "term", "")])
        await db.refresh(e)
        assert stats["tombstone_skipped"] == 1
        assert e.is_deleted and e.ref_count == 0

    async def test_delete_cascades_relation_tombstone(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("A模块", "module", ""), ("B模块", "module", "")],
                       relations=[("A模块", "B模块")])
        a = await _entity(db, "a模块")
        await gs.delete_entity(db, project_id=PID, entity_id=a.id)
        r = (await db.execute(select(KbRelation).where(KbRelation.project_id == PID))
             ).scalar_one()
        assert r.is_deleted
        # 重抽同一关系:关系墓碑不复活(端点也被墓碑拦)
        stats = await _extract(db, doc, [("A模块", "module", ""), ("B模块", "module", "")],
                               relations=[("A模块", "B模块")])
        await db.refresh(r)
        assert r.is_deleted and stats["tombstone_skipped"] == 1


class TestMergeThenReextract:
    async def test_merge_then_reextract_no_split(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("登录接口", "api", ""), ("登陆接口", "api", "")])
        winner = await _entity(db, "登录接口")
        loser = await _entity(db, "登陆接口")
        await gs.merge_entities(db, project_id=PID,
                                source_id=loser.id, target_id=winner.id)
        stats = await _extract(db, doc, [("登陆接口", "api", "旧名再现")])
        await db.refresh(winner)
        await db.refresh(loser)
        assert loser.merged_into_id == winner.id
        assert stats["created"] == 0  # 不分裂
        assert winner.ref_count == 1
        total = (await db.execute(
            select(func.count(KbEntity.id)).where(KbEntity.project_id == PID)
        )).scalar()
        assert total == 2  # 只有胜者+重定向行

    async def test_merge_redirects_relations_and_dedups(self, db):
        doc = await _seed_doc(db)
        await _extract(
            db, doc,
            [("登录接口", "api", ""), ("登陆接口", "api", ""), ("网关服务", "system", "")],
            relations=[("网关服务", "登录接口"), ("网关服务", "登陆接口")],
        )
        winner = await _entity(db, "登录接口")
        loser = await _entity(db, "登陆接口")
        await gs.merge_entities(db, project_id=PID,
                                source_id=loser.id, target_id=winner.id)
        rels = list((await db.execute(
            select(KbRelation).where(KbRelation.project_id == PID)
        )).scalars())
        assert len(rels) == 1  # 网关→登陆 与 网关→登录 合并成一条
        assert rels[0].target_entity_id == winner.id
        assert rels[0].weight == 2.0  # 权重并入

    async def test_merge_guards(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("甲实体", "term", ""), ("乙实体", "term", "")])
        a = await _entity(db, "甲实体")
        b = await _entity(db, "乙实体")
        with pytest.raises(BusinessException):
            await gs.merge_entities(db, project_id=PID, source_id=a.id, target_id=a.id)
        await gs.merge_entities(db, project_id=PID, source_id=a.id, target_id=b.id)
        with pytest.raises(BusinessException):  # 已被合并的行不能再当源
            await gs.merge_entities(db, project_id=PID, source_id=a.id, target_id=b.id)


class TestRelationMaintenance:
    async def test_edited_relation_not_reverted(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("A服务", "system", ""), ("B服务", "system", "")],
                       relations=[("A服务", "B服务")])
        r = (await db.execute(select(KbRelation).where(KbRelation.project_id == PID))
             ).scalar_one()
        await gs.update_relation(db, project_id=PID, relation_id=r.id,
                                 keywords="人工关系词")
        await _extract(db, doc, [("A服务", "system", ""), ("B服务", "system", "")],
                       relations=[("A服务", "B服务")])
        await db.refresh(r)
        assert r.keywords == "人工关系词" and r.human_edited
        assert r.weight == 1.0  # human_edited 关系不再被自动递增

    async def test_deleted_relation_not_revived(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("A服务", "system", ""), ("B服务", "system", "")],
                       relations=[("A服务", "B服务")])
        r = (await db.execute(select(KbRelation).where(KbRelation.project_id == PID))
             ).scalar_one()
        await gs.delete_relation(db, project_id=PID, relation_id=r.id)
        stats = await _extract(db, doc, [("A服务", "system", ""), ("B服务", "system", "")],
                               relations=[("A服务", "B服务")])
        await db.refresh(r)
        assert r.is_deleted and stats["rel_tombstone_skipped"] == 1


class TestDocumentGC:
    async def test_doc_delete_gc_spares_protected_rows(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("自动实体", "term", ""), ("被编辑实体", "term", "")])
        edited = await _entity(db, "被编辑实体")
        await gs.update_entity(db, project_id=PID, entity_id=edited.id,
                               description="人工描述")
        manual = await gs.create_entity(db, project_id=PID, user_id=9,
                                        name="手工实体", entity_type="module")
        # 走真实删除路径（同事务 GC）
        await ks.delete_document_from_kb(db, project_id=PID, kb_doc_id=doc.id)
        assert await _entity(db, "自动实体") is None  # 自动孤儿被 GC
        await db.refresh(edited)
        await db.refresh(manual)
        assert edited.ref_count == 0 and not edited.is_deleted  # 保护位存活
        assert manual.created_by == 9  # 手工行存活

    async def test_merge_redirect_survives_doc_gc(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("正名", "term", ""), ("别名", "term", "")])
        winner = await _entity(db, "正名")
        loser = await _entity(db, "别名")
        await gs.merge_entities(db, project_id=PID,
                                source_id=loser.id, target_id=winner.id)
        # 人工编辑保护胜者,避免 GC 后消失（未编辑的胜者 0 引用会被 GC——设计如此）
        winner_id = winner.id
        await gs.update_entity(db, project_id=PID, entity_id=winner_id,
                               description="保留")
        await ks.delete_document_from_kb(db, project_id=PID, kb_doc_id=doc.id)
        # bulk delete 的 synchronize_session 会把内存旧对象误标 deleted,一律重查
        loser_row = await _entity(db, "别名")
        winner_row = await _entity(db, "正名")
        assert winner_row is not None and winner_row.id == winner_id
        assert loser_row is not None and loser_row.merged_into_id == winner_id  # 重定向行不被 GC

    async def test_deprecate_withdraws_graph_contribution(self, db):
        doc = await _seed_doc(db)
        await _extract(db, doc, [("废弃前实体", "term", "")])
        doc.graph_status = "extracted"
        doc.entity_count = 1
        await db.commit()
        await ks.update_document_meta(db, project_id=PID, kb_doc_id=doc.id,
                                      validity="deprecated")
        await db.refresh(doc)
        assert doc.graph_status == "none" and doc.entity_count == 0
        assert await _entity(db, "废弃前实体") is None
        n_mentions = (await db.execute(
            select(func.count(KbEntityMention.id)).where(
                KbEntityMention.document_id == doc.id)
        )).scalar()
        assert n_mentions == 0
