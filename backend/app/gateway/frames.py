"""隧道控制帧协议 v1 编解码（契约 §2）

Agent ↔ 网关的控制帧全部是 JSON 文本帧，出站帧一律带 "v": 1。
本模块只管结构层（合法 JSON 对象 + 非空 type），业务校验（token、
register 版本门槛等）留在各 WS 处理器。
"""

import json
import uuid
from typing import Any

# 协议版本门槛：register 帧 protocol_version 低于此值 → close 4426
MIN_PROTOCOL_VERSION = 1
# 心跳节拍（registered 帧回给 Agent，契约 §2：每 10s 全量快照对账）
HEARTBEAT_INTERVAL_S = 10
# rpc 默认超时（契约 §2 示例值）
DEFAULT_RPC_TIMEOUT_MS = 15000


class FrameError(ValueError):
    """入站帧结构非法（非 JSON / 非对象 / 缺 type / 字段缺失）"""


def decode_frame(raw: str) -> dict[str, Any]:
    """解码入站文本帧：必须是 JSON 对象且带非空字符串 type"""
    try:
        frame = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise FrameError(f"非法 JSON 帧: {exc}") from exc
    if not isinstance(frame, dict):
        raise FrameError("帧必须是 JSON 对象")
    ftype = frame.get("type")
    if not isinstance(ftype, str) or not ftype:
        raise FrameError("帧缺少 type 字段")
    return frame


def new_rpc_id() -> str:
    """rpc_request 关联 id，契约示例形如 r-uuid"""
    return f"r-{uuid.uuid4()}"


def registered_frame(agent_id: int) -> dict[str, Any]:
    """网关 → Agent：register 握手成功回执"""
    return {
        "v": 1,
        "type": "registered",
        "agent_id": agent_id,
        "heartbeat_interval_s": HEARTBEAT_INTERVAL_S,
    }


def rpc_request_frame(
    rpc_id: str, cmd: str, params: dict[str, Any] | None, timeout_ms: int
) -> dict[str, Any]:
    """网关 → Agent：RPC 请求帧"""
    return {
        "v": 1,
        "type": "rpc_request",
        "id": rpc_id,
        "cmd": cmd,
        "params": params or {},
        "timeout_ms": timeout_ms,
    }


def error_frame(code: str, message: str) -> dict[str, Any]:
    """网关 → Agent：协议级错误提示（不拆隧道）"""
    return {"v": 1, "type": "error", "code": code, "message": message}


def rpc_payload(frame: dict[str, Any]) -> dict[str, Any]:
    """把 rpc_response 帧规约成 {ok, result|error}（剥掉信封字段）。

    ok 严格为 True 才算成功；失败但未携带 error 时补 internal，
    防止上游拿到空错误无从定位。
    """
    if frame.get("ok") is True:
        return {"ok": True, "result": frame.get("result") or {}}
    error = frame.get("error")
    if not isinstance(error, dict) or not error:
        error = {"code": "internal", "message": "agent 返回失败但未携带 error"}
    return {"ok": False, "error": error}
