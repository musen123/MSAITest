"""统一 AI 任务运维 Celery 任务（beat 周期调度）

  reap_zombies    僵尸任务巡检：无人观看也能把死任务标记为 failed
  archive_events  事件流归档：终态超过保留期的任务，事件导出 jsonl.gz 后删 DB 行

两者均遵循 prefork 事件循环纪律：每次执行 ``asyncio.run`` 新建 loop，
收尾必须 dispose 全局连接池 / 关闭 Redis 客户端（见 ai_task.py 同款处理）。
"""

import asyncio
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from celery.utils.log import get_task_logger
from app.core.config import settings
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


async def _dispose_globals() -> None:
    from app.ai_core.runtime import event_bus
    from app.db.session import engine

    try:
        await engine.dispose()
    except Exception:
        logger.warning("运维任务收尾 engine.dispose 失败", exc_info=True)
    try:
        await event_bus.close_redis()
    except Exception:
        logger.warning("运维任务收尾 close_redis 失败", exc_info=True)


_REAP_CANCEL_KINDS = frozenset({"app_exec"})


@celery_app.task(name="app.tasks.ai.reap_zombies", queue="ai_tasks")
def reap_zombies() -> dict:
    """周期巡检：把心跳超时的 running / 排队超时的 pending 标记为 failed。

    提交去重与 SSE 轮询里已有被动回收，但都依赖「有人来看/来提交」；
    本任务兜住无人观看的死任务，避免其永远占着活跃状态挡住后续提交。
    """

    async def _reap() -> dict:
        from app.ai_core.runtime import event_bus, registry
        from app.ai_core.runtime.events import EventType, make_event, task_end_payload
        from app.crud.ai.ai_task import crud_ai_task
        from app.db.session import async_session_maker

        reaped: list[int] = []
        async with async_session_maker() as db:
            zombies = await crud_ai_task.list_zombies(
                db,
                running_timeout_s=settings.AI_TASK_ZOMBIE_TIMEOUT_S,
                pending_timeout_s=settings.AI_TASK_PENDING_ZOMBIE_S,
            )
            for task in zombies:
                timeout = (
                    settings.AI_TASK_PENDING_ZOMBIE_S
                    if task.status == "pending"
                    else settings.AI_TASK_ZOMBIE_TIMEOUT_S
                )
                if await crud_ai_task.fail_if_zombie(db, task=task, timeout_s=timeout):
                    reaped.append(task.id)
                    try:
                        from app.services.ai_task_finalize import finalize_biz_records

                        await finalize_biz_records(db, task, canceled=False)
                    except Exception:
                        logger.warning(
                            "僵尸任务 %s 业务记录收尾失败", task.id, exc_info=True
                        )
                    spec = registry.get(task.task_type)
                    if spec and spec.kind in _REAP_CANCEL_KINDS:
                        try:
                            await event_bus.request_cancel(task.id)
                        except Exception:
                            pass
                    try:
                        await event_bus.publish(
                            task.id,
                            make_event(
                                999999,
                                EventType.TASK_END.value,
                                task_end_payload("failed", 0),
                            ),
                        )
                    except Exception:
                        pass
        if reaped:
            logger.warning("僵尸巡检：已回收 %s 个死任务 %s", len(reaped), reaped)
        return {"reaped": reaped}

    async def _main() -> dict:
        try:
            return await _reap()
        finally:
            await _dispose_globals()

    return asyncio.run(_main())


@celery_app.task(name="app.tasks.ai.archive_events", queue="ai_tasks")
def archive_events() -> dict:
    """把终态超过保留期的任务事件导出为 jsonl.gz 后从 DB 删除（内容零丢失）。

    归档文件：{AI_TASK_ARCHIVE_DIR}/{YYYY-MM}/task_{id}.jsonl.gz
    （按任务 completed_at 月份分目录）。任务主表不动——状态、result_summary、
    result_ref 仍在，任务中心列表与结果展示不受影响，仅历史回放不再可用。
    """

    async def _archive() -> dict:
        from app.crud.ai.ai_task import crud_ai_task
        from app.db.session import async_session_maker

        if settings.AI_TASK_EVENT_RETENTION_DAYS <= 0:
            return {"archived": 0, "skipped": "retention disabled"}
        before = datetime.now() - timedelta(days=settings.AI_TASK_EVENT_RETENTION_DAYS)
        base_dir = Path(settings.AI_TASK_ARCHIVE_DIR)
        archived: list[int] = []
        deleted_rows = 0
        async with async_session_maker() as db:
            task_ids = await crud_ai_task.list_archivable_task_ids(
                db, before=before, limit=settings.AI_TASK_ARCHIVE_BATCH
            )
            for task_id in task_ids:
                task = await crud_ai_task.get(db, task_id)
                events = await crud_ai_task.list_events(db, task_id=task_id)
                if task is None or not events:
                    continue
                month = (task.completed_at or datetime.now()).strftime("%Y-%m")
                out_dir = base_dir / month
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"task_{task_id}.jsonl.gz"
                try:
                    with gzip.open(out_file, "wt", encoding="utf-8") as f:
                        for ev in events:
                            f.write(
                                json.dumps(
                                    {
                                        "seq": ev.seq,
                                        "type": ev.event_type,
                                        "payload": ev.payload,
                                        "created_at": (
                                            ev.created_at.isoformat()
                                            if ev.created_at
                                            else None
                                        ),
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                except Exception:
                    logger.exception("任务 %s 事件导出失败，跳过", task_id)
                    try:
                        out_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
                deleted_rows += await crud_ai_task.delete_events(db, task_id=task_id)
                archived.append(task_id)
        if archived:
            logger.info(
                "事件归档：%s 个任务、%s 行事件已导出至 %s",
                len(archived),
                deleted_rows,
                base_dir,
            )
        return {"archived": len(archived), "deleted_rows": deleted_rows}

    async def _main() -> dict:
        try:
            return await _archive()
        finally:
            await _dispose_globals()

    return asyncio.run(_main())
