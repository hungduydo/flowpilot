"""create n8n_templates table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "n8n_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("n8n_template_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("node_types", sa.JSON(), nullable=True),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_views", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("distilled_text", sa.Text(), nullable=False),
        sa.Column("chroma_doc_ids", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_n8n_templates_n8n_id", "n8n_templates", ["n8n_template_id"], unique=True)
    op.create_index("ix_n8n_templates_active", "n8n_templates", ["is_active"])

def downgrade() -> None:
    op.drop_index("ix_n8n_templates_active")
    op.drop_index("ix_n8n_templates_n8n_id")
    op.drop_table("n8n_templates")
