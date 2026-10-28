"""RBAC 种子一致性回归测试（纯数据，无需数据库）。

守护「权限点定义 ↔ 系统角色授权 ↔ 端点 require_permission 使用」三者一致，
防止再次出现两类漂移：

  1. 权限点定义了却没授权给任何常规角色（app_test:* 曾如此：只在 super_admin
     的「全量」路径里生效，全新初始化时 admin/tester/... 都用不了 App 用例）；
  2. 端点 require_permission 用了某权限码，但 init_db 种子里没建这个点
     （新增模块最容易漏，导致该端点对所有非超管永久 403）。

数据来源：
  - 已定义的权限点：扫描 init_db.py 里的 `"code": "x:y"`（基础点 + 增量点）；
  - 角色授权矩阵：直接 import SYSTEM_ROLE_DEFINITIONS；
  - 端点使用：静态扫描 app/ 下 require_permission("x:y", ...) 的字符串字面量。
"""

import re
from pathlib import Path

import app.db.init_db as init_db_mod
from app.db.init_db import SYSTEM_ROLE_DEFINITIONS

_INIT_DB_PATH = Path(init_db_mod.__file__)
_APP_DIR = _INIT_DB_PATH.resolve().parents[1]  # .../app/db/init_db.py -> .../app

# 权限点定义恒为 {"code": "x:y", "name": ...}；角色授权是裸串 "x:y"，不带 "code":，
# 故按 `"code": "..."` 扫描恰好只取「点定义」，两种表示互不污染。
_CODE_DEF = re.compile(r'"code":\s*"([a-z_]+:[a-z_]+)"')
_REQUIRE_CALL = re.compile(r"require_permission\(([^)]*)\)")
_QUOTED_CODE = re.compile(r"""["']([a-z_]+:[a-z_]+)["']""")


def _defined_codes() -> set[str]:
    """init_db.py 种子里定义的全部权限点 code（基础点 + SUPPLEMENTAL）。"""
    return set(_CODE_DEF.findall(_INIT_DB_PATH.read_text(encoding="utf-8")))


def _endpoint_permission_codes() -> set[str]:
    """静态扫描 app/ 下 require_permission("x:y", ...) 的字面量权限码。

    动态调用（require_permission(code) / require_permission(*perms)）无引号字面量，
    自然被跳过，不产生误报。
    """
    codes: set[str] = set()
    for py in _APP_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for call in _REQUIRE_CALL.finditer(text):
            codes.update(_QUOTED_CODE.findall(call.group(1)))
    return codes


class TestRbacSeedConsistency:
    def test_role_grants_reference_defined_codes(self) -> None:
        """每个系统角色矩阵引用的权限码，都必须在种子点里有定义（无悬空授权）。"""
        defined = _defined_codes()
        dangling: dict[str, list[str]] = {}
        for role in SYSTEM_ROLE_DEFINITIONS:
            missing = [c for c in role["permission_codes"] if c not in defined]
            if missing:
                dangling[role["code"]] = missing
        assert not dangling, f"角色授权了未在种子中定义的权限码: {dangling}"

    def test_endpoint_permissions_are_seeded(self) -> None:
        """每个端点 require_permission 用到的权限码，都必须在种子里建了点。"""
        missing = sorted(_endpoint_permission_codes() - _defined_codes())
        assert not missing, f"以下权限码被端点使用但 init_db 种子未建点: {missing}"

    def test_no_duplicate_permission_points(self) -> None:
        """同一权限码不应在种子里定义两次（基础点与 SUPPLEMENTAL 撞码会静默覆盖排序）。"""
        codes = _CODE_DEF.findall(_INIT_DB_PATH.read_text(encoding="utf-8"))
        dups = sorted({c for c in codes if codes.count(c) > 1})
        assert not dups, f"种子权限点重复定义: {dups}"

    def test_app_tiering_locked(self) -> None:
        """锁定本次修复：app_test / perf_test 在各角色的分级与其它测试模块一致，防回退。"""
        grants = {
            r["code"]: set(r["permission_codes"]) for r in SYSTEM_ROLE_DEFINITIONS
        }
        # admin / project_admin：两模块全量（含 delete/execute）
        for role in ("admin", "project_admin"):
            for mod in ("app_test",):
                for act in ("view", "create", "edit", "delete", "execute"):
                    assert f"{mod}:{act}" in grants[role], f"{role} 缺 {mod}:{act}"
        # tester：查看/新建/编辑/执行，不含 delete（与 test_case/api_test/web_test 一致）
        for mod in ("app_test",):
            assert (
                f"{mod}:delete" not in grants["tester"]
            ), f"tester 不应有 {mod}:delete"
            for act in ("view", "create", "edit", "execute"):
                assert f"{mod}:{act}" in grants["tester"], f"tester 缺 {mod}:{act}"
        # developer / user：只读基线（有 view，无 execute）
        for role in ("developer", "user"):
            for mod in ("app_test", "app_device"):
                assert f"{mod}:view" in grants[role], f"{role} 缺 {mod}:view"
            assert "app_test:execute" not in grants[role]
