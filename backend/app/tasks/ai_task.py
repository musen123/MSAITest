"""统一 AI 任务 Celery 壳

所有 AI 任务共用此壳：
  task_id → registry 取 TaskSpec → 加载用户 LLM → 跑 LangGraph 图
  → StreamAdapter 扇出（实时 + 落库）→ 写终态

执行幂等（第2层）：
  - Redis 运行锁 SET NX
  - DB 原子抢占 pending→running（条件 UPDATE）
两者任一失败即视为重复执行，直接 return（Redis broker 重投兜底）。
"""

import asyncio
import time
import traceback
from celery import Task
from celery.utils.log import get_task_logger
from app.core.config import settings
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="app.tasks.ai.run", bind=True, queue="ai_tasks")
def run_ai_task(self: Task, task_id: int) -> dict:
    """统一 AI 任务入口"""
    return asyncio.run(_run_in_fresh_loop(task_id))


def queue_for_task_type(task_type: str) -> str:
    from app.ai_core.runtime.registry import get

    spec = get(task_type)
    return "app_tasks" if spec and spec.kind == "app_exec" else "ai_tasks"


def safe_dispatch(task_type: str, task_id: int):
    """按 task_type 路由队列投递统一壳；broker 不可用时返回 None。"""
    queue = queue_for_task_type(task_type)
    try:
        return run_ai_task.apply_async(args=[task_id], queue=queue)
    except Exception as exc:
        logger.warning("AI 任务投递失败 task_id=%s queue=%s: %s", task_id, queue, exc)
        return None


async def _run_in_fresh_loop(task_id: int) -> dict:
    """跑任务并在当前事件循环关闭前释放全局连接。

    prefork 下每个任务 ``asyncio.run`` 新建 loop，而 SQLAlchemy 连接池 /
    Redis 客户端是进程级全局：上个任务遗留的连接绑定旧 loop，复用必报
    "attached to a different loop" / "Event loop is closed"。
    """
    try:
        return await _run(task_id)
    except Exception as exc:
        logger.exception("AI 任务壳崩溃，启动最后兜底标记 task_id=%s", task_id)
        await _mark_failed_last_resort(task_id, exc)
        return {"status": "failed", "error": str(exc)}
    finally:
        from app.ai_core.runtime import event_bus
        from app.db.session import engine

        try:
            await engine.dispose()
        except Exception:
            logger.warning("任务收尾 engine.dispose 失败", exc_info=True)
        try:
            await event_bus.close_redis()
        except Exception:
            logger.warning("任务收尾 close_redis 失败", exc_info=True)


async def _mark_failed_last_resort(task_id: int, exc: Exception) -> None:
    """用全新连接把任务标记为 failed 并广播 task_end（不覆盖已终态）。

    先丢弃可能已损坏的全局连接池/Redis 客户端，再重建干净连接执行。
    """
    from app.ai_core.runtime import event_bus
    from app.ai_core.runtime.events import EventType, make_event, task_end_payload
    from app.crud.ai.ai_task import crud_ai_task
    from app.db.session import async_session_maker, engine

    try:
        await engine.dispose()
    except Exception:
        pass
    try:
        await event_bus.close_redis()
    except Exception:
        pass
    try:
        async with async_session_maker() as db:
            updated = await crud_ai_task.fail_if_active(
                db, task_id=task_id, error_message=f"任务执行异常（壳级兜底）：{exc}"
            )
        if updated:
            await event_bus.publish(
                task_id,
                make_event(
                    999999, EventType.TASK_END.value, task_end_payload("failed", 0)
                ),
            )
            logger.warning("AI 任务 %s 已由兜底逻辑标记为 failed", task_id)
    except Exception:
        logger.exception("AI 任务 %s 兜底标记失败（将依赖僵尸回收）", task_id)


