"""
文件处理工具函数

包含文件上传、验证、保存等功能
"""

import uuid
from pathlib import Path
from time import time
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.storage_utils import save_bytes, remove_file, get_access_url


def validate_avatar_file(file: UploadFile) -> None:
    """
    验证头像文件

    Args:
        file: 上传的文件对象

    Raises:
        HTTPException: 文件验证失败
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in settings.AVATAR_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，允许的格式：{', '.join(settings.AVATAR_ALLOWED_EXTENSIONS)}",
        )

    allowed_mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }

    if file.content_type not in allowed_mime_types.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型，请上传图片文件",
        )


async def save_avatar_file(
    file: UploadFile,
    user_id: int,
) -> str:
    """
    保存头像文件，返回前端可访问的 URL。

    COS 模式：返回 COS 预签名 URL。
    本地模式：返回 /uploads/avatars/{filename}。

    Args:
        file: 上传的文件对象
        user_id: 用户ID

    Returns:
        str: 前端可访问的 URL

    Raises:
        HTTPException: 文件保存失败
    """
    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{user_id}_{int(time())}_{uuid.uuid4().hex[:8]}{file_ext}"
    storage_key = f"avatars/{unique_filename}"

    try:
        content = await file.read()

        max_size = settings.AVATAR_MAX_SIZE * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小超过限制（最大 {settings.AVATAR_MAX_SIZE}MB）",
            )

        save_bytes(content, storage_key)
        return get_access_url(storage_key)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败：{str(e)}",
        )


def delete_avatar_file(file_path: Optional[str]) -> bool:
    """
    删除头像文件。

    兼容两种路径格式：
    - 本地路径: /uploads/avatars/xxx.jpg -> 提取 avatars/xxx.jpg
    - COS URL: https://...cos.../avatars/xxx.jpg -> 提取 avatars/xxx.jpg
    """
    if not file_path:
        return False
    storage_key = _extract_storage_key(file_path)
    return remove_file(storage_key)


def get_avatar_url(file_path: str) -> str:
    """获取头像访问 URL。COS 模式下重新生成预签名 URL。"""
    if not file_path:
        return file_path
    storage_key = _extract_storage_key(file_path)
    return get_access_url(storage_key)


def _extract_storage_key(file_path: str) -> str:
    """从 URL 或本地路径中提取 storage_key（如 avatars/xxx.jpg）"""
    # COS URL: https://bucket.cos.region.myqcloud.com/avatars/xxx.jpg?sign=...
    if file_path.startswith("http"):
        from urllib.parse import urlparse
        path = urlparse(file_path).path.lstrip("/")
        return path.split("?")[0]
    # 本地路径: /uploads/avatars/xxx.jpg
    return file_path.lstrip("/").removeprefix("uploads/")
