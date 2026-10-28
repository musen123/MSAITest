"""AI 需求盘点（统一 AI 任务图，设计见 docs/AI需求盘点-设计方案.md v2）

全库扫描 ready+effective 的知识库文档，把散落在多个文档里的需求批量提取为
结构化草稿。核心抽象 =「证据包」：三级合并键（K1 需求编号精确 / K2 标题归一 /
K3 图谱实体桥）把多来源块聚成一包，LLM 在证据包级结构化一次——调用次数 ≈
需求数，不随文档数膨胀，同时解决重复建需求与信息残缺。

原型图（单独上传的图片类文档）绝不独立成需求：只挂靠进证据包（实体桥 +
关键词兜底）或进「未归位材料」清单等人工归位。

纪律：
  - 幂等 = code 撞 uq_func_req_project_code 跳过 + 标题归一去重（重跑零新增）；
  - 人审闸门 = 全部 status=draft + source=ai_generated，绝不自动 published；
  - 合并/挂靠全零 LLM（纯逻辑，单测直测）；LLM 只在逐包结构化处调用；
  - 单包失败记清单继续；证据包/候选数硬封顶。
"""

import logging
import re
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai_core.llm_context import get_current_llm
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

# ── 封顶护栏 ──
MAX_CANDIDATES = 200          # 全库候选硬上限（异常语料兜底）
MAX_BLOCKS_PER_PACK = 6       # 单证据包来源块上限
MAX_PACK_CHARS = 8_000        # 单证据包拼接字符上限
MAX_PROTO_CHARS = 800         # 单张原型图描述并入上限
LOW_CONFIDENCE = 0.6          # 低置信阈值（仍落库，报告单列供人重点看）

REQ_CODE_RE = re.compile(r"REQ-[A-Z]+-\d+")
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


class SweepState(TypedDict, total=False):
    project_id: int


# ─────────────────────────────────────────────────────────────
# 纯逻辑层（与 DB 解耦，入参全为简单 dict，单测直测）
#   chunk  = {id, document_id, doc_name, doc_type, heading_path, content, is_parent}
#   entity = {id, name}
#   mention= {entity_id, chunk_id, document_id}
#   image_doc = {id, file_name, content_md}
# ─────────────────────────────────────────────────────────────


def normalize_title(text: str) -> str:
    """标题归一：去 REQ 编号/序号前缀/空白/常见标点，小写。K2 合并与落库去重共用。"""
    t = REQ_CODE_RE.sub("", text or "")
    t = re.sub(r"^[\d\.\s、›>/-]+", "", t.strip())
    # 中文序号前缀（带顿号才剥，防误伤「二维码登录」这类以数词开头的词）
    t = re.sub(r"^[一二三四五六七八九十百]+、", "", t)
    t = re.sub(r"[\s（）()【】\[\]:：,，。.·\-—_/\\*、；;\"“”'《》〈〉「」|]+", "", t)
    return t.lower()


def _heading_title(heading_path: str) -> str:
    """取标题面包屑最后一段作候选标题（去编号/序号前缀）。"""
    tail = (heading_path or "").split("›")[-1].strip()
    tail = REQ_CODE_RE.sub("", tail)
    tail = re.sub(r"^[一二三四五六七八九十百]+、", "", tail.strip())
    return re.sub(r"^[\d\.\s、/-]+|[（(].*?重点.*?[)）]", "", tail).strip(" -—│|") or tail


