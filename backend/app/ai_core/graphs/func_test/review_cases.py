"""AI 用例评审（统一 AI 任务图，从生成流水线拆出的独立任务）

按需求加载待评审用例（draft/pending_review）→ 一次批量评审 → 逐条写回 review_info。

设计原则（企业落地）：
  - **只标注不拦截**：AI 评审结论写入 review_info 供人工评审预筛，绝不改状态、
    绝不删除用例——最终裁决权在人（需求页/用例页的人工评审流）；
  - **失败显式**：LLM 调用/解析失败（含一次 JSON 修复重试后）直接任务失败，
    不做旧工作流那种"评审失败默认全部通过"的静默降级；
  - 可独立重跑：对同一需求可反复触发（覆盖旧标注）；生成任务收尾也会按
    enable_review 自动派发本任务。

入参：requirement_id（必填）；case_ids（可选，只评子集）。
"""

import logging
from typing import Any, Optional, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.func_test.requirement import crud_requirement
from app.crud.func_test.test_case import crud_test_case
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

_REVIEWABLE = {"draft", "pending_review"}


class ReviewCasesState(TypedDict, total=False):
    requirement_id: int
    case_ids: Optional[list]
    reviewed_count: int


def serialize_for_review(cases: list[Any]) -> list[dict]:
    """ORM 用例 → 评审 prompt 的输入 dict（与生成产物字段名对齐）。"""
    return [
        {
            "case_id": c.code or f"db_{c.id}",
            "case_name": c.title,
            "priority": c.priority,
            "preconditions": c.preconditions,
            "test_data": c.test_data,
            "execute_step": c.steps,
            "expected_result": c.expected_result,
        }
        for c in cases
    ]


