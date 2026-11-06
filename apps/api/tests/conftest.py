from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # apps/api
REPO = Path(__file__).resolve().parents[3]  # workspace
FIXTURES = REPO / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "packages" / "python"))
sys.path.insert(0, str(REPO / "workers"))

import pytest


@pytest.fixture(autouse=True)
def _reset_engine():
    # Ensure tests don't share global engine state unexpectedly across modules
    from app.services import engine as engine_mod
    from app.core.config import get_settings
    engine_mod._ENGINE = None
    get_settings.cache_clear()
    yield
    engine_mod._ENGINE = None
    get_settings.cache_clear()


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