def discover_candidates(chunks: list[dict]) -> tuple[dict[str, dict], dict]:
    """① 分域发现 + K1/K2 合并。

    返回 (candidates by key, 发现统计)。
    - 标题含 REQ 编号的块 → 该编号候选的主段（K1：同编号跨文档/跨块自然聚合）；
    - 仅正文提及编号的块 → 该编号候选的补充块（编号无独立章节则不造候选，防
      功能清单表格刷出大量单行薄需求——按设计「宁可报告提示，不造噪声」）；
    - 无编号的 requirement 类文档 → 父块章节作候选（LLM 结构化时判 is_requirement），
      标题归一后与已有候选同名则并入（K2）。
    """
    candidates: dict[str, dict] = {}
    title_index: dict[str, str] = {}  # norm_title -> key
    mention_only: set[str] = set()

    def _ensure(key: str, code: Optional[str], title: str) -> dict:
        cand = candidates.get(key)
        if cand is None:
            cand = {
                "key": key,
                "code": code,
                "title": title,
                "primary": [],
                "supplements": [],
                "prototypes": [],
            }
            candidates[key] = cand
            nt = normalize_title(title)
            if nt:
                title_index.setdefault(nt, key)
        return cand

    # 第一遍：标题锚定（主段）。**只收父块**——chunker 的子块是父块切片，
    # 父子同收会让主段重复膨胀、把原型/图谱桥挤出证据包块数上限。
    anchored_parent: set[str] = {
        code
        for ch in chunks
        if ch.get("is_parent")
        for code in REQ_CODE_RE.findall(ch.get("heading_path") or "")
    }
    for ch in chunks:
        codes = REQ_CODE_RE.findall(ch.get("heading_path") or "")
        for code in dict.fromkeys(codes):
            # 该编号存在父块锚定时跳过子块；完全无父块锚定的编号才用子块兜底
            if code in anchored_parent and not ch.get("is_parent"):
                continue
            cand = _ensure(code, code, _heading_title(ch["heading_path"]))
            cand["primary"].append(_block(ch, kind="primary"))

    # 第二遍：正文提及 → 已有候选的补充块（K1 跨文档聚合）
    for ch in chunks:
        heading_codes = set(REQ_CODE_RE.findall(ch.get("heading_path") or ""))
        for code in dict.fromkeys(REQ_CODE_RE.findall(ch.get("content") or "")):
            if code in heading_codes:
                continue
            if code in candidates:
                if not _has_block(candidates[code], ch["id"]):
                    candidates[code]["supplements"].append(_block(ch, kind="mention"))
            else:
                mention_only.add(code)

    # 第三遍：**完全无编号体系**的 requirement 文档，其父块章节作候选
    # （K2 标题归一并入或新建）。文档内任何位置（标题或正文）出现过 REQ 编号
    # 即视为「有编号体系」——其无编号章节多为背景/清单/术语，不造候选防噪声。
    coded_doc_ids = {
        b["chunk_id"]
        for c in candidates.values()
        for b in c["primary"]
    }
    docs_with_codes = {
        ch["document_id"]
        for ch in chunks
        if REQ_CODE_RE.search(
            (ch.get("heading_path") or "") + "\n" + (ch.get("content") or "")
        )
    }
    for ch in chunks:
        if not ch.get("is_parent"):
            continue
        if ch.get("doc_type") != "requirement":
            continue
        if ch["document_id"] in docs_with_codes:
            continue
        if ch["id"] in coded_doc_ids or not (ch.get("content") or "").strip():
            continue
        title = _heading_title(ch.get("heading_path") or "")
        nt = normalize_title(title)
        if not nt:
            continue
        if nt in title_index:  # K2：与已有候选同名 → 并入补充
            cand = candidates[title_index[nt]]
            if not _has_block(cand, ch["id"]):
                cand["supplements"].append(_block(ch, kind="mention"))
        else:
            cand = _ensure(f"title:{nt}", None, title)
            cand["primary"].append(_block(ch, kind="primary"))

    stats = {
        "candidates": len(candidates),
        "mention_only_codes": sorted(mention_only - set(candidates)),
    }
    return candidates, stats


def _block(ch: dict, *, kind: str) -> dict:
    return {
        "chunk_id": ch["id"],
        "document_id": ch["document_id"],
        "doc": ch.get("doc_name") or f"文档#{ch['document_id']}",
        "heading": ch.get("heading_path") or "",
        "content": ch.get("content") or "",
        "kind": kind,
    }


