"""account lifecycle: disable users, server-side sessions, password resets

Revision ID: a8f3c2d94b11
Revises: e51a9c3d7f20
Create Date: 2026-11-13

Additive only (see docs/deployment/06-deploy-and-rollback.md): a new column with
a default, a new table, a new column on invites with a default, and an index.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8f3c2d94b11"
down_revision: Union[str, Sequence[str], None] = "e51a9c3d7f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("invites", sa.Column("kind", sa.String(length=16), nullable=False, server_default="invite"))
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    # Login throttling counts recent failed logins.
    op.create_index("ix_audit_log_action_occurred_at", "audit_log", ["action", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_action_occurred_at", table_name="audit_log")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_column("invites", "kind")
    op.drop_column("users", "is_active")
