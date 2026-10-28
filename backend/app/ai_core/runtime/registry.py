"""task_type -> TaskSpec 注册表

新增一个 AI 任务 = 写一张 LangGraph 图 + 在此注册一个 TaskSpec。
统一 Celery 壳据此构图、构入参、跑流、抽结果。

注册集中在 ``app.ai_core.graphs`` 包的导入副作用中完成（worker 启动时加载）。
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.ai_core.runtime.context import TaskContext

# build_graph(params, ctx) -> 已 compile 的 langgraph 图（具备 .astream）
BuildGraph = Callable[[dict, TaskContext], Any]
# build_input(params) -> 图初始 state
BuildInput = Callable[[dict], dict]
# title(params) -> 任务展示名
TitleFn = Callable[[dict], str]
# extract_result(final_state) -> (summary, ref)
ExtractResult = Callable[[dict], tuple[Optional[dict], Optional[dict]]]


@dataclass
class TaskSpec:
    task_type: str
    build_graph: BuildGraph
    build_input: BuildInput
    title: TitleFn
    llm_kind: str = "text"  # text | vision | both
    extract_result: Optional[ExtractResult] = None
    # 任务类别：ai（生成/解析）| exec（用例执行）。
    # exec 类投递到 test_tasks 队列，与 AI 生成任务隔离并发；
    # 任务中心按此拆分「AI 任务 / 执行任务」视图。
    kind: str = "ai"
    # 该类型默认是否做提交去重（按 biz_ref）
    dedupe: bool = True
    # 是否订阅 LangGraph messages 模式（LLM token 流 → message_delta）。
    # 节点内手动驱动子 agent（如 deepagents）的图应设 False：内部 LLM token
    # 与工具消息会经 callback 冒泡成海量 message_delta，与图自身 custom 通道
    # 转发的完整思考段重复。
    stream_messages: bool = True
    # 是否启用 StreamAdapter 的事件计数取消检查（抛 TaskCanceled 硬中断图）。
    # 自带协作式取消的图（如 run_web_suite 每用例边界检查）应设 False：
    # adapter 硬中断会跳过图内的记录收尾，留下卡 running 的业务记录。
    adapter_cancel: bool = True


_REGISTRY: dict[str, TaskSpec] = {}


def register(spec: TaskSpec) -> None:
    _REGISTRY[spec.task_type] = spec


def get(task_type: str) -> Optional[TaskSpec]:
    return _REGISTRY.get(task_type)


def has(task_type: str) -> bool:
    return task_type in _REGISTRY


def all_types() -> list[str]:
    return list(_REGISTRY.keys())


def exec_task_types() -> frozenset[str]:
    """执行类任务的 task_type 集合（任务中心「执行监控」视图拆分 / 小测查询共用）。

    涵盖三种执行 kind：exec（Web/接口回放）、app_exec（App 回放，独立 app_tasks 队列）、
    load（压测执行，独立 load_tasks 队列）——语义上都是「用例/套件/任务执行」，在任务中心
    统一归入「执行监控」视图（与「AI 任务」相对）。
    注：仅用于视图/查询归类，**不参与队列路由**（路由见 queue_for_task_type）。
    """
    return frozenset(t for t, spec in _REGISTRY.items() if spec.kind in ("app_exec",))
