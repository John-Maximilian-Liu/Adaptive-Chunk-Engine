"""Integration workflow tests using deterministic mock LLM (no external keys)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.engine import Engine
from app.core.config import Settings

FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"


@pytest.fixture
def engine(tmp_path):
    settings = Settings(ACE_STORAGE_ROOT=str(tmp_path / "data") if False else None)
    # Settings may not map ACE_STORAGE_ROOT that way; pass storage_root
    eng = Engine(storage_root=tmp_path / "data")
    eng.seed_development()
    return eng


@pytest.mark.asyncio
async def test_upload_parse_plan_chunk_outbox_index_qa_eval_optimize(engine: Engine, tmp_path):
    tenant = engine.settings.default_tenant_id
    content = (FIXTURES / "sample.md").read_bytes()
    doc = engine.upload_document(tenant_id=tenant, filename="sample.md", content=content, content_type="text/markdown")
    version_id = doc["latest_version_id"]
    parse = engine.parse_document_version(version_id, tenant_id=tenant)
    assert parse["status"] == "READY"
    units = [u for u in engine.logical_units.values() if u["document_version_id"] == version_id]
    assert units

    plan = await engine.auto_plan(version_id, tenant_id=tenant)
    assert plan["validation"]["valid"]

    # different strategies per unit + region override
    if len(plan["effective_plan"]["unit_strategies"]) >= 2:
        u0 = plan["effective_plan"]["unit_strategies"][0]["logical_unit_id"]
        u1 = plan["effective_plan"]["unit_strategies"][1]["logical_unit_id"]
        engine.patch_unit_strategy(plan["plan_id"], u0, tenant_id=tenant, update={"strategy_id": "heading_section", "parameters": {"chunk_size": 256, "chunk_overlap": 32}})
        engine.patch_unit_strategy(plan["plan_id"], u1, tenant_id=tenant, update={"strategy_id": "fixed_token", "parameters": {"chunk_size": 384, "chunk_overlap": 32}})
    regions = [r for r in engine.regions.values() if r["document_version_id"] == version_id]
    if regions:
        engine.patch_region_strategy(plan["plan_id"], regions[0]["region_id"], tenant_id=tenant, update={"strategy_id": "no_split", "parameters": {}})

    run = engine.create_chunk_run(tenant_id=tenant, plan_id=plan["plan_id"])
    run = engine.execute_chunk_run(run["chunk_run_id"])
    assert run["status"] == "READY"
    assert run["chunk_count"] > 0
    # outbox processed -> indexing
    assert any(ev["event_type"] == "CHUNK_RUN_COMPLETED" and ev["status"] == "PROCESSED" for ev in engine.outbox.values())
    indexing = [i for i in engine.indexing_runs.values() if i["chunk_run_id"] == run["chunk_run_id"]]
    assert indexing
    assert indexing[0]["status"] in ("READY", "PARTIAL", "FAILED")
    # Qdrant may fail if not running; still assert indexing attempted
    targets = [engine.indexing_targets[t] for t in indexing[0]["targets"]]
    assert targets

    ds = engine.create_qa_dataset(tenant_id=tenant, document_version_id=version_id, name="it", distribution={"mode": "percentage", "total": 5, "by_type": {"direct_fact": 40, "definition": 20, "table_lookup": 20, "formula_reasoning": 20}})
    gen = await engine.generate_qa(ds["qa_dataset_id"], tenant_id=tenant, count=5)
    assert gen["count"] == 5

    uploaded = await engine.upload_qa(ds["qa_dataset_id"], tenant_id=tenant, items=[{"question": "What is Total for Widget?", "answer": "20"}])
    completed = await engine.complete_qa_schema(ds["qa_dataset_id"], tenant_id=tenant)
    assert completed["completed"]

    # Force indexing READY for evaluation path when qdrant unavailable
    for t in targets:
        if t["status"] != "READY":
            t["status"] = "READY"
            t["result"] = {"verify": {"ok": True, "degraded": True, "reason": "test_force"}}
    indexing[0]["status"] = "READY"

    ev = await engine.evaluate_experiment(run["experiment_id"], tenant_id=tenant)
    assert "composite_retrieval_score" in ev
    assert "metrics" in ev["result"]
    # disabled metrics don't affect — covered in unit; ensure failures list exists
    assert isinstance(ev.get("failures"), list)

    proposal = engine.create_optimization_proposal(ev["evaluation_run_id"], tenant_id=tenant)
    assert proposal["status"] == "PROPOSED"
    reviewed = engine.review_proposal(proposal["proposal_id"], tenant_id=tenant, decision="accept")
    assert reviewed["status"] == "ACCEPTED"
    nxt = engine.create_next_experiment(proposal["proposal_id"], tenant_id=tenant)
    assert nxt["parent_experiment_id"] == run["experiment_id"]
    # ensure next experiment did not auto-run chunking
    assert not any(r.get("experiment_id") == nxt["experiment_id"] and r["status"] == "READY" for r in engine.chunk_runs.values())

    # audit trail
    events = engine.audit.list_events(tenant_id=tenant)
    assert events
    # reproduction manifest
    manifest = engine.audit.get_reproduction(run["experiment_id"])
    assert manifest is not None


@pytest.mark.asyncio
async def test_parse_multiple_formats(engine: Engine):
    tenant = engine.settings.default_tenant_id
    for name, ctype in [
        ("sample.pdf", "application/pdf"),
        ("sample.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("sample.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("sample.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("sample.md", "text/markdown"),
        ("sample.png", "image/png"),
    ]:
        doc = engine.upload_document(tenant_id=tenant, filename=name, content=(FIXTURES / name).read_bytes(), content_type=ctype)
        run = engine.parse_document_version(doc["latest_version_id"], tenant_id=tenant)
        assert run["status"] == "READY", name
