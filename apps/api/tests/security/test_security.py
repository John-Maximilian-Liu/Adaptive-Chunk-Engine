"""Security-focused tests."""
from __future__ import annotations

import pytest

from app.services.engine import Engine
from audit_sdk.store import AuditStore


def test_oversized_upload_rejected(tmp_path, monkeypatch):
    from app.core.config import get_settings
    get_settings.cache_clear()
    eng = Engine(storage_root=tmp_path)
    monkeypatch.setattr(eng.settings, "max_upload_bytes", 100)
    with pytest.raises(ValueError, match="max size"):
        eng.upload_document(tenant_id="t1", filename="big.txt", content=b"x" * 200, content_type="text/plain")


def test_mime_extension_inconsistency(tmp_path):
    eng = Engine(storage_root=tmp_path)
    with pytest.raises(ValueError, match="MIME"):
        eng.upload_document(tenant_id="t1", filename="x.png", content=b"%PDF-1.4", content_type="application/pdf")


def test_cross_tenant_access(tmp_path):
    eng = Engine(storage_root=tmp_path)
    eng.seed_development()
    doc = eng.upload_document(tenant_id="tenant_a", filename="a.md", content=b"# A", content_type="text/markdown")
    with pytest.raises(KeyError):
        eng._get_version(doc["latest_version_id"], "tenant_b")


def test_secret_redaction_in_audit():
    store = AuditStore()
    ev = store.record(
        tenant_id="t", actor_type="human", actor_id="u", action="save",
        entity_type="llm", entity_id="1",
        after={"api_key": "sk-secret", "name": "x"},
    )
    assert ev.after["api_key"] == "***REDACTED***"
    assert ev.after["name"] == "x"


@pytest.mark.asyncio
async def test_invented_llm_element_ids_rejected(tmp_path):
    eng = Engine(storage_root=tmp_path)
    eng.seed_development()
    tenant = eng.settings.default_tenant_id
    demo = next(iter(eng.documents.values()))
    version_id = demo["latest_version_id"]
    ds = eng.create_qa_dataset(tenant_id=tenant, document_version_id=version_id, name="s")
    await eng.upload_qa(ds["qa_dataset_id"], tenant_id=tenant, items=[{"question": "q?", "answer": "a"}])
    await eng.complete_qa_schema(ds["qa_dataset_id"], tenant_id=tenant)
    items = [i for i in eng.qa_items.values() if i["qa_dataset_id"] == ds["qa_dataset_id"]]
    for item in items:
        for eid in item.get("expected_element_ids") or []:
            assert eid in eng.elements


def test_invalid_source_locator_excel_coverage():
    from chunk_adapters.excel import range_intersection_coverage
    assert range_intersection_coverage("NOT_A_RANGE", "A1:B2") == 0.0
