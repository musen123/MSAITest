"""AI 文档解析服务

将上传的项目文档解析为知识库 Markdown 文本（parse_document_to_markdown），供入库。
长文档分段重写引擎（rewrite_document_markdown）也在本模块，图任务与同步端点共用。

文件读取依赖：
  - pdf  → pymupdf (fitz)
  - docx → python-docx
  - txt/md → 直接读取
  - 图片  → VLM
"""

import base64
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.llm_context import get_current_llm, get_current_vision_llm
from app.ai_core.prompts.func_test_prompts import (
    build_doc_segment_markdown_prompt,
    build_doc_to_kb_markdown_prompt,
    build_vlm_messages,
)
from app.core.config import settings
from app.models.func_test.document import (
    DocumentParseStatus,
    ProjectDocument,
)
from app.utils.storage_utils import is_cos_enabled

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 文档文本提取
# ─────────────────────────────────────────────────────────────


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    import fitz

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        # 把 fitz 底层异常翻译成用户可读文案，避免原文直达用户
        raise ValueError("PDF 文件损坏或格式不正确，无法解析") from exc
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _read_docx(path: Path) -> str:
    from docx import Document

    # 就近兜底：docx 本质是 zip，文件头须为 zip 魔数 PK（0x50 0x4B）。
    # 0 字节 / 半截下载 / 实为旧版 .doc 二进制等会让 python-docx 抛
    # PackageNotFoundError，提前用魔数校验给出可读文案。
    try:
        with open(path, "rb") as fh:
            header = fh.read(2)
    except OSError as exc:
        raise ValueError("文档不存在或已损坏，请重新上传") from exc
    if header[:2] != b"PK":
        raise ValueError("文档不存在或已损坏，请重新上传（非有效的 docx 文件）")
    try:
        doc = Document(str(path))
    except Exception as exc:
        # 把 python-docx 的 PackageNotFoundError 等底层异常翻译成可读文案，
        # 避免『Package not found at ...』之类原文直达用户
        raise ValueError("docx 文件损坏或格式不正确，无法解析") from exc
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_local_file(local_path: Path) -> str:
    # 就近校验：文件须存在且非空，避免空/损坏文件流入下游
    # docx/pdf 解析触发『Package not found』之类晦涩错误
    if not local_path.exists() or local_path.stat().st_size == 0:
        raise ValueError("文档文件不存在或为空")
    ext = local_path.suffix.lower()
    if ext in (".txt", ".md"):
        return _read_txt(local_path)
    if ext == ".pdf":
        return _read_pdf(local_path)
    if ext in (".doc", ".docx"):
        return _read_docx(local_path)
    raise ValueError(f"不支持解析的文件格式：{ext}")


async def read_local_file_with_media(
    local_path: Path, *, vision_llm=None, on_image=None
) -> tuple[str, Optional[str]]:
    """带媒体无损提取的文档读取（parse_document 图专用）。

    与 `_read_local_file` 的差异：docx 补表格（旧 _read_docx 只读段落丢表格）、
    docx/pdf 内嵌图片经 VISION 描述按原位回填（vision_llm=None 时优雅降级为
    纯文本，与旧行为一致）。返回 (文本, 图片处理摘要或 None)。
    共享层见 app/services/common/doc_media.py。
    """
    import asyncio as _asyncio

    from app.services.common.doc_media import (
        describe_images,
        extract_docx_segments,
        extract_pdf_segments,
        render_pdf,
        render_plain,
    )

    if not local_path.exists() or local_path.stat().st_size == 0:
        raise ValueError("文档文件不存在或为空")
    ext = local_path.suffix.lower()
    if ext in (".txt", ".md"):
        return _read_txt(local_path), None
    if ext == ".pdf":
        segments = await _asyncio.to_thread(extract_pdf_segments, local_path)
        segments, media = await describe_images(
            segments, vision_llm, on_image=on_image
        )
        return render_pdf(segments), (
            media.summary() if media.total_images else None
        )
    if ext in (".doc", ".docx"):
        segments = await _asyncio.to_thread(extract_docx_segments, local_path)
        segments, media = await describe_images(
            segments, vision_llm, on_image=on_image
        )
        return render_plain(segments), (
            media.summary() if media.total_images else None
        )
    raise ValueError(f"不支持解析的文件格式：{ext}")