def _has_block(cand: dict, chunk_id: int) -> bool:
    return any(
        b["chunk_id"] == chunk_id
        for b in cand["primary"] + cand["supplements"]
    )


def bridge_graph_entities(
    candidates: dict[str, dict],
    entities: list[dict],
    mentions: list[dict],
    chunk_map: dict[int, dict],
) -> int:
    """K3 图谱实体桥：候选标题命中实体名 → 该实体在**其它文档**的提及块并入补充。

    返回桥接进的块数。零 LLM。"""
    by_entity: dict[int, list[dict]] = {}
    for m in mentions:
        by_entity.setdefault(m["entity_id"], []).append(m)
    added = 0
    for cand in candidates.values():
        nt = normalize_title(cand["title"])
        if len(nt) < 2:
            continue
        own_docs = {b["document_id"] for b in cand["primary"]}
        for ent in entities:
            en = normalize_title(ent["name"])
            if len(en) < 2 or (en not in nt and nt not in en):
                continue
            for m in by_entity.get(ent["id"], []):
                ch = chunk_map.get(m.get("chunk_id") or 0)
                if ch is None or ch["document_id"] in own_docs:
                    continue
                if _has_block(cand, ch["id"]):
                    continue
                cand["supplements"].append(_block(ch, kind="graph"))
                added += 1
    return added


def attach_prototypes(
    candidates: dict[str, dict],
    image_docs: list[dict],
    entities: list[dict],
    mentions: list[dict],
) -> tuple[int, list[dict]]:
    """S1 原型图挂靠：实体桥（图片文档的提及实体 ↔ 候选标题）+ 关键词兜底
    （文件名/描述 与 候选标题/编号 归一包含）。挂不上进未归位清单。零 LLM。"""
    ent_name = {e["id"]: e["name"] for e in entities}
    doc_entities: dict[int, set[str]] = {}
    for m in mentions:
        name = ent_name.get(m["entity_id"])
        if name:
            doc_entities.setdefault(m["document_id"], set()).add(
                normalize_title(name)
            )

    attached = 0
    unplaced: list[dict] = []
    for img in image_docs:
        stem = re.sub(r"\.[A-Za-z]+$", "", img.get("file_name") or "")
        stem_norm = normalize_title(stem)
        desc = (img.get("content_md") or "")[:2000]
        img_ents = doc_entities.get(img["id"], set())
        target = None
        for cand in candidates.values():
            nt = normalize_title(cand["title"])
            if len(nt) < 2:
                continue
            # a) 实体桥：图片文档提及的实体名 ≈ 候选标题
            if any(en and (en in nt or nt in en) for en in img_ents):
                target = cand
                break
            # b) 关键词兜底：文件名 ↔ 标题互含，或描述文本含标题/编号
            if (stem_norm and (stem_norm in nt or nt in stem_norm)) or (
                cand["title"] and cand["title"] in desc
            ) or (cand["code"] and cand["code"] in desc):
                target = cand
                break
        if target is not None:
            target["prototypes"].append(
                {
                    "chunk_id": -img["id"],
                    "document_id": img["id"],
                    "doc": img.get("file_name") or f"图片#{img['id']}",
                    "heading": "原型图",
                    "content": (img.get("content_md") or "")[:MAX_PROTO_CHARS],
                    "kind": "prototype",
                }
            )
            attached += 1
        else:
            unplaced.append(
                {"document_id": img["id"], "file_name": img.get("file_name")}
            )
    return attached, unplaced


