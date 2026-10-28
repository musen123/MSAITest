"""文档媒体无损提取共享层（设计见 docs/文档解析-图片与表格无损化-设计方案.md）

两条解析链路（func_test 文档解析 / 知识库入库）共用：
  - 确定性提取（零模型）：docx 按段落序、PDF 按页序，抽出文本/表格/内嵌图片段
  - VLM 描述（模型）：逐张内嵌图调 VISION 模型生成描述，回填原位
  - 双渲染：A 链纯文本（对齐旧 _read_docx 输出）/ B 链 Markdown（对齐旧
    _docx_to_markdown 输出）——**无图文档输出与旧实现逐字节等价**（单测钉死）

稳定性护栏（全部硬上限）：
  - 小图过滤（宽或高 <64px 或 <5KB：图标/logo/分隔线不值一次 VLM 调用）
  - 单文档描述图数上限 20，超出跳过并计数（不静默）
  - 同图 md5 去重（docx 页眉 logo 重复是常态），复用描述
  - 单图描述失败落占位继续，不炸整篇
  - 未注入 VISION 模型 → 全部图跳过并计数（优雅降级为纯文本现状）
  - 单图描述截 300 字（防 KB_PARSE_MAX_CHARS 截断风险放大）
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 护栏参数 ──
MIN_IMAGE_PX = 64          # 宽或高低于此值视为图标类，跳过
MIN_IMAGE_BYTES = 5 * 1024
MAX_IMAGES_PER_DOC = 20
MAX_DESC_CHARS = 300
SCANNED_PDF_MAX_PAGES = 30  # 扫描件页级转写上限（成本硬顶，超限截断并标记）
SCANNED_PDF_DPI = 150

# fitz 可探测/ VLM 可消费的图片格式（docx 里偶见 wmf/emf 矢量图，无法直接喂 VLM）
_SUPPORTED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}


@dataclass
class DocSegment:
    """文档内容段（严格保持文档内顺序）。

    kind: para（docx 段落）/ table（docx 表格，text 为 MD 表格）/
          page_text（PDF 单页文本）/ image（内嵌图，描述后 text 为 VLM 描述）
    """

    kind: str
    text: str = ""
    image_bytes: Optional[bytes] = None
    image_ext: str = ""
    style: str = ""            # docx 段落样式名（Markdown 渲染标题层级用）
    page: Optional[int] = None  # PDF 页码（1 起）


@dataclass
class MediaStats:
    """图片处理统计（解析结果如实展示，不静默）。"""

    total_images: int = 0
    described: int = 0
    deduped: int = 0
    skipped_small: int = 0
    skipped_over_cap: int = 0
    skipped_no_vision: int = 0
    skipped_unsupported: int = 0
    failed: int = 0
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"图片 {self.total_images} 张"]
        if self.described:
            parts.append(f"已解析 {self.described}")
        if self.deduped:
            parts.append(f"重复复用 {self.deduped}")
        skipped = (
            self.skipped_small
            + self.skipped_over_cap
            + self.skipped_no_vision
            + self.skipped_unsupported
        )
        if skipped:
            parts.append(f"跳过 {skipped}")
        if self.failed:
            parts.append(f"失败 {self.failed}")
        return "、".join(parts)


# ─────────────────────────────────────────────────────────────
# 提取（确定性，零模型）
# ─────────────────────────────────────────────────────────────

# docx drawing 里 blip 的 embed 属性（图片关系 id）
_BLIP_EMBED = (
    "{http://schemas.openxmlformats.org/drawingml/2006/main}blip",
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed",
)


def _para_image_segments(paragraph: Any, doc_part: Any) -> list[DocSegment]:
    """抽取一个段落内的全部内嵌图（按出现顺序；单图异常跳过不炸段落）。"""
    out: list[DocSegment] = []
    try:
        blips = paragraph._p.iter(_BLIP_EMBED[0])
    except Exception:  # noqa: BLE001
        return out
    for blip in blips:
        try:
            r_id = blip.get(_BLIP_EMBED[1])
            if not r_id:
                continue
            part = doc_part.related_parts.get(r_id)
            if part is None:
                continue
            ext = str(part.partname).rsplit(".", 1)[-1].lower()
            out.append(
                DocSegment(kind="image", image_bytes=part.blob, image_ext=ext)
            )
        except Exception:  # noqa: BLE001
            logger.warning("docx 单图抽取失败（已跳过）", exc_info=True)
    return out


def extract_docx_segments(path: Path) -> list[DocSegment]:
    """docx → 段序列：段落（含样式）/ 表格（MD 文本）/ 内嵌图（排在所属段落之后）。

    文件头魔数校验与可读报错口径对齐两条链路的旧实现。
    """
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        with open(path, "rb") as fh:
            if fh.read(2) != b"PK":
                raise ValueError("文档不存在或已损坏，请重新上传（非有效的 docx 文件）")
        doc = Document(str(path))
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("文档不存在或已损坏，请重新上传") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError("docx 文件损坏或格式不正确，无法解析") from exc

    segments: list[DocSegment] = []
    for item in doc.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if text:
                style = (item.style.name or "") if item.style is not None else ""
                segments.append(DocSegment(kind="para", text=text, style=style))
            # 段内图排在段文本之后（图的上下文=所属段落）
            segments.extend(_para_image_segments(item, doc.part))
        elif isinstance(item, Table):
            md = _table_to_markdown(item)
            if md:
                segments.append(DocSegment(kind="table", text=md))
    return segments


def _table_to_markdown(table: Any) -> str:
    """docx 表格 → MD 表格（与 kb_parse_service 旧 _docx_to_markdown 逐字一致）。"""
    rows = [
        [cell.text.strip().replace("\n", " ").replace("|", "\\|") for cell in row.cells]
        for row in table.rows
    ]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def extract_pdf_segments(path: Path) -> list[DocSegment]:
    """PDF → 段序列：每页一个 page_text 段 + 该页内嵌图段（页级定位）。"""
    import fitz

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("PDF 文件损坏或格式不正确，无法解析") from exc
    segments: list[DocSegment] = []
    try:
        for i, page in enumerate(doc):
            segments.append(
                DocSegment(kind="page_text", text=page.get_text(), page=i + 1)
            )
            try:
                images = page.get_images(full=True)
            except Exception:  # noqa: BLE001
                images = []
            for img in images:
                try:
                    info = doc.extract_image(img[0])  # xref
                    segments.append(
                        DocSegment(
                            kind="image",
                            image_bytes=info["image"],
                            image_ext=str(info.get("ext") or "png").lower(),
                            page=i + 1,
                        )
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("PDF 单图抽取失败（已跳过）", exc_info=True)
    finally:
        doc.close()
    return segments


# ─────────────────────────────────────────────────────────────
# VLM 描述（模型，逐图串行；失败/降级不炸整篇）
# ─────────────────────────────────────────────────────────────


def _probe_size(data: bytes, ext: str) -> Optional[tuple[int, int]]:
    """探测图片尺寸（fitz，免新增依赖）；探测失败返回 None（按通过处理）。"""
    import fitz

    try:
        pix = fitz.Pixmap(data)
        try:
            return pix.width, pix.height
        finally:
            pix = None  # noqa: F841
    except Exception:  # noqa: BLE001
        return None


async def describe_images(
    segments: list[DocSegment],
    vision_llm: Any,
    *,
    max_images: int = MAX_IMAGES_PER_DOC,
    on_image: Any = None,
) -> tuple[list[DocSegment], MediaStats]:
    """逐张内嵌图生成描述并回填 text；被过滤/降级的图段被移除。

    返回 (新段序列, 统计)。vision_llm=None → 全部图跳过（纯文本降级，
    与改造前输出一致）。on_image(done, total) 供任务进度上报。
    """
    stats = MediaStats()
    images = [s for s in segments if s.kind == "image"]
    stats.total_images = len(images)
    if not images:
        return segments, stats

    if vision_llm is None:
        stats.skipped_no_vision = len(images)
        stats.notes.append("未配置 VISION 模型，内嵌图片未解析")
        return [s for s in segments if s.kind != "image"], stats

    from app.ai_core.prompts.func_test_prompts import build_embedded_image_messages

    desc_cache: dict[str, str] = {}
    described_count = 0
    keep: dict[int, bool] = {}
    done = 0
    for idx, seg in enumerate(segments):
        if seg.kind != "image":
            continue
        data, ext = seg.image_bytes or b"", seg.image_ext
        if ext == "jpeg":
            ext = "jpg"
        if ext not in _SUPPORTED_IMAGE_EXTS:
            stats.skipped_unsupported += 1
            keep[idx] = False
            continue
        if len(data) < MIN_IMAGE_BYTES:
            stats.skipped_small += 1
            keep[idx] = False
            continue
        size = _probe_size(data, ext)
        if size is not None and (size[0] < MIN_IMAGE_PX or size[1] < MIN_IMAGE_PX):
            stats.skipped_small += 1
            keep[idx] = False
            continue

        digest = hashlib.md5(data).hexdigest()
        if digest in desc_cache:
            seg.text = desc_cache[digest]
            stats.deduped += 1
            keep[idx] = True
            continue

        if described_count >= max_images:
            stats.skipped_over_cap += 1
            keep[idx] = False
            continue

        import base64

        data_url = f"data:image/{ext};base64,{base64.b64encode(data).decode()}"
        try:
            resp = await vision_llm.ainvoke(build_embedded_image_messages(data_url))
            text = str(getattr(resp, "content", "") or "").strip()
            if not text:
                raise ValueError("视觉模型返回内容为空")
            # 单行化 + 限长（blockquote 单行渲染防断裂；限长防截断风险放大）
            text = " ".join(text.split())[:MAX_DESC_CHARS]
            seg.text = text
            desc_cache[digest] = text
            described_count += 1
            stats.described += 1
            keep[idx] = True
        except Exception as exc:  # noqa: BLE001 —— 单图失败落占位，不炸整篇
            logger.warning("内嵌图 VLM 描述失败（已占位跳过）: %s", exc)
            seg.text = "（图片解析失败）"
            stats.failed += 1
            keep[idx] = True
        done += 1
        if on_image is not None:
            try:
                await on_image(done, len(images))
            except Exception:  # noqa: BLE001
                pass

    if stats.skipped_over_cap:
        stats.notes.append(
            f"图片超过单文档上限（{max_images} 张），另有 {stats.skipped_over_cap} 张未解析"
        )
    out = [
        s
        for i, s in enumerate(segments)
        if s.kind != "image" or keep.get(i, False)
    ]
    return out, stats


# ─────────────────────────────────────────────────────────────
# 渲染（与旧实现逐字节等价是硬约束，改动前先看单测）
# ─────────────────────────────────────────────────────────────


def _image_block(seg: DocSegment) -> str:
    tag = f"【图片内容|第{seg.page}页】" if seg.page else "【图片内容】"
    return f"> {tag}{seg.text}"


def render_plain(segments: list[DocSegment]) -> str:
    """A 链 docx 渲染：纯段落文档与旧 `_read_docx`（"\\n" join 非空段落）逐字节等价；
    表格/图块是 A 链的净新增信息。"""
    lines: list[str] = []
    for seg in segments:
        if seg.kind == "para":
            lines.append(seg.text)
        elif seg.kind == "table":
            lines.append(seg.text)
        elif seg.kind == "image" and seg.text:
            lines.append(_image_block(seg))
    return "\n".join(lines)


def render_markdown_docx(segments: list[DocSegment]) -> str:
    """B 链 docx 渲染：无图文档与旧 `_docx_to_markdown` 逐字节等价
    （标题样式还原 #、表格块尾随空行、最终 strip）。"""
    lines: list[str] = []
    for seg in segments:
        if seg.kind == "para":
            style = seg.style or ""
            if style.startswith(("Heading", "标题")):
                digits = "".join(ch for ch in style if ch.isdigit())
                level = min(max(int(digits), 1), 6) if digits else 1
                lines.append(f"{'#' * level} {seg.text}")
            else:
                lines.append(seg.text)
        elif seg.kind == "table":
            lines.extend(seg.text.split("\n"))
            lines.append("")
        elif seg.kind == "image" and seg.text:
            lines.append(_image_block(seg))
    return "\n".join(lines).strip()


