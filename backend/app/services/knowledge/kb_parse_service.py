"""知识库解析入口（设计文档 §3#10：**改造**现有解析而非纯复用）

与 func_test 的 parse_document_to_markdown 的关键差异（引用忠实性优先，评审吸收）：
  - md/txt **直读不 LLM 重写**（parse_mode=raw）——旧管线对全部文本类一律
    LLM 重写，索引源是改写产物，有漏内容/改数字风险且白烧 token
  - docx 段落 + **表格提取**（旧 _read_docx 只读 paragraphs 丢表格），
    iter_inner_content 保持段落/表格文档顺序，Heading 样式还原为 # 标题
    （给 chunker 标题树喂料）；parse_mode=raw
  - PDF pymupdf 抽文本后走 **6k 分片 map LLM 规整**（parse_mode=llm_normalized）
    ——替代旧管线 24000 字符静默截断；规整 prompt 钉「不增不减不总结」，
    与旧 DOC_TO_KB prompt 的「重组织」倾向刻意不同
  - 图片走 VISION（调用方注入客户端；parse_mode=llm_normalized）
  - 超大文档 KB_PARSE_MAX_CHARS 兜底截断 + truncated=True **显式回写用户可见**，
    不静默丢尾部

复用 func_test 的底层提取器（_read_txt/_load_to_local/_read_image_to_data_url）与共享媒体层 doc_media，
不动其旧路径（防 func_test 回归）。
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.models.knowledge.document import KbParseMode
from app.services.func_test.document_parse_service import (
    _IMAGE_EXTS,
    _load_to_local,
    _read_image_to_data_url,
    _read_txt,
)

# —— 常量 ——
KB_PARSE_MAX_CHARS = 120_000  # 超此值截断 + truncated 标记（成本兜底，非静默）
PDF_SLICE_CHARS = 6_000  # PDF LLM 规整分片大小
_PDF_NORMALIZE_SYSTEM = (
    "你是文档规整器。输入是 PDF 逐页抽取的碎行文本（换行错乱、页眉页脚混入）。"
    "把它恢复为通顺的 Markdown：合并被硬换行拆断的句子、还原标题层级（#/##/###）、"
    "表格用 Markdown 表格语法、剔除重复页眉页脚页码。"
    "【铁律】保持全部信息与原文顺序，不增加、不删减、不总结、不改写数字与术语。"
    "【铁律】以「> 【图片内容」开头的引用块是文档内嵌图片的解析结果，"
    "必须原样保留在原位置，不得改写、删减、合并或移动。"
    "直接输出 Markdown，不要任何解释或代码块包裹。"
)


@dataclass
class KbParseResult:
    markdown: str
    parse_mode: str
    media_note: Optional[str] = None  # 内嵌图片处理摘要（如实展示，None=无图）
    truncated: bool = False


class UnsupportedKbFileError(ValueError):
    """不支持的格式（可读文案直达用户）"""


def _norm_ext(file_ext: str) -> str:
    ext = (file_ext or "").lower()
    return ext if ext.startswith(".") else f".{ext}"


def _slice_for_normalize(raw: str) -> list[str]:
    """按段落边界切 ≤6k 分片（map 逐段规整；跨片句子由相邻片重叠一行兜底不做，
    PDF 抽取本就按页断行，段落边界切割足够）"""
    paragraphs = raw.split("\n")
    slices: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in paragraphs:
        if cur and cur_len + len(p) + 1 > PDF_SLICE_CHARS:
            slices.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p) + 1
    if cur:
        slices.append("\n".join(cur))
    return [s for s in slices if s.strip()]


def _strip_llm_wrapping(text: str) -> str:
    md = (text or "").strip()
    if "</think>" in md:
        md = md.split("</think>", 1)[1].strip()
    if md.startswith("```"):
        parts = md.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("markdown"):
                inner = inner[len("markdown"):].lstrip()
            md = inner.strip()
    return md


async def _normalize_pdf_text(raw: str, *, text_llm: Any, on_slice=None) -> str:
    """6k 分片 map LLM 规整（串行——保持顺序且对用户 key 限流友好）"""
    slices = _slice_for_normalize(raw)
    out: list[str] = []
    for i, piece in enumerate(slices):
        messages = [
            ("system", _PDF_NORMALIZE_SYSTEM),
            ("human", f"【第 {i + 1}/{len(slices)} 片】\n\n{piece}"),
        ]
        resp = await text_llm.ainvoke(messages)
        out.append(_strip_llm_wrapping(getattr(resp, "content", "") or ""))
        if on_slice:
            await on_slice(i + 1, len(slices))
    return "\n\n".join(s for s in out if s)


async def parse_file_for_kb(
    *,
    storage_key: str,
    file_ext: str,
    file_name: str,
    text_llm: Any = None,
    vision_llm: Any = None,
    scanned_pdf: bool = False,
    on_slice=None,
) -> KbParseResult:
    """按扩展名路由解析（storage_key 经 _load_to_local 兼容 COS/本地）。

    text_llm 仅 PDF 需要；vision_llm 仅图片需要——调用方（kb_ingest parse 节点）
    按需注入，未注入即该类型不可解析（可读报错）。
    """
    ext = _norm_ext(file_ext)
    local_path: Optional[Path] = None
    tmp_path: Optional[Path] = None
    try:
        local_path, tmp_path = await asyncio.to_thread(_load_to_local, storage_key)

        if ext in _IMAGE_EXTS:
            if vision_llm is None:
                raise ValueError("图片文档需要 VISION 模型，请先在「用户中心 → 大模型配置」添加")
            data_url = await asyncio.to_thread(_read_image_to_data_url, local_path)
            from app.ai_core.prompts.func_test_prompts import build_vlm_messages

            resp = await vision_llm.ainvoke(build_vlm_messages(data_url))
            content = _strip_llm_wrapping(getattr(resp, "content", "") or "")
            if not content:
                raise ValueError("视觉模型返回内容为空")
            md = f"# {file_name}\n\n{content}"
            return KbParseResult(markdown=md, parse_mode=KbParseMode.LLM_NORMALIZED.value)

        if ext in (".txt", ".md"):
            raw = await asyncio.to_thread(_read_txt, local_path)
            truncated = len(raw) > KB_PARSE_MAX_CHARS
            return KbParseResult(
                markdown=raw[:KB_PARSE_MAX_CHARS].strip(),
                parse_mode=KbParseMode.RAW.value,
                truncated=truncated,
            )

        if ext in (".doc", ".docx"):
            # 共享层：段落/表格/内嵌图按文档序提取，图经 VISION 描述回填原位；
            # 无图文档渲染输出与旧 _docx_to_markdown 逐字节等价（单测钉死）
            from app.services.common.doc_media import (
                describe_images,
                extract_docx_segments,
                render_markdown_docx,
            )

            segments = await asyncio.to_thread(extract_docx_segments, local_path)
            segments, media = await describe_images(segments, vision_llm)
            md = render_markdown_docx(segments)
            if not md:
                raise ValueError("docx 未提取到任何内容（空文档？）")
            truncated = len(md) > KB_PARSE_MAX_CHARS
            return KbParseResult(
                markdown=md[:KB_PARSE_MAX_CHARS].strip(),
                parse_mode=KbParseMode.RAW.value,
                truncated=truncated,
                media_note=media.summary() if media.total_images else None,
            )

        if ext == ".pdf":
            from app.services.common.doc_media import (
                describe_images,
                extract_pdf_segments,
                render_pdf,
            )

            segments = await asyncio.to_thread(extract_pdf_segments, local_path)
            page_text_all = "".join(
                s.text for s in segments if s.kind == "page_text"
            )
            if not page_text_all.strip():
                if scanned_pdf:
                    # 显式开关：逐页渲染为图 → VLM 整页转写（成本高，调用方逐次决定）
                    from app.services.common.doc_media import transcribe_scanned_pdf

                    md, pages, over_cap = await transcribe_scanned_pdf(
                        local_path, vision_llm, on_page=on_slice
                    )
                    if not md.strip():
                        raise ValueError("扫描件转写内容为空")
                    truncated = over_cap or len(md) > KB_PARSE_MAX_CHARS
                    return KbParseResult(
                        markdown=md[:KB_PARSE_MAX_CHARS].strip(),
                        parse_mode=KbParseMode.LLM_NORMALIZED.value,
                        truncated=truncated,
                        media_note=f"扫描件已逐页转写 {pages} 页"
                        + ("（超页数上限截断）" if over_cap else ""),
                    )
                raise ValueError(
                    "PDF 未提取到文本（疑似扫描版/图片型 PDF）——可在文档操作中"
                    "「重新入库」并开启扫描件解析（需 VISION 模型），"
                    "或转存为文字版 PDF / 改传 docx/md"
                )
            segments, media = await describe_images(segments, vision_llm)
            raw = render_pdf(segments)
            truncated = len(raw) > KB_PARSE_MAX_CHARS
            raw = raw[:KB_PARSE_MAX_CHARS]
            if text_llm is None:
                raise ValueError("PDF 规整需要 TEXT 模型，请先在「用户中心 → 大模型配置」添加")
            md = await _normalize_pdf_text(raw, text_llm=text_llm, on_slice=on_slice)
            if not md.strip():
                raise ValueError("PDF 规整后内容为空")
            return KbParseResult(
                markdown=md,
                parse_mode=KbParseMode.LLM_NORMALIZED.value,
                truncated=truncated,
                media_note=media.summary() if media.total_images else None,
            )

        raise UnsupportedKbFileError(
            f"知识库暂不支持解析 {ext} 格式（支持：pdf/docx/txt/md/png/jpg/jpeg/gif/webp/bmp）"
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
