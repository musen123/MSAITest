"""智能体工具运行上下文

每次 agent 调用工具需要知道当前 project_id 和 user_id（用于权限隔离），
通过 ContextVar 传入，工具内部通过 getter 读取。
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentContext:
    project_id: int
    user_id: int
    conversation_id: int


_ctx: ContextVar[Optional[AgentContext]] = ContextVar(
    "chat_agent_context", default=None
)


def set_agent_context(ctx: AgentContext) -> None:
    _ctx.set(ctx)


def get_agent_context() -> AgentContext:
    ctx = _ctx.get()
    if ctx is None:
        raise RuntimeError(
            "agent context not set: 工具必须在 AgentOrchestrator.stream() 内运行"
        )
    return ctx