def render_pdf(segments: list[DocSegment]) -> str:
    """PDF 渲染：无图文档与旧 `_read_pdf`（"\\n" join 逐页 get_text）逐字节等价；
    图描述块紧跟所属页文本之后。"""
    lines: list[str] = []
    for seg in segments:
        if seg.kind == "page_text":
            lines.append(seg.text)
        elif seg.kind == "image" and seg.text:
            lines.append(_image_block(seg))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 扫描版 PDF：页级 VLM 转写（显式开关，成本高——调用方逐次决定）
# ─────────────────────────────────────────────────────────────


async def transcribe_scanned_pdf(
    path: Path,
    vision_llm: Any,
    *,
    max_pages: int = SCANNED_PDF_MAX_PAGES,
    on_page: Any = None,
) -> tuple[str, int, bool]:
    """无文本层 PDF：逐页渲染为图 → VLM 整页转写为 Markdown。

    返回 (markdown, 已转写页数, 是否超页数上限截断)。单页失败落占位继续。
    """
    import base64

    import fitz

    if vision_llm is None:
        raise ValueError(
            "扫描件解析需要 VISION 模型，请先在「用户中心 → 大模型配置」添加"
        )
    from app.ai_core.prompts.func_test_prompts import build_scanned_page_messages

    doc = fitz.open(str(path))
    try:
        total = doc.page_count
        pages = min(total, max_pages)
        out: list[str] = []
        for i in range(pages):
            try:
                pix = doc[i].get_pixmap(dpi=SCANNED_PDF_DPI)
                data_url = (
                    "data:image/png;base64,"
                    + base64.b64encode(pix.tobytes("png")).decode()
                )
                resp = await vision_llm.ainvoke(
                    build_scanned_page_messages(data_url, page_no=i + 1)
                )
                text = str(getattr(resp, "content", "") or "").strip()
                out.append(text or f"（第 {i + 1} 页转写为空）")
            except Exception as exc:  # noqa: BLE001 —— 单页失败不炸整份
                logger.warning("扫描件第 %s 页转写失败（已占位）: %s", i + 1, exc)
                out.append(f"（第 {i + 1} 页转写失败）")
            if on_page is not None:
                try:
                    await on_page(i + 1, pages)
                except Exception:  # noqa: BLE001
                    pass
        return "\n\n".join(out), pages, total > pages
    finally:
        doc.close()
