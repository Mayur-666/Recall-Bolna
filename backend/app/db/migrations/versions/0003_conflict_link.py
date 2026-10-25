"""memory_items.conflict_with_id

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memory_items", sa.Column("conflict_with_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_memory_items_conflict_with", "memory_items", "memory_items", ["conflict_with_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_memory_items_conflict_with", "memory_items", type_="foreignkey")
    op.drop_column("memory_items", "conflict_with_id")
