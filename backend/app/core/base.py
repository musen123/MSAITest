"""
基础模型类

定义 ORM 模型和 Schema 的基类
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ========================================
# ORM 基类
# ========================================


class Base(DeclarativeBase):
    """
    SQLAlchemy ORM 基类

    所有 ORM 模型都应继承此基类
    """

    pass


class TimestampMixin:
    """
    时间戳混入类

    为模型添加创建时间和更新时间字段
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class IDMixin:
    """
    ID 混入类

    为模型添加主键 ID 字段
    """

    id: Mapped[int] = mapped_column(
        BIGINT,
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )


class SoftDeleteMixin:
    """
    软删除混入类

    为模型添加软删除功能
    """

    is_deleted: Mapped[bool] = mapped_column(
        TINYINT,
        default=False,
        comment="是否删除",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        comment="删除时间",
    )


# ========================================
# Pydantic Schema 基类
# ========================================


class SchemaBase(BaseModel):
    """
    Schema 基类

    所有 Schema 都应继承此基类
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class SchemaCreate(SchemaBase):
    """
    创建 Schema 基类

    用于创建资源的请求
    """

    pass


class SchemaUpdate(SchemaBase):
    """
    更新 Schema 基类

    用于更新资源的请求
    """

    pass


class SchemaInDB(SchemaBase):
    """
    数据库 Schema 基类

    包含数据库中的所有字段
    """

    id: int
    created_at: datetime
    updated_at: datetime


class SchemaResponse(SchemaBase):
    """
    响应 Schema 基类

    用于 API 响应
    """

    pass


# ========================================
# 通用 Schema
# ========================================


class IdRequest(BaseModel):
    """
    ID 请求模型

    用于需要 ID 的请求
    """

    id: int


class IdsRequest(BaseModel):
    """
    批量 ID 请求模型
    """

    ids: list[int]


class PaginationRequest(BaseModel):
    """
    分页请求模型
    """

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """获取限制数量"""
        return self.page_size


class PaginationResponse(BaseModel):
    """
    分页响应模型
    """

    total: int
    page: int
    page_size: int
    total_pages: int
