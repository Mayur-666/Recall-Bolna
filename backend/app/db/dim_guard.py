from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def check_embedding_dim(conn: AsyncConnection, expected: int) -> None:
    """Refuse to run when the stored vectors don't match the configured embedding model."""
    actual = await conn.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        )
    )
    if actual != expected:
        raise RuntimeError(
            f"DB vector dim {actual} != EMBED_DIM {expected}; run a migration + reindex (see README)"
        )
