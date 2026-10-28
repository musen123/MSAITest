"""
LLM 上下文变量

用于在异步调用链中传递当前用户的 LLM 实例，
避免将 llm 参数逐层透传到每个函数。
"""

from contextvars import ContextVar
from typing import Any, Optional

_llm_var: ContextVar[Optional[Any]] = ContextVar("user_llm", default=None)
_embed_var: ContextVar[Optional[Any]] = ContextVar("user_embed_llm", default=None)
_vision_var: ContextVar[Optional[Any]] = ContextVar("user_vision_llm", default=None)


def set_current_llm(llm: Any) -> None:
    _llm_var.set(llm)


def get_current_llm() -> Any:
    from app.core.exceptions import BusinessException
    llm = _llm_var.get()
    if llm is None:
        raise BusinessException("请先配置文本大模型，再使用 AI 功能", code=400)
    return llm


def set_current_embed_llm(llm: Any) -> None:
    _embed_var.set(llm)


def get_current_embed_llm() -> Any:
    from app.core.exceptions import BusinessException
    llm = _embed_var.get()
    if llm is None:
        raise BusinessException("请先配置嵌入模型，再使用该功能", code=400)
    return llm


def set_current_vision_llm(llm: Any) -> None:
    _vision_var.set(llm)


def get_current_vision_llm() -> Any:
    from app.core.exceptions import BusinessException
    llm = _vision_var.get()
    if llm is None:
        raise BusinessException("请先配置视觉模型，再使用该功能", code=400)
    return llm