def assemble_evidence(cand: dict) -> tuple[str, list[str], bool]:
    """证据包拼接（封顶：≤MAX_BLOCKS 块 / ≤MAX_PACK_CHARS 字）。

    优先级：主段 > 原型保底一席 > K1/K2 补充 > 其余原型 > 图谱桥
    （原型图挂靠成功就必须进包——它承载正文没有的界面约束，不能被提及块挤出）。
    返回 (文本, 来源清单, 是否截断)。"""
    ordered = (
        cand["primary"]
        + cand["prototypes"][:1]
        + [b for b in cand["supplements"] if b["kind"] == "mention"]
        + cand["prototypes"][1:]
        + [b for b in cand["supplements"] if b["kind"] == "graph"]
    )
    truncated = len(ordered) > MAX_BLOCKS_PER_PACK
    ordered = ordered[:MAX_BLOCKS_PER_PACK]
    parts: list[str] = []
    sources: list[str] = []
    used = 0
    for b in ordered:
        label = f"《{b['doc']}》› {b['heading']}" if b["heading"] else f"《{b['doc']}》"
        body = b["content"]
        remain = MAX_PACK_CHARS - used
        if remain <= 0:
            truncated = True
            break
        if len(body) > remain:
            body = body[:remain]
            truncated = True
        parts.append(f"### 来源：{label}\n{body}")
        if label not in sources:
            sources.append(label)
        used += len(body)
    return "\n\n".join(parts), sources, truncated


