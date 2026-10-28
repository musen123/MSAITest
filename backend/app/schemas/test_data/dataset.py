"""测试数据集 Pydantic schema。

列名即执行时注入的变量键（``${{列名}}`` 引用），故须是合法变量名。
与压测数据集不同：行**明文存读**（内部测试平台），kind 仅作语义标签 +
AI 造数填充策略（identity/secret 列不让 AI 编造，留空待人工补真实值）。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 单数据集行数软上限（功能/Web 测试数据面向十~百级，远小于压测；防超大 JSON）
MAX_DATASET_ROWS = 10_000
VALID_KINDS = {"identity", "secret", "synthetic"}
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TestDatasetColumn(BaseModel):
    """一列定义：name(=变量键/``${{}}`` 引用名)、desc(给 AI 造数/人看)、kind(填充策略)。"""

    name: str = Field(..., max_length=64)
    desc: Optional[str] = Field(None, max_length=255)
    kind: str = Field(
        "synthetic",
        description="identity(真实身份,AI不编造)/secret(密码令牌,AI不编造)/synthetic(合成)",
    )

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v not in VALID_KINDS:
            raise ValueError(f"列 kind 非法：{v}（应为 {', '.join(sorted(VALID_KINDS))}）")
        return v

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not _NAME_RE.match(v or ""):
            raise ValueError(
                f"列名 {v!r} 非法：须为字母/下划线开头的变量名（用于 ${{{{列名}}}} 引用）"
            )
        return v


def _validate_columns_rows(columns, rows) -> None:
    """跨字段校验：列名唯一；行键 ⊆ 列名（防 typo）；行数上限。"""
    names = [
        c.name if isinstance(c, TestDatasetColumn) else c.get("name")
        for c in (columns or [])
    ]
    if len(names) != len(set(names)):
        raise ValueError("列名重复")
    if rows and len(rows) > MAX_DATASET_ROWS:
        raise ValueError(f"行数 {len(rows)} 超上限 {MAX_DATASET_ROWS}")
    if rows:
        if not names:
            raise ValueError("有数据行但未定义列（columns 为空）")
        nameset = set(names)
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"第 {i + 1} 行不是对象")
            extra = set(row.keys()) - nameset
            if extra:
                raise ValueError(
                    f"第 {i + 1} 行含未声明列 {sorted(extra)}（列定义：{sorted(nameset)}）"
                )


class TestDatasetCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    columns: list[TestDatasetColumn] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    source: str = Field("manual", description="manual/csv/ai")

    @model_validator(mode="after")
    def _check(self):
        _validate_columns_rows(self.columns, self.rows)
        return self


class TestDatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    columns: Optional[list[TestDatasetColumn]] = None
    rows: Optional[list[dict]] = None

    @model_validator(mode="after")
    def _check(self):
        if self.columns is not None or self.rows is not None:
            # 局部更新时至少要能自洽：两者都给才做交叉校验，单给 rows 由端点层
            # 用库中现有 columns 校验（此处无法拿到）
            if self.columns is not None and self.rows is not None:
                _validate_columns_rows(self.columns, self.rows)
        return self


class TestDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    columns: Optional[list] = None
    rows: Optional[list] = None
    row_count: int
    source: str
    ai_task_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestDatasetListResponse(BaseModel):
    """列表项（不带 rows，防大 JSON 撑爆列表页）"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    columns: Optional[list] = None
    row_count: int
    source: str
    ai_task_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
