"""测试文件锻造：按规格用代码生成**格式合法**的真实文件。

设计铁律：LLM 只产「规格 + 文本内容」，二进制格式一律由代码封装
（pymupdf=PDF/PNG、python-docx=Word、openpyxl=Excel、csv/json/txt 原生）——
格式正确性由库保证，杜绝模型手搓二进制的乱码文件。

大文件（target_size_bytes）：
  - txt/csv/bin：精确填充到目标大小；
  - pdf：追加随机噪声图页逼近目标（噪声不可压缩，逼近快；±5% 容差）；
  - 其它格式不支持定容（调用方应引导用 txt/bin/pdf 做大文件场景）。
"""

from __future__ import annotations

import csv
import io
import json
import os

MAX_FORGE_BYTES = 50 * 1024 * 1024  # 单文件上限，与上传通道一致
SUPPORTED_KINDS = {"pdf", "docx", "xlsx", "csv", "txt", "json", "md", "png", "bin"}

_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "txt": "text/plain",
    "json": "application/json",
    "md": "text/markdown",
    "png": "image/png",
    "bin": "application/octet-stream",
}


def normalize_kind(kind: str, file_name: str = "") -> str:
    """规格 kind 归一：优先显式 kind，非法时按扩展名兜底，仍无 → txt。"""
    k = (kind or "").strip().lower().lstrip(".")
    if k in SUPPORTED_KINDS:
        return k
    ext = os.path.splitext(file_name or "")[1].lstrip(".").lower()
    if ext in SUPPORTED_KINDS:
        return ext
    return "txt"


def mime_of(kind: str) -> str:
    return _MIME.get(kind, "application/octet-stream")


# ─────────────────────── 各格式锻造 ───────────────────────


def _forge_pdf(text: str, target_size: int | None) -> bytes:
    import fitz  # pymupdf

    doc = fitz.open()
    chunks = [text[i : i + 1800] for i in range(0, len(text), 1800)] or [""]
    for chunk in chunks[:50]:
        page = doc.new_page()
        page.insert_textbox(
            fitz.Rect(50, 50, page.rect.width - 50, page.rect.height - 50),
            chunk,
            fontsize=11,
            fontname="china-s",  # 内置中文字体，保证中文不豆腐块
        )
    if target_size:
        # 噪声图页逼近目标大小（随机像素不可压缩，逼近快）；每页 ~500² RGB 噪声
        target = min(target_size, MAX_FORGE_BYTES)
        while len(doc.tobytes()) < target and doc.page_count < 300:
            w = h = 500
            samples = os.urandom(w * h * 3)  # RGB 无 alpha
            pix = fitz.Pixmap(fitz.csRGB, w, h, samples, 0)
            page = doc.new_page()
            page.insert_image(fitz.Rect(20, 20, 580, 580), pixmap=pix)
    return doc.tobytes()


def _forge_docx(text: str) -> bytes:
    from docx import Document

    doc = Document()
    for line in (text or "").splitlines() or [""]:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _forge_xlsx(table: dict | None, text: str) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    headers = (table or {}).get("headers") or []
    rows = (table or {}).get("rows") or []
    if headers:
        ws.append(list(headers))
    for row in rows[:5000]:
        ws.append(list(row) if isinstance(row, (list, tuple)) else [str(row)])
    if not headers and not rows:
        ws.append([text or ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _forge_csv(table: dict | None, text: str) -> bytes:
    headers = (table or {}).get("headers") or []
    rows = (table or {}).get("rows") or []
    buf = io.StringIO()
    writer = csv.writer(buf)
    if headers:
        writer.writerow(headers)
    for row in rows[:50000]:
        writer.writerow(list(row) if isinstance(row, (list, tuple)) else [str(row)])
    if not headers and not rows:
        buf.write(text or "")
    # utf-8-sig：Excel 直接打开中文不乱码
    return buf.getvalue().encode("utf-8-sig")


def _forge_png(text: str) -> bytes:
    """带文字内容的 PNG：文字排进 PDF 页再栅格化（图里真有可读内容，
    供上传预览/OCR 类场景；比纯噪声图更接近真实测试图片）。"""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_textbox(
        fitz.Rect(40, 40, 760, 560), (text or "test image")[:1500],
        fontsize=14, fontname="china-s",
    )
    pix = page.get_pixmap()
    return pix.tobytes("png")


def _pad_text(content: bytes, target: int) -> bytes:
    if len(content) >= target:
        return content
    pad_line = ("x" * 79 + "\n").encode()
    need = target - len(content)
    return content + pad_line * (need // len(pad_line)) + b"x" * (need % len(pad_line))


def forge_file(spec: dict) -> tuple[bytes, str]:
    """按规格生成文件字节。返回 (content, mime)。

    spec: {kind, file_name, text?, table?{headers,rows}, target_size_bytes?}
    超限/未知格式在 normalize 层兜底；生成结果超 MAX_FORGE_BYTES 抛 ValueError。
    """
    kind = normalize_kind(spec.get("kind") or "", spec.get("file_name") or "")
    text = str(spec.get("text") or "")
    table = spec.get("table") if isinstance(spec.get("table"), dict) else None
    target = spec.get("target_size_bytes")
    target = int(target) if target else None
    if target and target > MAX_FORGE_BYTES:
        raise ValueError(f"目标大小 {target} 超上限 {MAX_FORGE_BYTES}")

    if kind == "pdf":
        content = _forge_pdf(text, target)
    elif kind == "docx":
        content = _forge_docx(text)
    elif kind == "xlsx":
        content = _forge_xlsx(table, text)
    elif kind == "csv":
        content = _forge_csv(table, text)
        if target:
            content = _pad_text(content, target)
    elif kind == "png":
        content = _forge_png(text)
    elif kind == "json":
        # text 若是合法 JSON 原样用，否则包成 {"content": text}
        try:
            json.loads(text)
            content = text.encode()
        except Exception:  # noqa: BLE001
            content = json.dumps({"content": text}, ensure_ascii=False, indent=2).encode()
    elif kind == "bin":
        content = os.urandom(min(target or 1024, MAX_FORGE_BYTES))
    else:  # txt / md
        content = (text or "").encode()
        if target:
            content = _pad_text(content, target)

    if len(content) > MAX_FORGE_BYTES:
        raise ValueError(f"生成文件 {len(content)} 字节超上限 {MAX_FORGE_BYTES}")
    return content, mime_of(kind)
