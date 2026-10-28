"""知识图谱抽取域逻辑（P1b WP-B2，设计文档 §4.2 / 拆解冻结决策）

分层：
  - **纯函数区**（normalize/validate/aggregate/attribute）：无 DB 无网络，单测主战场
  - **持久化区**（resolve_and_persist）：单事务写入——墓碑/重定向/保护位三大守护
    语义的唯一实现点，kb_extract 图的 resolve 节点只是薄壳
  - **派发区**（submit_extract / auto_dispatch_after_ingest）：统一任务六步提交，
    入库自动派发按 graph_doc_types 白名单 + graph_source_hash 短路

质量闸（冻结）：name≥2 字、单批≤15 实体、单文档≤200、relation 两端必须在已抽
实体内、description≤100 字、通用裸词黑名单。
"""

import hashlib
import logging
import re
import unicodedata
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.crud.knowledge import crud_knowledge_base
from app.crud.knowledge.graph import crud_kb_graph
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import (
    KbEntity,
    KbEntityMention,
    KbEntityType,
    KbGraphStatus,
    KbRelation,
    KbRelationMention,
)

logger = logging.getLogger(__name__)

# —— 锁定常量（拆解冻结；改动=改拆解文档） ——
BATCH_MAX_ENTITIES = 15  # 单批实体上限（prompt 约定 + 代码截断双保险）
DOC_MAX_ENTITIES = 200  # 单文档实体上限（到量即停后续批）
BATCH_TARGET_CHARS = 3000  # 每批拼接文本目标长度
CHUNK_PROMPT_MAX_CHARS = 2000  # 单 chunk 进 prompt 的截断长度（超长表格/代码防爆）
ENTITY_NAME_MIN = 2
ENTITY_NAME_MAX = 100
DESC_BATCH_MAX = 100  # 单次抽取 description 上限（prompt 约定）
DESC_STORE_MAX = 2000  # 库内多来源合并上限
NODES_SOFT_LIMIT = 10_000  # 单项目实体软红线（finalize 告警）

ENTITY_TYPE_SET = {t.value for t in KbEntityType}

# 通用裸词黑名单：这些词必须带限定语（「支付系统」可以，「系统」不行）
GENERIC_NAME_BLACKLIST = {
    "系统", "用户", "数据", "平台", "功能", "服务", "模块", "页面", "接口",
    "信息", "内容", "管理", "流程", "问题", "需求", "文档", "测试",
}

_WS_RE = re.compile(r"\s+")


# ────────────────────────── 纯函数区 ──────────────────────────

def normalize_entity_name(name: str) -> str:
    """canonical 归一键：NFKC（全角→半角）+ 空白折叠 + lower + strip"""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", str(name))
    s = _WS_RE.sub(" ", s).strip().lower()
    return s[:255]


def source_hash_of(content_md: Optional[str]) -> str:
    """增量短路键 = sha256(content_md)"""
    return hashlib.sha256((content_md or "").encode("utf-8")).hexdigest()


def validate_batch_payload(
    payload: dict, *, known_norms: set[str]
) -> tuple[list[dict], list[dict]]:
    """单批 LLM 输出 → 过质量闸后的实体/关系草稿。

    entities: [{name, norm, type, description}]（≤15，name≥2 字，黑名单拦裸词，
    非法 type 归 term）；relations: [{source, target, keywords, description}]
    （端点归一后必须 ∈ known_norms ∪ 本批实体，自环丢弃）。纯函数。
    """
    out_e: list[dict] = []
    seen: set[str] = set()
    for it in list(payload.get("entities") or [])[: BATCH_MAX_ENTITIES * 3]:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not (ENTITY_NAME_MIN <= len(name) <= ENTITY_NAME_MAX):
            continue
        if name in GENERIC_NAME_BLACKLIST:
            continue
        norm = normalize_entity_name(name)
        if not norm or norm in seen or norm in GENERIC_NAME_BLACKLIST:
            continue
        etype = str(it.get("type") or "").strip().lower()
        if etype not in ENTITY_TYPE_SET:
            etype = KbEntityType.TERM.value
        desc = str(it.get("description") or "").strip()[:DESC_BATCH_MAX]
        seen.add(norm)
        out_e.append({"name": name, "norm": norm, "type": etype, "description": desc})
        if len(out_e) >= BATCH_MAX_ENTITIES:
            break

    allowed = known_norms | {e["norm"] for e in out_e}
    out_r: list[dict] = []
    rseen: set[tuple[str, str]] = set()
    for it in list(payload.get("relations") or [])[: BATCH_MAX_ENTITIES * 4]:
        if not isinstance(it, dict):
            continue
        s = normalize_entity_name(str(it.get("source") or ""))
        t = normalize_entity_name(str(it.get("target") or ""))
        if not s or not t or s == t:
            continue
        if s not in allowed or t not in allowed:
            continue  # 两端必须在已抽实体内（冻结规则）
        key = (s, t)
        if key in rseen:
            continue
        rseen.add(key)
        out_r.append(
            {
                "source": s,
                "target": t,
                "keywords": str(it.get("keywords") or "").strip()[:200],
                "description": str(it.get("description") or "").strip()[:300],
            }
        )
    return out_e, out_r


