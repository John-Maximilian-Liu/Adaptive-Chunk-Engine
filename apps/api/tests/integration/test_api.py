"""API smoke tests via FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import engine as engine_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine_mod._ENGINE = None
    from app.core.config import get_settings
    get_settings.cache_clear()
    eng = engine_mod.Engine(storage_root=tmp_path / "data")
    eng.seed_development()
    engine_mod._ENGINE = eng
    with TestClient(app) as c:
        yield c
    engine_mod._ENGINE = None


def test_health_and_version(client):
    assert client.get("/api/v1/health/live").json()["status"] == "ok"
    assert client.get("/api/v1/health/ready").status_code == 200
    assert client.get("/api/v1/version").json()["name"]
    assert client.get("/api/v1/health/dependencies").status_code == 200


def test_strategies_and_dashboard(client):
    strategies = client.get("/api/v1/strategies").json()
    assert len(strategies) >= 10
    dash = client.get("/api/v1/dashboard").json()
    assert "documents" in dash


def test_upload_parse_via_api(client, fixtures_dir):
    files = {"file": ("sample.md", (fixtures_dir / "sample.md").read_bytes(), "text/markdown")}
    doc = client.post("/api/v1/documents", files=files).json()
    assert "document_id" in doc
    version = doc["latest_version_id"]
    parsed = client.post(f"/api/v1/document-versions/{version}/parse").json()
    assert parsed["status"] == "READY"
    units = client.get(f"/api/v1/document-versions/{version}/logical-units").json()
    assert units
