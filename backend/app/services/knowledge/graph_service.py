"""知识图谱维护与查询 service（P1b WP-B3/B4）

维护面（manage 权限）：编辑（置 human_edited 保护位）/ 删除（墓碑+连带关系墓碑）/
合并（mention 迁移、关系重定向去重、败者留重定向指针）/ 手工创建（created_by，
墓碑复活语义）/ 关系编辑删除。全部 commit 在本层（端点薄壳）。

查询面（view 权限）：子图 BFS（预算截断 ≤500 节点/≤3 层，按 ref_count DESC 纳入，
最后一次闭包查询收边）/ 实体详情（mentions 溯源到文档名+章节）/ 统计。

文档级 GC（gc_for_document，**不 commit**）：删文档/废弃/重入库时并入调用方事务
——清台账→重算→自动孤儿删行→totals。
"""

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.crud.knowledge.graph import crud_kb_graph
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import KbEntity, KbRelation
from app.services.knowledge.graph_extract import (
    ENTITY_TYPE_SET,
    _merge_desc,
    normalize_entity_name,
)

# BFS 预算（冻结：≤500 节点/≤3 层）
MAX_BFS_NODES = 500
MAX_BFS_DEPTH = 3
DEFAULT_BFS_NODES = 200


# ────────────────────────── 实体维护 ──────────────────────────

async def _get_active_entity(
    db: AsyncSession, *, project_id: int, entity_id: int
) -> KbEntity:
    e = await crud_kb_graph.get_entity(db, project_id=project_id, entity_id=entity_id)
    if e is None or e.is_deleted or e.merged_into_id:
        raise BusinessException("实体不存在或已删除/已合并", code=404)
    return e


async def update_entity(
    db: AsyncSession,
    *,
    project_id: int,
    entity_id: int,
    name: Optional[str] = None,
    entity_type: Optional[str] = None,
    description: Optional[str] = None,
) -> KbEntity:
    """编辑实体：置 human_edited 保护位（此后自动抽取只增 mention 不覆写）"""
    e = await _get_active_entity(db, project_id=project_id, entity_id=entity_id)
    if name is not None:
        nm = name.strip()
        if len(nm) < 2:
            raise BusinessException("实体名至少 2 个字符", code=400)
        norm = normalize_entity_name(nm)
        if norm != e.name_norm:
            dup = await crud_kb_graph.get_entities_by_norms(
                db, project_id=project_id, name_norms=[norm]
            )
            if dup:
                raise BusinessException(
                    f"同名实体已存在：{dup[0].name}（可改用「合并」）", code=409
                )
            old_name, old_norm = e.name, e.name_norm
            e.name_norm = norm
            db.add(e)
            await db.flush()
            # 旧 norm 留重定向行——否则自动抽取命中旧名会重建新实体（变相分裂）
            db.add(
                KbEntity(
                    project_id=project_id,
                    name=old_name,
                    name_norm=old_norm,
                    entity_type=e.entity_type,
                    merged_into_id=e.id,
                )
            )
        e.name = nm[:255]
    if entity_type is not None:
        et = entity_type.strip().lower()
        if et not in ENTITY_TYPE_SET:
            raise BusinessException(f"非法实体类型：{entity_type}", code=400)
        e.entity_type = et
    if description is not None:
        e.description = description.strip()[:2000] or None
    e.human_edited = True
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return e


async def delete_entity(
    db: AsyncSession, *, project_id: int, entity_id: int
) -> None:
    """删除实体：软删墓碑（防自动抽取复活）+ 连带关系墓碑。幂等。"""
    e = await crud_kb_graph.get_entity(db, project_id=project_id, entity_id=entity_id)
    if e is None:
        raise BusinessException("实体不存在", code=404)
    if e.is_deleted:
        return
    e.is_deleted = True
    db.add(e)
    rels = await crud_kb_graph.list_relations_of_entity(
        db, project_id=project_id, entity_id=e.id
    )
    for r in rels:
        if not r.is_deleted:
            r.is_deleted = True
            db.add(r)
    await crud_kb_graph.recount_totals(db, project_id=project_id)
    await db.commit()


