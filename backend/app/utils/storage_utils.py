"""
统一存储工具

封装本地存储和腾讯云 COS 的切换逻辑。
COS_ENABLED=True 时走 COS，否则保持本地文件操作。

COS 模式下前端直接通过 COS 地址访问文件，不经过后端代理。
"""

from pathlib import Path
from typing import Optional

from app.core.config import settings


def is_cos_enabled() -> bool:
    return settings.COS_ENABLED


def get_access_url(storage_key: str, expires: int = 3600 * 24 * 7) -> str:
    """
    根据存储路径返回前端可访问的 URL。

    COS 模式：返回 COS 预签名 URL（默认 7 天有效期）。
    本地模式：返回 /uploads/{key}。

    Args:
        storage_key: 存储路径，如 avatars/xxx.jpg
        expires: 预签名 URL 有效期（秒），默认 7 天

    Returns:
        前端可访问的 URL
    """
    if is_cos_enabled():
        from app.core.cos_storage import get_object_url
        return get_object_url(storage_key, expires=expires)
    return f"/uploads/{storage_key}"


def save_bytes(content: bytes, storage_key: str) -> tuple[str, str]:
    """
    保存文件内容。

    Args:
        content: 文件二进制内容
        storage_key: 存储路径，如 avatars/xxx.jpg

    Returns:
        (storage_key, access_url)
    """
    if is_cos_enabled():
        from app.core.cos_storage import upload_file
        upload_file(content, key=storage_key)
    else:
        local_path = Path(settings.UPLOAD_DIR) / storage_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
    return storage_key, get_access_url(storage_key)


def save_local_file(local_path: str, storage_key: str) -> tuple[str, str]:
    """
    上传本地文件到存储。

    Args:
        local_path: 本地文件路径
        storage_key: 目标存储路径

    Returns:
        (storage_key, access_url)
    """
    if is_cos_enabled():
        from app.core.cos_storage import upload_local_file
        upload_local_file(local_path, key=storage_key)
    return storage_key, get_access_url(storage_key)


def remove_file(storage_key: str) -> bool:
    """
    删除文件。
    """
    try:
        if is_cos_enabled():
            from app.core.cos_storage import delete_object
            delete_object(storage_key)
        else:
            full_path = Path(settings.UPLOAD_DIR) / storage_key
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
        return True
    except Exception:
        return False


def read_bytes(storage_key: str) -> bytes:
    """读取文件内容（COS 或本地）"""
    if is_cos_enabled():
        from app.core.cos_storage import get_object_bytes
        return get_object_bytes(storage_key)
    full_path = Path(settings.UPLOAD_DIR) / storage_key
    if not full_path.exists():
        raise FileNotFoundError(f"文件不存在：{storage_key}")
    return full_path.read_bytes()


def download_to_path(storage_key: str, dest_path: str) -> None:
    """把存储的文件下载到本地路径（COS 模式下用于临时处理）"""
    Path(dest_path).write_bytes(read_bytes(storage_key))
