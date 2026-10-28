"""统一 AI 任务 API

前缀：/projects/{project_id}/ai-tasks

  POST   ""              提交任务（含第1层提交去重）
  GET    ""              任务列表
  GET    "/stats"        状态统计（任务中心统计卡）
  GET    "/{id}"         任务详情（主表 + 已落库事件）
  GET    "/{id}/stream"  SSE：回放历史事件 + 订阅实时事件
  POST   "/{id}/cancel"  取消
  POST   "/{id}/retry"   用原参数重新提交
"""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.runtime import event_bus
from app.ai_core.runtime import registry
from app.core import deps
from app.core.config import settings
from app.core.response import ResponseModel, success_response
from app.crud.ai.ai_task import crud_ai_task
from app.db.session import async_session_maker
from app.models.ai.ai_task import AiTaskStatus
from app.models.auth.user import User
from app.schemas.ai.ai_task import (
    AiTaskCreate,
    AiTaskDetailResponse,
    AiTaskEventResponse,
    AiTaskListResponse,
    AiTaskResponse,
    AiTaskStatsResponse,
)
from app.tasks.ai_task import safe_dispatch
from app.utils.project_permission import require_project_access

# 导入图集合，完成 registry 注册（web 侧 submit 校验/标题需要）
import app.ai_core.graphs  # noqa: E402, F401

router = APIRouter()

TERMINAL = {
    AiTaskStatus.SUCCEEDED.value,
    AiTaskStatus.FAILED.value,
    AiTaskStatus.CANCELED.value,
}


@router.post(
    "",
    summary="提交 AI 任务",
    response_model=ResponseModel[AiTaskResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_task(
    project_id: int,
    body: AiTaskCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:manage"))
    ],
) -> ResponseModel[AiTaskResponse]:
    await require_project_access(db, project_id, current_user.id)

    spec = registry.get(body.task_type)
    if spec is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"未注册的任务类型：{body.task_type}",
        )

    # TODO(安全/纵深防御): body.params 是自由 dict，未在端点层校验其中
    # 携带的资源 ID（web_task_id / api_task_id / case_id / interface_id /
    # document_id / suite_id / environment_id ...）是否归属当前 project_id。
    # 各 task_type 的 params 键不同，spec 体系目前未声明「哪些键是本项目资源」，
    # 端点无法统一比对。现阶段依赖图层防御：各 graph 的 build_input/run_core
    # 均以 ctx.project_id 重取记录并比对归属（见 run_api_task / run_web_task），
    # 跨项目 ID 在执行期会 404/认领失败。彻底修复需给 TaskSpec 增加
    # params 资源校验钩子（validate_params(db, project_id, params)），属较大改动，
    # 单列后续处理，不在本次访问控制修复范围内。

    # ── 第1层提交去重 ──
    submit_lock_key: Optional[str] = None
    if spec.dedupe:
        submit_lock_key = f"{project_id}:{body.task_type}:{body.biz_ref_id}"
        await event_bus.acquire_submit_lock(submit_lock_key)
        try:
            # App 类任务带 device_udid：去重细化到 (biz_ref, 设备)，与专用提交
            # 端点（scripts/suites run）语义一致；其它任务类型无此键 → 行为不变
            _dedupe_udid = (body.params or {}).get("device_udid")
            existing = await crud_ai_task.find_active(
                db,
                project_id=project_id,
                task_type=body.task_type,
                biz_ref_id=body.biz_ref_id,
                device_udid=_dedupe_udid if isinstance(_dedupe_udid, str) else None,
            )
            if existing is not None:
                # 僵尸判定：pending 排队超时 / running 心跳超时 → 就地回收，放行新提交。
                # 防止 worker 崩溃遗留的假活跃任务永久挡住重新提交（前端「排队中」假状态）
                revived = await crud_ai_task.fail_if_zombie(
                    db, task=existing, timeout_s=settings.AI_TASK_ZOMBIE_TIMEOUT_S
                )
                if not revived:
                    return success_response(
                        data=AiTaskResponse.model_validate(existing),
                        message="已存在进行中的同类任务",
                    )
                # 回收成功：僵尸任务预创建的业务执行记录一并收尾
                from app.services.ai_task_finalize import finalize_biz_records

                await finalize_biz_records(db, existing, canceled=False)
        finally:
            await event_bus.release_submit_lock(submit_lock_key)

    title = body.title or spec.title(body.params)
    task = await crud_ai_task.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        task_type=body.task_type,
        title=title,
        biz_ref_type=body.biz_ref_type,
        biz_ref_id=body.biz_ref_id,
        input_params=body.params,
    )

    async_result = safe_dispatch(task.task_type, task.id)
    if async_result is not None:
        await crud_ai_task.set_celery_task_id(
            db, task_id=task.id, celery_task_id=async_result.id
        )
        await db.refresh(task)

    return success_response(
        data=AiTaskResponse.model_validate(task), message="任务已提交"
    )