async def create_entity(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    name: str,
    entity_type: str = "term",
    description: Optional[str] = None,
) -> KbEntity:
    """手工创建（created_by 非空 → 永不 GC）。同 norm 墓碑存在时=显式复活。"""
    nm = (name or "").strip()
    if len(nm) < 2:
        raise BusinessException("实体名至少 2 个字符", code=400)
    et = (entity_type or "term").strip().lower()
    if et not in ENTITY_TYPE_SET:
        raise BusinessException(f"非法实体类型：{entity_type}", code=400)
    norm = normalize_entity_name(nm)
    existing = await crud_kb_graph.get_entities_by_norms(
        db, project_id=project_id, name_norms=[norm]
    )
    if existing:
        row = existing[0]
        if row.is_deleted and not row.merged_into_id:
            # 人工创建同名 = 显式复活墓碑（自动抽取不许,人工可以）
            row.is_deleted = False
            row.human_edited = True
            row.created_by = user_id
            row.name = nm[:255]
            row.entity_type = et
            if description is not None:
                row.description = description.strip()[:2000] or None
            db.add(row)
            await crud_kb_graph.recount_totals(db, project_id=project_id)
            await db.commit()
            await db.refresh(row)
            return row
        raise BusinessException(f"同名实体已存在：{row.name}", code=409)
    row = KbEntity(
        project_id=project_id,
        name=nm[:255],
        name_norm=norm,
        entity_type=et,
        description=(description or "").strip()[:2000] or None,
        human_edited=True,
        created_by=user_id,
    )
    db.add(row)
    await crud_kb_graph.recount_totals(db, project_id=project_id)
    await db.commit()
    await db.refresh(row)
    return row


async def merge_entities(
    db: AsyncSession, *, project_id: int, source_id: int, target_id: int
) -> KbEntity:
    """合并：source（败者）→ target（胜者）。

    败者留 merged_into_id 重定向指针（后续抽取命中旧名沿指针落到胜者）；
    mention 迁移去重；关系端点重定向（撞已有同向边→权重并入+mention 迁移+删败者边；
    重定向后自环→删）。胜者 description 自动并入。
    """
    if source_id == target_id:
        raise BusinessException("不能与自身合并", code=400)
    loser = await crud_kb_graph.get_entity(
        db, project_id=project_id, entity_id=source_id
    )
    winner = await crud_kb_graph.get_entity(
        db, project_id=project_id, entity_id=target_id
    )
    if loser is None or winner is None:
        raise BusinessException("实体不存在", code=404)
    if loser.is_deleted or loser.merged_into_id:
        raise BusinessException("源实体已删除或已被合并", code=400)
    # 胜者若自身是重定向行,沿指针到最终胜者（≤5 跳带环卫）
    hops = 0
    seen = {winner.id}
    while winner.merged_into_id and hops < 5:
        nxt = await crud_kb_graph.get_entity(
            db, project_id=project_id, entity_id=winner.merged_into_id
        )
        if nxt is None or nxt.id in seen:
            break
        winner = nxt
        seen.add(winner.id)
        hops += 1
    if winner.is_deleted:
        raise BusinessException("目标实体已删除", code=400)
    if winner.id == loser.id:
        raise BusinessException("合并链成环，禁止操作", code=400)

    # 1. mention 迁移（去重）
    await crud_kb_graph.move_entity_mentions(
        db, from_entity_id=loser.id, to_entity_id=winner.id
    )

    # 2. 关系端点重定向
    touched_rel_ids: set[int] = set()
    rels = await crud_kb_graph.list_relations_of_entity(
        db, project_id=project_id, entity_id=loser.id
    )
    for r in rels:
        new_s = winner.id if r.source_entity_id == loser.id else r.source_entity_id
        new_t = winner.id if r.target_entity_id == loser.id else r.target_entity_id
        if new_s == new_t:
            await db.delete(r)  # 重定向后自环：删行（mention 级联）
            continue
        dup_rows = await crud_kb_graph.get_relations_by_pairs(
            db, project_id=project_id, pairs=[(new_s, new_t)]
        )
        dup = next((d for d in dup_rows if d.id != r.id), None)
        if dup is not None:
            if not dup.is_deleted and not r.is_deleted:
                dup.weight = float(dup.weight or 0) + float(r.weight or 0)
                if not dup.keywords and r.keywords:
                    dup.keywords = r.keywords
                db.add(dup)
            await crud_kb_graph.move_relation_mentions(
                db, from_relation_id=r.id, to_relation_id=dup.id
            )
            await db.delete(r)
            touched_rel_ids.add(dup.id)
        else:
            r.source_entity_id = new_s
            r.target_entity_id = new_t
            db.add(r)
            touched_rel_ids.add(r.id)
    await db.flush()

    # 3. 败者留重定向墓碑指针;胜者 description 并入
    loser.merged_into_id = winner.id
    db.add(loser)
    merged_desc = _merge_desc(winner.description, loser.description or "")
    if merged_desc != winner.description:
        winner.description = merged_desc
        db.add(winner)

    # 4. 计数收口
    await crud_kb_graph.recount_entities(db, entity_ids=[winner.id, loser.id])
    if touched_rel_ids:
        await crud_kb_graph.recount_relations(db, relation_ids=sorted(touched_rel_ids))
    await crud_kb_graph.recount_totals(db, project_id=project_id)
    await db.commit()
    await db.refresh(winner)
    return winner


