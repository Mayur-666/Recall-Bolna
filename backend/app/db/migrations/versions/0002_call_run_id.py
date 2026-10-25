"""call_sessions.bolna_run_id

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("call_sessions", sa.Column("bolna_run_id", sa.String(length=64), nullable=True))
    op.create_index("ix_call_sessions_bolna_run_id", "call_sessions", ["bolna_run_id"])


def downgrade() -> None:
    op.drop_index("ix_call_sessions_bolna_run_id", table_name="call_sessions")
    op.drop_column("call_sessions", "bolna_run_id")