# ─────────────────────────────────────────────────────────────
# 图
# ─────────────────────────────────────────────────────────────


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def run(state: SweepState) -> dict:
        from sqlalchemy import select

        from app.crud.func_test.requirement import crud_requirement
        from app.models.func_test.requirement import (
            RequirementSource,
            RequirementStatus,
            TestRequirement,
        )
        from app.models.knowledge.chunk import KbChunk
        from app.models.knowledge.document import (
            KbDocument,
            KbDocumentStatus,
            KbDocValidity,
        )
        from app.models.knowledge.graph import KbEntity, KbEntityMention
        from app.services.func_test.document_parse_service import parse_llm_json

        project_id = ctx.project_id

        # ── ① 读取语料（全库 ready+effective）──
        ctx.stage("扫描项目文档", index=1, total=4)
        ctx.progress(5)
        async with async_session_maker() as db:
            doc_rows = (
                await db.execute(
                    select(
                        KbDocument.id,
                        KbDocument.file_name,
                        KbDocument.doc_type,
                        KbDocument.file_ext,
                        KbDocument.content_md,
                    ).where(
                        KbDocument.project_id == project_id,
                        KbDocument.status == KbDocumentStatus.READY.value,
                        KbDocument.validity == KbDocValidity.EFFECTIVE.value,
                    )
                )
            ).all()
            doc_info = {r[0]: {"name": r[1], "type": r[2], "ext": (r[3] or "").lower()} for r in doc_rows}
            image_docs = [
                {"id": r[0], "file_name": r[1], "content_md": r[4] or ""}
                for r in doc_rows
                if (r[3] or "").lower() in _IMAGE_EXTS
            ]
            text_doc_ids = [d for d in doc_info if doc_info[d]["ext"] not in _IMAGE_EXTS]
            chunks: list[dict] = []
            if text_doc_ids:
                rows = (
                    await db.execute(
                        select(
                            KbChunk.id,
                            KbChunk.document_id,
                            KbChunk.parent_chunk_id,
                            KbChunk.heading_path,
                            KbChunk.content,
                        ).where(
                            KbChunk.project_id == project_id,
                            KbChunk.document_id.in_(text_doc_ids),
                        )
                    )
                ).all()
                chunks = [
                    {
                        "id": r[0],
                        "document_id": r[1],
                        "is_parent": r[2] is None,
                        "heading_path": r[3] or "",
                        "content": r[4] or "",
                        "doc_name": doc_info[r[1]]["name"],
                        "doc_type": doc_info[r[1]]["type"],
                    }
                    for r in rows
                ]
            entities = [
                {"id": e.id, "name": e.name}
                for e in (
                    await db.execute(
                        select(KbEntity).where(
                            KbEntity.project_id == project_id,
                            KbEntity.is_deleted.is_(False),
                            KbEntity.merged_into_id.is_(None),
                        )
                    )
                ).scalars()
            ]
            mentions = [
                {
                    "entity_id": m.entity_id,
                    "chunk_id": m.chunk_id,
                    "document_id": m.document_id,
                }
                for m in (
                    await db.execute(
                        select(KbEntityMention).where(
                            KbEntityMention.project_id == project_id
                        )
                    )
                ).scalars()
            ]
        ctx.log(
            f"语料：文本文档 {len(text_doc_ids)} 份（{len(chunks)} 块）、"
            f"图片文档 {len(image_docs)} 份、图谱实体 {len(entities)} 个"
        )
        if not chunks:
            raise ValueError("知识库中没有可盘点的文本文档，请先在「项目知识库」上传并入库文档")

        # ── ② 发现 + 三级合并 + 原型挂靠（全零 LLM）──
        ctx.stage("候选发现与跨文档合并", index=2, total=4)
        ctx.progress(15)
        candidates, disc = discover_candidates(chunks)
        if len(candidates) > MAX_CANDIDATES:
            ctx.log(
                f"候选超上限（{MAX_CANDIDATES}），截断 {len(candidates) - MAX_CANDIDATES} 个",
                level="warning",
            )
            candidates = dict(list(candidates.items())[:MAX_CANDIDATES])
        chunk_map = {c["id"]: c for c in chunks}
        bridged = bridge_graph_entities(candidates, entities, mentions, chunk_map)
        proto_attached, unplaced = attach_prototypes(
            candidates, image_docs, entities, mentions
        )
        ctx.log(
            f"候选 {len(candidates)} 个；图谱桥接补充块 {bridged} 个；"
            f"原型图挂靠 {proto_attached} 张、未归位 {len(unplaced)} 张"
        )
        if disc["mention_only_codes"]:
            ctx.log(
                f"提及但无独立章节的编号（未造候选，防清单噪声）："
                f"{'、'.join(disc['mention_only_codes'][:10])}"
                + ("…" if len(disc["mention_only_codes"]) > 10 else "")
            )

        # ── ③ 逐证据包 LLM 结构化 ──
        ctx.stage("AI 逐条结构化", index=3, total=4)
        from app.ai_core.prompts.func_test_prompts import (
            build_requirement_sweep_prompt,
        )

        llm = get_current_llm()
        structured: list[dict] = []
        failed: list[str] = []
        items = list(candidates.values())
        for i, cand in enumerate(items):
            ctx.progress(20 + int(60 * (i + 1) / max(len(items), 1)))
            evidence, sources, truncated = assemble_evidence(cand)
            try:
                resp = await llm.ainvoke(
                    build_requirement_sweep_prompt(
                        evidence, hint_code=cand["code"], hint_title=cand["title"]
                    )
                )
                raw = str(getattr(resp, "content", "") or "")
                try:
                    data = parse_llm_json(raw)
                except ValueError:
                    # 一次修复重试：把原输出回喂请其只输出合法 JSON
                    resp2 = await llm.ainvoke(
                        build_requirement_sweep_prompt(
                            evidence,
                            hint_code=cand["code"],
                            hint_title=cand["title"],
                            repair_from=raw[:2000],
                        )
                    )
                    data = parse_llm_json(str(getattr(resp2, "content", "") or ""))
                if not isinstance(data, dict):
                    raise ValueError("结构化结果不是 JSON 对象")
                data["_sources"] = sources
                data["_truncated"] = truncated
                data["_hint_code"] = cand["code"]
                structured.append(data)
                ctx.log(
                    f"[{i + 1}/{len(items)}] {cand['code'] or cand['title']}："
                    + ("✓" if data.get("is_requirement", True) else "非需求，跳过")
                )
            except Exception as exc:  # noqa: BLE001 —— 单包失败不炸整轮
                logger.warning("证据包结构化失败 %s: %s", cand["key"], exc)
                failed.append(cand["code"] or cand["title"])

        # ── ④ 幂等落库 ──
        ctx.stage("幂等落库", index=4, total=4)
        ctx.progress(85)
        created: list[int] = []
        skipped: list[str] = []
        low_conf: list[str] = []
        async with async_session_maker() as db:
            rows = (
                await db.execute(
                    select(
                        TestRequirement.code, TestRequirement.title
                    ).where(
                        TestRequirement.project_id == project_id,
                        TestRequirement.is_deleted == False,  # noqa: E712
                    )
                )
            ).all()
            existing_codes = {r[0] for r in rows if r[0]}
            existing_titles = {normalize_title(r[1]) for r in rows}

            for data in structured:
                if not data.get("is_requirement", True):
                    continue
                # code 以确定性的候选锚为准（LLM 可能返回「REQ-X-001 / 003」复合串，
                # 与候选 key 漂移会破坏重跑幂等）；LLM code 仅兜底且只取首个合法编号
                llm_code = REQ_CODE_RE.findall(str(data.get("code") or ""))
                code = data.get("_hint_code") or (llm_code[0] if llm_code else None)
                title = str(data.get("title") or "").strip()
                if not title:
                    continue
                if code and code in existing_codes:
                    skipped.append(code)
                    continue
                if normalize_title(title) in existing_titles:
                    skipped.append(title)
                    continue
                desc = str(data.get("description") or "").strip()
                if data.get("_sources"):
                    desc += "\n\n---\n**来源**：\n" + "\n".join(
                        f"- {s}" for s in data["_sources"]
                    )
                priority = str(data.get("priority") or "medium").lower()
                if priority not in ("urgent", "high", "medium", "low"):
                    priority = "medium"
                req = await crud_requirement.create(
                    db,
                    project_id=project_id,
                    title=title[:200],
                    code=code,
                    priority=priority,
                    status=RequirementStatus.DRAFT.value,
                    description=desc or None,
                    acceptance_criteria=(
                        str(data.get("acceptance_criteria") or "").strip() or None
                    ),
                    source=RequirementSource.AI_GENERATED.value,
                    created_by=ctx.user_id,
                )
                created.append(req.id)
                if code:
                    existing_codes.add(code)
                existing_titles.add(normalize_title(title))
                try:
                    conf = float(data.get("confidence") or 1.0)
                except (TypeError, ValueError):
                    conf = 1.0
                if conf < LOW_CONFIDENCE:
                    low_conf.append(f"{code or title}（{conf:.2f}）")

        if not created:
            ctx.log("本次未新增需求：候选均已存在或非需求。", level="warning")
        ctx.log(f"盘点完成：新增 {len(created)} 条草稿、跳过 {len(skipped)} 条已存在")
        ctx.set_result(
            summary={
                "metrics": [
                    {
                        "label": "新增需求草稿",
                        "value": len(created),
                        "highlight": True,
                        "color": "warning" if not created else None,
                    },
                    {"label": "已存在跳过", "value": len(skipped)},
                    {
                        "label": "低置信",
                        "value": len(low_conf),
                        "color": "warning" if low_conf else None,
                    },
                    {
                        "label": "结构化失败",
                        "value": len(failed),
                        "color": "danger" if failed else None,
                    },
                    {"label": "原型图挂靠", "value": proto_attached},
                    {
                        "label": "未归位原型图",
                        "value": len(unplaced),
                        "color": "warning" if unplaced else None,
                    },
                ],
                "low_confidence": low_conf,
                "failed": failed,
                "unplaced_materials": [u["file_name"] for u in unplaced],
                "mention_only_codes": disc["mention_only_codes"],
                "new_requirements": len(created),
            },
            ref={
                "kind": "requirements",
                "requirement_ids": created,
            },
        )
        return {"created_count": len(created)}

    graph = StateGraph(SweepState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {"project_id": int(params.get("project_id") or 0)}


def title(params: dict) -> str:
    return "AI 需求盘点"


register(
    TaskSpec(
        task_type="extract_requirements",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",
        dedupe=True,
    )
)