# ────────────────────────── 关系维护 ──────────────────────────

async def update_relation(
    db: AsyncSession,
    *,
    project_id: int,
    relation_id: int,
    keywords: Optional[str] = None,
    description: Optional[str] = None,
) -> KbRelation:
    r = await crud_kb_graph.get_relation(
        db, project_id=project_id, relation_id=relation_id
    )
    if r is None or r.is_deleted:
        raise BusinessException("关系不存在或已删除", code=404)
    if keywords is not None:
        r.keywords = keywords.strip()[:200]
    if description is not None:
        r.description = description.strip()[:2000] or None
    r.human_edited = True
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def delete_relation(
    db: AsyncSession, *, project_id: int, relation_id: int
) -> None:
    """关系墓碑（防自动抽取复活）。幂等。"""
    r = await crud_kb_graph.get_relation(
        db, project_id=project_id, relation_id=relation_id
    )
    if r is None:
        raise BusinessException("关系不存在", code=404)
    if r.is_deleted:
        return
    r.is_deleted = True
    db.add(r)
    await crud_kb_graph.recount_totals(db, project_id=project_id)
    await db.commit()


# ────────────────────────── 文档级 GC（不 commit,并入调用方事务） ──────────────────────────

async def gc_for_document(
    db: AsyncSession, *, project_id: int, document_id: int
) -> dict[str, int]:
    """文档删除/废弃/重入库时清除其图谱贡献：清台账→重算→自动孤儿删行→totals。

    手工创建/human_edited/墓碑/重定向行永不被 GC（crud 层守护）。**不 commit**。
    """
    ent_ids, rel_ids = await crud_kb_graph.delete_mentions_by_document(
        db, document_id=document_id
    )
    if not ent_ids and not rel_ids:
        return {"gc_entities": 0, "gc_relations": 0}
    await crud_kb_graph.recount_entities(db, entity_ids=ent_ids)
    await crud_kb_graph.recount_relations(db, relation_ids=rel_ids)
    gc_rel, gc_ent = await crud_kb_graph.delete_orphans(
        db, project_id=project_id, entity_ids=ent_ids, relation_ids=rel_ids
    )
    await crud_kb_graph.recount_totals(db, project_id=project_id)
    return {"gc_entities": gc_ent, "gc_relations": gc_rel}


