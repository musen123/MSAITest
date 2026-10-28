"""功能测试域 AI 任务图

导入即注册各 task_type 的 TaskSpec。
"""

from app.ai_core.graphs.func_test import extract_requirements  # noqa: F401
from app.ai_core.graphs.func_test import generate_case  # noqa: F401
from app.ai_core.graphs.func_test import parse_document  # noqa: F401
from app.ai_core.graphs.func_test import review_cases  # noqa: F401
from app.ai_core.graphs.func_test import understand_requirement  # noqa: F401

__all__ = [
    "parse_document",
    "generate_case",
    "understand_requirement",
    "extract_requirements",
    "review_cases",
]
