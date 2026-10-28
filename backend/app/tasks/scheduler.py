"""定时任务派发巡检（beat 周期任务）

beat 每 SCHEDULED_JOB_DISPATCH_INTERVAL_S 秒触发一次，扫描
sys_scheduled_job 中到期的计划并派发（核心逻辑在
scheduled_job_service.dispatch_due_jobs：原子抢占 + 防重叠 + 错过跳过）。
"""

import asyncio

from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="app.tasks.ai.dispatch_scheduled_jobs")
def dispatch_scheduled_jobs() -> dict:
    """扫描并派发到期的定时计划"""

    async def _main() -> dict:
        # prefork 纪律：asyncio.run 退出前必须 dispose 全局连接，
        # 否则归还进池的连接绑定已关闭的 loop，污染后续任务
        from app.tasks.ai_maintenance import _dispose_globals

        try:
            return await _dispatch()
        finally:
            await _dispose_globals()

    return asyncio.run(_main())


async def _dispatch() -> dict:
    from app.db.session import async_session_maker
    from app.services.scheduler.scheduled_job_service import (
        dispatch_due_jobs,
    )

    async with async_session_maker() as db:
        result = await dispatch_due_jobs(db)
    if result["due"]:
        logger.info(
            "定时派发：到期 %d，派发 %d，跳过 %d，失败 %d",
            result["due"],
            result["dispatched"],
            result["skipped"],
            result["failed"],
        )
    return result
