"""网关内部 RPC 端点（契约 §9）

业务 API / Celery → POST /internal/rpc/{agent_id}，头 X-Internal-Key 对
settings.GATEWAY_INTERNAL_KEY。网关在本进程完成 rpc_request 关联与超时，
同步返回结果。调用方走 http://127.0.0.1:8889，httpx 必须 trust_env=False
（代理环境劫持坑）。
"""

import secrets
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.response import ResponseModel, error_response, success_response
from app.gateway.agent_ws import AgentNotConnectedError, RpcTimeoutError, send_rpc
from app.gateway.frames import DEFAULT_RPC_TIMEOUT_MS

router = APIRouter()

# timeout_ms 上限：调用方自己声明超时，网关只挡明显异常值。
# 上限须容纳自动化长 RPC（run_app_step 单句 aiAct 可多轮规划，S2 实测 136s）
MAX_RPC_TIMEOUT_MS = 300_000


class InternalRpcIn(BaseModel):
    """rpc_request 构造参数（契约 §9 body {cmd, params, timeout_ms}）"""

    cmd: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=DEFAULT_RPC_TIMEOUT_MS, ge=100, le=MAX_RPC_TIMEOUT_MS)


def _json(status_code: int, payload: ResponseModel) -> JSONResponse:
    """网关无全局异常处理器，直接以 HTTP 状态 + {code,message,data} 包装返回"""
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@router.post("/internal/rpc/{agent_id}")
async def internal_rpc(
    agent_id: int,
    body: InternalRpcIn,
    x_internal_key: str = Header(default=""),
) -> JSONResponse:
    """向指定 agent 发一次 RPC 并同步等待结果"""
    if not settings.GATEWAY_INTERNAL_KEY or not secrets.compare_digest(
        x_internal_key, settings.GATEWAY_INTERNAL_KEY
    ):
        return _json(401, error_response("X-Internal-Key 无效", code=401))
    try:
        payload = await send_rpc(agent_id, body.cmd, body.params, body.timeout_ms)
    except AgentNotConnectedError:
        return _json(404, error_response(f"agent {agent_id} 未连接", code=404))
    except RpcTimeoutError:
        return _json(
            504, error_response(f"rpc {body.cmd} 等待 agent 响应超时", code=504)
        )
    return _json(200, success_response(payload))
