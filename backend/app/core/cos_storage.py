"""
腾讯云 COS 对象存储工具模块

提供文件上传、下载、获取 URL、删除等公共方法。
"""

import mimetypes
import os
import uuid
from datetime import datetime
from typing import BinaryIO

from qcloud_cos import CosConfig, CosS3Client

from app.core.config import settings

# 常见文件扩展名 MIME 映射（补充 mimetypes 未覆盖的）
_EXTRA_MIME_TYPES = {
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".sql": "text/plain",
    ".sh": "text/x-shellscript",
    ".bash": "text/x-shellscript",
}


def _guess_content_type(filename: str) -> str:
    """根据文件名猜测 Content-Type"""
    ext = os.path.splitext(filename)[1].lower()
    if ext in _EXTRA_MIME_TYPES:
        return _EXTRA_MIME_TYPES[ext]
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"

_client: CosS3Client | None = None


def _get_client() -> CosS3Client:
    """获取或创建 COS 客户端单例"""
    global _client
    if _client is None:
        config = CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
        _client = CosS3Client(config)
    return _client


def _build_key(filename: str, prefix: str = "") -> str:
    """
    自动生成 COS 对象 Key。

    格式: {prefix}/{年月}/{uuid}{扩展名}
    """
    dir_prefix = prefix.rstrip("/") + "/" if prefix else settings.COS_UPLOAD_DIR
    dir_prefix = dir_prefix.rstrip("/") + "/"
    ext = os.path.splitext(filename)[1] or ""
    month_dir = datetime.now().strftime("%Y%m")
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return f"{dir_prefix}{month_dir}/{unique_name}"


def upload_file(
    file_data: BinaryIO | bytes,
    filename: str = "",
    prefix: str = "",
    key: str = "",
) -> str:
    """
    上传文件到 COS。

    Args:
        file_data: 文件内容（文件对象或字节）
        filename: 原始文件名，自动生成 Key 时使用
        prefix: 自定义目录前缀
        key: 直接指定完整 COS Key，优先级最高

    Returns:
        上传后的 COS Key
    """
    cos_key = key or _build_key(filename, prefix)
    body = file_data if isinstance(file_data, bytes) else file_data.read()
    content_type = _guess_content_type(filename or cos_key)

    _get_client().put_object(
        Bucket=settings.COS_BUCKET,
        Key=cos_key,
        Body=body,
        ContentType=content_type,
    )
    return cos_key


def upload_local_file(local_path: str, key: str = "") -> str:
    """
    上传本地文件到 COS。

    Args:
        local_path: 本地文件路径
        key: 自定义 Key，不传则自动生成

    Returns:
        上传后的 COS Key
    """
    filename = os.path.basename(local_path)
    cos_key = key or _build_key(filename)
    content_type = _guess_content_type(filename or cos_key)

    with open(local_path, "rb") as f:
        _get_client().put_object(
            Bucket=settings.COS_BUCKET,
            Key=cos_key,
            Body=f,
            ContentType=content_type,
        )
    return cos_key


def get_object_url(key: str, expires: int = 3600) -> str:
    """
    获取文件的预签名访问 URL。

    Args:
        key: COS 对象 Key
        expires: URL 有效期（秒），默认 1 小时

    Returns:
        预签名 URL
    """
    return _get_client().get_presigned_url(
        Method="GET",
        Bucket=settings.COS_BUCKET,
        Key=key,
        Expired=expires,
    )


def get_object_bytes(key: str) -> bytes:
    """
    下载文件内容到内存。

    Args:
        key: COS 对象 Key

    Returns:
        文件二进制内容
    """
    resp = _get_client().get_object(
        Bucket=settings.COS_BUCKET,
        Key=key,
    )
    # ⚠ 坑：腾讯云 COS SDK 返回的 StreamBody.read() 无参数时只返回首个 ~1024B 分块，
    # 并非标准 file-like 的「读到 EOF」语义 → >1KB 的文件（docx/pdf/图片等）会被截断成
    # 残缺内容（现象：docx 变残缺 zip → python-docx PackageNotFoundError「文件损坏」）。
    # 必须走底层 raw stream 一次性读全。
    return resp["Body"].get_raw_stream().read()


def download_to_local(key: str, local_path: str) -> str:
    """
    下载 COS 文件到本地。

    Args:
        key: COS 对象 Key
        local_path: 本地保存路径

    Returns:
        本地文件路径
    """
    resp = _get_client().get_object(
        Bucket=settings.COS_BUCKET,
        Key=key,
    )
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    # ⚠ 同 get_object_bytes：不能用 Body.read()（只读首个 ~1024B 分块，会截断文件），
    # 用官方流式落盘接口写全量。
    resp["Body"].get_stream_to_file(local_path)
    return local_path


def delete_object(key: str) -> None:
    """
    删除 COS 上的文件。

    Args:
        key: COS 对象 Key
    """
    _get_client().delete_object(
        Bucket=settings.COS_BUCKET,
        Key=key,
    )


def object_exists(key: str) -> bool:
    """
    检查文件是否存在于 COS。

    Args:
        key: COS 对象 Key

    Returns:
        是否存在
    """
    try:
        _get_client().head_object(
            Bucket=settings.COS_BUCKET,
            Key=key,
        )
        return True
    except Exception:
        return False
