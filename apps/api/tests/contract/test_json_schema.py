"""Canonical JSON Schema contract tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate

from canonical_schemas.chunk import CanonicalChunk
from shared.ids import new_id

SCHEMA = Path(__file__).resolve().parents[4] / "contracts" / "json-schema" / "canonical-chunk-1.0.0.json"


def test_canonical_chunk_schema_contract():
    schema = json.loads(SCHEMA.read_text())
    chunk = CanonicalChunk(
        chunk_run_id=new_id(),
        document_id=new_id(),
        document_version_id=new_id(),
        tenant_id="t",
        text="hello",
    ).finalize_measurements()
    validate(instance=chunk.model_dump(mode="json"), schema=schema)


def test_unnormalized_provider_payload_not_top_level():
    chunk = CanonicalChunk(
        chunk_run_id=new_id(), document_id=new_id(), document_version_id=new_id(), tenant_id="t", text="x",
        extensions={"provider_payload": {"library_specific": True}},
    )
    data = chunk.model_dump()
    assert "library_specific" not in data
    assert data["extensions"]["provider_payload"]["library_specific"] is True
