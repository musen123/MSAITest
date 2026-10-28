"""定时计划核心逻辑

- compute_next_run：cron 按本地时区（settings.TIMEZONE）语义解析，
  next_run_at 统一换算为 UTC naive 落库（与全库时间口径一致）。
- fire_job：创建 ai_task 并投递（dispatch 巡检与 run-now 共用）。
  防重叠：上次派发的任务仍在 pending/running 时跳过本次。
- 错过即跳过：next_run 始终从「当前时间」起算，服务停摆期间
  错过的运行不补跑，避免重启风暴。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo
from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.crud.ai.ai_task import crud_ai_task
from app.crud.scheduler.scheduled_job import crud_scheduled_job
from app.models.scheduler.scheduled_job import ScheduledJob

logger = logging.getLogger(__name__)
JOB_TYPE_MAP: dict[str, tuple[str, str]] = {"app_suite": ("run_app_suite", "suite_id")}
JOB_TYPE_LABELS = {"app_suite": "App 套件"}


def validate_cron(expr: str) -> bool:
    return croniter.is_valid(expr)


def compute_next_run(
    *,
    schedule_type: str,
    cron_expr: Optional[str],
    interval_seconds: Optional[int],
    base_utc: Optional[datetime] = None,
) -> Optional[datetime]:
    """计算下一次运行时间（UTC naive）。

    cron 模式按本地时区语义解析（「每天 2 点」= 本地 2 点）；
    interval 模式从 base 顺延固定秒数。
    """
    base = base_utc or datetime.utcnow()
    if schedule_type == "interval":
        if not interval_seconds or interval_seconds < 60:
            return None
        return base + timedelta(seconds=interval_seconds)
    if not cron_expr or not croniter.is_valid(cron_expr):
        return None
    tz = ZoneInfo(settings.TIMEZONE)
    base_local = base.replace(tzinfo=timezone.utc).astimezone(tz)
    next_local = croniter(cron_expr, base_local).get_next(datetime)
    return next_local.astimezone(timezone.utc).replace(tzinfo=None)


def preview_cron(expr: str, count: int = 3) -> list[str]:
    """未来 count 次运行的本地时间（前端预览）"""
    if not croniter.is_valid(expr):
        return []
    tz = ZoneInfo(settings.TIMEZONE)
    it = croniter(expr, datetime.now(tz))
    result = []
    for _ in range(count):
        nxt = it.get_next(datetime)
        result.append(nxt.strftime("%Y-%m-%d %H:%M"))
    return result


async def resolve_target_name(
    db: AsyncSession, *, job_type: str, target_id: int, project_id: int
) -> Optional[str]:
    if job_type != "app_suite":
        return None
    from app.crud.app_test import crud_app_suite

    suite = await crud_app_suite.get_in_project(db, project_id, target_id)
    return suite.name if suite else None


def _build_input_params(
    job: ScheduledJob, *, target_name: Optional[str]
) -> dict[str, Any]:
    params = dict(job.params or {})
    return {
        "suite_id": job.target_id,
        "device_udid": params.get("device_udid"),
        "suite_name": target_name,
        "trigger_type": "scheduled",
        "scheduled_job_id": job.id,
    }


async def fire_job(
    db: AsyncSession, *, job: ScheduledJob, manual: bool = False
) -> dict[str, Any]:
    """派发一次定时计划：防重叠检查 → 创建 ai_task → 投递。

    返回 {status, ai_task_id?, note?}；
    status: dispatched / skipped_overlap / failed
    """
    from app.ai_core.runtime import event_bus

    fired_at = datetime.utcnow()
    note_prefix = "手动触发" if manual else "定时触发"
    task_type, _ = JOB_TYPE_MAP[job.job_type]
    lock_key = f"sched-fire:{job.id}"
    if not await event_bus.acquire_submit_lock(lock_key):
        note = "该计划正在派发中，本次跳过"
        await crud_scheduled_job.mark_fired(
            db, job_id=job.id, fired_at=fired_at, status="skipped_overlap", note=note
        )
        return {"status": "skipped_overlap", "note": note}
    try:
        return await _fire_job_locked(
            db, job=job, task_type=task_type, fired_at=fired_at, note_prefix=note_prefix
        )
    finally:
        await event_bus.release_submit_lock(lock_key)


async def _fire_job_locked(
    db: AsyncSession,
    *,
    job: ScheduledJob,
    task_type: str,
    fired_at: datetime,
    note_prefix: str,
) -> dict[str, Any]:
    from app.tasks.ai_task import safe_dispatch

    if not job.allow_overlap:
        active = await crud_ai_task.find_active(
            db, project_id=job.project_id, task_type=task_type, biz_ref_id=job.target_id
        )
        last = (
            await crud_ai_task.get(db, job.last_task_id) if job.last_task_id else None
        )
        running = active or (
            last if last and last.status in ("pending", "running") else None
        )
        if running:
            note = f"上次执行未完成（task_id={running.id}），本次跳过"
            await crud_scheduled_job.mark_fired(
                db,
                job_id=job.id,
                fired_at=fired_at,
                status="skipped_overlap",
                note=note,
            )
            return {"status": "skipped_overlap", "note": note}
    target_name = await resolve_target_name(
        db, job_type=job.job_type, target_id=job.target_id, project_id=job.project_id
    )
    if target_name is None:
        note = f"{JOB_TYPE_LABELS.get(job.job_type, job.job_type)} #{job.target_id} 不存在或已删除"
        await crud_scheduled_job.mark_fired(
            db, job_id=job.id, fired_at=fired_at, status="failed", note=note
        )
        return {"status": "failed", "note": note}
    task = await crud_ai_task.create(
        db,
        project_id=job.project_id,
        created_by=job.created_by,
        task_type=task_type,
        title=f"{note_prefix}：{target_name}",
        input_params=_build_input_params(job, target_name=target_name),
        biz_ref_type=job.job_type,
        biz_ref_id=job.target_id,
    )
    await db.commit()
    async_result = safe_dispatch(task_type, task.id)
    if async_result is None:
        await crud_ai_task.set_failed(
            db, task_id=task.id, error_message="任务投递失败（broker 不可用）"
        )
        await crud_scheduled_job.mark_fired(
            db,
            job_id=job.id,
            fired_at=fired_at,
            status="failed",
            ai_task_id=task.id,
            note="投递失败（broker 不可用）",
        )
        return {
            "status": "failed",
            "ai_task_id": task.id,
            "note": "投递失败（broker 不可用）",
        }
    try:
        await crud_ai_task.set_celery_task_id(
            db, task_id=task.id, celery_task_id=async_result.id
        )
        await crud_scheduled_job.mark_fired(
            db,
            job_id=job.id,
            fired_at=fired_at,
            status="dispatched",
            ai_task_id=task.id,
            note=note_prefix,
        )
    except Exception:
        logger.warning(
            "定时计划 %d 派发后簿记失败（任务已投递 ai_task=%d）",
            job.id,
            task.id,
            exc_info=True,
        )
    logger.info("定时计划 %d 已派发：%s ai_task=%d", job.id, task_type, task.id)
    return {"status": "dispatched", "ai_task_id": task.id}


async def dispatch_due_jobs(db: AsyncSession) -> dict[str, int]:
    """巡检派发所有到期计划（beat → celery 任务调用）"""
    now = datetime.utcnow()
    due = await crud_scheduled_job.list_due(db, now=now)
    dispatched = skipped = failed = 0
    for job in due:
        expected = job.next_run_at
        new_next = compute_next_run(
            schedule_type=job.schedule_type,
            cron_expr=job.cron_expr,
            interval_seconds=job.interval_seconds,
            base_utc=now,
        )
        if expected is None or not await crud_scheduled_job.claim(
            db, job_id=job.id, expected_next=expected, new_next=new_next
        ):
            continue
        try:
            result = await fire_job(db, job=job)
        except Exception as exc:
            logger.exception("定时计划 %d 派发异常", job.id)
            try:
                await crud_scheduled_job.mark_fired(
                    db,
                    job_id=job.id,
                    fired_at=now,
                    status="failed",
                    note=f"派发异常：{exc}"[:200],
                )
            except Exception:
                pass
            failed += 1
            continue
        if result["status"] == "dispatched":
            dispatched += 1
        elif result["status"] == "skipped_overlap":
            skipped += 1
        else:
            failed += 1
    return {
        "due": len(due),
        "dispatched": dispatched,
        "skipped": skipped,
        "failed": failed,
    }
