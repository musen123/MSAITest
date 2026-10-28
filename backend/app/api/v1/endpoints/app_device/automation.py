"""录制操作台端点（P2，契约 §3.2）

/app/devices/{udid}/automation/*：同步 HTTP 单步会话（Playground 模式，不走
Celery）——浏览器发一句自然语言 → 校验设备锁（owner + session）→ 取该用户
默认 VISION 模型（Midscene 家族必填）→ 经网关 /internal/rpc 代理 run_app_step
→ 同步返回执行结果 + 回收步骤。abort / end 同路径代理。

锁语义：录制与投屏同属一个锁 owner、一条隧道（方案 §2.2）——操作台先经
control-ticket 抢锁连投屏，再带同一 session_id 调本端点；本端点逐请求校验
holder（owner_user_id + session_id 双匹配），in-flight RPC 期间每 10s 续期
（契约 §4 续期来源②，防长 aiAct 期间 30s TTL 过期被抢）。
"""

import asyncio
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, error_response
from app.crud.app_device.device import crud_app_device
from app.crud.auth.user_llm_config import crud_user_llm_config as crud_llm_config
from app.models.auth.user import User
from app.models.auth.user_llm_config import ModelType
from app.schemas.app_test import (
    AutomationSessionRef,
    AutomationStepIn,
    AutomationStepOut,
)
from app.services.app_device.gateway_rpc import (
    AUTOMATION_RPC_TIMEOUT_MS,
    AgentRpcError,
    GatewayRpcError,
    call_agent_rpc,
)
from app.services.app_device.lock import device_lock

logger = logging.getLogger(__name__)

router = APIRouter()

# in-flight RPC 期间锁续期节拍（契约 §4 续期来源②）
_RENEW_INTERVAL_S = 10
# 单句 aiAct 重规划轮数上限。Agent 缺省 8 在复合指令下不够用（实测
# 「打开chrome 搜索python 点第一个结果」8 轮超限——且操作台占位文案本就
# 引导复合指令），放宽到 16；成本闸门语义保留（一轮≈一次 VL 规划调用）。
# 注意：该值在 Agent 侧建会话时生效，已有会话要「结束会话」重开才应用。
_RECORD_REPLANNING_CYCLE_LIMIT = 16


async def _require_lock_owner(udid: str, session_id: str, user: User) -> None:
    """逐请求校验设备锁：必须存在且 owner_user_id + session_id 双匹配。"""
    holder = await device_lock.holder(udid)
    if holder is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="设备未被占用，请先进入投屏控制建立会话"
        )
    if holder.get("owner_user_id") != user.id or holder.get("session_id") != session_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="设备控制权已变更，请重新进入投屏控制"
        )


async def _resolve_vision_model(db: AsyncSession, user: User) -> dict:
    """取该用户默认 VISION 配置 → Agent model 参数（Midscene 家族必填）。"""
    cfg = await crud_llm_config.get_default(
        db, user_id=user.id, model_type=ModelType.VISION
    )
    if cfg is None or not cfg.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="未配置视觉（VISION）模型，请到「用户中心 → 大模型配置」添加",
        )
    if not cfg.base_url:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="VISION 模型缺少 Base URL"
        )
    if not cfg.model_family:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "VISION 模型缺少 model_family（Midscene 兼容家族，如 doubao-seed / "
                "qwen3-vl / glm-v）。当前配置的模型若不属于任一家族则无法用于 App "
                "自动化，请更换为兼容的视觉定位模型"
            ),
        )
    return {
        "name": cfg.model,
        "base_url": cfg.base_url,
        "api_key": cfg.api_key,
        "family": cfg.model_family,
    }


