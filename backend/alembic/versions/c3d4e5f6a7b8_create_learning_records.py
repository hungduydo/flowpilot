"""create learning_records table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-19 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "learning_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("record_type", sa.String(30), nullable=False),
        sa.Column("node_type", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("fix_data", sa.JSON(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_learning_records_node_type", "learning_records", ["node_type"])
    op.create_index("ix_learning_records_frequency", "learning_records", ["frequency"])

def downgrade() -> None:
    op.drop_index("ix_learning_records_frequency")
    op.drop_index("ix_learning_records_node_type")
    op.drop_table("learning_records")
