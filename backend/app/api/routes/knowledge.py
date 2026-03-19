"""API routes for user knowledge notes and learning records."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.repositories import KnowledgeNoteRepository, LearningRepository

router = APIRouter()


class NoteCreate(BaseModel):
    content: str
    category: str | None = None


class NoteUpdate(BaseModel):
    content: str | None = None
    category: str | None = None
    is_active: bool | None = None


@router.get("/knowledge/notes")
async def list_notes(
    active_only: bool = True,
    session: AsyncSession = Depends(get_db),
):
    notes = await KnowledgeNoteRepository.list_all(session, active_only=active_only)
    return [
        {
            "id": str(n.id),
            "content": n.content,
            "category": n.category,
            "is_active": n.is_active,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n in notes
    ]


@router.post("/knowledge/notes", status_code=201)
async def create_note(
    body: NoteCreate,
    session: AsyncSession = Depends(get_db),
):
    note = await KnowledgeNoteRepository.create(session, body.content, body.category)
    return {
        "id": str(note.id),
        "content": note.content,
        "category": note.category,
        "is_active": note.is_active,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


@router.put("/knowledge/notes/{note_id}")
async def update_note(
    note_id: str,
    body: NoteUpdate,
    session: AsyncSession = Depends(get_db),
):
    try:
        nid = uuid.UUID(note_id)
    except ValueError:
        raise HTTPException(400, "Invalid note ID")
    note = await KnowledgeNoteRepository.update(
        session, nid,
        content=body.content,
        category=body.category,
        is_active=body.is_active,
    )
    if not note:
        raise HTTPException(404, "Note not found")
    return {
        "id": str(note.id),
        "content": note.content,
        "category": note.category,
        "is_active": note.is_active,
    }


@router.delete("/knowledge/notes/{note_id}", status_code=204)
async def delete_note(
    note_id: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        nid = uuid.UUID(note_id)
    except ValueError:
        raise HTTPException(400, "Invalid note ID")
    deleted = await KnowledgeNoteRepository.delete(session, nid)
    if not deleted:
        raise HTTPException(404, "Note not found")


# ═══════════════════════════════════════════════════════════════════
#  Learning Records (auto-captured corrections)
# ═══════════════════════════════════════════════════════════════════


@router.get("/knowledge/learning/records")
async def list_learning_records(
    session: AsyncSession = Depends(get_db),
):
    records = await LearningRepository.list_all(session)
    return [
        {
            "id": str(r.id),
            "record_type": r.record_type,
            "node_type": r.node_type,
            "description": r.description,
            "frequency": r.frequency,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.delete("/knowledge/learning/records/{record_id}", status_code=204)
async def delete_learning_record(
    record_id: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "Invalid record ID")
    deleted = await LearningRepository.delete(session, rid)
    if not deleted:
        raise HTTPException(404, "Record not found")
