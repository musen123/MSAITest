"""知识图谱 CRUD（P1b 四表数据访问层）

设计文档《知识库自研-总体设计方案》§4.2：

⚠ 事务约定（同 crud/knowledge/chunk.py）：所有**写**方法一律不 commit——
kb_extract 的 resolve/finalize 与维护 service 的「删 mention + 重算计数 + 孤儿清理」
必须在同一事务内原子完成，事务边界归调用方所有。

计数纪律：ref_count/doc_count/total_nodes/total_edges 的**唯一事实源是 mention 台账
与实体/关系存活行**，一切计数变更走本文件的 recount_* 单点函数（correlated 子查询
重算，不做增量加减）——计数永远可重建，不怕漂移。

隔离纪律：凡按 id 取行的方法都带 project_id 过滤（归属校验铁律，跨项目即拿不到行）；
resolve 批量方法以 project_id 为第一过滤条件。
"""

from typing import Optional, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge.graph import (
    KbEntity,
    KbEntityMention,
    KbRelation,
    KbRelationMention,
)
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase


class CRUDKbGraph:
    """知识图谱四表 CRUD"""

    # ────────────────────────── 实体 · 读 ──────────────────────────

    async def get_entity(
        self, db: AsyncSession, *, project_id: int, entity_id: int
    ) -> Optional[KbEntity]:
        stmt = select(KbEntity).where(
            KbEntity.project_id == project_id, KbEntity.id == entity_id
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_entities_by_norms(
        self, db: AsyncSession, *, project_id: int, name_norms: Sequence[str]
    ) -> list[KbEntity]:
        """按归一键批量取行（**含墓碑与合并行**——resolve 需要看到它们才能跳过/沿指针）"""
        if not name_norms:
            return []
        stmt = select(KbEntity).where(
            KbEntity.project_id == project_id, KbEntity.name_norm.in_(name_norms)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def list_popular_entities(
        self, db: AsyncSession, *, project_id: int, limit: int = 100
    ) -> list[KbEntity]:
        """热门实体（活跃行按 ref_count 降序，走 idx_kb_entity_project_hot 索引序）"""
        stmt = (
            select(KbEntity)
            .where(
                KbEntity.project_id == project_id,
                KbEntity.is_deleted.is_(False),
                KbEntity.merged_into_id.is_(None),
            )
            .order_by(KbEntity.ref_count.desc(), KbEntity.id.asc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def search_entities(
        self, db: AsyncSession, *, project_id: int, keyword: str, limit: int = 50
    ) -> list[KbEntity]:
        """实体名模糊搜索（标签搜索框；活跃行）"""
        stmt = (
            select(KbEntity)
            .where(
                KbEntity.project_id == project_id,
                KbEntity.is_deleted.is_(False),
                KbEntity.merged_into_id.is_(None),
                KbEntity.name.like(f"%{keyword}%"),
            )
            .order_by(KbEntity.ref_count.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_entities_by_ids(
        self, db: AsyncSession, *, project_id: int, entity_ids: Sequence[int]
    ) -> list[KbEntity]:
        if not entity_ids:
            return []
        stmt = select(KbEntity).where(
            KbEntity.project_id == project_id, KbEntity.id.in_(entity_ids)
        )
        return list((await db.execute(stmt)).scalars().all())

    # ────────────────────────── 关系 · 读 ──────────────────────────

    async def get_relation(
        self, db: AsyncSession, *, project_id: int, relation_id: int
    ) -> Optional[KbRelation]:
        stmt = select(KbRelation).where(
            KbRelation.project_id == project_id, KbRelation.id == relation_id
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_relations_by_pairs(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        pairs: Sequence[tuple[int, int]],
    ) -> list[KbRelation]:
        """按 (source,target) 有向对批量取行（含墓碑——resolve 防复活需要看到）"""
        if not pairs:
            return []
        source_ids = {p[0] for p in pairs}
        stmt = select(KbRelation).where(
            KbRelation.project_id == project_id,
            KbRelation.source_entity_id.in_(source_ids),
        )
        rows = (await db.execute(stmt)).scalars().all()
        want = set(pairs)
        return [
            r for r in rows if (r.source_entity_id, r.target_entity_id) in want
        ]

    async def list_relations_touching(
        self, db: AsyncSession, *, project_id: int, entity_ids: Sequence[int]
    ) -> list[KbRelation]:
        """取一批实体的全部出边+入边（BFS 每层两条索引 IN 查询合并写法；活跃行）"""
        if not entity_ids:
            return []
        ids = list(entity_ids)
        stmt = select(KbRelation).where(
            KbRelation.project_id == project_id,
            KbRelation.is_deleted.is_(False),
            (
                KbRelation.source_entity_id.in_(ids)
                | KbRelation.target_entity_id.in_(ids)
            ),
        )
        return list((await db.execute(stmt)).scalars().all())

    async def list_relations_of_entity(
        self, db: AsyncSession, *, project_id: int, entity_id: int
    ) -> list[KbRelation]:
        """某实体的全部关系行（**含墓碑**，维护语义用：删除/合并要连带处理）"""
        stmt = select(KbRelation).where(
            KbRelation.project_id == project_id,
            (
                (KbRelation.source_entity_id == entity_id)
                | (KbRelation.target_entity_id == entity_id)
            ),
        )
        return list((await db.execute(stmt)).scalars().all())

    # ────────────────────────── mention · 写（不 commit） ──────────────────────────

    async def delete_mentions_by_document(
        self, db: AsyncSession, *, document_id: int
    ) -> tuple[list[int], list[int]]:
        """按文档一把清两类 mention（重抽替换/文档删除 GC 入口）。

        返回 (受影响 entity_ids, 受影响 relation_ids)——调用方随后 recount。
        """
        entity_ids = list(
            (
                await db.execute(
                    select(KbEntityMention.entity_id.distinct()).where(
                        KbEntityMention.document_id == document_id
                    )
                )
            ).scalars()
        )
        relation_ids = list(
            (
                await db.execute(
                    select(KbRelationMention.relation_id.distinct()).where(
                        KbRelationMention.document_id == document_id
                    )
                )
            ).scalars()
        )
        await db.execute(
            delete(KbEntityMention).where(KbEntityMention.document_id == document_id)
        )
        await db.execute(
            delete(KbRelationMention).where(
                KbRelationMention.document_id == document_id
            )
        )
        return entity_ids, relation_ids

    async def move_entity_mentions(
        self, db: AsyncSession, *, from_entity_id: int, to_entity_id: int
    ) -> None:
        """合并：败者 mention 迁移到胜者（(doc,chunk) 撞唯一键的重复行直接删）"""
        existing = set(
            (
                await db.execute(
                    select(
                        KbEntityMention.document_id, KbEntityMention.chunk_id
                    ).where(KbEntityMention.entity_id == to_entity_id)
                )
            ).all()
        )
        rows = (
            await db.execute(
                select(KbEntityMention).where(
                    KbEntityMention.entity_id == from_entity_id
                )
            )
        ).scalars().all()
        for m in rows:
            if (m.document_id, m.chunk_id) in existing:
                await db.delete(m)
            else:
                m.entity_id = to_entity_id
                existing.add((m.document_id, m.chunk_id))
        await db.flush()

    async def move_relation_mentions(
        self, db: AsyncSession, *, from_relation_id: int, to_relation_id: int
    ) -> None:
        """合并去重时：败者边 mention 迁移到胜者边（撞唯一键的重复行直接删）"""
        existing = set(
            (
                await db.execute(
                    select(
                        KbRelationMention.document_id, KbRelationMention.chunk_id
                    ).where(KbRelationMention.relation_id == to_relation_id)
                )
            ).all()
        )
        rows = (
            await db.execute(
                select(KbRelationMention).where(
                    KbRelationMention.relation_id == from_relation_id
                )
            )
        ).scalars().all()
        for m in rows:
            if (m.document_id, m.chunk_id) in existing:
                await db.delete(m)
            else:
                m.relation_id = to_relation_id
                existing.add((m.document_id, m.chunk_id))
        await db.flush()

    # ────────────────────────── 计数重算（单点，不 commit） ──────────────────────────

    async def recount_entities(
        self, db: AsyncSession, *, entity_ids: Sequence[int]
    ) -> None:
        """ref_count/doc_count 从台账重算（correlated 子查询，MySQL/SQLite 通吃）"""
        if not entity_ids:
            return
        ref_sq = (
            select(func.count(KbEntityMention.id))
            .where(KbEntityMention.entity_id == KbEntity.id)
            .scalar_subquery()
        )
        doc_sq = (
            select(func.count(KbEntityMention.document_id.distinct()))
            .where(KbEntityMention.entity_id == KbEntity.id)
            .scalar_subquery()
        )
        await db.execute(
            update(KbEntity)
            .where(KbEntity.id.in_(list(entity_ids)))
            .values(ref_count=ref_sq, doc_count=doc_sq)
        )

    async def recount_relations(
        self, db: AsyncSession, *, relation_ids: Sequence[int]
    ) -> None:
        if not relation_ids:
            return
        ref_sq = (
            select(func.count(KbRelationMention.id))
            .where(KbRelationMention.relation_id == KbRelation.id)
            .scalar_subquery()
        )
        await db.execute(
            update(KbRelation)
            .where(KbRelation.id.in_(list(relation_ids)))
            .values(ref_count=ref_sq)
        )

    async def recount_totals(self, db: AsyncSession, *, project_id: int) -> tuple[int, int]:
        """total_nodes/total_edges 重算并回写 kb 行，返回 (nodes, edges)"""
        nodes = (
            await db.execute(
                select(func.count(KbEntity.id)).where(
                    KbEntity.project_id == project_id,
                    KbEntity.is_deleted.is_(False),
                    KbEntity.merged_into_id.is_(None),
                )
            )
        ).scalar() or 0
        edges = (
            await db.execute(
                select(func.count(KbRelation.id)).where(
                    KbRelation.project_id == project_id,
                    KbRelation.is_deleted.is_(False),
                )
            )
        ).scalar() or 0
        await db.execute(
            update(ProjectKnowledgeBase)
            .where(ProjectKnowledgeBase.project_id == project_id)
            .values(total_nodes=int(nodes), total_edges=int(edges))
        )
        return int(nodes), int(edges)

    # ────────────────────────── 孤儿清理（GC，不 commit） ──────────────────────────

    async def delete_orphans(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        entity_ids: Sequence[int],
        relation_ids: Sequence[int],
    ) -> tuple[int, int]:
        """删除零引用的**自动**行（手工创建/human_edited/墓碑/合并指针行永不 GC）。

        先删关系再删实体（实体物理删会 CASCADE 掉关系，但显式顺序让 rowcount 可审计）。
        返回 (删除关系数, 删除实体数)。调用方须先 recount 再 GC。
        """
        deleted_rel = 0
        if relation_ids:
            r = await db.execute(
                delete(KbRelation).where(
                    KbRelation.project_id == project_id,
                    KbRelation.id.in_(list(relation_ids)),
                    KbRelation.ref_count == 0,
                    KbRelation.created_by.is_(None),
                    KbRelation.human_edited.is_(False),
                    KbRelation.is_deleted.is_(False),
                )
            )
            deleted_rel = int(r.rowcount or 0)
        deleted_ent = 0
        if entity_ids:
            r = await db.execute(
                delete(KbEntity).where(
                    KbEntity.project_id == project_id,
                    KbEntity.id.in_(list(entity_ids)),
                    KbEntity.ref_count == 0,
                    KbEntity.created_by.is_(None),
                    KbEntity.human_edited.is_(False),
                    KbEntity.is_deleted.is_(False),
                    KbEntity.merged_into_id.is_(None),
                )
            )
            deleted_ent = int(r.rowcount or 0)
        return deleted_rel, deleted_ent

    # ────────────────────────── 溯源 · 读 ──────────────────────────

    async def list_entity_mentions(
        self, db: AsyncSession, *, project_id: int, entity_id: int, limit: int = 50
    ) -> list[KbEntityMention]:
        stmt = (
            select(KbEntityMention)
            .where(
                KbEntityMention.project_id == project_id,
                KbEntityMention.entity_id == entity_id,
            )
            .order_by(KbEntityMention.id.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def count_documents_by_graph_status(
        self, db: AsyncSession, *, project_id: int
    ) -> dict[str, int]:
        """各 graph_status 文档计数（stats 端点）"""
        from app.models.knowledge.document import KbDocument, KbDocumentStatus

        stmt = (
            select(KbDocument.graph_status, func.count(KbDocument.id))
            .where(
                KbDocument.project_id == project_id,
                KbDocument.status != KbDocumentStatus.DELETED.value,
            )
            .group_by(KbDocument.graph_status)
        )
        return {row[0]: int(row[1]) for row in (await db.execute(stmt)).all()}


crud_kb_graph = CRUDKbGraph()