async def _run(task_id: int) -> dict:
    from app.ai_core.runtime import event_bus
    from app.ai_core.runtime.context import TaskContext
    from app.ai_core.runtime.events import (
        EventType,
        error_payload,
        make_event,
        result_payload,
        task_end_payload,
        task_start_payload,
    )
    from app.ai_core.runtime.llm import load_user_llms
    from app.ai_core.runtime.registry import get as get_spec
    from app.ai_core.runtime.stream_adapter import StreamAdapter, TaskCanceled
    from app.crud.ai.ai_task import crud_ai_task
    from app.db.session import async_session_maker

    start_ts = time.monotonic()
    got_lock = False
    async with async_session_maker() as db:
        task = await crud_ai_task.get(db, task_id)
        if task is None:
            logger.warning("AI 任务不存在：%s", task_id)
            return {"status": "missing"}
        spec = get_spec(task.task_type)
        if spec is None:
            await crud_ai_task.set_failed(
                db, task_id=task_id, error_message=f"未注册的任务类型：{task.task_type}"
            )
            return {"status": "failed", "reason": "unknown_type"}
        got_lock = await event_bus.acquire_run_lock(
            task_id, ttl=settings.AI_TASK_RUN_LOCK_TTL
        )
        if not got_lock:
            logger.info(
                "AI 任务 %s 已被其它 worker 持有运行锁，跳过（重投兜底）", task_id
            )
            return {"status": "duplicate"}
        claimed = await crud_ai_task.try_claim_running(db, task_id=task_id)
        if not claimed:
            logger.info("AI 任务 %s 非 pending（已抢占/完成），跳过", task_id)
            await event_bus.release_run_lock(task_id)
            return {"status": "duplicate"}
        params = task.input_params or {}
        project_id = task.project_id
        user_id = task.created_by
        ctx = TaskContext(task_id=task_id, project_id=project_id, user_id=user_id)
        adapter = StreamAdapter(
            db=db,
            task_id=task_id,
            ctx=ctx,
            flush_ms=settings.AI_TASK_EVENT_FLUSH_MS,
            stream_messages=spec.stream_messages,
            adapter_cancel=spec.adapter_cancel,
        )
        hb_task = asyncio.create_task(
            _heartbeat_loop(task_id, settings.AI_TASK_HEARTBEAT_S)
        )
        try:
            model_name = await load_user_llms(user_id, kind=spec.llm_kind)
            if model_name:
                await crud_ai_task.update_progress(db, task_id=task_id, heartbeat=True)
                task.ai_model = model_name
                db.add(task)
                await db.commit()
            await event_bus.publish(
                task_id,
                make_event(
                    0,
                    EventType.TASK_START.value,
                    task_start_payload(task.task_type, task.title, task.total_stages),
                ),
            )
            graph = spec.build_graph(params, ctx)
            graph_input = spec.build_input(params)
            await adapter.consume(graph, graph_input)
            summary = ctx.result_summary or adapter.result_summary
            ref = ctx.result_ref or adapter.result_ref
            if summary is None and ref is None and spec.extract_result:
                summary, ref = spec.extract_result(adapter.final_state or {})
            await crud_ai_task.set_succeeded(
                db, task_id=task_id, result_summary=summary, result_ref=ref
            )
            await _emit_end(
                event_bus,
                adapter,
                task_id,
                "succeeded",
                start_ts,
                make_event,
                task_end_payload,
                result_event=(EventType.RESULT.value, result_payload(summary, ref)),
            )
            return {"status": "succeeded"}
        except TaskCanceled:
            await crud_ai_task.set_canceled(db, task_id=task_id)
            await _emit_end(
                event_bus,
                adapter,
                task_id,
                "canceled",
                start_ts,
                make_event,
                task_end_payload,
            )
            return {"status": "canceled"}
        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("AI 任务执行失败 task_id=%s", task_id)
            await crud_ai_task.set_failed(db, task_id=task_id, error_message=str(exc))
            try:
                await adapter.flush()
                await adapter.emit(
                    EventType.ERROR.value, error_payload(str(exc), tb[-2000:])
                )
                await adapter.flush()
            except Exception:
                pass
            await _emit_end(
                event_bus,
                adapter,
                task_id,
                "failed",
                start_ts,
                make_event,
                task_end_payload,
            )
            return {"status": "failed", "error": str(exc)}
        finally:
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass
            if got_lock:
                await event_bus.release_run_lock(task_id)
            await event_bus.clear_cancel(task_id)


async def _heartbeat_loop(task_id: int, interval: int) -> None:
    """周期性更新 ai_task.heartbeat_at（独立 DB 会话）。"""
    from app.crud.ai.ai_task import crud_ai_task
    from app.db.session import async_session_maker

    try:
        while True:
            await asyncio.sleep(interval)
            try:
                async with async_session_maker() as hb_db:
                    await crud_ai_task.heartbeat(hb_db, task_id=task_id)
            except Exception:
                pass
    except asyncio.CancelledError:
        return


async def _emit_end(
    event_bus,
    adapter,
    task_id,
    status,
    start_ts,
    make_event,
    task_end_payload,
    *,
    result_event=None,
):
    """收尾：落库剩余事件 +（可选）result 事件 + task_end 哨兵（落库 + 实时推送）。

    result 事件必须先于 task_end 推送/落库——前端在 task_end 收流，晚到即丢。
    """
    from app.ai_core.runtime.events import EventType
    from app.crud.ai.ai_task import crud_ai_task

    await adapter.flush()
    duration_ms = int((time.monotonic() - start_ts) * 1000)
    tail_events = []
    if result_event is not None:
        adapter.seq += 1
        tail_events.append(make_event(adapter.seq, result_event[0], result_event[1]))
    adapter.seq += 1
    tail_events.append(
        make_event(
            adapter.seq, EventType.TASK_END.value, task_end_payload(status, duration_ms)
        )
    )
    await crud_ai_task.append_events(
        adapter.db,
        task_id=task_id,
        events=[
            {"seq": e["seq"], "type": e["type"], "payload": e["payload"]}
            for e in tail_events
        ],
    )
    for e in tail_events:
        await event_bus.publish(task_id, e)
