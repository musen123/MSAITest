"""AI 造测试文件 —— 统一 AI 任务图（kind=ai，结构化输出）

据自然语言需求让 LLM 产**文件规格清单**，代码侧逐个 forge 真实文件（file_forge，
LLM 不碰二进制）→ 存平台 → 注册 test_file_asset。逐个落库：单文件失败跳过不炸任务
（对齐分批生成理念）。产出的资产供 Web 脚本 ${{file:名}} 引用（D3）。
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.ai_core.llm_context import get_current_llm
from app.ai_core.prompts.test_data_prompts import build_file_spec_prompt, spec_to_forge
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.test_data import crud_test_file_asset
from app.db.session import async_session_maker
from app.schemas.test_data.file_asset import validate_asset_name
from app.services.test_data.file_forge import forge_file, normalize_kind
from app.utils.storage_utils import save_bytes

AI_MAX_FILES = 30  # 单任务造文件数上限（防失控）


class FileSpec(BaseModel):
    name: str = Field(description="资产引用名（项目内唯一，不含空格/冒号/花括号）")
    file_name: str = Field(description="文件名含扩展名")
    kind: str = Field(description="pdf/docx/xlsx/csv/txt/json/md/png/bin")
    text: str = Field("", description="文件文本内容")
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    target_size_bytes: Optional[int] = Field(None, description="仅大文件需求给")


class FileSpecList(BaseModel):
    files: list[FileSpec] = Field(description="要生成的文件规格清单")
    notes: str = Field("", description="一句中文小结")


class GenFilesState(TypedDict, total=False):
    requirement: str
    count: int


def build_graph(params: dict, ctx: TaskContext) -> Any:
    async def run(state: GenFilesState) -> dict:
        requirement = (state.get("requirement") or "").strip()
        if not requirement:
            raise ValueError("请描述要生成的测试文件需求")
        count = max(1, min(int(state.get("count") or 3), AI_MAX_FILES))

        # 1. LLM 产规格清单
        ctx.stage("规划文件规格", index=1, total=3)
        ctx.progress(10)
        async with async_session_maker() as db:
            existing, _ = await crud_test_file_asset.list_by_project(
                db, project_id=ctx.project_id, limit=50
            )
        existing_names = [a.name for a in existing]
        llm = get_current_llm().with_structured_output(FileSpecList)
        messages = build_file_spec_prompt(
            requirement=requirement, count=count, existing_names=existing_names
        )
        plan: FileSpecList = await llm.ainvoke(messages)
        specs = plan.files[:AI_MAX_FILES]
        if not specs:
            raise ValueError("AI 未产出任何文件规格，请细化需求后重试")
        ctx.log(f"规划出 {len(specs)} 个文件，开始逐个生成…")

        # 2. 逐个 forge + 存 + 落库（失败跳过）
        ctx.stage("生成并入库", index=2, total=3)
        used_names = set(existing_names)
        created: list[dict] = []
        failed = 0
        for i, spec in enumerate(specs):
            raw_name = (spec.name or f"file_{i + 1}").strip()
            # 引用名去重 + 合法化
            name = raw_name
            suffix = 1
            while name in used_names:
                suffix += 1
                name = f"{raw_name}_{suffix}"
            try:
                validate_asset_name(name)
            except ValueError:
                name = f"file_{uuid.uuid4().hex[:8]}"
            file_name = spec.file_name or f"{name}.txt"
            kind = normalize_kind(spec.kind, file_name)
            try:
                content, mime = await asyncio.to_thread(
                    forge_file, spec_to_forge(spec.model_dump())
                )
                ext = Path(file_name).suffix.lower() or f".{kind}"
                storage_key = f"test_data/{ctx.project_id}/{uuid.uuid4().hex}{ext}"
                await asyncio.to_thread(save_bytes, content, storage_key)
                async with async_session_maker() as db:
                    asset = await crud_test_file_asset.create(
                        db,
                        project_id=ctx.project_id,
                        created_by=ctx.user_id,
                        name=name,
                        file_name=file_name,
                        storage_key=storage_key,
                        mime=mime,
                        size_bytes=len(content),
                        source="ai",
                        spec=(spec.text or "")[:500] or requirement[:500],
                        ai_task_id=ctx.task_id,
                    )
                used_names.add(name)
                created.append({"id": asset.id, "name": name, "size": len(content), "kind": kind})
                ctx.log(
                    f"  + {name}（{kind}，{len(content)} 字节）已入库", level="stream"
                )
            except Exception as exc:  # noqa: BLE001 —— 单文件失败不炸任务
                failed += 1
                ctx.log(
                    f"  ✗ 文件「{name}」生成失败已跳过：{exc}", level="warning"
                )
            ctx.progress(10 + int(80 * (i + 1) / len(specs)))

        # 3. 收尾
        ctx.stage("收尾", index=3, total=3)
        if not created:
            raise RuntimeError(
                f"全部 {len(specs)} 个文件生成失败（检查文件类型/内容规格）"
            )
        ctx.log(
            f"已生成 {len(created)} 个测试文件资产"
            + (f"，{failed} 个失败已跳过" if failed else "")
        )
        ctx.set_result(
            summary={
                "metrics": [
                    {"label": "生成文件", "value": len(created), "unit": "个", "highlight": True},
                    {
                        "label": "失败",
                        "value": failed,
                        "color": "warning" if failed else None,
                    },
                    {"label": "引用名", "value": "、".join(c["name"] for c in created[:8]) or "—"},
                ],
                "notes": (plan.notes or "")[:500],
                "assets": created,
            },
            ref={"kind": "test_files", "asset_ids": [c["id"] for c in created]},
        )
        return {}

    graph = StateGraph(GenFilesState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {
        "requirement": params.get("requirement") or params.get("intent") or "",
        "count": int(params.get("count") or 3),
    }


def title(params: dict) -> str:
    return "AI 造测试文件"


register(
    TaskSpec(
        task_type="generate_test_files",
        kind="ai",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",
        dedupe=False,
        stream_messages=False,
    )
)
