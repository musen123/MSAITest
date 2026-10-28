"""持久记忆工具（对标 Claude Code 的记忆读写）。

让小测把用户的**跨对话偏好/约定**沉淀下来，下轮/下次对话自动带上。按 (project,user)
命名空间隔离，只碰用户自己的聊天记忆、不动任何平台数据，故免 RBAC 鉴权（见
permissions.UNGATED）。刻意只记「偏好/约定」，不记数量/列表等会过期的数据快照。
"""

from langchain.tools import tool

from app.ai_core.chat_agent.tools.base import tool_error, tool_json


@tool(
    "remember",
    description=(
        "记住一条跨对话的偏好或约定，之后的对话会自动带上（仅本项目、本人可见）。"
        "适合：默认选择（如「App 默认使用测试设备」）、关注重点（如「重点盯支付模块」）、"
        "命名约定等。**不要**用它记数量/列表等会变的数据。参数：key（简短主题，如"
        "「默认 App 测试设备」）、value（具体内容）。"
    ),
)
async def remember(key: str, value: str) -> str:
    from app.ai_core.chat_agent.memory_store import remember as _remember

    key = (key or "").strip()
    value = (value or "").strip()
    if not key or not value:
        return tool_error("key 和 value 均不能为空")
    await _remember(key, value)
    return tool_json(
        {
            "remembered": True,
            "key": key,
            "value": value,
            "message": "已记住，后续对话会自动带上",
        }
    )


@tool(
    "recall",
    description="列出你之前记下的跨对话事项（本项目、本人）。无参数。",
)
async def recall() -> str:
    from app.ai_core.chat_agent.memory_store import recall as _recall

    items = await _recall()
    return tool_json({"total": len(items), "items": items})


@tool(
    "forget",
    description="删除一条已记事项。参数：key（要删除的主题，用 recall 查看有哪些）。",
)
async def forget(key: str) -> str:
    from app.ai_core.chat_agent.memory_store import forget as _forget

    key = (key or "").strip()
    if not key:
        return tool_error("key 不能为空")
    ok = await _forget(key)
    return tool_json(
        {
            "forgotten": ok,
            "key": key,
            "message": "已删除" if ok else "未找到该事项",
        }
    )
