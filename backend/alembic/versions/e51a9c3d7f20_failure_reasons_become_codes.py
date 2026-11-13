"""document failure reasons become codes

Revision ID: e51a9c3d7f20
Revises: defda4a6ae63
Create Date: 2026-11-13 20:00:00

The worker used to store the English sentence explaining why a file failed.
It now stores a short code and the web app shows the explanation in the
reader's language, so existing English sentences are converted to their codes.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e51a9c3d7f20'
down_revision: Union[str, Sequence[str], None] = 'defda4a6ae63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (code, start of the English sentence the worker used to store)
CODES = [
    ("no_text", "No text could be found in this file"),
    ("unreadable", "This file could not be read"),
    ("timed_out", "Processing this file took too long"),
    ("index_outdated", "The search index for this matter was built with an older"),
    ("unexpected", "Something went wrong while processing this file"),
]


def upgrade() -> None:
    for code, prefix in CODES:
        op.execute(
            f"UPDATE documents SET error_message = '{code}' "
            f"WHERE error_message LIKE '{prefix}%'"
        )


def downgrade() -> None:
    # The sentences are not restored: the web app understands both forms, and a
    # code is shown as a code only to someone reading the database directly.
    pass
