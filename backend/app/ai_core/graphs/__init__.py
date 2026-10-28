"""AI 任务 LangGraph 图集合（按域分组）

导入本包即完成所有 task_type 的 registry 注册（worker 启动时加载）。
新增任务：在对应 graphs/<域>/ 写图 + register(TaskSpec)，并在此 import。
"""

from app.ai_core.graphs import demo
from app.ai_core.graphs import func_test
from app.ai_core.graphs import app_test
from app.ai_core.graphs import knowledge
from app.ai_core.graphs import test_data

__all__ = ["demo", "func_test", "app_test", "knowledge", "test_data"]
