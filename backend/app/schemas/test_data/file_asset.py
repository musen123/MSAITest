"""测试文件资产 Pydantic schema。

``name`` 是项目内引用键（Web 脚本 ``${{file:名}}`` 渲染期解析为 storage_key），
故限定为不含花括号/冒号的短名；创建走 multipart 上传端点（无 Create schema）。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 资产名：排除 { } : 与空白（引用语法 ${{file:名}} 的解析安全），其余中英文均可
_ASSET_NAME_RE = re.compile(r"^[^{}:\s]{1,100}$")


def validate_asset_name(name: str) -> str:
    if not _ASSET_NAME_RE.match(name or ""):
        raise ValueError(
            "资产名非法：1~100 字符，不能含空白、冒号或花括号（将用于 ${{file:名}} 引用）"
        )
    return name


class TestFileAssetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    spec: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v):
        if v is None:
            return v
        return validate_asset_name(v)


class TestFileAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    file_name: str
    storage_key: str
    mime: Optional[str] = None
    size_bytes: Optional[int] = None
    source: str
    spec: Optional[str] = None
    ai_task_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 访问 URL（本地 /uploads 或 COS 签名 URL），端点层填充
    url: Optional[str] = None


class TestFileAssetListResponse(TestFileAssetResponse):
    pass
