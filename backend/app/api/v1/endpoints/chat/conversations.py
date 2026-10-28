"""对话会话 CRUD API"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.chat.conversation import crud_conversation, crud_message
from app.models.auth.user import User
from app.schemas.chat.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.post(
    "",
    summary="创建对话",
    response_model=ResponseModel[ConversationResponse],
)
async def create_conversation(
    project_id: int,
    body: ConversationCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("chat:use"))
    ],
) -> ResponseModel[ConversationResponse]:
    await require_project_access(db, project_id, current_user.id)
    conv = await crud_conversation.create(
        db,
        project_id=project_id,
        title=body.title,
        created_by=current_user.id,
    )
    return success_response(data=ConversationResponse.model_validate(conv))


@router.get(
    "",
    summary="获取对话列表",
    response_model=ResponseModel[ConversationListResponse],
)
async def list_conversations(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("chat:use"))
    ],
    status_: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[ConversationListResponse]:
    await require_project_access(db, project_id, current_user.id)
    items, total = await crud_conversation.list_by_project(
        db,
        project_id=project_id,
        status=status_,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return success_response(
        data=ConversationListResponse(
            total=total,
            items=[ConversationResponse.model_validate(c) for c in items],
        )
    )


@router.get(
    "/{conv_id}",
    summary="获取对话详情（含消息列表）",
    response_model=ResponseModel[ConversationDetail],
)
async def get_conversation(
    project_id: int,
    conv_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("chat:use"))
    ],
) -> ResponseModel[ConversationDetail]:
    await require_project_access(db, project_id, current_user.id)
    conv = await crud_conversation.get(db, conv_id)
    if not conv or conv.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")

    msgs = await crud_message.list_by_conversation(db, conversation_id=conv_id)
    # 不能直接 model_validate(conv)：ConversationDetail 的 messages 字段会
    # 触发 ORM 关系的同步惰性加载（异步驱动下 MissingGreenlet）
    detail = ConversationDetail(
        **ConversationResponse.model_validate(conv).model_dump(),
        messages=[MessageResponse.model_validate(m) for m in msgs],
    )
    return success_response(data=detail)


@router.patch(
    "/{conv_id}",
    summary="更新对话",
    response_model=ResponseModel[ConversationResponse],
)
async def update_conversation(
    project_id: int,
    conv_id: int,
    body: ConversationUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("chat:use"))
    ],
) -> ResponseModel[ConversationResponse]:
    await require_project_access(db, project_id, current_user.id)
    conv = await crud_conversation.get(db, conv_id)
    if not conv or conv.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")
    conv = await crud_conversation.update(
        db, conv=conv, title=body.title, status=body.status
    )
    return success_response(data=ConversationResponse.model_validate(conv))


@router.delete(
    "/{conv_id}",
    summary="删除对话",
    response_model=ResponseModel,
)
async def delete_conversation(
    project_id: int,
    conv_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("chat:use"))
    ],
) -> ResponseModel:
    await require_project_access(db, project_id, current_user.id)
    conv = await crud_conversation.get(db, conv_id)
    if not conv or conv.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")
    await crud_conversation.delete(db, conv=conv)
    return success_response(message="对话已删除")
