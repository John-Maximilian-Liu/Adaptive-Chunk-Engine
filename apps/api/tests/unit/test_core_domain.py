"""Unit tests for core domain logic."""
from __future__ import annotations

import pytest

from canonical_schemas.config_field import ConfigField, ConfigSource, resolve_precedence
from canonical_schemas.chunk import CanonicalChunk
from canonical_schemas.evaluation import (
    EvaluationProfile,
    MetricDefinition,
    normalize_weights,
    normalize_metric_value,
    compute_composite,
    recommend_stopping,
    MetricResult,
)
from chunk_adapters.excel import range_intersection_coverage, parse_range
from chunk_adapters.builtin import FixedTokenAdapter, _validate_size_params
from chunk_adapters.base import ChunkRequest, get_registry
from canonical_schemas.document import LogicalUnitModel, ElementModel, ElementType
from evaluation_engine.hits import determine_hit
from evaluation_engine.failures import classify_failures
from evaluation_engine.optimization import generate_json_patch_proposal
from shared.hashing import sha256_text
from shared.ids import new_id


def test_config_precedence():
    fields = [
        ConfigField(effective=512, source=ConfigSource.ENVIRONMENT_DEFAULT),
        ConfigField(effective=256, source=ConfigSource.LLM_AUTO),
        ConfigField(effective=768, source=ConfigSource.MANUAL_DOCUMENT, locked=True),
        ConfigField(effective=1024, source=ConfigSource.HARD_ENVIRONMENT),
    ]
    winner = resolve_precedence(fields)
    assert winner.source == ConfigSource.HARD_ENVIRONMENT
    assert winner.effective == 1024


def test_chunk_parameter_validation_no_silent_clamp():
    result = _validate_size_params(
        {"chunk_size": 50, "chunk_overlap": 10},
        {"CHUNK_SIZE_MIN": 128, "CHUNK_SIZE_MAX": 4096, "CHUNK_OVERLAP_MAX_RATIO": 0.3},
    )
    assert not result.valid
    assert any(e["code"] == "INVALID_CHUNK_SIZE" for e in result.errors)


def test_canonical_schema_validation():
    chunk = CanonicalChunk(
        chunk_run_id=new_id(),
        document_id=new_id(),
        document_version_id=new_id(),
        tenant_id="t1",
        text="hello world",
    ).finalize_measurements()
    assert chunk.schema_version == "1.0.0"
    assert chunk.content_hash == sha256_text("hello world")
    assert chunk.character_count == 11


def test_metric_normalization_and_weights():
    metrics = [
        MetricDefinition(name="a", label="A", enabled=True, configured_weight=1, direction="higher"),
        MetricDefinition(name="b", label="B", enabled=True, configured_weight=3, direction="higher"),
        MetricDefinition(name="c", label="C", enabled=False, configured_weight=100, direction="higher"),
    ]
    weights = normalize_weights(metrics)
    assert abs(weights["a"] - 0.25) < 1e-9
    assert abs(weights["b"] - 0.75) < 1e-9
    assert "c" not in weights


def test_lower_is_better_conversion():
    assert normalize_metric_value(0.2, "lower") == pytest.approx(0.8)
    assert normalize_metric_value(0.9, "higher") == pytest.approx(0.9)


def test_weighted_composite():
    results = [
        MetricResult(name="a", raw_value=1, normalized_value=1, configured_weight=1, effective_weight=0.5, contribution=0.5, direction="higher"),
        MetricResult(name="b", raw_value=0.8, normalized_value=0.8, configured_weight=1, effective_weight=0.5, contribution=0.4, direction="higher"),
    ]
    assert compute_composite(results) == pytest.approx(0.9)


def test_stopping_recommendation():
    accept = recommend_stopping(0.95, 0.9, 0.96, 0.9, [0.01], True, 0.9)
    assert accept.recommendation == "ACCEPT"
    assert accept.automatic is False

    stop = recommend_stopping(0.905, 0.9, 0.902, 0.9, [0.001], False, 0.95)
    assert stop.recommendation == "STOP_NO_MEANINGFUL_HEADROOM"

    regress = recommend_stopping(0.8, 0.9, 0.8, 0.9, [], False, 0.95)
    assert regress.recommendation == "REGRESSION"


def test_excel_range_intersection():
    assert parse_range("Sheet1!A1:B2") == (1, 1, 2, 2)
    assert range_intersection_coverage("A1:C3", "B2:D4") == pytest.approx(4 / 9)


def test_chunk_hit_determination_element_id():
    qa = {"qa_id": "q1", "expected_element_ids": ["e1"], "evidence_quotes": []}
    chunks = [{"chunk_id": "c1", "element_ids": ["e1"], "text": "hello"}]
    hit = determine_hit(qa_item=qa, retrieved_chunks=chunks)
    assert hit.is_hit
    assert hit.stage == "element_id"


def test_chunk_hit_not_by_chunk_id_alone():
    qa = {"qa_id": "q1", "expected_element_ids": ["e9"], "evidence_quotes": [{"quote": "zzz"}]}
    chunks = [{"chunk_id": "c1", "element_ids": ["e2"], "text": "no match"}]
    hit = determine_hit(qa_item=qa, retrieved_chunks=chunks)
    assert not hit.is_hit


def test_failure_classification_split_evidence():
    qa_items = [{"qa_id": "q1", "expected_element_ids": ["e1", "e2"], "expected_logical_unit_ids": ["u1"], "evidence_quotes": [{"quote": "alpha"}]}]
    chunks = [
        {"chunk_id": "c1", "element_ids": ["e1"], "token_count": 40, "text": "alpha"},
        {"chunk_id": "c2", "element_ids": ["e2"], "token_count": 40, "text": "beta"},
    ]
    hits = [{"qa_id": "q1", "is_hit": False, "reason": "no", "details": {"per_chunk": []}}]
    failures = classify_failures(hits=hits, qa_items=qa_items, chunks=chunks)
    assert failures
    assert "EVIDENCE_SPLIT_ACROSS_CHUNKS" in failures[0].reason_codes


def test_json_patch_generation_localized():
    plan = {"unit_strategies": [{"logical_unit_id": "u1", "strategy_id": "fixed_token", "parameters": {"chunk_size": 512}}]}
    from evaluation_engine.failures import FailureRecord
    failures = [FailureRecord(
        failure_id="f1", primary_category="CHUNKING", reason_codes=["EVIDENCE_SPLIT_ACROSS_CHUNKS"],
        affected_logical_units=["u1"], affected_qa_ids=["q1"], safe_to_optimize_via_chunk_config=True,
    )]
    proposal = generate_json_patch_proposal(plan=plan, failures=failures, metrics={})
    assert proposal["changes"]
    assert proposal["changes"][0]["path"].startswith("/unit_strategies/0/")
    assert proposal["automatic_execution"] is False


def test_idempotency_key_generation():
    tenant, exp, run, chunk, sink_ver = "t", "e", "r", "c", "1"
    key = f"{tenant}:{exp}:{run}:{chunk}:{sink_ver}"
    assert key.count(":") == 4


def test_strategy_registry_lists_builtin():
    reg = get_registry()
    ids = {s.strategy_id for s in reg.list_strategies()}
    for required in ["fixed_token", "recursive_text", "excel_table_row_group", "excel_record_per_row", "excel_region", "excel_formula_dependency"]:
        assert required in ids


def test_no_enabled_metrics_raises():
    with pytest.raises(ValueError):
        normalize_weights([MetricDefinition(name="a", label="A", enabled=False, configured_weight=1)])
