"""initial

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

# Vector size comes from the configured embedding model at upgrade time.
DIM = get_settings().EMBED_DIM

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "call_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bolna_execution_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("user_data_sent", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("transcript_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_call_sessions_bolna_execution_id"), "call_sessions", ["bolna_execution_id"], unique=False
    )
    op.create_index(op.f("ix_call_sessions_token_hash"), "call_sessions", ["token_hash"], unique=True)
    op.create_index(op.f("ix_call_sessions_user_id"), "call_sessions", ["user_id"], unique=False)
    op.create_table(
        "conversations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("conversation_date", sa.Date(), nullable=False),
        sa.Column("participants", postgresql.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("self_speaker", sa.String(length=120), nullable=True),
        sa.Column("source_type", sa.String(length=10), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "content_hash", name="uq_conversations_user_hash"),
    )
    op.create_index(op.f("ix_conversations_status"), "conversations", ["status"], unique=False)
    op.create_index(
        "ix_conversations_user_date", "conversations", ["user_id", "conversation_date"], unique=False
    )
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_table(
        "chunks",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("speakers", postgresql.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("embed_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chunks_conversation_id"), "chunks", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_chunks_user_id"), "chunks", ["user_id"], unique=False)
    op.create_table(
        "ingestion_jobs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("timings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_jobs_conversation_id"), "ingestion_jobs", ["conversation_id"], unique=False
    )
    op.create_index(op.f("ix_ingestion_jobs_status"), "ingestion_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_ingestion_jobs_user_id"), "ingestion_jobs", ["user_id"], unique=False)
    op.create_table(
        "tool_calls",
        sa.Column("call_session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=40), nullable=False),
        sa.Column("original_question", sa.Text(), nullable=True),
        sa.Column("standalone_query", sa.Text(), nullable=True),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_status", sa.String(length=24), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timings_ms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["call_session_id"], ["call_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_calls_call_session_id"), "tool_calls", ["call_session_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_user_id"), "tool_calls", ["user_id"], unique=False)
    op.create_table(
        "transcript_segments",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=120), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transcript_segments_conversation_id"),
        "transcript_segments",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_transcript_segments_user_id"), "transcript_segments", ["user_id"], unique=False)
    op.create_table(
        "memory_items",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("speaker", sa.String(length=120), nullable=True),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("owner_is_user", sa.Boolean(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("decision_state", sa.String(length=12), nullable=True),
        sa.Column("change_signal", sa.Boolean(), nullable=False),
        sa.Column("superseded_by_id", sa.UUID(), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column("topic_embedding", Vector(DIM), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', topic || ' ' || statement || ' ' || evidence_quote)", persisted=True),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["memory_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_memory_items_conversation_id"), "memory_items", ["conversation_id"], unique=False
    )
    op.create_index(op.f("ix_memory_items_user_id"), "memory_items", ["user_id"], unique=False)
    for table, col in (
        ("chunks", "embedding"),
        ("memory_items", "embedding"),
        ("memory_items", "topic_embedding"),
    ):
        op.execute(f"CREATE INDEX ix_{table}_{col}_hnsw ON {table} USING hnsw ({col} vector_cosine_ops)")
    op.execute("CREATE INDEX ix_chunks_search_tsv ON chunks USING gin (search_tsv)")
    op.execute("CREATE INDEX ix_memory_items_search_tsv ON memory_items USING gin (search_tsv)")


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_items_user_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_conversation_id"), table_name="memory_items")
    op.drop_table("memory_items")
    op.drop_index(op.f("ix_transcript_segments_user_id"), table_name="transcript_segments")
    op.drop_index(op.f("ix_transcript_segments_conversation_id"), table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_index(op.f("ix_tool_calls_user_id"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_call_session_id"), table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index(op.f("ix_ingestion_jobs_user_id"), table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_status"), table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_conversation_id"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index(op.f("ix_chunks_user_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_conversation_id"), table_name="chunks")
    op.drop_table("chunks")
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_index("ix_conversations_user_date", table_name="conversations")
    op.drop_index(op.f("ix_conversations_status"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_call_sessions_user_id"), table_name="call_sessions")
    op.drop_index(op.f("ix_call_sessions_token_hash"), table_name="call_sessions")
    op.drop_index(op.f("ix_call_sessions_bolna_execution_id"), table_name="call_sessions")
    op.drop_table("call_sessions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
