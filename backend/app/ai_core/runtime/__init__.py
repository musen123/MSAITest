"""AI 任务统一运行时（task-agnostic 底座）

组成：
  - events        事件协议（类型常量 + 信封构造）
  - event_bus     Redis Pub/Sub 实时通道 + 取消标志 + 运行锁
  - llm           worker 安全的用户 LLM 加载
  - context       TaskContext（节点上报 stage/progress/log/result）
  - registry      task_type -> TaskSpec 注册表
  - stream_adapter LangGraph 流 -> 标准事件（实时推送 + 落库）

该包**禁止 import fastapi / app.core.deps** 等 Web 层依赖，保证 Celery worker 可独立运行。
"""
