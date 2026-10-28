"""页面导航工具：返回动作卡片，用户点击后前端跳转"""

from langchain.tools import tool

from app.ai_core.chat_agent.tools.base import (
    PAGE_MAP,
    navigate_action,
    tool_error,
    tool_json,
)

_PAGE_DOC = "、".join(f"{k}={v[1]}" for k, v in PAGE_MAP.items())


@tool(
    "open_page",
    description=(
        "生成一个平台页面的跳转卡片（用户点击后跳转，不会自动跳转）。"
        f"参数：page，可选值：{_PAGE_DOC}。"
    ),
)
async def open_page(page: str) -> str:
    key = (page or "").strip().lower()
    if key not in PAGE_MAP:
        return tool_error(
            f"未知页面：{page}。可选值：{'、'.join(PAGE_MAP.keys())}"
        )
    route_name, label = PAGE_MAP[key]
    return tool_json(
        {"page": key, "label": label},
        action=navigate_action(route_name, f"打开{label}"),
    )
