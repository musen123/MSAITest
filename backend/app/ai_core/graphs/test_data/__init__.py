"""测试数据中心 AI 造数图（导入即注册 TaskSpec）"""

from app.ai_core.graphs.test_data import generate_dataset  # noqa: F401
from app.ai_core.graphs.test_data import generate_test_files  # noqa: F401

__all__ = ["generate_dataset", "generate_test_files"]