# ─────────────────────────────────────────────────────────────
# LLM 输出解析
# ─────────────────────────────────────────────────────────────


def _strip_markdown(raw: str) -> str:
    """去除 LLM 输出中的 markdown 代码块、<think> 块"""
    txt = raw.strip()
    # 处理 <think>...</think>
    if "</think>" in txt:
        txt = txt.split("</think>", 1)[1].strip()
    # 处理 ```json ... ```
    if txt.startswith("```"):
        parts = txt.split("```")
        if len(parts) >= 2:
            txt = parts[1]
            if txt.startswith("json"):
                txt = txt[4:]
            txt = txt.strip()
    return txt


def parse_llm_json(raw: str):
    """安全解析 LLM 返回的 JSON

    约定：
      - 永不静默返回 None；
      - 输入为空/空白 → 抛 ValueError（区分『LLM 真的返回空』）；
      - JSON 格式损坏/截断 → 抛 ValueError 并携带原始片段截断 + 清晰中文提示，
        以便上层据此判定『LLM 输出异常』，而非把空 JSON 当成『去重后 0 条』。
    """
    if raw is None or not str(raw).strip():
        raise ValueError("LLM 返回为空，无法解析用例 JSON")
    cleaned = _strip_markdown(raw)
    if not cleaned.strip():
        raise ValueError("LLM 返回内容去除 markdown 包裹后为空，无法解析用例 JSON")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        snippet = cleaned[:300]
        raise ValueError(
            f"LLM 输出不是合法 JSON，无法解析用例（原因：{exc.msg}）。"
            f"返回片段：{snippet}"
        ) from exc


# ─────────────────────────────────────────────────────────────
# 文档 → 知识库 Markdown 化（供 LightRAG 入库）
# ─────────────────────────────────────────────────────────────

# 图片类扩展名
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _read_image_to_data_url(local_path: Path) -> str:
    """读取图片转 data url（VLM 使用）"""
    # 就近校验：文件须存在且非空，避免 read_bytes() 对不存在文件抛
    # FileNotFoundError 原文直达用户，或空文件生成无效 data url
    if not local_path.exists() or local_path.stat().st_size == 0:
        raise ValueError("图片文件不存在或为空，请重新上传")
    suffix = local_path.suffix.lower().lstrip(".")
    if suffix == "jpg":
        suffix = "jpeg"
    content = local_path.read_bytes()
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:image/{suffix};base64,{encoded}"


def _load_to_local(storage_key: str) -> tuple[Path, Optional[Path]]:
    """把存储 key 落到本地路径

    返回 (local_path, tmp_path)：tmp_path 不为 None 时需要在用完后清理
    """
    if is_cos_enabled():
        import tempfile

        from app.utils.storage_utils import download_to_path

        suffix = Path(storage_key).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        download_to_path(storage_key, str(tmp_path))
        # 就近校验：下载后文件须存在且非空，避免 0 字节/半途下载的空文件
        # 流入 _read_docx/_read_pdf 触发『Package not found』之类晦涩错误
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise ValueError(f"文档下载失败或为空：{storage_key}")
        return tmp_path, tmp_path

    local_path = Path(settings.UPLOAD_DIR) / storage_key
    if not local_path.exists():
        raise ValueError(f"文件不存在：{local_path}")
    return local_path, None


