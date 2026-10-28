"""APP 自动化任务图（回放执行 / 探索式生成 / 套件批量执行）"""

from app.ai_core.graphs.app_test import (  # noqa: F401
    explore_app_script,
    run_app_script,
    run_app_suite,
)

__all__ = ["explore_app_script", "run_app_script", "run_app_suite"]