def attribute_chunks(text_needle: str, batch_chunks: list[dict]) -> set[int]:
    """出处归因：批内正文包含实体名的 chunk 集合（找不到 → 空集，落文档级 0）"""
    if not text_needle:
        return set()
    return {c["id"] for c in batch_chunks if text_needle in (c.get("text") or "")}


def merge_entity_aggs(
    aggs: dict[str, dict], entities: list[dict], batch_chunks: list[dict]
) -> None:
    """批结果并入跨批聚合（norm 首见定 name/type,description 取更长,chunk 出处并集）"""
    for e in entities:
        cur = aggs.get(e["norm"])
        chunk_ids = attribute_chunks(e["name"], batch_chunks)
        if cur is None:
            aggs[e["norm"]] = {
                "name": e["name"],
                "type": e["type"],
                "description": e["description"],
                "chunk_ids": set(chunk_ids),
            }
        else:
            if len(e["description"]) > len(cur["description"]):
                cur["description"] = e["description"]
            cur["chunk_ids"] |= chunk_ids


def merge_relation_aggs(
    aggs: dict[tuple[str, str], dict],
    relations: list[dict],
    entity_aggs: dict[str, dict],
    batch_chunks: list[dict],
) -> None:
    """关系跨批聚合（出处=同时含两端展示名的 chunk）"""
    for r in relations:
        key = (r["source"], r["target"])
        s_name = (entity_aggs.get(r["source"]) or {}).get("name", "")
        t_name = (entity_aggs.get(r["target"]) or {}).get("name", "")
        chunk_ids = (
            attribute_chunks(s_name, batch_chunks) & attribute_chunks(t_name, batch_chunks)
            if s_name and t_name
            else set()
        )
        cur = aggs.get(key)
        if cur is None:
            aggs[key] = {
                "keywords": r["keywords"],
                "description": r["description"],
                "chunk_ids": set(chunk_ids),
            }
        else:
            if not cur["keywords"] and r["keywords"]:
                cur["keywords"] = r["keywords"]
            if len(r["description"]) > len(cur["description"]):
                cur["description"] = r["description"]
            cur["chunk_ids"] |= chunk_ids


def _merge_desc(old: Optional[str], new: str) -> Optional[str]:
    """description 多来源合并：新内容未包含则追加，封顶 DESC_STORE_MAX"""
    old = (old or "").strip()
    new = (new or "").strip()
    if not new:
        return old or None
    if not old:
        return new[:DESC_STORE_MAX]
    if new in old:
        return old
    if len(old) >= DESC_STORE_MAX - 20:
        return old
    return f"{old}；{new}"[:DESC_STORE_MAX]


# ────────────────────────── 持久化区（单事务，不 commit） ──────────────────────────

