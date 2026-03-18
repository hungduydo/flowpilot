"""Async repository layer for database CRUD operations."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, Workflow


# ═══════════════════════════════════════════════════════════════════
#  Conversations
# ═══════════════════════════════════════════════════════════════════


class ConversationRepository:

    @staticmethod
    async def create(session: AsyncSession, title: str | None = None) -> Conversation:
        conv = Conversation(title=title)
        session.add(conv)
        await session.flush()
        return conv

    @staticmethod
    async def get(
        session: AsyncSession, conversation_id: uuid.UUID
    ) -> Conversation | None:
        result = await session.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_recent(
        session: AsyncSession, limit: int = 20, offset: int = 0
    ) -> list[Conversation]:
        result = await session.execute(
            select(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_title(
        session: AsyncSession, conversation_id: uuid.UUID, title: str
    ) -> None:
        conv = await session.get(Conversation, conversation_id)
        if conv:
            conv.title = title
            await session.flush()

    @staticmethod
    async def delete(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
        conv = await session.get(Conversation, conversation_id)
        if conv:
            await session.delete(conv)
            await session.flush()
            return True
        return False


# ═══════════════════════════════════════════════════════════════════
#  Messages
# ═══════════════════════════════════════════════════════════════════


class MessageRepository:

    @staticmethod
    async def create(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            meta=metadata,
        )
        session.add(msg)
        await session.flush()
        return msg

    @staticmethod
    async def get_history(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count(session: AsyncSession, conversation_id: uuid.UUID) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        return result.scalar_one()


# ═══════════════════════════════════════════════════════════════════
#  Workflows
# ═══════════════════════════════════════════════════════════════════


class WorkflowRepository:

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str,
        workflow_json: dict[str, Any],
        conversation_id: uuid.UUID | None = None,
        n8n_workflow_id: str | None = None,
        status: str = "draft",
    ) -> Workflow:
        wf = Workflow(
            conversation_id=conversation_id,
            name=name,
            workflow_json=workflow_json,
            n8n_workflow_id=n8n_workflow_id,
            status=status,
        )
        session.add(wf)
        await session.flush()
        return wf

    @staticmethod
    async def get(session: AsyncSession, workflow_id: uuid.UUID) -> Workflow | None:
        return await session.get(Workflow, workflow_id)

    @staticmethod
    async def get_by_conversation(
        session: AsyncSession, conversation_id: uuid.UUID
    ) -> list[Workflow]:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.conversation_id == conversation_id)
            .order_by(Workflow.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        session: AsyncSession,
        workflow_id: uuid.UUID,
        status: str,
        n8n_workflow_id: str | None = None,
    ) -> None:
        wf = await session.get(Workflow, workflow_id)
        if wf:
            wf.status = status
            if n8n_workflow_id is not None:
                wf.n8n_workflow_id = n8n_workflow_id
            await session.flush()
