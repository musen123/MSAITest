"""APP 自动化设备 API（挂载于 /app/devices，设备域不带 /projects 前缀）。

列表返回 库存设备信息 + online 现算（所属 Agent 心跳 + adb state）+ 当前锁占用
（实时读 Redis）。control-ticket 端点先抢设备锁再签一次性 ticket（契约 §5）；
被占返回持有者信息（body code=409），同用户重复抢锁走 takeover 语义（换标签页）。
"""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, error_response, page_response, success_response
from app.crud.app_device.agent import crud_app_agent
from app.crud.app_device.control_session import crud_app_control_session
from app.crud.app_device.device import crud_app_device
from app.models.app_device.control_session import AppControlKind
from app.models.app_device.device import AppDevice
from app.models.auth.user import User
from app.services.app_device import service as app_device_service
from app.services.app_device.lock import device_lock
from app.services.app_device.ticket import issue_ticket

router = APIRouter()


def _control_ws_path(udid: str) -> str:
    return f"/api/v1/app/devices/{udid}/control/ws"


def _new_session_id() -> str:
    return f"s-{uuid.uuid4()}"


def _device_view(device: AppDevice, agent_status_value: str, holder: Optional[dict]) -> dict:
    """设备视图：库字段 + online 现算 + 当前锁占用。"""
    return {
        "id": device.id,
        "agent_id": device.agent_id,
        "serial": device.serial,
        "udid": device.udid,
        "model": device.model,
        "brand": device.brand,
        "android_version": device.android_version,
        "platform": device.platform,
        "resolution": device.resolution,
        "source": device.source,
        "connection": device.connection,
        "state": device.state,
        "project_id": device.project_id,
        "last_seen_at": device.last_seen_at,
        "agent_status": agent_status_value,
        "online": app_device_service.device_online(agent_status_value, device.state),
        "lock": holder,
    }


def _can_manage(user: User) -> bool:
    """是否有 app_device:manage（强制释放他人锁用），super_admin 直通。"""
    return "super_admin" in user.role_codes or "app_device:manage" in user.permissions


async def _resolve_owner_names(
    db: AsyncSession, holders: list[Optional[dict]]
) -> None:
    """给锁持有者补占用人显示名（real_name || username）。

    锁值只存 owner_user_id（Redis），前端要显示人名——批量查一次用户表，
    就地给每个 holder 塞 owner_name。查不到/无锁不塞（前端按 ID 兜底）。
    """
    ids = {h["owner_user_id"] for h in holders if h and h.get("owner_user_id") is not None}
    if not ids:
        return
    rows = (
        await db.execute(
            select(User.id, User.username, User.real_name).where(User.id.in_(ids))
        )
    ).all()
    name_by_id = {r.id: (r.real_name or r.username) for r in rows}
    for h in holders:
        if h and h.get("owner_user_id") in name_by_id:
            h["owner_name"] = name_by_id[h["owner_user_id"]]


