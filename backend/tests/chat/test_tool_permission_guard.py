"""小测工具权限守卫回归测试（纯逻辑 + 覆盖，无需真实用户）。

守护三件事，防止「走小测越权」复发：
  1. **覆盖**：每个注册进 ALL_TOOLS 的工具都被鉴权覆盖（在 PERM_MAP 或 UNGATED）——
     新增工具若忘挂守卫会红，杜绝再出现无鉴权工具。
  2. **权限码有效**：PERM_MAP 引用的权限码都是 init_db 种子里真实定义的——打错码
     （如 app_test:exec）会让守卫要么永远拒绝、要么形同虚设，此测拦住。
  3. **判定规则**：与 core.deps.require_permission 一致——super_admin 放行 + OR 语义。
"""

import re
from pathlib import Path

import app.db.init_db as init_db_mod
from app.ai_core.chat_agent.agent_context import AgentContext, set_agent_context
from app.ai_core.chat_agent.tools import ALL_TOOLS
from app.ai_core.chat_agent.tools import permissions as perm_mod
from app.ai_core.chat_agent.tools.permissions import (
    PERM_MAP,
    UNGATED,
    check_tool_permission,
)

_CODE_DEF = re.compile(r'"code":\s*"([a-z_]+:[a-z_]+)"')
_DEFINED_CODES = set(
    _CODE_DEF.findall(Path(init_db_mod.__file__).read_text(encoding="utf-8"))
)


class TestToolPermissionGuardCoverage:
    def test_every_tool_is_gated_or_explicitly_ungated(self) -> None:
        names = {t.name for t in ALL_TOOLS}
        uncovered = sorted(n for n in names if n not in PERM_MAP and n not in UNGATED)
        assert not uncovered, (
            f"以下工具未挂权限守卫（既不在 PERM_MAP 也不在 UNGATED），存在越权风险: "
            f"{uncovered}"
        )

    def test_perm_map_codes_are_defined_in_seed(self) -> None:
        used = {c for codes in PERM_MAP.values() for c in codes}
        missing = sorted(used - _DEFINED_CODES)
        assert (
            not missing
        ), f"PERM_MAP 引用了未在种子中定义的权限码（疑打错）: {missing}"

    def test_no_stale_perm_map_entries(self) -> None:
        names = {t.name for t in ALL_TOOLS}
        stale = sorted(k for k in PERM_MAP if k not in names)
        assert not stale, f"PERM_MAP 存在已不再注册的工具项: {stale}"


class TestToolPermissionGuardLogic:
    async def test_super_admin_bypass(self, monkeypatch) -> None:
        async def fake(_uid):
            return set(), True  # 无具体权限但 super_admin

        monkeypatch.setattr(perm_mod, "_load_user_perms", fake)
        set_agent_context(AgentContext(project_id=1, user_id=11, conversation_id=0))
        assert await check_tool_permission("run_app_case") is None

    async def test_denied_without_permission(self, monkeypatch) -> None:
        async def fake(_uid):
            return set(), False

        monkeypatch.setattr(perm_mod, "_load_user_perms", fake)
        set_agent_context(AgentContext(project_id=1, user_id=12, conversation_id=0))
        denied = await check_tool_permission("run_app_case")
        assert denied is not None and "无权限" in denied

    async def test_allowed_with_matching_permission(self, monkeypatch) -> None:
        async def fake(_uid):
            return {"app_test:execute"}, False

        monkeypatch.setattr(perm_mod, "_load_user_perms", fake)
        set_agent_context(AgentContext(project_id=1, user_id=13, conversation_id=0))
        assert await check_tool_permission("run_app_case") is None

    async def test_or_semantics_precise(self, monkeypatch) -> None:
        # 持有别域 execute 与本域 view，但没有 app_test:execute → 必须拒绝
        async def fake(_uid):
            return {"app_test:view", "test_case:execute"}, False

        monkeypatch.setattr(perm_mod, "_load_user_perms", fake)
        set_agent_context(AgentContext(project_id=1, user_id=14, conversation_id=0))
        assert await check_tool_permission("run_app_case") is not None

    async def test_ungated_tool_always_allowed(self, monkeypatch) -> None:
        async def fake(_uid):
            return set(), False

        monkeypatch.setattr(perm_mod, "_load_user_perms", fake)
        set_agent_context(AgentContext(project_id=1, user_id=15, conversation_id=0))
        assert await check_tool_permission("open_page") is None
