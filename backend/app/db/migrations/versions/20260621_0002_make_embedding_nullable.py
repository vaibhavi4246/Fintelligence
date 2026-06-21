"""make chunks.embedding nullable

Revision ID: 20260621_0002
Revises: 20260619_0001
Create Date: 2026-06-21

Chunks are inserted before embedding; the NOT NULL constraint was premature.
"""
from alembic import op

revision = "20260621_0002"
down_revision = "20260619_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("chunks", "embedding", nullable=True)


def downgrade() -> None:
    op.alter_column("chunks", "embedding", nullable=False)
