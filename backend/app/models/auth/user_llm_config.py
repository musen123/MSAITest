"""用户大模型配置表"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base

if TYPE_CHECKING:
    from app.models.auth.user import User


class ModelType(str, Enum):
    TEXT = "text"
    EMBED = "embed"
    VISION = "vision"
    RERANK = "rerank"  # P2：检索重排（OpenAI 兼容 /rerank，深度模式替代 listwise LLM）


class UserLlmConfig(Base):
    __tablename__ = "sys_user_llm_config"
    # 注：每用户每类型可配置多个，运行时取 is_default=True 的那条。
    # MySQL/InnoDB 不支持 partial unique index，"同 (user_id, model_type) 恰好一个默认"
    # 由 CRUD 层在事务内用 SELECT ... FOR UPDATE 锁行保证，不在此建唯一约束。

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("sys_user.id"), nullable=False
    )
    model_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ModelType.TEXT, comment="模型类型: text/embed/vision"
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="配置别名/备注，用于区分同类型多个配置"
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="模型提供商: openai/anthropic 等"
    )
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="模型名称"
    )
    api_key: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="API Key"
    )
    base_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="自定义 Base URL"
    )
    model_family: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment=(
            "模型家族（Midscene VL grounding 必填，如 doubao-seed/qwen3-vl/glm-v；"
            "配错=坐标静默偏移。仅 vision 类型使用"
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="是否为该用户该类型的默认配置（运行时取默认那条）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="llm_configs")
