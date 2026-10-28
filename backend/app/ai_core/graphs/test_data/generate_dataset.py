"""AI 造测试数据集 —— 统一 AI 任务图（kind=ai，结构化输出）

据列定义(name/desc/kind)+意图让 LLM 批量生成多样化数据，落 test_dataset(source=ai)。
复用压测造数 prompt（列结构一致）与清洗逻辑；行明文（内部测试平台）。执行时由
Web/接口执行配置绑定数据集、按策略取行注入为变量覆盖（D3）。

安全口径同压测：prompt 只发列元信息（名/说明/性质），绝不发样例值。
"""

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.ai_core.llm_context import get_current_llm
from app.ai_core.prompts.test_data_prompts import build_dataset_gen_prompt
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.test_data import crud_test_dataset
from app.db.session import async_session_maker
from app.schemas.test_data.dataset import MAX_DATASET_ROWS, TestDatasetColumn

AI_MAX_ROWS = 200  # 单次 LLM 造数行数预算


class DatasetGen(BaseModel):
    rows: list[dict] = Field(description="数据行数组，每行键对齐列名，只含声明的列")
    notes: str = Field("", description="一句中文：哪些列已合成、哪些需用户预置真实数据")


class GenDatasetState(TypedDict, total=False):
    columns: list
    count: int
    intent: Optional[str]
    dataset_name: Optional[str]


def _validate_gen_columns(raw_cols) -> list[dict]:
    cols = [TestDatasetColumn.model_validate(c).model_dump() for c in (raw_cols or [])]
    if not cols:
        raise ValueError("造数需先定义至少一列")
    names = [c["name"] for c in cols]
    if len(names) != len(set(names)):
        raise ValueError("列名重复")
    return cols


def _row_value(row: dict, col: dict):
    """从 LLM 行里容错取值：精确列名 → desc → 去空格大小写不敏感（模型常不严格回 key）。"""
    name = str(col.get("name") or "")
    if name in row and row[name] not in (None, ""):
        return row[name]
    desc = str(col.get("desc") or "")
    norm = {str(k).strip().lower(): v for k, v in row.items()}
    for cand in (name.strip().lower(), desc.strip().lower()):
        if cand and norm.get(cand) not in (None, ""):
            return norm[cand]
    return None


def _sanitize_rows(rows, columns) -> list[dict]:
    valid_cols = [c for c in columns if c.get("name")]
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append({c["name"]: ("" if _row_value(row, c) is None else str(_row_value(row, c))) for c in valid_cols})
    return out


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def run(state: GenDatasetState) -> dict:
        ctx.stage("校验列定义", index=1, total=3)
        ctx.progress(10)
        cols = _validate_gen_columns(state.get("columns") or [])
        count = max(1, min(int(state.get("count") or 50), AI_MAX_ROWS, MAX_DATASET_ROWS))
        intent = state.get("intent")
        ds_name = (state.get("dataset_name") or "").strip() or "AI 造数集"
        all_col_names = [c["name"] for c in cols]

        ctx.stage("AI 生成数据", index=2, total=3)
        ctx.progress(40)
        ctx.log(f"调用文本模型造数：{count} 行 × {len(cols)} 列")
        llm = get_current_llm().with_structured_output(DatasetGen)
        gen: DatasetGen = await llm.ainvoke(
            build_dataset_gen_prompt(columns=cols, count=count, intent=intent)
        )
        rows = _sanitize_rows(gen.rows, cols)[:MAX_DATASET_ROWS]
        for sc in all_col_names:
            if rows and all(not (r.get(sc) or "") for r in rows):
                ctx.log(
                    f"⚠ 列「{sc}」整列为空——模型可能未按列名回值；"
                    "建议列名用规范英文（username/password）后重试",
                    "warning",
                )
        if not rows:
            raise ValueError("AI 未产出有效数据行，请调整意图或列定义后重试")

        ctx.stage("落库", index=3, total=3)
        ctx.progress(85)
        desc = (gen.notes or "").strip()[:500] or f"AI 造数：{intent or '通用测试数据'}"
        async with async_session_maker() as db:
            ds = await crud_test_dataset.create(
                db,
                project_id=ctx.project_id,
                created_by=ctx.user_id,
                name=ds_name,
                description=desc,
                columns=cols,
                rows=rows,
                source="ai",
                ai_task_id=ctx.task_id,
            )
            dataset_id = ds.id

        ctx.log(f"已生成数据集 #{dataset_id}「{ds_name}」{len(rows)} 行")
        ctx.set_result(
            summary={
                "metrics": [
                    {"label": "数据集", "value": ds_name, "highlight": True},
                    {"label": "行数", "value": len(rows), "unit": "行"},
                    {"label": "生成列", "value": "、".join(all_col_names) or "—"},
                ],
                "dataset_id": dataset_id,
                "notes": desc,
            },
            ref={"kind": "test_dataset", "dataset_id": dataset_id},
        )
        return {}

    graph = StateGraph(GenDatasetState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {
        "columns": params.get("columns") or [],
        "count": int(params.get("count") or 50),
        "intent": params.get("intent"),
        "dataset_name": params.get("dataset_name"),
    }


def title(params: dict) -> str:
    return "AI 生成测试数据集"


register(
    TaskSpec(
        task_type="generate_test_dataset",
        kind="ai",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",
        dedupe=False,
        stream_messages=False,
    )
)