async def _agent_id_of(db: AsyncSession, udid: str) -> tuple[int, str]:
    """udid → (agent_id, serial)；设备不存在 → 404。"""
    device = await crud_app_device.get_by_udid(db, udid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return device.agent_id, device.serial


async def _renew_lock_while_running(udid: str, session_id: str) -> None:
    """in-flight RPC 期间的锁续期循环（被调用方 cancel 结束）。"""
    try:
        while True:
            await asyncio.sleep(_RENEW_INTERVAL_S)
            renewed = await device_lock.renew(udid, session_id)
            if not renewed:
                logger.warning(
                    "自动化步骤执行中锁续期失败（已过期/被接管）udid=%s session=%s",
                    udid,
                    session_id,
                )
                return
    except asyncio.CancelledError:  # 正常收尾
        raise


@router.post(
    "/{udid}/automation/step",
    summary="录制单步：一句自然语言 → Midscene aiAct（契约 §3.2）",
    response_model=ResponseModel[AutomationStepOut],
)
async def run_automation_step(
    udid: str,
    body: AutomationStepIn,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
):
    """校锁 → 取 VISION 模型 → 代理 run_app_step（宽超时 + in-flight 续期）。"""
    await _require_lock_owner(udid, body.session_id, current_user)
    model = await _resolve_vision_model(db, current_user)
    agent_id, serial = await _agent_id_of(db, udid)

    params: dict = {
        "serial": serial,
        "session_id": body.session_id,
        "instruction": body.instruction,
        "model": model,
        "replanning_cycle_limit": _RECORD_REPLANNING_CYCLE_LIMIT,
    }
    if body.act_context:
        params["act_context"] = body.act_context

    renew_task = asyncio.create_task(
        _renew_lock_while_running(udid, body.session_id)
    )
    try:
        result = await call_agent_rpc(
            agent_id, "run_app_step", params, timeout_ms=AUTOMATION_RPC_TIMEOUT_MS
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        if exc.code == "busy":
            # 真并发冲突（另一会话正在跑步骤）→ 409（不能返回与 response_model
            # 不符的 body，否则 ResponseValidationError → 500）
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="执行机正被其他会话占用，请重新开始录制会话",
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"Agent 执行失败：{exc}"
        ) from exc
    finally:
        renew_task.cancel()

    return ResponseModel(data=AutomationStepOut.model_validate(result))


@router.get(
    "/{udid}/automation/progress",
    summary="执行进度增量读（单步 in-flight 轮询直播，契约 §3.2）",
    response_model=ResponseModel[dict],
)
async def get_automation_progress(
    udid: str,
    session_id: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
    after_seq: int = 0,
):
    """只读旁路：Agent 侧按 seq 增量回进度行（规划原话/定位/动作），
    aiAct in-flight 期间可用。会话不匹配 Agent 回 exists=false，前端安静停表。"""
    await _require_lock_owner(udid, session_id, current_user)
    agent_id, _ = await _agent_id_of(db, udid)
    try:
        result = await call_agent_rpc(
            agent_id,
            "get_app_step_progress",
            {"session_id": session_id, "after_seq": after_seq},
            timeout_ms=10_000,
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"进度查询失败：{exc}"
        ) from exc
    return ResponseModel(data=result)


# ==================== 手动操作录制（投屏触控流 → VL 语义化步骤） ====================


@router.post(
    "/{udid}/automation/manual/start",
    summary="开始手动录制：投屏触控流 tee → VL 语义化步骤（契约 §3.2）",
    response_model=ResponseModel[dict],
)
async def start_manual_record(
    udid: str,
    body: AutomationSessionRef,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
):
    """校锁 → 取 VISION 模型（点击语义化用）→ RPC start_manual_record。
    录制挂在活跃投屏会话上（触控从那来），未连投屏 Agent 侧会明确报错。"""
    await _require_lock_owner(udid, body.session_id, current_user)
    model = await _resolve_vision_model(db, current_user)
    device = await crud_app_device.get_by_udid(db, udid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="设备不存在")
    try:
        result = await call_agent_rpc(
            device.agent_id,
            "start_manual_record",
            {
                "serial": device.serial,
                "session_id": body.session_id,
                "model": model,
                # 设备物理分辨率：触控消息坐标在缩放流坐标系，Agent 语义化前换算
                "resolution": device.resolution or "",
            },
            timeout_ms=10_000,
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"开始手动录制失败：{exc}"
        ) from exc
    return ResponseModel(data=result, message="手动录制已开始")


@router.get(
    "/{udid}/automation/manual/steps",
    summary="手动录制步骤增量读（识别结果轮询，契约 §3.2）",
    response_model=ResponseModel[dict],
)
async def get_manual_steps(
    udid: str,
    session_id: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
    after_seq: int = 0,
):
    await _require_lock_owner(udid, session_id, current_user)
    agent_id, _ = await _agent_id_of(db, udid)
    try:
        result = await call_agent_rpc(
            agent_id,
            "get_manual_steps",
            {"session_id": session_id, "after_seq": after_seq},
            timeout_ms=10_000,
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"读取录制步骤失败：{exc}"
        ) from exc
    return ResponseModel(data=result)


@router.post(
    "/{udid}/automation/manual/stop",
    summary="结束手动录制：回全部步骤 + YAML flow（契约 §3.2）",
    response_model=ResponseModel[dict],
)
async def stop_manual_record(
    udid: str,
    body: AutomationSessionRef,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
):
    """停止录制（等在途 VL 识别落定），回 {steps, yaml_flow} 供并入草稿。"""
    await _require_lock_owner(udid, body.session_id, current_user)
    agent_id, _ = await _agent_id_of(db, udid)
    try:
        result = await call_agent_rpc(
            agent_id,
            "stop_manual_record",
            {"session_id": body.session_id},
            # 等在途 VL 识别收尾（最多几条 × 30s 超时，给 60s 富余）
            timeout_ms=60_000,
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"结束手动录制失败：{exc}"
        ) from exc
    return ResponseModel(data=result, message="手动录制已结束")


@router.post(
    "/{udid}/automation/abort",
    summary="取消当前在跑的自动化步骤（契约 §3.2 取消闭环）",
    response_model=ResponseModel[dict],
)
async def abort_automation_flow(
    udid: str,
    body: AutomationSessionRef,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
):
    """abort 当前 aiAct（真机立即停，不空烧 token）。"""
    session_id = body.session_id
    await _require_lock_owner(udid, session_id, current_user)
    agent_id, _ = await _agent_id_of(db, udid)
    try:
        result = await call_agent_rpc(
            agent_id, "abort_app_flow", {"session_id": session_id}, timeout_ms=10_000
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"取消失败：{exc}"
        ) from exc
    return ResponseModel(data=result, message="已发送取消")


@router.post(
    "/{udid}/automation/end",
    summary="结束自动化会话（dispose Agent 侧 AndroidAgent，契约 §3.2）",
    response_model=ResponseModel[dict],
)
async def end_automation_session(
    udid: str,
    body: AutomationSessionRef,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
):
    """结束会话（幂等）。锁本身仍由投屏关闭/释放流程管理。"""
    session_id = body.session_id
    await _require_lock_owner(udid, session_id, current_user)
    agent_id, _ = await _agent_id_of(db, udid)
    try:
        result = await call_agent_rpc(
            agent_id, "end_app_session", {"session_id": session_id}, timeout_ms=15_000
        )
    except GatewayRpcError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except AgentRpcError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"结束会话失败：{exc}"
        ) from exc
    return ResponseModel(data=result, message="会话已结束")
