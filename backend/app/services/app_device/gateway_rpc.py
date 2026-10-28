"""网关内部 RPC 客户端（契约 §9）

业务 API / Celery → POST {GATEWAY_INTERNAL_URL}/internal/rpc/{agent_id}，
头 X-Internal-Key。网关同步完成 rpc_request 关联与超时并返回
{code, message, data}，data = Agent 的规约结果 {"ok": bool, "result"|"error": ...}。

⚠ trust_env=False 必须：本机 shell 可能带 http_proxy 无 no_proxy，会劫持
127.0.0.1 请求（代理环境坑，CLAUDE.md）。
"""

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# aiAct 单句可多轮规划（S2 实测 7 轮/136s），录制/回放走宽超时档
AUTOMATION_RPC_TIMEOUT_MS = 240_000


class GatewayRpcError(Exception):
    """网关层调用失败（agent 未连接 / 网关超时 / 网关不可达）"""

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class AgentRpcError(Exception):
    """Agent 规约错误（result.ok=False）：code 为协议错误码（busy/timeout/internal…）"""

    def __init__(self, code: str, message: str, detail: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


async def call_agent_rpc(
    agent_id: int,
    cmd: str,
    params: dict[str, Any],
    *,
    timeout_ms: int = AUTOMATION_RPC_TIMEOUT_MS,
) -> dict[str, Any]:
    """经网关向 Agent 发一次 RPC，返回 Agent result（ok=True 的 result 字段）。

    - 网关不可达 / agent 未连接 / 网关超时 → GatewayRpcError
    - Agent 回规约错误（ok=False）→ AgentRpcError（code 透传，busy 附 detail）
    """
    url = f"{settings.GATEWAY_INTERNAL_URL}/internal/rpc/{agent_id}"
    body = {"cmd": cmd, "params": params, "timeout_ms": timeout_ms}
    try:
        async with httpx.AsyncClient(
            trust_env=False, timeout=timeout_ms / 1000 + 10
        ) as client:
            resp = await client.post(
                url, json=body, headers={"X-Internal-Key": settings.GATEWAY_INTERNAL_KEY}
            )
    except httpx.HTTPError as exc:
        raise GatewayRpcError(f"网关不可达：{exc}") from exc

    if resp.status_code == 404:
        raise GatewayRpcError("执行机（Agent）当前不在线", status_code=404)
    if resp.status_code == 504:
        raise GatewayRpcError(f"Agent 执行 {cmd} 超时", status_code=504)
    if resp.status_code != 200:
        raise GatewayRpcError(
            f"网关返回异常 HTTP {resp.status_code}", status_code=502
        )

    payload = resp.json().get("data") or {}
    if payload.get("ok"):
        result = payload.get("result")
        return result if isinstance(result, dict) else {}
    error = payload.get("error") or {}
    code = str(error.get("code") or "internal")
    message = str(error.get("message") or "Agent 执行失败")
    detail = {k: v for k, v in error.items() if k not in ("code", "message")}
    logger.warning("agent rpc %s 规约错误 code=%s detail=%s", cmd, code, detail)
    raise AgentRpcError(code, message, detail)
