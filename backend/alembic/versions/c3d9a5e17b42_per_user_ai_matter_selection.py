"""per-user AI matter selection, replacing the global active collection

Revision ID: c3d9a5e17b42
Revises: 936e418b037c
Create Date: 2026-11-12 23:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d9a5e17b42'
down_revision: Union[str, Sequence[str], None] = '936e418b037c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_matter_selections',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('collection_id', sa.Uuid(), nullable=False),
        sa.Column('selected_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'collection_id'),
    )
    # The old global selection is deliberately not carried over: it was never
    # anyone's personal choice, and starting from "nothing selected" is the
    # safe default. People re-enable the matters they want from the UI.
    op.drop_table('mcp_active_collection')


def downgrade() -> None:
    op.create_table(
        'mcp_active_collection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Uuid(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute("INSERT INTO mcp_active_collection (id, collection_id) VALUES (1, NULL)")
    op.drop_table('ai_matter_selections')