# ─────────────────────────────────────────────────────────────
# 长文档分段重写引擎（图任务 parse_document 与同步端点共用）
#
# 单发全文重写是「输出∝输入」的任务：长文档必然撞模型输出上限，历史上
# 还叠加了 prompt 侧 [:24000] 静默截断——两处都导致解析结果无声残缺。
# 此引擎的口径：
#   1. 输入永不静默截断：超过单段上限就按自然边界切段、逐段重写、按序拼接；
#   2. 输出截断（finish_reason=length/max_tokens）必被检测：该段二分重试，
#      缩到下限仍截断则任务失败——绝不把半截结果标成功落库。
# ─────────────────────────────────────────────────────────────

_SEG_TARGET_CHARS = 8000      # 单段目标上限（中文约 5k~8k token 输出，留足余量）
_SEG_SEARCH_WINDOW = 4000     # 从目标点向前回溯找自然边界的窗口
_SEG_MIN_TAIL = 1500          # 尾段小于此值时并入前一段，避免碎段
_MIN_BISECT_CHARS = 1200      # 段缩到此值仍被截断 → 放弃重试，显式报错
_MAX_BISECT_DEPTH = 3         # 二分重试最大深度
_TRUNCATED_FINISH = {"length", "max_tokens"}  # OpenAI 系 / Anthropic 的截断标记

# 切分边界模式，按优先级排列：(正则, 新段是否从匹配处行首开始)
# 标题/章节类边界切在行首（标题归属下一段）；空行/换行/句读切在其后。
_BOUNDARY_PATTERNS: list[tuple[re.Pattern, bool]] = [
    (re.compile(r"\n(?=#{1,6}\s)"), True),                            # markdown 标题
    (re.compile(r"\n(?=第[0-9一二三四五六七八九十百]{1,4}[章节篇部])"), True),  # 中文章节
    (re.compile(r"\n(?=\d{1,2}(?:\.\d{1,2}){0,3}[ \t、.．)）])"), True),     # 数字大纲 3.2
    (re.compile(r"\n[ \t]*\n"), False),                               # 空行
    (re.compile(r"\n"), False),                                       # 换行
    (re.compile(r"[。！？!?]"), False),                                # 句读
]


def _find_cut(text: str, target: int) -> int:
    """在 [target-窗口, target) 内找最优切点，返回新段起始下标；找不到则硬切。"""
    window_start = max(1, target - _SEG_SEARCH_WINDOW)
    window = text[window_start:target]
    for pattern, cut_at_line_start in _BOUNDARY_PATTERNS:
        last = None
        for m in pattern.finditer(window):
            last = m
        if last is not None:
            if cut_at_line_start:
                return window_start + last.start() + 1  # 越过 \n，新段从标题行首开始
            return window_start + last.end()
    return target


