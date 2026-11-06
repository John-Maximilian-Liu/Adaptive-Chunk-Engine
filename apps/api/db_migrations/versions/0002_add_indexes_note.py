"""add documentation note for upgrade path

Revision ID: 0002_add_indexes_note
Revises: 0001_initial
Create Date: 2026-11-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_add_indexes_note"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Placeholder revision to exercise upgrade-from-previous migration tests.
    op.execute("SELECT 1")


def downgrade() -> None:
    op.execute("SELECT 1")
