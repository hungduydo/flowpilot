"""SQLAlchemy models for conversations, messages, and workflows."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True
    )  # token counts, intent, provider, etc.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    n8n_workflow_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft, deployed, active, error

    # Relationships
    conversation: Mapped["Conversation | None"] = relationship(
        back_populates="workflows"
    )


class WorkflowVersion(Base):
    """Tracks version history for n8n workflows."""

    __tablename__ = "workflow_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # n8n workflow ID
    version: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(50), default="user", nullable=False
    )


class KnowledgeNote(Base):
    """User-defined knowledge notes injected into LLM prompts."""
    __tablename__ = "knowledge_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "node", "credential", "pattern"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class N8nTemplate(TimestampMixin, Base):
    """Imported n8n community templates for RAG knowledge enrichment."""
    __tablename__ = "n8n_templates"
    __table_args__ = (
        Index("ix_n8n_templates_n8n_id", "n8n_template_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    n8n_template_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True
    )  # The n8n.io template ID
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["Marketing", "DevOps"]
    node_types: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["n8n-nodes-base.slack", ...]
    node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distilled_text: Mapped[str] = mapped_column(Text, nullable=False)  # Embedding-friendly text
    chroma_doc_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ChromaDB chunk IDs
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LearningRecord(Base):
    """Auto-captured corrections from post-processing and user edits."""
    __tablename__ = "learning_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # "auto_fix", "user_edit", "validation_error"
    node_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g., "n8n-nodes-base.slack"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fix_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    frequency: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