# ────────────────────────── 查询面 ──────────────────────────

def _entity_node(e: KbEntity) -> dict[str, Any]:
    return {
        "id": e.id,
        "name": e.name,
        "entity_type": e.entity_type,
        "description": e.description,
        "ref_count": e.ref_count,
        "doc_count": e.doc_count,
        "human_edited": bool(e.human_edited),
    }


def _relation_edge(r: KbRelation) -> dict[str, Any]:
    return {
        "id": r.id,
        "source": r.source_entity_id,
        "target": r.target_entity_id,
        "keywords": r.keywords,
        "description": r.description,
        "weight": r.weight,
        "ref_count": r.ref_count,
        "human_edited": bool(r.human_edited),
    }


async def get_subgraph(
    db: AsyncSession,
    *,
    project_id: int,
    label: Optional[str] = None,
    max_depth: int = MAX_BFS_DEPTH,
    max_nodes: int = DEFAULT_BFS_NODES,
) -> dict[str, Any]:
    """label 起点 BFS 子图；label 空/'*' = 全量模式（图谱页默认视图）。

    预算截断：节点 ≤min(max_nodes,500)、层 ≤min(max_depth,3)，邻居按
    ref_count DESC 纳入；最后一次闭包查询收「两端都在结果集内」的边。

    全量模式不走 BFS 而是整图直出——种子 BFS 只能覆盖与热门实体连通的
    部分，会漏掉没有任何关系的孤立实体；直取活跃实体（ref_count 序）+
    闭包收边才是完整的「全部图谱」。预算依旧生效（多取 1 行探测截断）。
    """
    max_depth = max(1, min(int(max_depth or MAX_BFS_DEPTH), MAX_BFS_DEPTH))
    max_nodes = max(1, min(int(max_nodes or DEFAULT_BFS_NODES), MAX_BFS_NODES))
    truncated = False

    if not label or label == "*":
        rows = await crud_kb_graph.list_popular_entities(
            db, project_id=project_id, limit=max_nodes + 1
        )
        full_nodes = {e.id: e for e in rows[:max_nodes]}
        if not full_nodes:
            return {"nodes": [], "edges": [], "is_truncated": False}
        closure = await crud_kb_graph.list_relations_touching(
            db, project_id=project_id, entity_ids=list(full_nodes)
        )
        return {
            "nodes": [_entity_node(e) for e in full_nodes.values()],
            "edges": [
                _relation_edge(r)
                for r in closure
                if r.source_entity_id in full_nodes
                and r.target_entity_id in full_nodes
            ],
            "is_truncated": len(rows) > max_nodes,
        }

    # 定点模式：label 起点 BFS
    norm = normalize_entity_name(label)
    rows = await crud_kb_graph.get_entities_by_norms(
        db, project_id=project_id, name_norms=[norm]
    )
    seeds = [e for e in rows if not e.is_deleted and not e.merged_into_id]
    if not seeds:
        seeds = await crud_kb_graph.search_entities(
            db, project_id=project_id, keyword=label, limit=1
        )
    if not seeds:
        return {"nodes": [], "edges": [], "is_truncated": False}

    nodes: dict[int, KbEntity] = {}
    for e in seeds:
        if len(nodes) >= max_nodes:
            truncated = True
            break
        nodes[e.id] = e
    frontier = list(nodes)

    for _ in range(max_depth):
        if not frontier or len(nodes) >= max_nodes:
            break
        rels = await crud_kb_graph.list_relations_touching(
            db, project_id=project_id, entity_ids=frontier
        )
        neighbor_ids = {
            nid
            for r in rels
            for nid in (r.source_entity_id, r.target_entity_id)
            if nid not in nodes
        }
        if not neighbor_ids:
            frontier = []
            break
        neighbors = await crud_kb_graph.get_entities_by_ids(
            db, project_id=project_id, entity_ids=list(neighbor_ids)
        )
        neighbors = [e for e in neighbors if not e.is_deleted and not e.merged_into_id]
        neighbors.sort(key=lambda e: (-(e.ref_count or 0), e.id))
        budget = max_nodes - len(nodes)
        if len(neighbors) > budget:
            truncated = True
            neighbors = neighbors[:budget]
        for e in neighbors:
            nodes[e.id] = e
        frontier = [e.id for e in neighbors]

    # 闭包收边：两端都在结果集内的活跃边（一条 IN 查询）
    closure = await crud_kb_graph.list_relations_touching(
        db, project_id=project_id, entity_ids=list(nodes)
    )
    edges = [
        r
        for r in closure
        if r.source_entity_id in nodes and r.target_entity_id in nodes
    ]
    return {
        "nodes": [_entity_node(e) for e in nodes.values()],
        "edges": [_relation_edge(r) for r in edges],
        "is_truncated": truncated,
    }