async def resolve_and_persist(
    db: AsyncSession,
    *,
    project_id: int,
    document_id: int,
    entity_aggs: dict[str, dict],
    relation_aggs: dict[tuple[str, str], dict],
) -> dict:
    """抽取聚合 → 图谱落库（重抽=替换本文档贡献,不累积）。

    守护语义实现点：墓碑跳过（不落 mention）/ merged_into 沿指针（≤5 跳防环）/
    human_edited 只增 mention / 自动行温和更新（type 覆写、description 合并、
    weight 递增）。收尾：受影响行 recount → 自动孤儿 GC。**不 commit**。
    返回统计 dict（供 finalize/set_result）。
    """
    stats = {
        "entities": 0, "created": 0, "updated": 0, "mention_only": 0,
        "tombstone_skipped": 0, "relations": 0, "relations_created": 0,
        "rel_tombstone_skipped": 0, "dropped_endpoints": 0,
        "gc_entities": 0, "gc_relations": 0,
    }

    # 1. 清本文档旧台账（重抽替换语义）
    old_ent_ids, old_rel_ids = await crud_kb_graph.delete_mentions_by_document(
        db, document_id=document_id
    )

    # 2. 实体 resolve
    existing = {
        e.name_norm: e
        for e in await crud_kb_graph.get_entities_by_norms(
            db, project_id=project_id, name_norms=list(entity_aggs)
        )
    }
    final_entity_id: dict[str, int] = {}
    for norm, agg in entity_aggs.items():
        row = existing.get(norm)
        if row is None:
            row = KbEntity(
                project_id=project_id,
                name=agg["name"][:255],
                name_norm=norm,
                entity_type=agg["type"],
                description=(agg["description"] or None),
            )
            db.add(row)
            await db.flush()
            stats["created"] += 1
        else:
            hops = 0
            seen_ids = {row.id}
            while row.merged_into_id and hops < 5:
                nxt = await crud_kb_graph.get_entity(
                    db, project_id=project_id, entity_id=row.merged_into_id
                )
                if nxt is None or nxt.id in seen_ids:
                    break  # 断链/环：停在当前行
                row = nxt
                seen_ids.add(row.id)
                hops += 1
            if row.is_deleted:
                stats["tombstone_skipped"] += 1
                continue  # 墓碑：不落 mention（防复活铁律）
            if row.human_edited:
                stats["mention_only"] += 1  # 保护位：只增 mention
            else:
                if agg["type"] and agg["type"] != row.entity_type:
                    row.entity_type = agg["type"]
                merged = _merge_desc(row.description, agg["description"])
                if merged != row.description:
                    row.description = merged
                stats["updated"] += 1
        final_entity_id[norm] = row.id
    stats["entities"] = len(final_entity_id)

    # 3. 实体 mention（(entity_id, chunk_id) 内存去重——多 norm 沿指针撞同一胜者）
    mention_keys: set[tuple[int, int]] = set()
    for norm, agg in entity_aggs.items():
        eid = final_entity_id.get(norm)
        if eid is None:
            continue
        for cid in sorted(agg["chunk_ids"] or {0}):
            if (eid, cid) in mention_keys:
                continue
            mention_keys.add((eid, cid))
            db.add(
                KbEntityMention(
                    project_id=project_id,
                    entity_id=eid,
                    document_id=document_id,
                    chunk_id=cid,
                )
            )
    await db.flush()

    # 4. 关系 resolve（norm 对 → id 对；重定向后可能折叠/自环）
    pairs: dict[tuple[int, int], dict] = {}
    for (s_norm, t_norm), agg in relation_aggs.items():
        sid, tid = final_entity_id.get(s_norm), final_entity_id.get(t_norm)
        if not sid or not tid:
            stats["dropped_endpoints"] += 1  # 端点被墓碑拦下等
            continue
        if sid == tid:
            stats["dropped_endpoints"] += 1  # 合并重定向后的自环丢弃
            continue
        cur = pairs.get((sid, tid))
        if cur is None:
            pairs[(sid, tid)] = dict(agg)
        else:
            if not cur["keywords"] and agg["keywords"]:
                cur["keywords"] = agg["keywords"]
            cur["chunk_ids"] = set(cur["chunk_ids"]) | set(agg["chunk_ids"])

    existing_rels = {
        (r.source_entity_id, r.target_entity_id): r
        for r in await crud_kb_graph.get_relations_by_pairs(
            db, project_id=project_id, pairs=list(pairs)
        )
    }
    touched_rel_ids: set[int] = set()
    rel_mention_keys: set[tuple[int, int]] = set()
    for (sid, tid), agg in pairs.items():
        row = existing_rels.get((sid, tid))
        if row is None:
            row = KbRelation(
                project_id=project_id,
                source_entity_id=sid,
                target_entity_id=tid,
                keywords=agg["keywords"][:200],
                description=(agg["description"] or None),
                weight=1.0,
            )
            db.add(row)
            await db.flush()
            stats["relations_created"] += 1
        elif row.is_deleted:
            stats["rel_tombstone_skipped"] += 1
            continue  # 关系墓碑同样防复活
        elif not row.human_edited:
            row.weight = float(row.weight or 0) + 1.0
            if not row.keywords and agg["keywords"]:
                row.keywords = agg["keywords"][:200]
            merged = _merge_desc(row.description, agg["description"])
            if merged != row.description:
                row.description = merged
        touched_rel_ids.add(row.id)
        for cid in sorted(set(agg["chunk_ids"]) or {0}):
            if (row.id, cid) in rel_mention_keys:
                continue
            rel_mention_keys.add((row.id, cid))
            db.add(
                KbRelationMention(
                    project_id=project_id,
                    relation_id=row.id,
                    document_id=document_id,
                    chunk_id=cid,
                )
            )
    stats["relations"] = len(touched_rel_ids)
    await db.flush()

    # 5. 受影响行重算 → 自动孤儿 GC（守护条件在 crud 层，顺序：先 recount 后 GC）
    ent_ids = sorted(set(old_ent_ids) | set(final_entity_id.values()))
    rel_ids = sorted(set(old_rel_ids) | touched_rel_ids)
    await crud_kb_graph.recount_entities(db, entity_ids=ent_ids)
    await crud_kb_graph.recount_relations(db, relation_ids=rel_ids)
    gc_rel, gc_ent = await crud_kb_graph.delete_orphans(
        db, project_id=project_id, entity_ids=ent_ids, relation_ids=rel_ids
    )
    stats["gc_relations"], stats["gc_entities"] = gc_rel, gc_ent
    return stats


