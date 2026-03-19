"""Async repository layer for database CRUD operations."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, N8nTemplate, Workflow, WorkflowVersion, KnowledgeNote, LearningRecord


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


# ═══════════════════════════════════════════════════════════════════
#  Workflow Versions
# ═══════════════════════════════════════════════════════════════════


class WorkflowVersionRepository:

    @staticmethod
    async def save_version(
        session: AsyncSession,
        workflow_id: str,
        name: str,
        workflow_json: dict[str, Any],
        change_summary: str | None = None,
    ) -> WorkflowVersion:
        """Save a new version snapshot for a workflow."""
        # Get next version number
        result = await session.execute(
            select(func.coalesce(func.max(WorkflowVersion.version), 0))
            .where(WorkflowVersion.workflow_id == workflow_id)
        )
        next_version = result.scalar_one() + 1

        version = WorkflowVersion(
            workflow_id=workflow_id,
            version=next_version,
            name=name,
            workflow_json=workflow_json,
            change_summary=change_summary,
        )
        session.add(version)
        await session.flush()
        return version

    @staticmethod
    async def list_versions(
        session: AsyncSession, workflow_id: str
    ) -> list[WorkflowVersion]:
        """List all versions for a workflow, newest first."""
        result = await session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_version(
        session: AsyncSession, version_id: str
    ) -> WorkflowVersion | None:
        """Get a specific version by ID."""
        try:
            vid = uuid.UUID(version_id)
        except ValueError:
            return None
        return await session.get(WorkflowVersion, vid)


# ═══════════════════════════════════════════════════════════════════
#  Knowledge Notes
# ═══════════════════════════════════════════════════════════════════


class KnowledgeNoteRepository:

    @staticmethod
    async def create(session: AsyncSession, content: str, category: str | None = None) -> KnowledgeNote:
        note = KnowledgeNote(content=content, category=category)
        session.add(note)
        await session.flush()
        return note

    @staticmethod
    async def list_all(session: AsyncSession, active_only: bool = True) -> list[KnowledgeNote]:
        stmt = select(KnowledgeNote).order_by(KnowledgeNote.created_at.desc())
        if active_only:
            stmt = stmt.where(KnowledgeNote.is_active == True)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, note_id: uuid.UUID) -> KnowledgeNote | None:
        return await session.get(KnowledgeNote, note_id)

    @staticmethod
    async def update(session: AsyncSession, note_id: uuid.UUID, content: str | None = None, category: str | None = None, is_active: bool | None = None) -> KnowledgeNote | None:
        note = await session.get(KnowledgeNote, note_id)
        if note:
            if content is not None:
                note.content = content
            if category is not None:
                note.category = category
            if is_active is not None:
                note.is_active = is_active
            await session.flush()
        return note

    @staticmethod
    async def delete(session: AsyncSession, note_id: uuid.UUID) -> bool:
        note = await session.get(KnowledgeNote, note_id)
        if note:
            await session.delete(note)
            await session.flush()
            return True
        return False

    @staticmethod
    async def search(session: AsyncSession, query: str) -> list[KnowledgeNote]:
        """Simple text search in note content."""
        result = await session.execute(
            select(KnowledgeNote)
            .where(KnowledgeNote.is_active == True)
            .where(KnowledgeNote.content.ilike(f"%{query}%"))
            .order_by(KnowledgeNote.created_at.desc())
        )
        return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════
#  n8n Templates
# ═══════════════════════════════════════════════════════════════════


class N8nTemplateRepository:

    @staticmethod
    async def create(
        session: AsyncSession,
        n8n_template_id: int,
        name: str,
        distilled_text: str,
        description: str | None = None,
        categories: list[str] | None = None,
        node_types: list[str] | None = None,
        node_count: int = 0,
        total_views: int = 0,
        chroma_doc_ids: list[str] | None = None,
    ) -> N8nTemplate:
        template = N8nTemplate(
            n8n_template_id=n8n_template_id,
            name=name,
            description=description,
            categories=categories,
            node_types=node_types,
            node_count=node_count,
            total_views=total_views,
            distilled_text=distilled_text,
            chroma_doc_ids=chroma_doc_ids,
        )
        session.add(template)
        await session.flush()
        return template

    @staticmethod
    async def get_by_n8n_id(
        session: AsyncSession, n8n_template_id: int
    ) -> N8nTemplate | None:
        result = await session.execute(
            select(N8nTemplate).where(
                N8nTemplate.n8n_template_id == n8n_template_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        category: str | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[N8nTemplate]:
        stmt = (
            select(N8nTemplate)
            .order_by(N8nTemplate.total_views.desc())
            .limit(limit)
            .offset(offset)
        )
        if active_only:
            stmt = stmt.where(N8nTemplate.is_active == True)
        if category:
            # Filter by category in JSON array
            stmt = stmt.where(
                N8nTemplate.categories.cast(func.text()).ilike(f"%{category}%")
            )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_imported_ids(session: AsyncSession) -> set[int]:
        """Get all imported n8n template IDs for quick duplicate check."""
        result = await session.execute(
            select(N8nTemplate.n8n_template_id).where(N8nTemplate.is_active == True)
        )
        return set(result.scalars().all())

    @staticmethod
    async def delete(session: AsyncSession, template_id: uuid.UUID) -> N8nTemplate | None:
        """Soft delete (deactivate) a template."""
        template = await session.get(N8nTemplate, template_id)
        if template:
            template.is_active = False
            await session.flush()
        return template

    @staticmethod
    async def hard_delete(session: AsyncSession, template_id: uuid.UUID) -> bool:
        """Permanently delete a template."""
        template = await session.get(N8nTemplate, template_id)
        if template:
            await session.delete(template)
            await session.flush()
            return True
        return False

    @staticmethod
    async def get_stats(session: AsyncSession) -> dict[str, Any]:
        """Get import statistics."""
        total_result = await session.execute(
            select(func.count()).select_from(N8nTemplate).where(N8nTemplate.is_active == True)
        )
        total = total_result.scalar_one()

        # We can't easily group by JSON array elements in SQLAlchemy,
        # so just return total count
        return {
            "total_templates": total,
        }

    @staticmethod
    async def update_chroma_ids(
        session: AsyncSession,
        template_id: uuid.UUID,
        chroma_doc_ids: list[str],
    ) -> None:
        template = await session.get(N8nTemplate, template_id)
        if template:
            template.chroma_doc_ids = chroma_doc_ids
            await session.flush()


# ═══════════════════════════════════════════════════════════════════
#  Learning Records
# ═══════════════════════════════════════════════════════════════════


class LearningRepository:

    @staticmethod
    async def record_fix(
        session: AsyncSession,
        record_type: str,
        node_type: str | None,
        description: str,
        fix_data: dict | None = None,
    ) -> LearningRecord:
        """Record a fix. If same description exists, increment frequency."""
        result = await session.execute(
            select(LearningRecord).where(
                LearningRecord.description == description
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.frequency += 1
            await session.flush()
            return existing

        record = LearningRecord(
            record_type=record_type,
            node_type=node_type,
            description=description,
            fix_data=fix_data,
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def get_relevant(
        session: AsyncSession,
        node_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[LearningRecord]:
        """Get most frequent/relevant learning records."""
        query = (
            select(LearningRecord)
            .order_by(LearningRecord.frequency.desc())
            .limit(limit)
        )
        if node_types:
            query = query.where(
                (LearningRecord.node_type.in_(node_types))
                | (LearningRecord.node_type.is_(None))
            )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_all(session: AsyncSession) -> list[LearningRecord]:
        result = await session.execute(
            select(LearningRecord).order_by(LearningRecord.frequency.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete(session: AsyncSession, record_id: uuid.UUID) -> bool:
        result = await session.execute(
            select(LearningRecord).where(LearningRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if record:
            await session.delete(record)
            await session.flush()
            return True
        return False
