"""APP 自动化执行机 API（挂载于 /app/agents，设备域不带 /projects 前缀）。

执行机是平台级资源（宿主机），不归属单个项目，故只走 app_device:* RBAC，
不做 require_project_access。token 明文仅创建/轮转响应返回一次，库存 sha256。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, page_response
from app.crud.app_device.agent import crud_app_agent
from app.models.app_device.agent import AppAgent
from app.models.auth.user import User
from app.services.app_device import service as app_device_service

router = APIRouter()


class AgentCreateRequest(BaseModel):
    """创建执行机请求"""

    name: str = Field(..., min_length=1, max_length=64, description="执行机名称")
    host_label: Optional[str] = Field(None, max_length=128, description="宿主机标签")


def _agent_view(agent: AppAgent) -> dict:
    """执行机视图：库字段 + 现算在线状态（不含 token_hash）。"""
    return {
        "id": agent.id,
        "name": agent.name,
        "host_label": agent.host_label,
        "host_fingerprint": agent.host_fingerprint,
        "agent_version": agent.agent_version,
        "capabilities": agent.capabilities,
        "protocol_version": agent.protocol_version,
        "token_version": agent.token_version,
        "last_heartbeat_at": agent.last_heartbeat_at,
        "status": app_device_service.agent_status(agent.last_heartbeat_at),
        "created_at": agent.created_at,
    }


@router.post("", summary="创建执行机", response_model=ResponseModel[dict])
async def create_agent(
    obj_in: AgentCreateRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:manage"))],
) -> ResponseModel[dict]:
    agent, plain_token = await app_device_service.create_agent(
        db, name=obj_in.name, host_label=obj_in.host_label
    )
    return ResponseModel(
        data={**_agent_view(agent), "token": plain_token},
        message="创建成功，token 明文仅本次返回，请妥善保存",
    )


@router.get("", summary="执行机列表")
async def list_agents(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:view"))],
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    items, total = await crud_app_agent.get_list(
        db, keyword=keyword, skip=(page - 1) * page_size, limit=page_size
    )
    return page_response(
        items=[_agent_view(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{agent_id}/rotate-token",
    summary="轮转执行机 token",
    response_model=ResponseModel[dict],
)
async def rotate_agent_token(
    agent_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_device:manage"))],
) -> ResponseModel[dict]:
    result = await app_device_service.rotate_agent_token(db, agent_id=agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="执行机不存在")
    agent, plain_token = result
    return ResponseModel(
        data={**_agent_view(agent), "token": plain_token},
        message="token 已轮转，旧 token 立即失效，新明文仅本次返回",
    )
