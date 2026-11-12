"""pgvector extension + semantic index on memories

Revision ID: a1b2c3d4e5f6
Revises: 8835d54b7de1
Create Date: 2026-11-12

Adds real semantic search storage for PostgreSQL (no-op on SQLite).
"""
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "8835d54b7de1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_embedding_vec "
        "ON memories USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding_vec")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS embedding_vec")
