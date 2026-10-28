"""知识库检索离线评测（P2 WP-C5，图路/深度模式放量 gate 的实测依据）

golden set YAML 形如：
    - query: 退款多久能到账
      expect_doc_ids: [12]            # 命中判定其一：document_id 命中
      expect_keywords: ["三个工作日"]   # 或：单条 hit 内容包含全部关键词
    - query: 登录失败几次锁定
      expect_keywords: ["五次", "锁定"]

用法（backend/ 下）：
    PYTHONPATH=. uv run python scripts/kb_eval.py --project 1 --golden golden.yaml \
        [--user 1] [--top-k 10] [--deep] [--compare-graph]

--compare-graph：同一 golden set 跑「图路关 vs 开」对照（临时翻转
kb.settings.graph_channel,跑完恢复原值）——输出两组 hit@k/MRR 对照表,
是 §5 P2「≥20 条评测不回退+净增益才放」gate 的证据产出器。

指标：hit@1 / hit@3 / hit@k、MRR（按首条相关命中名次）。
⚠ dev 无 EMBED key 时向量路降级,结果仅代表全文(+图)单路水平——发版 gate
必须在配好真实 EMBED 的环境跑。脚本不进 CI。
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.crud.knowledge import crud_knowledge_base  # noqa: E402
from app.db.session import async_session_maker, engine  # noqa: E402
from app.services.knowledge import retrieval_service  # noqa: E402


def _is_relevant(hit: Any, case: dict) -> bool:
    doc_ids = case.get("expect_doc_ids") or []
    if doc_ids and hit.document_id in set(doc_ids):
        return True
    keywords = case.get("expect_keywords") or []
    if keywords:
        text = f"{hit.doc_name}\n{hit.heading_path}\n{hit.content}"
        if all(str(k) in text for k in keywords):
            return True
    return False


async def _run_suite(
    *, project_id: int, cases: list[dict], top_k: int, user_id: Optional[int], deep: bool
) -> dict[str, Any]:
    rows = []
    async with async_session_maker() as db:
        for case in cases:
            query = str(case.get("query") or "").strip()
            if not query:
                continue
            data = await retrieval_service.search(
                db,
                project_id=project_id,
                query=query,
                top_k=top_k,
                prefer_user_id=user_id,
                consumer="search",
                deep=deep,
            )
            rank = next(
                (i + 1 for i, h in enumerate(data.hits) if _is_relevant(h, case)),
                None,
            )
            rows.append(
                {
                    "query": query,
                    "rank": rank,
                    "hits": len(data.hits),
                    "degraded": data.degraded.vector or data.degraded.fulltext,
                    "graph_boosted": data.graph_boosted,
                }
            )
    n = len(rows) or 1
    ranked = [r["rank"] for r in rows if r["rank"]]
    return {
        "rows": rows,
        "n": len(rows),
        "hit@1": sum(1 for r in ranked if r <= 1) / n,
        "hit@3": sum(1 for r in ranked if r <= 3) / n,
        f"hit@{top_k}": len(ranked) / n,
        "mrr": sum(1.0 / r for r in ranked) / n,
    }


def _print_suite(title: str, s: dict[str, Any], top_k: int) -> None:
    print(f"\n== {title}（{s['n']} 条）==")
    print(
        f"  hit@1={s['hit@1']:.2f}  hit@3={s['hit@3']:.2f}  "
        f"hit@{top_k}={s[f'hit@{top_k}']:.2f}  MRR={s['mrr']:.3f}"
    )
    for r in s["rows"]:
        mark = f"#{r['rank']}" if r["rank"] else "MISS"
        flags = ("⚠降级 " if r["degraded"] else "") + ("图路 " if r["graph_boosted"] else "")
        print(f"  [{mark:>4}] {flags}{r['query']}")


async def _set_graph_channel(project_id: int, value: Optional[bool]) -> Optional[bool]:
    """翻转图路开关,返回旧值（value=None 表示只读取）"""
    async with async_session_maker() as db:
        kb = await crud_knowledge_base.get_by_project(db, project_id=project_id)
        if kb is None:
            raise SystemExit(f"项目 {project_id} 无知识库")
        old = bool((kb.settings or {}).get("graph_channel"))
        if value is not None:
            settings = dict(kb.settings or {})
            settings["graph_channel"] = value
            kb.settings = settings
            db.add(kb)
            await db.commit()
        return old


async def main() -> None:
    ap = argparse.ArgumentParser(description="知识库检索离线评测")
    ap.add_argument("--project", type=int, required=True)
    ap.add_argument("--golden", type=str, required=True, help="golden set YAML 路径")
    ap.add_argument("--user", type=int, default=None, help="prefer_user_id（embed key 解析）")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--compare-graph", action="store_true", help="图路关/开对照")
    args = ap.parse_args()

    cases = yaml.safe_load(Path(args.golden).read_text(encoding="utf-8")) or []
    if not isinstance(cases, list) or not cases:
        raise SystemExit("golden set 为空或格式错误（应为条目数组）")

    try:
        if not args.compare_graph:
            suite = await _run_suite(
                project_id=args.project, cases=cases, top_k=args.top_k,
                user_id=args.user, deep=args.deep,
            )
            _print_suite("检索评测", suite, args.top_k)
        else:
            original = await _set_graph_channel(args.project, None)
            try:
                await _set_graph_channel(args.project, False)
                off = await _run_suite(project_id=args.project, cases=cases,
                                       top_k=args.top_k, user_id=args.user, deep=args.deep)
                await _set_graph_channel(args.project, True)
                on = await _run_suite(project_id=args.project, cases=cases,
                                      top_k=args.top_k, user_id=args.user, deep=args.deep)
            finally:
                await _set_graph_channel(args.project, original)
            _print_suite("图路 OFF", off, args.top_k)
            _print_suite("图路 ON", on, args.top_k)
            print("\n== gate 判定参考 ==")
            regressed = sum(
                1 for a, b in zip(off["rows"], on["rows"])
                if a["rank"] and (b["rank"] is None or b["rank"] > a["rank"])
            )
            improved = sum(
                1 for a, b in zip(off["rows"], on["rows"])
                if b["rank"] and (a["rank"] is None or b["rank"] < a["rank"])
            )
            print(f"  改善 {improved} 条 / 回退 {regressed} 条 / MRR {off['mrr']:.3f} → {on['mrr']:.3f}")
            print("  放量条件：回退=0 且 MRR 净增益（设计 §5 P2 gate）")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
