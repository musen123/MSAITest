"""需求理解（统一 AI 任务图）

VLM 逐张理解需求附件图片 → LLM 综合原始描述整理为结构化 Markdown
→ 写回 ``requirement.understood_content``。

图结构（2 节点）：
    understand_images  逐图 VLM 流式理解（每张图一个 stage，token 冒泡为 message_delta）
    summarize          LLM 流式整理（token 冒泡），回写需求

前端面板按 stage 事件切换 token 写入目标（图片卡片 / 总结区）。
"""

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai_core.llm_client import strip_think_tags
from app.ai_core.llm_context import get_current_llm, get_current_vision_llm
from app.ai_core.prompts.func_test_prompts import (
    build_understand_prompt,
    build_vlm_messages,
)
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.llm import load_user_llms
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.func_test.requirement import crud_requirement
from app.db.session import async_session_maker
from app.services.func_test.document_parse_service import _read_image_to_data_url


class UnderstandState(TypedDict, total=False):
    requirement_id: int
    description: str
    attachments: list  # 原始 URL（前端展示用顺序）
    image_results: list  # 每张图的理解文本
    summary: str


async def _resolve_image_url(url: str) -> str:
    """把附件 URL 解析为 VLM 可消费的形式。

    - 本地 ``/uploads/{key}``：worker 直接读文件转 data url（提供商无法访问本机）
    - http(s)（COS 预签名等外网可达）：原样传递
    - 其他（已是 data url 等）：原样传递
    """
    if url.startswith("/uploads/"):
        from pathlib import Path

        from app.core.config import settings

        local_path = Path(settings.UPLOAD_DIR) / url[len("/uploads/"):]
        if not local_path.exists():
            raise ValueError(f"附件文件不存在：{url}")
        return _read_image_to_data_url(local_path)
    return url


async def _astream_text(llm: Any, messages: Any) -> str:
    """流式调用并累计文本（token 由 messages 模式自动转 message_delta）"""
    acc: list[str] = []
    async for chunk in llm.astream(messages):
        content = getattr(chunk, "content", None)
        if isinstance(content, str):
            acc.append(content)
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, str):
                    acc.append(c)
                elif isinstance(c, dict):
                    acc.append(c.get("text") or "")
    return "".join(acc)


def build_graph(params: dict, ctx: TaskContext) -> Any:
    custom_prompt: Optional[str] = params.get("custom_prompt")
    extra_attachments: list = params.get("extra_attachments") or []

    async def understand_images(state: UnderstandState) -> dict:
        requirement_id = state["requirement_id"]
        async with async_session_maker() as db:
            req = await crud_requirement.get(db, requirement_id)
            if not req:
                raise ValueError(f"需求不存在：{requirement_id}")
            if req.project_id != ctx.project_id:
                raise ValueError(f"需求不属于该项目：{requirement_id}")
            description = req.description or ""
            attachments = list(req.attachments or [])
        attachments.extend(extra_attachments)

        if not description and not attachments:
            raise ValueError("需求描述和附件均为空，无法理解")

        total = len(attachments)
        ctx.log(
            f"需求「{req.title}」：附件图片 {total} 张"
            + ("" if description else "（无文字描述）")
        )

        image_results: list[str] = []
        if total:
            await load_user_llms(ctx.user_id, kind="vision")
            vlm = get_current_vision_llm()
            for idx, url in enumerate(attachments):
                # 每张图一个 stage，前端据此把 token 路由到对应图片卡片
                ctx.stage(f"图片理解 {idx + 1}/{total}", index=idx + 1, total=total + 1)
                ctx.progress(int((idx / total) * 70))
                try:
                    image_url = await _resolve_image_url(str(url))
                    acc = await _astream_text(vlm, build_vlm_messages(image_url))
                except Exception as exc:  # 单图失败不阻断（与旧逻辑一致）
                    acc = f"图片理解失败：{exc}"
                    ctx.log(f"图片 {idx + 1} 理解失败：{exc}", level="warning")
                else:
                    ctx.log(f"图片 {idx + 1}/{total} 理解完成（{len(acc)} 字符）")
                image_results.append(acc)

        return {
            "description": description,
            "attachments": attachments,
            "image_results": image_results,
        }

    async def summarize(state: UnderstandState) -> dict:
        requirement_id = state["requirement_id"]
        total = len(state.get("attachments") or [])
        ctx.stage("整理需求", index=total + 1, total=total + 1)
        ctx.progress(75)

        llm = get_current_llm()
        summary = await _astream_text(
            llm,
            build_understand_prompt(
                state.get("description", ""),
                state.get("image_results") or [],
                custom_prompt,
            ),
        )
        # 推理模型会把 <think>...</think> 思考过程混在输出里，落库前剥离
        summary = strip_think_tags(summary)
        if not summary.strip():
            raise ValueError("LLM 返回内容为空")

        ctx.progress(95)
        async with async_session_maker() as db:
            req = await crud_requirement.get(db, requirement_id)
            if not req:
                raise ValueError(f"需求不存在：{requirement_id}")
            if req.project_id != ctx.project_id:
                raise ValueError(f"需求不属于该项目：{requirement_id}")
            await crud_requirement.update(db, req=req, understood_content=summary)

        ctx.log(f"理解完成，生成 Markdown {len(summary)} 字符，已写回需求")
        ctx.set_result(
            summary={
                "metrics": [
                    {"label": "生成字符数", "value": len(summary), "highlight": True},
                    {"label": "理解图片", "value": total, "unit": "张"},
                ],
                "chars": len(summary),
                "images": total,
            },
            ref={"kind": "func_requirement", "requirement_id": requirement_id},
        )
        return {"summary": summary}

    graph = StateGraph(UnderstandState)
    graph.add_node("understand_images", understand_images)
    graph.add_node("summarize", summarize)
    graph.add_edge(START, "understand_images")
    graph.add_edge("understand_images", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {"requirement_id": int(params["requirement_id"])}


def title(params: dict) -> str:
    name = params.get("requirement_title")
    return f"需求理解：{name}" if name else "AI 需求理解"


register(
    TaskSpec(
        task_type="understand_requirement",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",  # 文本基线；有图时在节点内按需加载 vision
        dedupe=True,
    )
)
