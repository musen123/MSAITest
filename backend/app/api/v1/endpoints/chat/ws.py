"""智能体对话 WebSocket 端点

协议（JSON 帧）：
  C→S  {"type": "user_message", "content": "..."}
  C→S  {"type": "interrupt"}
  C→S  {"type": "ping"}
  S→C  {"type": "init", "conversation_id": int, "resumed": bool, "message_count": int}
  S→C  {"type": "thinking_start"}
  S→C  {"type": "block_start",  "block_id": str, "block_type": "text|tool|thinking", ...}
  S→C  {"type": "block_delta",  "block_id": str, "delta": str}
  S→C  {"type": "block_end",    "block_id": str, "status": "success|error|interrupted",
        ["action": {"kind": "navigate", "route_name", "params", "label"}], ...}
  S→C  {"type": "done", "interrupted": bool}
  S→C  {"type": "interrupted"}
  S→C  {"type": "pong"}
  S→C  {"type": "error", "error": "..."}

鉴权：
  WebSocket 通过 query 参数 ?token=xxx 传入 JWT；后端验证 token + 加载用户 LLM。
"""

import asyncio
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from app.ai_core.chat_agent.agent import aget_state_snapshot
from app.ai_core.chat_agent.agent_context import AgentContext
from app.ai_core.llm_client import build_llm_from_config
from app.ai_core.llm_context import set_current_llm
from app.core.security import verify_token
from app.crud.auth.user import user_crud
from app.crud.auth.user_llm_config import crud_user_llm_config
from app.crud.chat.conversation import crud_conversation, crud_message
from app.db.session import async_session_maker
from app.models.auth.user_llm_config import ModelType
from app.services.chat.agent_service import (
    EVENT_TIMEOUT,
    AgentOrchestrator,
    registry,
)
from app.utils.project_permission import check_project_access

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{conv_id}")
async def chat_ws(
    websocket: WebSocket,
    project_id: int,
    conv_id: int,
    token: str = Query(...),
):
    """WebSocket 智能体对话"""
    await websocket.accept()

    # 1. 验证 token
    user_id_raw = verify_token(token, token_type="access")
    if not user_id_raw:
        await websocket.send_json({"type": "error", "error": "invalid_token"})
        await websocket.close(code=4401)
        return
    user_id = int(user_id_raw)

    # 2. 校验对话存在 + 同项目；加载用户 LLM
    async with async_session_maker() as db:
        conv = await crud_conversation.get(db, conv_id)
        if not conv or conv.project_id != project_id:
            await websocket.send_json({"type": "error", "error": "conversation_not_found"})
            await websocket.close(code=4404)
            return

        user = await user_crud.get_with_relations(db, user_id=user_id)
        if not user or user.status.value != "active":
            await websocket.send_json({"type": "error", "error": "user_inactive"})
            await websocket.close(code=4403)
            return

        # 项目成员校验（与平台端点同口径）：助手工具带执行/写库能力，
        # 非项目成员不允许建立对话连接
        try:
            allowed = await check_project_access(db, project_id, user_id)
        except HTTPException:
            allowed = False
        if not allowed:
            await websocket.send_json({"type": "error", "error": "forbidden"})
            await websocket.close(code=4403)
            return

        cfg = await crud_user_llm_config.get_default(
            db, user_id=user_id, model_type=ModelType.TEXT
        )
        if not cfg or not cfg.is_active:
            await websocket.send_json(
                {"type": "error", "error": "llm_not_configured"}
            )
            await websocket.close(code=4400)
            return
        llm = build_llm_from_config(cfg)
        set_current_llm(llm)

    # 3. 互斥占位
    if not registry.mark_streaming(conv_id):
        await websocket.send_json({"type": "error", "error": "conversation_busy"})
        await websocket.close(code=4001)
        return

    # 发送锁：跑流子任务与主循环（pong/error）并发发帧时防交错
    send_lock = asyncio.Lock()

    async def send(payload: dict) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    run_task: Optional[asyncio.Task] = None

    try:
        # 4. 握手 init
        snap = await aget_state_snapshot(conv_id)
        msg_count = snap["message_count"] if snap else 0
        await send(
            {
                "type": "init",
                "conversation_id": conv_id,
                "resumed": msg_count > 0,
                "message_count": msg_count,
            }
        )

        # 5. 消息循环（双任务：主循环持续收帧，轮次在子任务中跑流，
        #    这样流式生成期间 interrupt 帧才能被实时处理）
        ctx = AgentContext(
            project_id=project_id,
            user_id=user_id,
            conversation_id=conv_id,
        )
        while True:
            try:
                frame = await asyncio.wait_for(
                    websocket.receive_json(), timeout=EVENT_TIMEOUT
                )
            except asyncio.TimeoutError:
                # 生成中不算空闲（长任务期间客户端可以不发帧）
                if run_task is not None and not run_task.done():
                    continue
                raise
            if not isinstance(frame, dict):
                await send({"type": "error", "error": "invalid_frame"})
                continue
            t = frame.get("type")
            if t == "user_message":
                content = (frame.get("content") or "").strip()
                if not content:
                    await send({"type": "error", "error": "empty_message"})
                    continue
                if run_task is not None and not run_task.done():
                    # done 帧发出后任务还有收尾（极短），给 2s 宽限
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(run_task), timeout=2.0
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    if not run_task.done():
                        await send(
                            {"type": "error", "error": "conversation_busy"}
                        )
                        continue
                # 中断标志按轮重置（否则中断过一次后续轮全部误中断）
                registry.event_for(conv_id).clear()
                run_task = asyncio.create_task(
                    _run_one_turn(
                        send, llm, conv_id, content, agent_context=ctx
                    )
                )
                run_task.add_done_callback(_log_turn_exception)
            elif t == "interrupt":
                registry.interrupt(conv_id)
            elif t == "ping":
                await send({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("ws disconnected conv=%s", conv_id)
    except asyncio.TimeoutError:
        try:
            await send({"type": "error", "error": "timeout"})
        except Exception:
            pass
    except Exception as exc:
        logger.exception("ws handler error conv=%s", conv_id)
        try:
            await send({"type": "error", "error": str(exc)})
        except Exception:
            pass
    finally:
        if run_task is not None and not run_task.done():
            run_task.cancel()
        registry.clear(conv_id)


def _log_turn_exception(task: asyncio.Task) -> None:
    """子任务异常不被 await，统一在回调里捞出来打日志"""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None and not isinstance(
        exc, (WebSocketDisconnect, asyncio.CancelledError)
    ):
        logger.error("chat turn task error: %s", exc, exc_info=exc)


async def _run_one_turn(
    send,
    llm,
    conv_id: int,
    user_text: str,
    *,
    agent_context: AgentContext,
) -> None:
    """跑一轮：落库 user_msg → 启动 orchestrator → 转发流 → 落库 assistant_msg

    运行在独立子任务中：ContextVar 需在本任务内重新注入。
    """
    # ContextVar 在子任务内注入（create_task 只继承创建时刻的快照）
    set_current_llm(llm)

    # 1. 落库 user 消息
    async with async_session_maker() as db:
        await crud_message.create(
            db, conversation_id=conv_id, role="user", content=user_text
        )

    # 2. 启动 orchestrator
    orch = AgentOrchestrator(conv_id, user_text, agent_context=agent_context)
    interrupted = False
    saved = False

    async def _save() -> None:
        nonlocal saved
        if saved:
            return
        saved = True
        text = "".join(orch._text_chunks)
        # 归一化 tool_calls：残留 running 的按中断/错误收尾
        normalized: list[dict] = []
        for tc in list(orch._tool_calls):
            t = dict(tc)
            if t.get("status") == "running":
                t["status"] = "interrupted" if interrupted else "error"
            normalized.append(t)
        await _save_assistant_message(conv_id, text, normalized)

    try:
        async for ev in orch.stream():
            await send(ev)
            if ev.get("type") == "interrupted":
                interrupted = True
        # 3. 先落库再发 done：客户端收到 done 即可立刻发下一条。
        #    shield：此刻断连触发的 cancel 不打断进行中的 DB 写入
        try:
            await asyncio.shield(_save())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("save assistant message failed conv=%s", conv_id)
        await send({"type": "done", "interrupted": interrupted})
    finally:
        # 异常/取消路径兜底落库（shield：连接断开取消本任务时仍完成）
        if not saved:
            try:
                await asyncio.shield(_save())
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "save assistant message failed conv=%s", conv_id
                )


async def _save_assistant_message(
    conv_id: int, text: str, tool_calls: list[dict]
) -> None:
    async with async_session_maker() as db:
        await crud_message.create(
            db,
            conversation_id=conv_id,
            role="assistant",
            content=text,
            tool_calls=tool_calls or None,
        )