@router.get(
    "",
    summary="获取 AI 任务列表",
    response_model=ResponseModel[AiTaskListResponse],
)
async def list_tasks(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:view"))
    ],
    task_type: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(
        default=None, description="任务类别：ai（生成）/ exec（执行）"
    ),
    status_: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[AiTaskListResponse]:
    await require_project_access(db, project_id, current_user.id)

    from app.ai_core.runtime.registry import exec_task_types

    items, total = await crud_ai_task.list_by_project(
        db,
        project_id=project_id,
        task_type=task_type,
        task_types=exec_task_types() if kind == "exec" else None,
        exclude_task_types=exec_task_types() if kind == "ai" else None,
        status=status_,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return success_response(
        data=AiTaskListResponse(
            total=total,
            items=[AiTaskResponse.model_validate(t) for t in items],
        )
    )


# 注意：必须注册在 /{task_id} 之前，否则 "stats" 会被当作路径参数
@router.get(
    "/stats",
    summary="AI 任务状态统计（任务中心统计卡）",
    response_model=ResponseModel[AiTaskStatsResponse],
)
async def task_stats(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:view"))
    ],
    task_type: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(
        default=None, description="任务类别：ai（生成）/ exec（执行）"
    ),
) -> ResponseModel[AiTaskStatsResponse]:
    await require_project_access(db, project_id, current_user.id)

    from app.ai_core.runtime.registry import exec_task_types

    counts = await crud_ai_task.count_by_status(
        db,
        project_id=project_id,
        task_type=task_type,
        task_types=exec_task_types() if kind == "exec" else None,
        exclude_task_types=exec_task_types() if kind == "ai" else None,
    )
    stats = AiTaskStatsResponse(
        total=sum(counts.values()),
        **{k: v for k, v in counts.items() if k in AiTaskStatsResponse.model_fields},
    )
    return success_response(data=stats)


