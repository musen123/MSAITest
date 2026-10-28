"""智能体对话 CRUD"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat.conversation import (
    Conversation,
    ConversationStatus,
    Message,
)


class CRUDConversation:
    """对话 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        created_by: int,
        title: Optional[str] = None,
    ) -> Conversation:
        conv = Conversation(
            project_id=project_id,
            title=title or "新对话",
            status=ConversationStatus.ACTIVE.value,
            created_by=created_by,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    async def get(
        self, db: AsyncSession, conv_id: int
    ) -> Optional[Conversation]:
        return await db.get(Conversation, conv_id)

    async def list_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Conversation], int]:
        cond = [Conversation.project_id == project_id]
        if status:
            cond.append(Conversation.status == status)

        stmt = (
            select(Conversation)
            .where(*cond)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(Conversation).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def update(
        self,
        db: AsyncSession,
        *,
        conv: Conversation,
        title: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Conversation:
        if title is not None:
            conv.title = title
        if status is not None:
            conv.status = status
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    async def delete(self, db: AsyncSession, *, conv: Conversation) -> None:
        await db.delete(conv)
        await db.commit()


class CRUDMessage:
    """消息 CRUD"""

    async def list_by_conversation(
        self,
        db: AsyncSession,
        *,
        conversation_id: int,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        conversation_id: int,
        role: str,
        content: str,
        tool_calls: Optional[list] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg


crud_conversation = CRUDConversation()
crud_message = CRUDMessage()