async def get_entity_detail(
    db: AsyncSession, *, project_id: int, entity_id: int
) -> dict[str, Any]:
    """实体详情：基本信息 + mentions 溯源（文档名+章节面包屑）+ 邻接关系"""
    e = await _get_active_entity(db, project_id=project_id, entity_id=entity_id)
    mentions = await crud_kb_graph.list_entity_mentions(
        db, project_id=project_id, entity_id=e.id, limit=50
    )
    doc_ids = {m.document_id for m in mentions}
    chunk_ids = {m.chunk_id for m in mentions if m.chunk_id}
    doc_map: dict[int, str] = {}
    if doc_ids:
        rows = await db.execute(
            select(KbDocument.id, KbDocument.file_name).where(
                KbDocument.id.in_(doc_ids)
            )
        )
        doc_map = {row[0]: row[1] for row in rows.all()}
    chunk_map: dict[int, str] = {}
    if chunk_ids:
        rows = await db.execute(
            select(KbChunk.id, KbChunk.heading_path).where(KbChunk.id.in_(chunk_ids))
        )
        chunk_map = {row[0]: row[1] for row in rows.all()}

    rels = await crud_kb_graph.list_relations_touching(
        db, project_id=project_id, entity_ids=[e.id]
    )
    peer_ids = {
        nid
        for r in rels
        for nid in (r.source_entity_id, r.target_entity_id)
        if nid != e.id
    }
    peers = {
        p.id: p
        for p in await crud_kb_graph.get_entities_by_ids(
            db, project_id=project_id, entity_ids=list(peer_ids)
        )
    }

    return {
        **_entity_node(e),
        "created_by": e.created_by,
        "mentions": [
            {
                "document_id": m.document_id,
                "doc_name": doc_map.get(m.document_id, f"文档#{m.document_id}"),
                "chunk_id": m.chunk_id or None,
                "heading_path": chunk_map.get(m.chunk_id, "") if m.chunk_id else "",
            }
            for m in mentions
        ],
        "relations": [
            {
                **_relation_edge(r),
                "source_name": (
                    e.name
                    if r.source_entity_id == e.id
                    else getattr(peers.get(r.source_entity_id), "name", "?")
                ),
                "target_name": (
                    e.name
                    if r.target_entity_id == e.id
                    else getattr(peers.get(r.target_entity_id), "name", "?")
                ),
            }
            for r in rels
        ],
    }


async def get_graph_stats(db: AsyncSession, *, project_id: int) -> dict[str, Any]:
    """图谱统计（只读，不回写 kb 行）"""
    from sqlalchemy import func

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
    status_counts = await crud_kb_graph.count_documents_by_graph_status(
        db, project_id=project_id
    )
    return {
        "total_nodes": int(nodes),
        "total_edges": int(edges),
        "doc_graph_status": status_counts,
    }


# 变更影响分析规模上限（防扩散爆炸 / token 膨胀）
_IMPACT_MAX_RADIUS = 60
_IMPACT_MAX_CASES = 200


