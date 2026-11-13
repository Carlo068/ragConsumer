"""add collection member roles

Revision ID: b7c41e2d9a10
Revises: 93dd4710b5c7
Create Date: 2026-11-12 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c41e2d9a10'
down_revision: Union[str, Sequence[str], None] = '93dd4710b5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

collection_role = sa.Enum('viewer', 'editor', 'owner', name='collection_role')


def upgrade() -> None:
    # Autogenerate can't do this one: adding a column that uses a Postgres
    # enum needs the type created first, by hand.
    collection_role.create(op.get_bind(), checkfirst=True)
    # Every existing member predates roles and could do everything, so they
    # become owners. server_default does the backfill, then is dropped so
    # new rows must choose a role explicitly instead of silently inheriting
    # this one.
    op.add_column(
        'collection_members',
        sa.Column('role', collection_role, server_default='owner', nullable=False),
    )
    op.alter_column('collection_members', 'role', server_default=None)


def downgrade() -> None:
    op.drop_column('collection_members', 'role')
    collection_role.drop(op.get_bind(), checkfirst=True)
