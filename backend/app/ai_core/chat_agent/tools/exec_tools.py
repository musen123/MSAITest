"""执行操作类工具（产生真实测试执行，调用前须确认用户意图明确）

全部复用平台执行端点的六步提交模式（base.submit_unified_task）：
提交锁 → 活跃任务去重 → 预创建执行记录 → 建统一任务 → 投递 → 失败补偿。
派发成功后返回任务中心动作卡片。
"""

from typing import Optional
from langchain.tools import tool
from app.ai_core.chat_agent.tools.base import (
    check_environment,
    ctx_ids,
    submit_unified_task,
    task_action,
    tool_error,
    tool_json,
)
from app.db.session import async_session_maker


@tool(
    "run_scheduled_job",
    description="立即触发一次定时任务计划（不影响其调度周期）。参数：job_id（计划 ID，可用 query_scheduled_jobs 查询）。",
)
async def run_scheduled_job(job_id: int) -> str:
    from app.crud.scheduler.scheduled_job import crud_scheduled_job
    from app.services.scheduler.scheduled_job_service import fire_job

    project_id, _ = ctx_ids()
    async with async_session_maker() as db:
        job = await crud_scheduled_job.get(db, job_id)
        if not job or job.project_id != project_id:
            return tool_error(f"定时计划不存在：{job_id}")
        result = await fire_job(db, job=job, manual=True)
    status = result.get("status")
    if status == "dispatched":
        return tool_json(
            {
                "dispatched": True,
                "job_name": job.name,
                "ai_task_id": result["ai_task_id"],
                "message": "已触发执行",
            },
            action=task_action(result["ai_task_id"], "查看执行进度"),
        )
    if status == "skipped_overlap":
        return tool_error(f"已跳过：{result.get('note') or '上次执行未完成'}")
    return tool_error(f"触发失败：{result.get('note') or '未知原因'}")


@tool(
    "toggle_scheduled_job",
    description="启用或停用一个定时任务计划。参数：job_id（计划 ID）、enabled（true=启用 / false=停用）。",
)
async def toggle_scheduled_job(job_id: int, enabled: bool) -> str:
    from app.crud.scheduler.scheduled_job import crud_scheduled_job
    from app.services.scheduler.scheduled_job_service import compute_next_run

    project_id, _ = ctx_ids()
    async with async_session_maker() as db:
        job = await crud_scheduled_job.get(db, job_id)
        if not job or job.project_id != project_id:
            return tool_error(f"定时计划不存在：{job_id}")
        job = await crud_scheduled_job.update_fields(
            db,
            job=job,
            enabled=bool(enabled),
            next_run_at=(
                compute_next_run(
                    schedule_type=job.schedule_type,
                    cron_expr=job.cron_expr,
                    interval_seconds=job.interval_seconds,
                )
                if enabled
                else None
            ),
        )
    return tool_json(
        {
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "next_run_at_utc": job.next_run_at,
            "message": "已启用" if enabled else "已停用",
        }
    )
