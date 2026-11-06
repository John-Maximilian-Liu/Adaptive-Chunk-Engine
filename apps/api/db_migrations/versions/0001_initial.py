"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create all tables from metadata for initial bootstrap
    from app.db.base import Base
    from app.db import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.db.base import Base
    from app.db import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
