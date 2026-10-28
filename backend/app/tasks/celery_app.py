"""
Celery 应用实例

创建和配置 Celery 应用
"""

import logging
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

logger = logging.getLogger(__name__)
celery_app = Celery(
    "ai_test_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,
    enable_utc=True,
    result_expires=3600,
    task_time_limit=300,
    task_soft_time_limit=280,
    task_routes={"app.tasks.ai.*": {"queue": "ai_tasks"}},
    worker_direct=True,
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=20,
    worker_max_memory_per_child=1500000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_transport_options={
        "visibility_timeout": settings.AI_TASK_VISIBILITY_TIMEOUT
    },
    result_backend_transport_options={
        "visibility_timeout": settings.AI_TASK_VISIBILITY_TIMEOUT
    },
)
celery_app.conf.task_annotations = {
    "app.tasks.ai.run": {
        "time_limit": settings.AI_TASK_TIME_LIMIT,
        "soft_time_limit": settings.AI_TASK_SOFT_TIME_LIMIT,
    }
}
celery_app.conf.beat_schedule = {
    "reap-zombie-ai-tasks": {
        "task": "app.tasks.ai.reap_zombies",
        "schedule": settings.AI_TASK_REAP_INTERVAL_S,
    },
    "archive-ai-task-events": {
        "task": "app.tasks.ai.archive_events",
        "schedule": crontab(hour=3, minute=0),
    },
    "dispatch-scheduled-jobs": {
        "task": "app.tasks.ai.dispatch_scheduled_jobs",
        "schedule": settings.SCHEDULED_JOB_DISPATCH_INTERVAL_S,
    },
}
celery_app.autodiscover_tasks(["app.tasks"])
from celery.signals import worker_process_init


@worker_process_init.connect
def _reseed_rng_per_fork(**_kwargs):
    import os
    import random as _random

    _random.seed(os.urandom(16))
    try:
        from app.utils.script_runtime.global_function import fk

        fk.seed_instance(int.from_bytes(os.urandom(8), "big"))
    except Exception:
        pass


import app.models
import app.tasks.ai_task
import app.tasks.ai_maintenance
import app.tasks.scheduler
import app.ai_core.graphs


@celery_app.task(name="health_check")
def health_check_task() -> dict:
    """
    健康检查任务

    Returns:
        dict: 健康状态
    """
    return {"status": "ok"}


def safe_delay(task, *args, **kwargs):
    """安全调用 Celery 任务的 delay 方法，失败时仅打日志不抛异常。"""
    try:
        return task.delay(*args, **kwargs)
    except Exception as exc:
        logger.warning("Celery 任务 %s 调用失败: %s", getattr(task, "name", task), exc)
