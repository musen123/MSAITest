"""Agent 控制 WS（契约 §2）

握手：升级头 X-Agent-Token（sha256 对 app_agent.token_hash）+
X-Host-Fingerprint（库里指纹为空则首连绑定写库，已绑定则必须一致）
→ 首帧必须 register（protocol_version 门槛）→ 回 registered
→ heartbeat / device_event / rpc_response 帧循环。

close code（契约 §2）：4401 token 无效 / 4403 指纹不符 /
4409 同 agent 二连 / 4426 protocol_version 过低。

app_agent 表结构由契约 §7 冻结，鉴权与 register 元信息直接 SQL 读写；
heartbeat / device_event 落库调 backend-core 的 app_device service
（并行开发，接口以契约为准，未落地时降级为只维持隧道并告警）。
"""

import asyncio
import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.db.session import async_session_maker
from app.gateway.connections import registry
from app.gateway.frames import (
    DEFAULT_RPC_TIMEOUT_MS,
    MIN_PROTOCOL_VERSION,
    FrameError,
    decode_frame,
    error_frame,
    new_rpc_id,
    registered_frame,
    rpc_request_frame,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 首帧 register 等待上限（秒）：握手完成前不进入常规帧循环
REGISTER_TIMEOUT_S = 15


class AgentNotConnectedError(Exception):
    """目标 agent 当前无控制 WS 连接"""


class RpcTimeoutError(Exception):
    """rpc_request 已发出但超时未收到 rpc_response"""


# ── 鉴权（app_agent 表，结构见契约 §7） ─────────────────────────


def hash_token(token: str) -> str:
    """token 明文 → sha256 hex（库存 token_hash 的口径）"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def resolve_agent_by_token(token: str) -> tuple[int, str | None] | None:
    """按 token 哈希查 app_agent，返回 (agent_id, host_fingerprint)；不存在 → None"""
    if not token:
        return None
    async with async_session_maker() as db:
        row = (
            await db.execute(
                text(
                    "SELECT id, host_fingerprint FROM app_agent "
                    "WHERE token_hash = :th LIMIT 1"
                ),
                {"th": hash_token(token)},
            )
        ).first()
    if row is None:
        return None
    return int(row[0]), row[1]


async def _check_fingerprint(
    agent_id: int, bound: str | None, fingerprint: str
) -> bool:
    """指纹校验：首连（库里为空）则绑定写库；已绑定则必须一致"""
    if not fingerprint:
        return False
    if bound:
        return bound == fingerprint
    async with async_session_maker() as db:
        await db.execute(
            text(
                "UPDATE app_agent SET host_fingerprint = :fp, updated_at = NOW() "
                "WHERE id = :id AND (host_fingerprint IS NULL OR host_fingerprint = '')"
            ),
            {"fp": fingerprint, "id": agent_id},
        )
        await db.commit()
    return True


async def _record_register(agent_id: int, frame: dict[str, Any]) -> None:
    """register 帧元信息落 app_agent（agent_version / capabilities / protocol_version）"""
    caps = frame.get("capabilities")
    async with async_session_maker() as db:
        await db.execute(
            text(
                "UPDATE app_agent SET agent_version = :av, capabilities = :caps, "
                "protocol_version = :pv, updated_at = NOW() WHERE id = :id"
            ),
            {
                "av": (str(frame.get("agent_version") or "")[:32]) or None,
                "caps": json.dumps(caps if isinstance(caps, list) else []),
                "pv": int(frame["protocol_version"]),
                "id": agent_id,
            },
        )
        await db.commit()


# ── heartbeat / device_event 落库（backend-core service） ──────

_svc_missing_logged = False


def _load_device_service() -> Any | None:
    """heartbeat/device_event 落库 service，由 backend-core 并行实现（契约 §1）。

    未落地时返回 None（网关降级为只维持隧道），不在此处重写其逻辑。
    """
    global _svc_missing_logged
    try:
        from app.services.app_device import service as device_service

        return device_service
    except ImportError:
        if not _svc_missing_logged:
            _svc_missing_logged = True
            logger.warning(
                "app.services.app_device.service 未就绪，heartbeat/device_event 暂不落库"
            )
        return None


async def _handle_heartbeat(agent_id: int, frame: dict[str, Any]) -> None:
    """心跳：更新 last_heartbeat_at + 设备全量快照对账（契约 §2/§7）"""
    svc = _load_device_service()
    if svc is None:
        return
    async with async_session_maker() as db:
        await svc.sync_heartbeat(
            db, agent_id=agent_id, devices=frame.get("devices") or []
        )


async def _handle_device_event(agent_id: int, frame: dict[str, Any]) -> None:
    """事件驱动的设备增量（upsert / remove）"""
    event = frame.get("event")
    device = frame.get("device")
    if event not in ("upsert", "remove") or not isinstance(device, dict):
        raise FrameError("device_event 帧缺 event/device 字段")
    svc = _load_device_service()
    if svc is None:
        return
    async with async_session_maker() as db:
        await svc.apply_device_event(db, agent_id=agent_id, event=event, device=device)


async def _handle_screenshot(agent_id: int, frame: dict[str, Any]) -> None:
    """设备静态截图（契约 §2.1）：存 Redis 供列表缩略图端点读取。"""
    serial = frame.get("serial")
    data_b64 = frame.get("data_b64")
    if not isinstance(serial, str) or not serial or not isinstance(data_b64, str):
        raise FrameError("device_screenshot 帧缺 serial/data_b64 字段")
    from app.services.app_device.screenshot import store_screenshot

    udid = f"{agent_id}:{serial}"
    await store_screenshot(udid, data_b64)


# ── RPC（网关 → Agent，internal_api 与 control_ws 共用） ────────


async def send_rpc(
    agent_id: int,
    cmd: str,
    params: dict[str, Any] | None = None,
    timeout_ms: int = DEFAULT_RPC_TIMEOUT_MS,
) -> dict[str, Any]:
    """经控制 WS 向 agent 发 rpc_request 并等待 rpc_response（契约 §2/§9）。

    返回规约结果 {"ok": bool, "result"|"error": ...}；
    agent 不在线 → AgentNotConnectedError；超时 → RpcTimeoutError。
    """
    ws = registry.get_agent(agent_id)
    if ws is None:
        raise AgentNotConnectedError(f"agent {agent_id} 未连接")
    rpc_id = new_rpc_id()
    fut = registry.create_rpc(rpc_id, agent_id)
    try:
        await ws.send_json(rpc_request_frame(rpc_id, cmd, params, timeout_ms))
        return await asyncio.wait_for(fut, timeout=timeout_ms / 1000)
    except asyncio.TimeoutError as exc:
        raise RpcTimeoutError(f"rpc {cmd} 等待响应超时（{timeout_ms}ms）") from exc
    finally:
        registry.discard_rpc(rpc_id)


# ── WS 端点 ────────────────────────────────────────────────────


@router.websocket("/api/v1/app/agents/ws")
async def agent_control_ws(websocket: WebSocket) -> None:
    """Agent 出站控制隧道（契约 §2）"""
    token = websocket.headers.get("X-Agent-Token", "")
    fingerprint = (websocket.headers.get("X-Host-Fingerprint") or "").strip()
    await websocket.accept()

    # 1. token → agent
    try:
        resolved = await resolve_agent_by_token(token)
    except Exception:
        logger.exception("agent 鉴权查询失败")
        await websocket.close(code=1011)
        return
    if resolved is None:
        await websocket.close(code=4401)
        return
    agent_id, bound_fp = resolved

    # 2. 指纹：首连绑定 / 不符拒连
    try:
        fp_ok = await _check_fingerprint(agent_id, bound_fp, fingerprint)
    except Exception:
        logger.exception("agent 指纹绑定写库失败 agent=%s", agent_id)
        await websocket.close(code=1011)
        return
    if not fp_ok:
        await websocket.close(code=4403)
        return

    # 3. 同 agent 二连拒绝（旧连接保留）
    if not registry.register_agent(agent_id, websocket):
        await websocket.close(code=4409)
        return

    logger.info("agent 控制 WS 建立 agent=%s", agent_id)
    try:
        if not await _do_register(agent_id, websocket):
            return
        await _frame_loop(agent_id, websocket)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("agent 控制 WS 异常退出 agent=%s", agent_id)
    finally:
        registry.unregister_agent(agent_id, websocket)
        failed = registry.fail_agent_rpcs(
            agent_id, code="internal", message="agent 控制连接断开"
        )
        if failed:
            logger.info("agent=%s 断开，%s 个在途 rpc 已失败返回", agent_id, failed)
        logger.info("agent 控制 WS 断开 agent=%s", agent_id)


async def _do_register(agent_id: int, websocket: WebSocket) -> bool:
    """握手：首帧必须 register，protocol_version 达标才回 registered"""
    try:
        raw = await asyncio.wait_for(
            websocket.receive_text(), timeout=REGISTER_TIMEOUT_S
        )
        frame = decode_frame(raw)
    except asyncio.TimeoutError:
        await websocket.close(code=1002)
        return False
    except (FrameError, KeyError):
        # 非文本帧 / 非法 JSON：协议错误
        await websocket.close(code=1002)
        return False
    if frame["type"] != "register":
        await websocket.close(code=1002)
        return False
    pv = frame.get("protocol_version")
    if not isinstance(pv, int) or pv < MIN_PROTOCOL_VERSION:
        await websocket.close(code=4426)
        return False
    try:
        await _record_register(agent_id, frame)
    except Exception:
        # 元信息落库失败不拆隧道
        logger.exception("register 元信息落库失败 agent=%s", agent_id)
    await websocket.send_json(registered_frame(agent_id))
    logger.info(
        "agent 注册完成 agent=%s version=%s", agent_id, frame.get("agent_version")
    )
    return True


async def _frame_loop(agent_id: int, websocket: WebSocket) -> None:
    """常规帧循环：heartbeat / device_event / rpc_response"""
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        raw = message.get("text")
        if raw is None:
            await websocket.send_json(
                error_frame("binary_not_allowed", "控制 WS 仅接受 JSON 文本帧")
            )
            continue
        try:
            frame = decode_frame(raw)
        except FrameError as exc:
            await websocket.send_json(error_frame("bad_frame", str(exc)))
            continue
        ftype = frame["type"]
        try:
            if ftype == "heartbeat":
                await _handle_heartbeat(agent_id, frame)
            elif ftype == "device_event":
                await _handle_device_event(agent_id, frame)
            elif ftype == "device_screenshot":
                await _handle_screenshot(agent_id, frame)
            elif ftype == "rpc_response":
                if not registry.resolve_rpc(frame):
                    logger.debug(
                        "迟到/未知 rpc_response 丢弃 agent=%s id=%s",
                        agent_id,
                        frame.get("id"),
                    )
            else:
                await websocket.send_json(
                    error_frame("unknown_type", f"未知帧类型: {ftype}")
                )
        except FrameError as exc:
            await websocket.send_json(error_frame("bad_frame", str(exc)))
        except Exception:
            # 单帧处理失败（如落库瞬时故障）不拆隧道
            logger.exception("处理 %s 帧失败 agent=%s", ftype, agent_id)
