import pytest
from sqlalchemy import text

from app.db.dim_guard import check_embedding_dim

EXPECTED_TABLES = {
    "users",
    "conversations",
    "transcript_segments",
    "chunks",
    "memory_items",
    "ingestion_jobs",
    "call_sessions",
    "tool_calls",
}


async def test_migration_creates_tables(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        tables = {r[0] for r in rows}
        assert EXPECTED_TABLES <= tables

        dim = await conn.scalar(
            text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid='chunks'::regclass AND attname='embedding'"
            )
        )
        assert dim == 768

        idx = await conn.execute(text("SELECT indexdef FROM pg_indexes WHERE schemaname='public'"))
        defs = " ".join(r[0] for r in idx)
        assert "USING hnsw (embedding vector_cosine_ops)" in defs
        assert "USING gin (search_tsv)" in defs

        cols = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name='call_sessions'")
        )
        assert "bolna_run_id" in {r[0] for r in cols}


async def test_dim_guard_raises_on_mismatch(db_engine):
    async with db_engine.connect() as conn:
        await check_embedding_dim(conn, 768)  # matches: no error
        with pytest.raises(RuntimeError, match="EMBED_DIM"):
            await check_embedding_dim(conn, 1024)
