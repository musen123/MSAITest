"""文档解析 → 知识库 Markdown（统一 AI 任务图）

把项目文档解析为适合知识库检索的 Markdown，回写 ``parsed_content``。

图结构（2 节点）：
    load    提取文档内容（文本 / 图片 data url）
    rewrite 调用 LLM/VLM 重写为 Markdown，回写文档；长文本由
            ``rewrite_document_markdown`` 分段逐段重写并做输出截断检测

token 通过 ``astream`` 产生，由 StreamAdapter 的 messages 模式自动转 message_delta。
图状态/进度通过 ctx.stage/progress/log 上报。
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai_core.llm_context import get_current_llm, get_current_vision_llm
from app.ai_core.prompts.func_test_prompts import build_vlm_messages
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.llm import load_user_llms
from app.ai_core.runtime.registry import TaskSpec, register
from app.crud.func_test.document import crud_document
from app.db.session import async_session_maker
from app.models.func_test.document import DocumentParseStatus
from app.services.func_test.document_parse_service import (
    _IMAGE_EXTS,
    _TRUNCATED_FINISH,
    _astream_text_meta,
    _load_to_local,
    _read_image_to_data_url,
    read_local_file_with_media,
    rewrite_document_markdown,
)


class ParseDocState(TypedDict, total=False):
    doc_id: int
    is_image: bool
    raw_text: str
    image_url: str
    doc_name: str
    markdown: str


async def _mark_failed(doc_id: int, error: str) -> None:
    async with async_session_maker() as db:
        doc = await crud_document.get(db, doc_id)
        if doc:
            doc.parse_status = DocumentParseStatus.FAILED.value
            doc.parse_error_message = error[:500]
            db.add(doc)
            await db.commit()


def build_graph(params: dict, ctx: TaskContext) -> Any:
    custom_prompt: Optional[str] = params.get("custom_prompt")

    async def load(state: ParseDocState) -> dict:
        ctx.stage("提取文档内容", index=1, total=2)
        ctx.progress(10)
        doc_id = state["doc_id"]
        tmp_path: Optional[Path] = None
        try:
            async with async_session_maker() as db:
                doc = await crud_document.get(db, doc_id)
                if not doc:
                    raise ValueError(f"文档不存在：{doc_id}")
                if doc.project_id != ctx.project_id:
                    raise ValueError(f"文档不属于该项目：{doc_id}")
                doc.parse_status = DocumentParseStatus.PARSING.value
                doc.parse_error_message = None
                db.add(doc)
                await db.commit()
                await db.refresh(doc)
                ext = (doc.file_ext or "").lower()
                if not ext.startswith("."):
                    ext = "." + ext
                file_path = doc.file_path
                name = doc.name

            is_image = ext in _IMAGE_EXTS
            ctx.log(
                f"文档「{name}」类型 {ext}，"
                f"{'图片(VLM)' if is_image else '文本(LLM)'} 解析"
            )
            local_path, tmp_path = _load_to_local(file_path)
            if is_image:
                return {
                    "is_image": True,
                    "image_url": _read_image_to_data_url(local_path),
                    "doc_name": name,
                }
            # 内嵌图片按需加载 VISION（未配置→优雅降级为纯文本，与旧行为一致）
            vision_llm = None
            if ext in (".pdf", ".doc", ".docx"):
                try:
                    await load_user_llms(ctx.user_id, kind="vision")
                    vision_llm = get_current_vision_llm()
                except Exception:  # noqa: BLE001
                    ctx.log("未配置 VISION 模型，文档内嵌图片将跳过", level="warning")

            async def on_image(done: int, total: int) -> None:
                ctx.log(f"内嵌图片解析 {done}/{total}")

            raw_text, media_note = await read_local_file_with_media(
                local_path, vision_llm=vision_llm, on_image=on_image
            )
            if media_note:
                ctx.log(f"内嵌图片：{media_note}")
            return {
                "is_image": False,
                "raw_text": raw_text,
                "doc_name": name,
            }
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    async def rewrite(state: ParseDocState) -> dict:
        ctx.stage("AI 解析为 Markdown", index=2, total=2)
        ctx.progress(40)
        doc_id = state["doc_id"]
        try:
            async with async_session_maker() as db:
                doc = await crud_document.get(db, doc_id)
                doc_type = doc.doc_type if doc else "other"

            if state.get("is_image"):
                await load_user_llms(ctx.user_id, kind="vision")
                vlm = get_current_vision_llm()
                ctx.log("调用视觉模型识别图片内容")
                acc, finish = await _astream_text_meta(
                    vlm, build_vlm_messages(state["image_url"])
                )
                if (finish or "").lower() in _TRUNCATED_FINISH:
                    # 图片无法二分重试，截断降级为显式警告（描述可能不完整）
                    ctx.log(
                        f"视觉模型输出疑似被截断（finish_reason={finish}），"
                        "图片描述可能不完整",
                        level="warning",
                    )
                markdown = f"# {state.get('doc_name', '')}\n\n{acc.strip()}".strip()
            else:
                llm = get_current_llm()
                ctx.log("调用文本模型重写为知识库 Markdown")
                # 长文自动分段逐段重写；进度按完成字符数在 40→90 区间推进
                markdown = await rewrite_document_markdown(
                    llm,
                    state["raw_text"],
                    doc_type=doc_type,
                    doc_name=state.get("doc_name", ""),
                    custom_prompt=custom_prompt,
                    log=lambda msg, level: ctx.log(msg, level=level),
                    progress=lambda ratio: ctx.progress(40 + int(ratio * 50)),
                )

            if not markdown:
                raise ValueError("LLM 返回内容为空")

            ctx.progress(90)
            async with async_session_maker() as db:
                doc = await crud_document.get(db, doc_id)
                doc.parsed_content = markdown
                doc.parse_status = DocumentParseStatus.PARSED.value
                doc.parsed_at = datetime.utcnow()
                doc.parse_error_message = None
                db.add(doc)
                await db.commit()

            ctx.log(f"解析完成，生成 Markdown {len(markdown)} 字符")
            ctx.set_result(
                summary={
                    "metrics": [
                        {
                            "label": "生成字符数",
                            "value": len(markdown),
                            "highlight": True,
                        },
                        {
                            "label": "类型",
                            "value": "图片(VLM)" if state.get("is_image") else "文本(LLM)",
                        },
                    ],
                    "chars": len(markdown),
                },
                ref={"kind": "func_document", "doc_id": doc_id},
            )
            return {"markdown": markdown}
        except Exception as exc:
            await _mark_failed(doc_id, str(exc))
            raise

    graph = StateGraph(ParseDocState)
    graph.add_node("load", load)
    graph.add_node("rewrite", rewrite)
    graph.add_edge(START, "load")
    graph.add_edge("load", "rewrite")
    graph.add_edge("rewrite", END)
    return graph.compile()


def build_input(params: dict) -> dict:
    return {"doc_id": int(params["doc_id"])}


def title(params: dict) -> str:
    name = params.get("doc_name")
    return f"文档解析：{name}" if name else "文档解析"


register(
    TaskSpec(
        task_type="parse_document",
        build_graph=build_graph,
        build_input=build_input,
        title=title,
        llm_kind="text",  # 文本基线；图片在节点内按需加载 vision
        dedupe=True,
    )
)