@router.get("", summary="设备列表")
async def list_devices(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:view"))],
    agent_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    devices, total = await crud_app_device.get_list(
        db,
        agent_id=agent_id,
        project_id=project_id,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    # 所属 Agent 心跳一次性取全，避免逐台查库
    agents, _ = await crud_app_agent.get_list(db, limit=1000)
    status_by_agent = {
        a.id: app_device_service.agent_status(a.last_heartbeat_at) for a in agents
    }
    holders: list[Optional[dict]] = []
    for device in devices:
        try:
            holders.append(await device_lock.holder(device.udid))
        except RedisError:
            # Redis 故障时降级：库存与在线照常展示，占用信息缺失
            holders.append(None)
    await _resolve_owner_names(db, holders)
    items = [
        _device_view(device, status_by_agent.get(device.agent_id, "offline"), holder)
        for device, holder in zip(devices, holders)
    ]
    return page_response(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/{udid}/control-ticket",
    summary="抢占设备并签发控制 ticket（mode=observe 为只读观战，不占锁）",
    response_model=ResponseModel[dict],
)
async def create_control_ticket(
    udid: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
    body: Optional[dict] = None,
) -> ResponseModel[dict]:
    """先 acquire 设备锁（kind=control）再签一次性 ticket。

    被他人占用 → body code=409 + data.holder；占用者是自己 → takeover 换新
    session（同用户换标签页），旧会话审计记 takeover 结束。

    body.mode=observe（P4 观战锁）：**跳过锁**直接签只读票——自动化执行/
    他人操控期间也能观看；网关侧强制只读（丢弃入站控制字节）。观看行为
    照记审计（屏幕可能含敏感内容）。
    """
    device = await crud_app_device.get_by_udid(db, udid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="设备不存在")

    mode = str((body or {}).get("mode") or "control")
    if mode not in ("control", "observe"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="mode 只支持 control/observe"
        )
    session_id = _new_session_id()

    if mode == "observe":
        ticket = await issue_ticket(current_user.id, udid, session_id, mode="observe")
        await crud_app_control_session.create(
            db,
            session_id=session_id,
            udid=udid,
            agent_id=device.agent_id,
            owner_user_id=current_user.id,
            kind=AppControlKind.OBSERVE.value,
        )
        return ResponseModel(
            data={
                "ticket": ticket,
                "session_id": session_id,
                "ws_path": _control_ws_path(udid),
                "mode": "observe",
            },
            message="观战 ticket 已签发（只读，30 秒内有效）",
        )

    kind = AppControlKind.CONTROL.value
    acquired, holder = await device_lock.acquire(udid, current_user.id, session_id, kind)
    if not acquired:
        await _resolve_owner_names(db, [holder])  # 冲突提示带占用人名
        # 自动化任务锁（record=探索/replay=回放套件）不许经换签接管——夺走后
        # exec 图续期失败、设备被双驱动。想看进度走观战，想停走取消任务。
        if holder and holder.get("kind") in ("record", "replay"):
            return error_response(
                message="设备正被自动化任务占用（探索/回放执行中），可只读观战或取消对应任务",
                code=status.HTTP_409_CONFLICT,
                data={"holder": holder},
            )
        if holder and holder.get("owner_user_id") == current_user.id:
            if not await device_lock.takeover(udid, current_user.id, session_id, kind):
                # takeover 竞争失败（锁刚好过期/易主），按被占返回让前端重试
                fresh = await device_lock.holder(udid)
                await _resolve_owner_names(db, [fresh])
                return error_response(
                    message="设备占用状态变化，请重试",
                    code=status.HTTP_409_CONFLICT,
                    data={"holder": fresh},
                )
            old_session_id = holder.get("session_id")
            if old_session_id:
                await crud_app_control_session.end(
                    db, session_id=old_session_id, end_reason="takeover"
                )
        else:
            return error_response(
                message="设备已被占用",
                code=status.HTTP_409_CONFLICT,
                data={"holder": holder},
            )

    ticket = await issue_ticket(current_user.id, udid, session_id)
    await crud_app_control_session.create(
        db,
        session_id=session_id,
        udid=udid,
        agent_id=device.agent_id,
        owner_user_id=current_user.id,
        kind=kind,
    )
    return ResponseModel(
        data={
            "ticket": ticket,
            "session_id": session_id,
            "ws_path": _control_ws_path(udid),
            "mode": "control",
        },
        message="ticket 已签发（30 秒内有效，一次性）",
    )


@router.post("/{udid}/release", summary="释放设备锁", response_model=ResponseModel[dict])
async def release_device(
    udid: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:control"))],
    body: Optional[dict] = None,
) -> ResponseModel[dict]:
    """释放设备锁：仅锁 owner 本人，或持 app_device:manage 的强制释放。幂等。

    body.session_id（可选，CAS 语义）：只释放「自己那把」会话锁——holder 已
    易主（如投屏会话被 exec 接管）时静默 no-op。前端投屏 cleanup 必须带上，
    否则同用户的自动化任务锁会被顺手放掉（设备被无锁驱动）。
    """
    holder = await device_lock.holder(udid)
    if holder is None:
        return success_response(data={"released": False}, message="设备未被占用")

    expect_session = str((body or {}).get("session_id") or "")
    if expect_session and holder.get("session_id") != expect_session:
        # CAS 不匹配：这把锁已不是请求方那个会话的（被接管/易主），不动
        return success_response(data={"released": False}, message="会话已易主，未释放")

    is_owner = holder.get("owner_user_id") == current_user.id
    if not is_owner and not _can_manage(current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="仅锁持有者或设备管理员可释放"
        )
    # 自动化任务锁（record=探索 / replay=回放/套件）不许裸放（无 session CAS
    # 的整锁强放）——必须走取消任务（abort 帧要到真机，S级铁律），否则设备
    # 被无锁驱动。manage 强制释放放行（运维兜底，明知有残留时用）。
    if (
        not expect_session
        and holder.get("kind") in ("record", "replay")
        and not _can_manage(current_user)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="设备正被自动化任务占用，请取消对应任务而非直接释放锁",
        )

    session_id = holder.get("session_id") or ""
    released = await device_lock.release(udid, session_id)
    if released and session_id:
        await crud_app_control_session.end(
            db,
            session_id=session_id,
            end_reason="released" if is_owner else "force_released",
        )
    return success_response(data={"released": released}, message="释放成功")


@router.get(
    "/{udid}/screenshot",
    summary="设备静态截图（列表缩略图，契约 §2.1）",
    response_class=Response,
)
async def get_device_screenshot(
    udid: str,
    current_user: Annotated[User, Depends(deps.require_permission("app_device:view"))],
) -> Response:
    """返回设备最近一张静态截图（android=PNG；harmony=JPEG，按魔数嗅探 content-type）。
    无缓存（离线/未采集/已过期）→ 404。

    ⚠ 安全：设备屏幕可能含生产 App 内容（G9）。走鉴权端点，绝不落 /uploads
    静态目录；不设长缓存（画面会变），只允许私有短缓存。
    """
    from app.services.app_device.screenshot import load_screenshot

    img = await load_screenshot(udid)
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="暂无截图")
    media_type = "image/jpeg" if img[:2] == b"\xff\xd8" else "image/png"
    return Response(
        content=img,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=30"},
    )