async def analyze_change_impact(
    db: AsyncSession, *, project_id: int, entity_id: int, hops: int = 1
) -> dict[str, Any]:
    """变更影响分析（v1，零新表）：一个实体发生变更时，沿知识图谱关系边扩散出
    受影响的实体集，再经「需求文本提及」桥接到需要回归的功能用例。

    链路：变更实体 → N-hop 图邻域（受影响实体） → 需求文本子串命中这些实体的需求
    → 这些需求关联的功能用例 = 建议回归清单。

    局限（诚实）：实体↔用例是**经需求文本子串匹配的启发式关联**，非维护式精确映射
    （精确版需在用例生成时落 用例↔实体 关联表，属后续专项）。hops 默认 1（1-hop
    邻域已足够圈定直接影响面；2-hop 易过度扩散）。
    """
    from app.crud.func_test.test_case import crud_test_case
    from app.models.func_test.requirement import TestRequirement

    seed = await _get_active_entity(db, project_id=project_id, entity_id=entity_id)

    # 1) N-hop 邻域扩散（受影响实体集，含种子）
    radius: dict[int, KbEntity] = {seed.id: seed}
    frontier = [seed.id]
    for _ in range(max(1, hops)):
        if not frontier or len(radius) >= _IMPACT_MAX_RADIUS:
            break
        rels = await crud_kb_graph.list_relations_touching(
            db, project_id=project_id, entity_ids=frontier
        )
        nbr_ids = {
            nid
            for r in rels
            for nid in (r.source_entity_id, r.target_entity_id)
            if nid not in radius
        }
        if not nbr_ids:
            break
        nbrs = await crud_kb_graph.get_entities_by_ids(
            db, project_id=project_id, entity_ids=list(nbr_ids)
        )
        nbrs = [e for e in nbrs if not e.is_deleted and not e.merged_into_id]
        for e in nbrs:
            if len(radius) >= _IMPACT_MAX_RADIUS:
                break
            radius[e.id] = e
        frontier = [e.id for e in nbrs]

    impacted_names = [e.name for e in radius.values()]

    # 2) 需求文本子串命中受影响实体 → 受影响需求集
    req_rows = (
        await db.execute(
            select(
                TestRequirement.id,
                TestRequirement.title,
                TestRequirement.understood_content,
                TestRequirement.description,
                TestRequirement.acceptance_criteria,
            ).where(
                TestRequirement.project_id == project_id,
                TestRequirement.is_deleted.is_(False),
            )
        )
    ).all()
    impacted_reqs: list[dict[str, Any]] = []
    for rid, title, understood, desc, accept in req_rows:
        text = " ".join(filter(None, [title, understood or desc, accept]))
        hit = [n for n in impacted_names if len(n) >= 2 and n in text]
        if hit:
            impacted_reqs.append({"id": rid, "title": title, "matched": hit})

    # 3) 受影响需求关联的功能用例 = 回归清单
    cases: list[dict[str, Any]] = []
    for req in impacted_reqs:
        if len(cases) >= _IMPACT_MAX_CASES:
            break
        for c in await crud_test_case.list_by_requirement(
            db, requirement_id=req["id"]
        ):
            cases.append(
                {
                    "id": c.id,
                    "code": c.code,
                    "title": c.title,
                    "priority": c.priority,
                    "requirement_id": req["id"],
                }
            )
            if len(cases) >= _IMPACT_MAX_CASES:
                break

    return {
        "seed": {"id": seed.id, "name": seed.name, "type": seed.entity_type},
        "impacted_entities": impacted_names,
        "impacted_entity_count": len(radius),
        "impacted_requirements": impacted_reqs,
        "regression_cases": cases,
        "regression_case_count": len(cases),
        "truncated": len(radius) >= _IMPACT_MAX_RADIUS
        or len(cases) >= _IMPACT_MAX_CASES,
    }
