"""Migration smoke using SQLAlchemy metadata create/drop (SQLite)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text


def test_empty_db_to_latest_metadata(tmp_path):
    from app.db.base import Base
    from app.db import models  # noqa: F401

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    names = {t[0] for t in tables}
    for required in ["documents", "chunks", "outbox_events", "evaluation_runs", "audit_events"]:
        assert required in names
    Base.metadata.drop_all(engine)