@router.get(
    "/{task_id}",
    summary="获取 AI 任务详情（含已落库事件）",
    response_model=ResponseModel[AiTaskDetailResponse],
)
async def get_task(
    project_id: int,
    task_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:view"))
    ],
    after_seq: int = Query(default=0, ge=0),
) -> ResponseModel[AiTaskDetailResponse]:
    await require_project_access(db, project_id, current_user.id)

    task = await crud_ai_task.get(db, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    events = await crud_ai_task.list_events(db, task_id=task_id, after_seq=after_seq)
    detail = AiTaskDetailResponse.model_validate(task)
    detail.events = [AiTaskEventResponse.model_validate(e) for e in events]
    return success_response(data=detail)


@router.get("/{task_id}/stream", summary="SSE 实时事件流（回放 + 订阅）")
async def stream_task(
    project_id: int,
    task_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:view"))
    ],
    after_seq: int = Query(default=0, ge=0),
) -> StreamingResponse:
    # 项目成员校验（必须在建立 SSE 流之前；流内仅比对 project_id，非成员校验）
    await require_project_access(db, project_id, current_user.id)

    # 支持断线重连：Last-Event-ID 优先于 after_seq
    last_event_id = request.headers.get("last-event-id")
    start_seq = after_seq
    if last_event_id and last_event_id.isdigit():
        start_seq = int(last_event_id)

    async def gen():
        # 1) 先订阅，避免回放与订阅之间丢事件
        pubsub = await event_bus.open_subscription(task_id)
        last_seq = start_seq

        try:
            # 2) 回放 DB 历史事件
            async with async_session_maker() as db2:
                task = await crud_ai_task.get(db2, task_id)
                if not task or task.project_id != project_id:
                    yield _sse(0, {"type": "error", "payload": {"message": "任务不存在"}})
                    return
                history = await crud_ai_task.list_events(
                    db2, task_id=task_id, after_seq=start_seq
                )
                terminal = task.status in TERMINAL

            for e in history:
                last_seq = max(last_seq, e.seq)
                yield _sse(e.seq, {"type": e.event_type, "payload": e.payload, "seq": e.seq})
                if e.event_type == "task_end":
                    return

            # 3) 已终态且历史里没 task_end（壳崩溃/旧数据）→ 补发终态
            if terminal:
                last_seq += 1
                yield _sse(
                    last_seq,
                    {
                        "type": "task_end",
                        "payload": {"status": task.status, "duration_ms": 0},
                        "seq": last_seq,
                    },
                )
                return

            # 4) 实时循环：get_message(超时) + keep-alive + 周期性 DB 轮询兜底
            idle = 0
            while True:
                if await request.is_disconnected():
                    return
                try:
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                except Exception:  # noqa: BLE001  Redis 读超时/瞬断 → 当作无消息
                    msg = None

                if msg and msg.get("type") == "message":
                    idle = 0
                    try:
                        ev = json.loads(msg["data"])
                    except (ValueError, TypeError, KeyError):
                        continue
                    seq = ev.get("seq", 0)
                    if seq <= last_seq:
                        continue
                    last_seq = seq
                    yield _sse(seq, ev)
                    if ev.get("type") == "task_end":
                        return
                    continue

                # 无消息：发 keep-alive 注释，保活连接
                idle += 1
                yield ": keepalive\n\n"

                # 每 ~5s 兜底查 DB：补发漏掉的事件 + 终态则结束 + 僵尸回收
                if idle % 5 == 0:
                    final_status: Optional[str] = None
                    async with async_session_maker() as db3:
                        t = await crud_ai_task.get(db3, task_id)
                        missed = await crud_ai_task.list_events(
                            db3, task_id=task_id, after_seq=last_seq
                        )
                        if t is not None and t.status in TERMINAL:
                            final_status = t.status
                        elif t is not None:
                            # 僵尸判定：避免对死任务无限 keep-alive
                            if await crud_ai_task.fail_if_zombie(
                                db3,
                                task=t,
                                timeout_s=settings.AI_TASK_ZOMBIE_TIMEOUT_S,
                            ):
                                final_status = "failed"
                                from app.services.ai_task_finalize import (
                                    finalize_biz_records,
                                )

                                await finalize_biz_records(db3, t, canceled=False)
                    for e in missed:
                        last_seq = max(last_seq, e.seq)
                        yield _sse(
                            e.seq,
                            {"type": e.event_type, "payload": e.payload, "seq": e.seq},
                        )
                        if e.event_type == "task_end":
                            return
                    if final_status is not None:
                        # 事件流里没有 task_end（壳崩溃/僵尸回收），按真实终态补发
                        last_seq += 1
                        yield _sse(
                            last_seq,
                            {
                                "type": "task_end",
                                "payload": {"status": final_status, "duration_ms": 0},
                                "seq": last_seq,
                            },
                        )
                        return
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{task_id}/cancel",
    summary="取消 AI 任务",
    response_model=ResponseModel[AiTaskResponse],
)
async def cancel_task(
    project_id: int,
    task_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:manage"))
    ],
) -> ResponseModel[AiTaskResponse]:
    await require_project_access(db, project_id, current_user.id)

    task = await crud_ai_task.get(db, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if task.status in TERMINAL:
        return success_response(
            data=AiTaskResponse.model_validate(task), message="任务已结束，无需取消"
        )
    # 协作式取消标志 + Celery revoke（对活着的 worker/图生效）
    await event_bus.request_cancel(task_id)
    if task.celery_task_id:
        from app.tasks.celery_app import celery_app

        try:
            celery_app.control.revoke(task.celery_task_id, terminate=False)
        except Exception:  # noqa: BLE001
            pass

    # 协作式信号可能永远无人响应（排队消息丢失/队列无 worker/worker 已崩溃），
    # 这类任务在这里就地转终态，否则前端永远停在「排队中/执行中」且无法取消
    final_status = await _force_finalize_stuck(db, task)
    if final_status is not None:
        from app.ai_core.runtime.events import EventType, make_event, task_end_payload
        from app.services.ai_task_finalize import finalize_biz_records

        # 预创建的业务执行记录一并收尾（app/web/api/perf 各家族），
        # 否则各执行记录列表页留下永久「排队中」残骸
        await finalize_biz_records(db, task, canceled=(final_status == "canceled"))
        # task_end 哨兵：让挂着的 SSE 观看端优雅收流（回放端会按真实终态补发）
        try:
            await event_bus.publish(
                task_id,
                make_event(
                    999_999, EventType.TASK_END.value, task_end_payload(final_status, 0)
                ),
            )
        except Exception:  # noqa: BLE001
            pass

    await db.refresh(task)
    if final_status == "canceled":
        message = "任务已取消（排队中的任务直接终止）"
    elif final_status == "failed":
        message = "执行方已失联，任务已标记为失败"
    else:
        message = "取消请求已发送，任务将在感知到信号后停止"
    return success_response(data=AiTaskResponse.model_validate(task), message=message)


async def _force_finalize_stuck(db: AsyncSession, task) -> Optional[str]:
    """取消时就地终结「不会有人来收尾」的任务，返回写入的终态（未命中返回 None）。

    - pending：原子 pending→canceled（与 worker 的 try_claim_running 同为条件
      UPDATE，安全竞争；worker 恰好刚领走则 0 行更新，走协作取消）。
    - running 且心跳超过僵尸阈值：worker 已死，协作信号无人消费，复用
      fail_if_zombie 就地标记失败（内部再次校验超时 + 条件 UPDATE）。
      心跳正常的 running 任务不动——协作取消数秒内即生效。
    """
    if task.status == AiTaskStatus.PENDING.value:
        if await crud_ai_task.cancel_if_pending(db, task_id=task.id):
            return "canceled"
        return None
    if task.status == AiTaskStatus.RUNNING.value:
        if await crud_ai_task.fail_if_zombie(
            db, task=task, timeout_s=settings.AI_TASK_ZOMBIE_TIMEOUT_S
        ):
            return "failed"
    return None


@router.post(
    "/{task_id}/retry",
    summary="重试 AI 任务（用原参数新建）",
    response_model=ResponseModel[AiTaskResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_task(
    project_id: int,
    task_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:manage"))
    ],
) -> ResponseModel[AiTaskResponse]:
    await require_project_access(db, project_id, current_user.id)

    old = await crud_ai_task.get(db, task_id)
    if not old or old.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")

    new_task = await crud_ai_task.create(
        db,
        project_id=project_id,
        created_by=current_user.id,
        task_type=old.task_type,
        title=old.title,
        biz_ref_type=old.biz_ref_type,
        biz_ref_id=old.biz_ref_id,
        input_params=old.input_params,
    )
    async_result = safe_dispatch(new_task.task_type, new_task.id)
    if async_result is not None:
        await crud_ai_task.set_celery_task_id(
            db, task_id=new_task.id, celery_task_id=async_result.id
        )
        await db.refresh(new_task)
    return success_response(
        data=AiTaskResponse.model_validate(new_task), message="已重新提交"
    )


@router.delete(
    "/{task_id}",
    summary="删除 AI 任务（含事件流，仅限终态任务）",
    response_model=ResponseModel[None],
)
async def delete_task(
    project_id: int,
    task_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("ai_task:manage"))
    ],
) -> ResponseModel[None]:
    await require_project_access(db, project_id, current_user.id)

    task = await crud_ai_task.get(db, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if task.status not in TERMINAL:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="任务尚未结束，请先取消再删除"
        )
    await crud_ai_task.delete(db, task_id=task_id)
    return success_response(message="已删除")


def _sse(event_id: int, data: dict) -> str:
    return f"id: {event_id}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