def split_document_for_rewrite(
    text: str, target: int = _SEG_TARGET_CHARS
) -> list[str]:
    """把原文按自然边界切成 ≤target 字符的段（内容无损，仅切点处丢弃换行）。"""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= target:
        return [text]
    # 尾段合并阈值须随 target 缩放：二分重试时 target 减半，若仍用全局阈值，
    # 切出的后半段会被当碎尾并回前段，二分退化为原段重发
    tail_min = min(_SEG_MIN_TAIL, max(1, target // 4))
    segments: list[str] = []
    rest = text
    while len(rest) > target:
        cut = _find_cut(rest, target)
        head = rest[:cut].rstrip("\n")
        if head:
            segments.append(head)
        rest = rest[cut:].lstrip("\n")
    if rest.strip():
        if len(rest) < tail_min and segments:
            segments[-1] = segments[-1] + "\n" + rest
        else:
            segments.append(rest)
    return segments


_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _update_heading_stack(
    stack: list[tuple[int, str]], markdown: str
) -> list[tuple[int, str]]:
    """按本段输出的标题更新「当前打开的标题路径」（h1→h2→h3 栈）。"""
    new = list(stack)
    for m in _HEADING_LINE_RE.finditer(markdown):
        level = len(m.group(1))
        title = m.group(2).strip()
        while new and new[-1][0] >= level:
            new.pop()
        new.append((level, title))
    return new


def _render_heading_stack(stack: list[tuple[int, str]]) -> str:
    return " > ".join(f"{'#' * lvl} {title}" for lvl, title in stack)


def _prev_tail(parts: list[str], max_chars: int = 300) -> str:
    """取上一段输出的最后几行，作为下一段的衔接锚。"""
    if not parts:
        return ""
    lines = [ln for ln in parts[-1].strip().splitlines() if ln.strip()]
    return "\n".join(lines[-3:])[-max_chars:]


def _stitch_parts(parts: list[str]) -> str:
    """按序拼接分段输出，拼缝处做轻量去重（下段开头原样重复上段末行时丢弃）。"""
    acc: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if acc:
            prev_last = acc[-1].rstrip().splitlines()[-1].strip()
            lines = part.splitlines()
            while lines and lines[0].strip() and lines[0].strip() == prev_last:
                lines.pop(0)
            part = "\n".join(lines).strip()
            if not part:
                continue
        acc.append(part)
    return "\n\n".join(acc)


def _clean_markdown(raw: str) -> str:
    """去掉 <think> 与 ```markdown 包裹"""
    md = (raw or "").strip()
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


async def _astream_text_meta(llm: Any, messages: Any) -> tuple[str, Optional[str]]:
    """流式调用并累计文本，同时捕获 finish_reason/stop_reason（截断检测依据）。

    在图任务里调用时，token 由 StreamAdapter 的 messages 模式自动转 message_delta，
    实时直播不受影响。
    """
    acc: list[str] = []
    finish: Optional[str] = None
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
        meta = getattr(chunk, "response_metadata", None) or {}
        reason = meta.get("finish_reason") or meta.get("stop_reason")
        if reason:
            finish = str(reason)
    return "".join(acc), finish


def _emit(
    log: Optional[Callable[[str, str], None]], message: str, level: str = "info"
) -> None:
    if log is not None:
        log(message, level)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


async def rewrite_document_markdown(
    llm: Any,
    raw_text: str,
    *,
    doc_type: str = "other",
    doc_name: str = "",
    custom_prompt: Optional[str] = None,
    log: Optional[Callable[[str, str], None]] = None,
    progress: Optional[Callable[[float], None]] = None,
) -> str:
    """文档全文 → 知识库 Markdown，长文自动分段，输出截断必检测。

    - 短文档（≤单段上限）：沿用整篇 prompt 单发，行为与历史一致；
    - 长文档：切段 → 逐段重写（携带标题栈+前段结尾衔接）→ 按序拼接；
    - 任一段 finish_reason 为截断：该段二分重试（≤3 层），缩到下限仍截断
      则抛错，绝不静默落半截；
    - progress 回调收 [0,1] 完成度（按已完成字符数计），log 回调收 (消息, 级别)。
    """
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("文档内容为空，无法解析")
    segments = split_document_for_rewrite(text)
    single_shot = len(segments) == 1
    total_chars = sum(len(s) for s in segments)
    if not single_shot:
        _emit(
            log,
            f"文档共 {total_chars} 字符，超出单次解析上限，切分为 {len(segments)} 段逐段解析",
        )

    work: list[tuple[str, int]] = [(s, 0) for s in segments]
    parts: list[str] = []
    stack: list[tuple[int, str]] = []
    done_chars = 0
    seg_no = 0
    while work:
        seg, depth = work.pop(0)
        seg_no += 1
        seg_total = seg_no + len(work)
        if seg_total > 1:
            _emit(log, f"解析第 {seg_no}/{seg_total} 段（{len(seg)} 字符）")
        if single_shot and depth == 0:
            messages = build_doc_to_kb_markdown_prompt(
                seg, doc_type=doc_type, custom_prompt=custom_prompt
            )
        else:
            messages = build_doc_segment_markdown_prompt(
                seg,
                doc_type=doc_type,
                doc_name=doc_name,
                seg_no=seg_no,
                seg_total=seg_total,
                heading_stack=_render_heading_stack(stack),
                prev_tail=_prev_tail(parts),
                custom_prompt=custom_prompt,
            )
        acc, finish = await _astream_text_meta(llm, messages)

        if (finish or "").lower() in _TRUNCATED_FINISH:
            if depth >= _MAX_BISECT_DEPTH or len(seg) <= _MIN_BISECT_CHARS:
                raise ValueError(
                    f"模型输出被截断（finish_reason={finish}），"
                    f"第 {seg_no} 段已缩小到 {len(seg)} 字符仍无法完整输出；"
                    "请更换输出上限更大的文本模型后重试"
                )
            halves = split_document_for_rewrite(
                seg, target=max(_MIN_BISECT_CHARS, len(seg) // 2)
            )
            if len(halves) <= 1:
                raise ValueError(
                    f"模型输出被截断（finish_reason={finish}）且该段无法再切分，"
                    "请更换输出上限更大的文本模型后重试"
                )
            _emit(
                log,
                f"第 {seg_no} 段输出被模型截断，切为 {len(halves)} 个小段重试",
                "warning",
            )
            seg_no -= 1  # 本段未完成，重试段重新占位计数
            work[:0] = [(h, depth + 1) for h in halves]
            continue

        md = _clean_markdown(acc)
        if not md:
            if len(seg.strip()) < 200:
                # 页码/空白等碎片段，模型无话可说属正常，跳过但留痕
                _emit(log, f"第 {seg_no} 段内容过短且模型无输出，已跳过", "warning")
                done_chars += len(seg)
                continue
            raise ValueError("LLM 返回内容为空")
        parts.append(md)
        stack = _update_heading_stack(stack, md)
        done_chars += len(seg)
        if progress is not None and total_chars:
            progress(done_chars / total_chars)

    result = _stitch_parts(parts)
    if not result:
        raise ValueError("LLM 返回内容为空")
    return result


async def parse_document_to_markdown(
    db: AsyncSession,
    *,
    doc: ProjectDocument,
    custom_prompt: Optional[str] = None,
) -> str:
    """把项目文档解析为 Markdown（供 LightRAG 入库）

    - 文本类（pdf/docx/txt/md）→ 抽文本 + LLM 重写为 Markdown
    - 图片类（png/jpg/...）→ 调 VLM 描述

    成功时回写 ``doc.parsed_content / parse_status='parsed' / parsed_at``，
    失败时回写 ``parse_status='failed' / parse_error_message``。

    返回最终的 markdown 内容。
    """
    # 状态置为 parsing
    doc.parse_status = DocumentParseStatus.PARSING.value
    doc.parse_error_message = None
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    ext = (doc.file_ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext

    tmp_path: Optional[Path] = None
    try:
        local_path, tmp_path = _load_to_local(doc.file_path)

        if ext in _IMAGE_EXTS:
            # 图片走 VLM
            vlm = get_current_vision_llm()
            data_url = _read_image_to_data_url(local_path)
            messages = build_vlm_messages(data_url)
            response = await vlm.ainvoke(messages)
            content = (response.content or "").strip()
            markdown = f"# {doc.name}\n\n{content}"
        else:
            # 文本走 LLM 重写（长文自动分段 + 截断检测，与图任务共用引擎）
            raw_text = _read_local_file(local_path)
            llm = get_current_llm()
            markdown = await rewrite_document_markdown(
                llm,
                raw_text,
                doc_type=doc.doc_type,
                doc_name=doc.name,
                custom_prompt=custom_prompt,
            )

        if not markdown:
            raise ValueError("LLM 返回内容为空")

        # 回写
        doc.parsed_content = markdown
        doc.parse_status = DocumentParseStatus.PARSED.value
        doc.parsed_at = datetime.utcnow()
        doc.parse_error_message = None
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return markdown

    except Exception as exc:
        doc.parse_status = DocumentParseStatus.FAILED.value
        doc.parse_error_message = str(exc)[:500]
        db.add(doc)
        await db.commit()
        raise
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