def map_review_results(cases: list[Any], results: Any) -> tuple[dict, list]:
    """评审输出 results → {case.id: {review_info, ui_automatable}}；返回 (映射, 未评到清单)。

    按 case_id（code/db_id 兜底键）对齐；LLM 漏评的用例不猜结论，进未评清单。
    ui_automatable 只认布尔值，缺失/非法归 None（=本次不改动该列，保留生成期初判）。
    """
    by_key = {}
    for r in results if isinstance(results, list) else []:
        if isinstance(r, dict) and r.get("case_id"):
            by_key[str(r["case_id"])] = r
    mapped: dict[int, dict] = {}
    missed: list = []
    for c in cases:
        key = c.code or f"db_{c.id}"
        r = by_key.get(str(key))
        if r is None:
            missed.append(c)
            continue
        ua = r.get("ui_automatable")
        mapped[c.id] = {
            "review_info": {
                "review_result": r.get("review_result") or "通过",
                "review_decs": str(r.get("review_decs") or "")[:200],
            },
            "ui_automatable": ua if isinstance(ua, bool) else None,
        }
    return mapped, missed


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def run(state: ReviewCasesState) -> dict:
        from app.ai_core.llm_context import get_current_llm
        from app.ai_core.prompts.func_test_prompts import build_review_prompt
        from app.services.func_test.document_parse_service import parse_llm_json

        requirement_id = state["requirement_id"]
        only_ids = set(state.get("case_ids") or [])

        # 1. 加载需求与待评审用例
        ctx.stage("加载用例", index=1, total=3)
        ctx.progress(10)
        async with async_session_maker() as db:
            req = await crud_requirement.get(db, requirement_id)
            if not req:
                raise ValueError(f"需求不存在：{requirement_id}")
            if req.project_id != ctx.project_id:
                raise ValueError(f"需求不属于该项目：{requirement_id}")
            from app.ai_core.graphs.func_test.generate_case import (
                _build_requirements_text,
            )

            requirements_text = _build_requirements_text(req)
            all_cases = await crud_test_case.list_by_requirement(
                db, requirement_id=requirement_id
            )
        cases = [
            c
            for c in all_cases
            if c.status in _REVIEWABLE and (not only_ids or c.id in only_ids)
        ]
        if not cases:
            ctx.log("该需求下没有待评审用例（draft/pending_review），无需评审。", level="warning")
            ctx.set_result(
                summary={
                    "metrics": [
                        {"label": "待评审用例", "value": 0, "color": "warning"}
                    ]
                },
                ref={"kind": "func_cases", "case_ids": [], "requirement_id": requirement_id},
            )
            return {"reviewed_count": 0}
        ctx.log(f"需求「{req.title}」，待评审用例 {len(cases)} 条")

        # 2. 批量评审（失败显式，绝不静默通过）
        ctx.stage("AI 评审", index=2, total=3)
        ctx.progress(30)
        llm = get_current_llm()
        messages = build_review_prompt(requirements_text, serialize_for_review(cases))

        async def _call(msgs) -> str:
            acc: list[str] = []
            async for chunk in llm.astream(msgs):
                c = getattr(chunk, "content", None)
                if isinstance(c, str):
                    acc.append(c)
                elif isinstance(c, list):
                    for x in c:
                        if isinstance(x, str):
                            acc.append(x)
                        elif isinstance(x, dict):
                            acc.append(x.get("text") or "")
            return "".join(acc)

        content = await _call(messages)
        try:
            data = parse_llm_json(content)
        except Exception:
            ctx.log("评审输出非法 JSON，进行修复重试…", level="warning")
            content = await _call(
                messages
                + [
                    HumanMessage(
                        content=(
                            "⚠ 你上一次的输出不是合法 JSON（截取如下），"
                            "请重新**只输出**符合约定的 JSON 对象：\n"
                            f"{content[:1500]}"
                        )
                    )
                ]
            )
            data = parse_llm_json(content)
        if not isinstance(data, dict):
            raise RuntimeError(
                f"用例评审失败：模型返回结构非评审对象（实际为 {type(data).__name__}）"
            )
        mapped, missed = map_review_results(cases, data.get("results"))

        # 3. 写回 review_info + ui_automatable（只标注，不改状态）
        ctx.stage("写回评审结论", index=3, total=3)
        ctx.progress(80)
        passed = failed = 0
        non_ui = 0  # 评审判定"不适合 UI 自动化"的条数
        async with async_session_maker() as db:
            for c in cases:
                m = mapped.get(c.id)
                if m is None:
                    continue
                fresh = await crud_test_case.get(db, case_id=c.id)
                if fresh is None:
                    continue
                info = m["review_info"]
                # ui_automatable=None 时 crud.update 会跳过该列（保留生成期初判，不误清）
                await crud_test_case.update(
                    db, case=fresh, review_info=info, ui_automatable=m["ui_automatable"]
                )
                if info["review_result"] == "通过":
                    passed += 1
                else:
                    failed += 1
                    ctx.log(f"  ✗ {c.title}：{info['review_decs']}", level="warning")
                if m["ui_automatable"] is False:
                    non_ui += 1
                    ctx.log(
                        f"  ⛔ 不适合 UI 自动化：{c.title}（{info['review_decs']}）",
                        level="warning",
                    )
        for c in missed:
            ctx.log(f"  ? 模型未给出评审结论：{c.title}", level="warning")

        ctx.log(
            f"评审完成：通过 {passed}，不通过 {failed}，未评到 {len(missed)}，"
            f"其中判定不适合 UI 自动化 {non_ui} 条"
        )
        ctx.set_result(
            summary={
                "metrics": [
                    {"label": "评审通过", "value": passed, "highlight": True},
                    {
                        "label": "评审不通过",
                        "value": failed,
                        "color": "warning" if failed else None,
                    },
                    {
                        "label": "不适合UI自动化",
                        "value": non_ui,
                        "color": "warning" if non_ui else None,
                    },
                    {
                        "label": "未评到",
                        "value": len(missed),
                        "color": "warning" if missed else None,
                    },
                ],
                "report": str(data.get("report") or "")[:2000],
                "passed": passed,
                "failed": failed,
                "missed": len(missed),
            },
            ref={
                "kind": "func_cases",
                "case_ids": [c.id for c in cases],
                "requirement_id": requirement_id,
            },
        )
        return {"reviewed_count": passed + failed}

    graph = StateGraph(ReviewCasesState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    out: dict = {"requirement_id": int(params["requirement_id"])}
    if params.get("case_ids"):
        out["case_ids"] = [int(v) for v in params["case_ids"]]
    return out


def title(params: dict) -> str:
    name = params.get("requirement_title")
    return f"用例评审：{name}" if name else "AI 用例评审"


register(
    TaskSpec(
        task_type="review_cases",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",
        dedupe=True,
    )
)
