"""测试文档在线预览服务

策略：
  - .pdf            → url（前端 iframe / pdf.js）
  - .png/.jpg/...   → url（前端 <img>）
  - .docx/.doc      → html（mammoth 转换；doc 不支持时返回 unsupported）
  - .md             → markdown（直接读文本）
  - .txt            → text
  - 其他            → unsupported（仅给 download_url）
"""

from pathlib import Path
from typing import Optional

from app.models.func_test.document import ProjectDocument
from app.schemas.func_test.document import DocumentPreviewResponse
from app.utils.document_storage import get_document_url
from app.utils.storage_utils import is_cos_enabled

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def _read_local_to_temp(storage_key: str) -> tuple[Path, Optional[Path]]:
    """COS 模式下下载到临时文件；本地模式直接返回路径"""
    from app.core.config import settings

    if is_cos_enabled():
        import tempfile

        from app.utils.storage_utils import download_to_path

        suffix = Path(storage_key).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        download_to_path(storage_key, str(tmp_path))
        return tmp_path, tmp_path

    local_path = Path(settings.UPLOAD_DIR) / storage_key
    return local_path, None


def _docx_to_html(local_path: Path) -> Optional[str]:
    """docx → HTML，失败返回 None"""
    try:
        import mammoth

        with open(local_path, "rb") as f:
            result = mammoth.convert_to_html(f)
            return result.value or ""
    except ImportError:
        return None
    except Exception:
        return None


def build_preview(doc: ProjectDocument) -> DocumentPreviewResponse:
    """构造文档预览响应"""
    ext = (doc.file_ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext

    base = DocumentPreviewResponse(
        preview_type="unsupported",
        file_ext=ext,
        file_name=doc.file_name,
        url=None,
        content=None,
        parsed_content=doc.parsed_content,
    )

    # URL 直显类
    if ext == ".pdf" or ext in _IMAGE_EXTS:
        try:
            base.url = get_document_url(doc.file_path)
            base.preview_type = "url"
        except Exception:
            base.preview_type = "unsupported"
        return base

    # 文本类
    if ext in (".md", ".txt"):
        try:
            local_path, tmp = _read_local_to_temp(doc.file_path)
            try:
                content = local_path.read_text(encoding="utf-8", errors="ignore")
            finally:
                if tmp is not None:
                    tmp.unlink(missing_ok=True)
            base.content = content
            base.preview_type = "markdown" if ext == ".md" else "text"
        except Exception:
            base.preview_type = "unsupported"
        return base

    # Word
    if ext in (".doc", ".docx"):
        try:
            local_path, tmp = _read_local_to_temp(doc.file_path)
            try:
                html = _docx_to_html(local_path) if ext == ".docx" else None
            finally:
                if tmp is not None:
                    tmp.unlink(missing_ok=True)
            if html is not None:
                base.content = html
                base.preview_type = "html"
            else:
                base.preview_type = "unsupported"
                base.url = get_document_url(doc.file_path)
        except Exception:
            base.preview_type = "unsupported"
        return base

    # 其他：仅给下载链接
    try:
        base.url = get_document_url(doc.file_path)
    except Exception:
        pass
    return base
