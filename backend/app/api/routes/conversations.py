"""Conversation management endpoints."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    ConversationRepository,
    MessageRepository,
    WorkflowRepository,
)
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
    WorkflowSummary,
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List recent conversations."""
    convs = await ConversationRepository.list_recent(db, limit=limit, offset=offset)
    items = []
    for c in convs:
        msg_count = await MessageRepository.count(db, c.id)
        items.append(
            ConversationResponse(
                id=str(c.id),
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=msg_count,
            )
        )
    return ConversationListResponse(conversations=items, total=len(items))


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new empty conversation."""
    conv = await ConversationRepository.create(db, title=body.title)
    return ConversationResponse(
        id=str(conv.id),
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get conversation with full message history and workflows."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conv = await ConversationRepository.get(db, conv_uuid)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await MessageRepository.get_history(db, conv.id)
    workflows = await WorkflowRepository.get_by_conversation(db, conv.id)

    return ConversationDetailResponse(
        id=str(conv.id),
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                metadata=m.meta,
                created_at=m.created_at,
            )
            for m in messages
        ],
        workflows=[
            WorkflowSummary(
                id=str(w.id),
                name=w.name,
                n8n_workflow_id=w.n8n_workflow_id,
                status=w.status,
                created_at=w.created_at,
            )
            for w in workflows
        ],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update conversation title."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conv = await ConversationRepository.get(db, conv_uuid)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await ConversationRepository.update_title(db, conv_uuid, body.title)
    msg_count = await MessageRepository.count(db, conv_uuid)

    return ConversationResponse(
        id=str(conv.id),
        title=body.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=msg_count,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all related messages/workflows."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    deleted = await ConversationRepository.delete(db, conv_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
