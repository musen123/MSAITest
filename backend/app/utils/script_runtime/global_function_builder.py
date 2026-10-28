"""运行时全局函数命名空间构建器

用于把数据库中存储的"全局函数"（test_global_function 表）与代码内置的
global_function 模块函数合并成一个独立的 namespace 对象。每次用例执行时
构建一份独立 namespace，注入到脚本 exec 的 globals 里覆盖 global_function
名字，避免跨项目/跨请求污染进程级模块。
"""

import logging
from types import SimpleNamespace
from typing import Any, Iterable

from app.utils.script_runtime import global_function as builtin_module

logger = logging.getLogger(__name__)


def _collect_builtin_callables() -> dict[str, Any]:
    """收集内置 global_function 模块中的可调用对象"""
    return {
        name: obj
        for name, obj in vars(builtin_module).items()
        if callable(obj) and not name.startswith("_")
    }


def _compile_db_function(name: str, code: str) -> Any:
    """编译数据库中的函数代码，返回函数对象（失败返回 None）"""
    namespace: dict[str, Any] = {}
    try:
        from app.utils.script_runtime.script_env import build_script_globals

        exec(code, build_script_globals(), namespace)
    except Exception as e:
        logger.warning("编译数据库全局函数 %r 失败：%s", name, e)
        return None
    fn = namespace.get(name)
    if not callable(fn):
        logger.warning("数据库全局函数 %r 编译后未找到同名 callable，跳过注入", name)
        return None
    return fn


def build_runtime_global_function(db_funcs: Iterable[Any]) -> SimpleNamespace:
    """构建运行时 global_function namespace

    Args:
        db_funcs: 数据库全局函数对象的可迭代集合，每个对象需具备
            ``name`` / ``code`` / ``language`` / ``is_active`` 属性
            （ORM 对象或 dict 都支持，dict 用 .get 兜底）。

    Returns:
        SimpleNamespace: 包含内置函数 + 项目可见的数据库函数；
        命名冲突时数据库函数覆盖内置函数。
    """
    members = _collect_builtin_callables()

    for func in db_funcs or []:
        # 兼容 ORM 对象与 dict
        get = (
            (lambda k: func.get(k))
            if isinstance(func, dict)
            else (lambda k: getattr(func, k, None))
        )
        if get("language") != "python":
            continue
        if get("is_active") is False:
            continue
        name = get("name")
        code = get("code")
        if not name or not code:
            continue
        fn = _compile_db_function(name, code)
        if fn is not None:
            members[name] = fn

    return SimpleNamespace(**members)