# ────────────────────────── 派发区 ──────────────────────────

async def submit_extract(
    db: AsyncSession, *, project_id: int, user_id: int, doc: KbDocument
) -> int:
    """提交 kb_extract 统一任务（六步模式），置 graph_status=pending。

    同文档已有在途抽取任务时返回既有任务 id（幂等语义，同 _submit_ingest）。
    """
    from app.ai_core.chat_agent.tools.base import submit_unified_task

    result = await submit_unified_task(
        db,
        project_id=project_id,
        user_id=user_id,
        task_type="kb_extract",
        biz_ref_type="kb_document",
        biz_ref_id=doc.id,
        title=f"图谱抽取：{doc.file_name}",
        input_params={"kb_document_id": doc.id, "file_name": doc.file_name},
    )
    if not result.get("ok"):
        existing_id = result.get("ai_task_id")
        if existing_id:
            return int(existing_id)
        raise BusinessException(
            f"图谱抽取任务投递失败：{result.get('error') or '未知错误'}", code=500
        )
    task_id = int(result["ai_task_id"])
    doc.graph_status = KbGraphStatus.PENDING.value
    doc.graph_task_id = task_id
    db.add(doc)
    await db.commit()
    return task_id


async def auto_dispatch_after_ingest(
    db: AsyncSession, *, project_id: int, user_id: int, doc: KbDocument
) -> Optional[int]:
    """入库完成后的自动派发：doc_type ∈ graph_doc_types 白名单 且 hash 变化才派。

    返回任务 id 或 None（不满足条件）。调用方负责 try/except（派发失败不影响入库）。
    """
    kb = await crud_knowledge_base.get_by_project(db, project_id=project_id)
    if kb is None:
        return None
    whitelist = {t.strip() for t in (kb.graph_doc_types or "").split(",") if t.strip()}
    if doc.doc_type not in whitelist:
        return None
    if (
        doc.graph_status == KbGraphStatus.EXTRACTED.value
        and doc.graph_source_hash == source_hash_of(doc.content_md)
    ):
        return None  # 内容未变，短路
    return await submit_extract(db, project_id=project_id, user_id=user_id, doc=doc)
