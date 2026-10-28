"""小测工具权限守卫 —— 修复「绕过端点 require_permission 的越权」。

背景：小测工具直接调 service/CRUD，不经过挂着 `require_permission(...)` 的 HTTP
端点，导致平台的细粒度 RBAC 对「走小测」这条路失效——任何项目成员只要能用聊天，
就能做小测暴露的任何操作，无视其系统角色权限。

本模块给每个工具补一道与端点**同口径**的权限闸：
  - `PERM_MAP`：工具名 → 所需权限码（OR 语义，满足其一即可），逐一对齐对应端点的
    require_permission；查询类按 `:view`，写/执行类按其操作码。
  - `guard_tool(tool)`：组装 ALL_TOOLS 时把每个工具包一层——执行前用 ctx.user_id 加载
    该用户权限集，`super_admin` 直接放行、否则 OR 校验（与 core.deps.require_permission
    逐字一致）；缺权限返回 tool_error 而非执行。
  - 权限集按连接缓存（ContextVar），一轮对话多次工具调用只查一次库。

注：generic `/ai-tasks` 端点本身只校验 `ai_task:manage`（对 web/api 生成等偏松），
本守卫按**语义权限**判定（run_web_script→web_test:execute 等），只会比端点更严、
绝不更松——不会引入新的越权面。open_page（纯导航）不设限。
"""

from contextvars import ContextVar
from typing import Optional

PERM_MAP: dict[str, tuple[str, ...]] = {
    "get_project_overview": ("project:view",),
    "query_requirements": ("test_case:view",),
    "get_requirement_detail": ("test_case:view",),
    "query_func_cases": ("test_case:view",),
    "query_app_assets": ("app_test:view",),
    "query_app_devices": ("app_device:view",),
    "query_bugs": ("bug:view",),
    "query_environments": ("environment:view",),
    "query_scheduled_jobs": ("scheduler:view",),
    "query_ai_tasks": ("ai_task:view",),
    "query_members": ("member:view",),
    "get_execution_report": ("report:view",),
    "kb_search": ("knowledge:view",),
    "query_kb_graph": ("knowledge:view",),
    "analyze_change_impact": ("test_case:view",),
    "run_app_case": ("app_test:execute",),
    "run_app_suite": ("app_test:execute",),
    "explore_app": ("app_test:create", "app_test:execute"),
    "run_scheduled_job": ("scheduler:execute",),
    "toggle_scheduled_job": ("scheduler:execute",),
    "create_bug": ("bug:create",),
    "review_func_cases": ("test_case:edit",),
    "generate_func_cases": ("test_case:create",),
    "extract_requirements": ("test_case:create",),
    "create_scheduled_job": ("scheduler:create",),
    "update_scheduled_job": ("scheduler:edit",),
    "create_environment": ("environment:create",),
    "update_environment": ("environment:edit",),
    "kb_ingest_text": ("knowledge:manage",),
}
UNGATED: frozenset[str] = frozenset({"open_page", "remember", "recall", "forget"})
_perm_cache: ContextVar[Optional[tuple[int, set[str], bool]]] = ContextVar(
    "chat_tool_perm_cache", default=None
)


async def _load_user_perms(user_id: int) -> tuple[set[str], bool]:
    """加载用户权限集与是否 super_admin（带角色/权限关系，避免 MissingGreenlet）。"""
    from app.crud.auth import user_crud
    from app.db.session import async_session_maker

    async with async_session_maker() as db:
        user = await user_crud.get_with_relations(db, user_id=user_id)
    if not user:
        return (set(), False)
    return (set(user.permissions), "super_admin" in user.role_codes)


async def _current_user_perms() -> tuple[set[str], bool]:
    from app.ai_core.chat_agent.tools.base import ctx_ids

    _, user_id = ctx_ids()
    cached = _perm_cache.get()
    if cached is not None and cached[0] == user_id:
        return (cached[1], cached[2])
    perms, is_super = await _load_user_perms(user_id)
    _perm_cache.set((user_id, perms, is_super))
    return (perms, is_super)


async def check_tool_permission(tool_name: str) -> Optional[str]:
    """返回 None=放行；否则返回 tool_error 字符串（缺权限）。

    与 core.deps.require_permission 同规则：super_admin 放行 + OR 语义。
    """
    codes = PERM_MAP.get(tool_name)
    if not codes:
        return None
    perms, is_super = await _current_user_perms()
    if is_super or any((c in perms for c in codes)):
        return None
    from app.ai_core.chat_agent.tools.base import tool_error

    return tool_error(
        f"无权限执行此操作（需要以下权限之一：{'、'.join(codes)}）。如需该权限请联系管理员调整你的系统角色。"
    )


def guard_tool(tool):
    """给一个 langchain 工具包一层权限闸；免鉴权的原样返回。"""
    if tool.name in UNGATED or tool.name not in PERM_MAP:
        return tool
    orig_coroutine = tool.coroutine

    async def _guarded(**kwargs):
        denied = await check_tool_permission(tool.name)
        if denied is not None:
            return denied
        return await orig_coroutine(**kwargs)

    tool.coroutine = _guarded
    return tool
