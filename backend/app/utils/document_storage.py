"""
项目文档存储工具

封装项目文档（需求文档、原型图、数据库字典等）和附件图片的存储操作。

存储路径约定：
  文档：projects/{project_id}/documents/{year}/{month}/{uuid}.{ext}
  附件：projects/{project_id}/attachments/{uuid}.{ext}

COS 模式下前端直接通过 COS 地址访问文件。
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.storage_utils import save_bytes, remove_file, get_access_url

# 文档支持的扩展名（含 MIME 类型映射）
DOCUMENT_ALLOWED_EXTENSIONS: dict[str, list[str]] = {
    ".pdf": ["application/pdf"],
    ".doc": ["application/msword"],
    ".docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ],
    ".xls": ["application/vnd.ms-excel"],
    ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ".ppt": ["application/vnd.ms-powerpoint"],
    ".pptx": [
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ],
    ".txt": ["text/plain"],
    ".md": ["text/markdown", "text/plain"],
    ".png": ["image/png"],
    ".jpg": ["image/jpeg"],
    ".jpeg": ["image/jpeg"],
    ".gif": ["image/gif"],
    ".webp": ["image/webp"],
}

# 附件支持的扩展名（仅图片）
ATTACHMENT_ALLOWED_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _build_document_key(project_id: int, file_ext: str) -> str:
    """构建文档存储路径（按年/月分层）"""
    now = datetime.now()
    return f"projects/{project_id}/documents/{now.year}/{now.month:02d}/{uuid.uuid4().hex}{file_ext}"


def _build_attachment_key(project_id: int, file_ext: str) -> str:
    """构建附件存储路径"""
    return f"projects/{project_id}/attachments/{uuid.uuid4().hex}{file_ext}"


def validate_document_file(file: UploadFile) -> str:
    """校验上传的项目文档文件，返回小写扩展名"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in DOCUMENT_ALLOWED_EXTENSIONS:
        allowed = ", ".join(DOCUMENT_ALLOWED_EXTENSIONS.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，允许：{allowed}",
        )
    return file_ext


async def save_document_file(
    file: UploadFile,
    project_id: int,
) -> tuple[str, int, str]:
    """
    将上传文件保存到存储。

    Returns:
        tuple: (storage_key, file_size_bytes, file_ext)
    """
    file_ext = validate_document_file(file)
    storage_key = _build_document_key(project_id, file_ext)

    try:
        content = await file.read()

        max_bytes = settings.MAX_UPLOAD_SIZE * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小超过限制（最大 {settings.MAX_UPLOAD_SIZE}MB）",
            )

        save_bytes(content, storage_key)
        return storage_key, len(content), file_ext

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败：{exc}",
        )


async def save_attachment_file(
    file: UploadFile,
    project_id: int,
) -> str:
    """保存需求附件图片到存储，返回 storage_key"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ATTACHMENT_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"附件仅支持图片格式：{', '.join(ATTACHMENT_ALLOWED_EXTENSIONS)}",
        )

    storage_key = _build_attachment_key(project_id, file_ext)

    try:
        content = await file.read()

        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="附件大小超过限制（最大 20MB）",
            )

        save_bytes(content, storage_key)
        return storage_key

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"附件保存失败：{exc}",
        )


def delete_document_file(storage_key: Optional[str]) -> bool:
    """删除文档文件"""
    return remove_file(storage_key)


def get_document_url(storage_key: str) -> str:
    """将存储路径转换为前端可访问的 URL"""
    return get_access_url(storage_key)
