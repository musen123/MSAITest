"""worker 安全的用户 LLM 加载

不依赖 FastAPI ``Depends``：自开 DB 会话，按发起人配置构建 LangChain 模型
并注入 ContextVar，供 graph 节点内 ``get_current_llm()/get_current_vision_llm()`` 使用。
"""

from typing import Optional

from app.ai_core.llm_client import build_llm_from_config
from app.ai_core.llm_context import set_current_llm, set_current_vision_llm
from app.crud.auth.user_llm_config import crud_user_llm_config
from app.db.session import async_session_maker
from app.models.auth.user_llm_config import ModelType


async def load_user_llms(user_id: int, *, kind: str = "text") -> Optional[str]:
    """按 kind 加载并注入用户 LLM 到 ContextVar。

    kind: ``text`` / ``vision`` / ``both``
    返回所用文本模型名（用于回写 ai_task.ai_model），无文本模型时返回 None。
    """
    if kind == "none":
        return None

    model_name: Optional[str] = None
    async with async_session_maker() as db:
        if kind in ("text", "both"):
            cfg = await crud_user_llm_config.get_default(
                db, user_id=user_id, model_type=ModelType.TEXT
            )
            if not cfg or not cfg.is_active:
                raise RuntimeError("用户未配置可用的文本大模型")
            set_current_llm(build_llm_from_config(cfg))
            model_name = getattr(cfg, "model_name", None) or getattr(cfg, "model", None)

        if kind in ("vision", "both"):
            cfg_v = await crud_user_llm_config.get_default(
                db, user_id=user_id, model_type=ModelType.VISION
            )
            if not cfg_v or not cfg_v.is_active:
                raise RuntimeError("用户未配置可用的视觉模型")
            set_current_vision_llm(build_llm_from_config(cfg_v))

    return model_name
