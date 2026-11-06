"""Adapter contract tests."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from canonical_schemas.document import ElementModel, ElementType, LogicalUnitModel, Locator
from chunk_adapters import get_registry, ChunkRequest
from document_parsers import get_parser_for, list_parsers
from llm_gateway.providers.mock import MockLLMProvider
from llm_gateway.providers.openai_provider import OpenAIProvider
from llm_gateway.providers.azure_openai import AzureOpenAIProvider
from vector_adapters.azure_ai_search import AzureAISearchSink
from vector_adapters.dify_sink import DifyKnowledgeBaseSink
from vector_adapters import CanonicalVectorRecord
from shared.ids import new_id

FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"


def _request(strategy_id: str, text: str = "Hello world. More content for chunking.") -> ChunkRequest:
    unit = LogicalUnitModel(tenant_id="t", document_version_id="v", unit_type="page", ordinal=0, title="P1")
    el = ElementModel(
        tenant_id="t", document_version_id="v", logical_unit_id=unit.logical_unit_id,
        element_type=ElementType.PARAGRAPH, text=text, locator=Locator(page=1),
    )
    return ChunkRequest(
        tenant_id="t", document_id="d", document_version_id="v", chunk_run_id="r", experiment_id="e",
        logical_unit=unit, region=None, elements=[el], strategy_id=strategy_id,
        parameters={"chunk_size": 128, "chunk_overlap": 16},
        hard_constraints={"CHUNK_SIZE_MIN": 128, "CHUNK_SIZE_MAX": 4096, "CHUNK_OVERLAP_MAX_RATIO": 0.3, "CHUNK_HARD_TOKEN_LIMIT": 4096, "CHUNK_ALLOW_OVERSIZE_ATOMIC_BLOCK": True},
    )


@pytest.mark.parametrize("strategy_id", [
    "fixed_token", "recursive_text", "sentence_window", "heading_section", "parent_child",
    "table_atomic", "table_row_group", "no_split", "skip_unit", "markdown_structural",
    "cross_unit_continuation", "spreadsheet_record", "spreadsheet_row_group", "spreadsheet_region",
    "excel_table_row_group", "excel_record_per_row", "excel_region", "excel_formula_dependency",
])
def test_chunk_adapter_contract(strategy_id):
    adapter = get_registry().get_adapter(strategy_id)
    req = _request(strategy_id)
    if strategy_id.startswith("excel") or strategy_id.startswith("spreadsheet") or strategy_id.startswith("table"):
        req.elements = [
            ElementModel(tenant_id="t", document_version_id="v", logical_unit_id=req.logical_unit.logical_unit_id,
                         element_type=ElementType.TABLE_ROW, text="a | 1", locator=Locator(sheet="Sheet1", range="A1:B1")),
            ElementModel(tenant_id="t", document_version_id="v", logical_unit_id=req.logical_unit.logical_unit_id,
                         element_type=ElementType.TABLE_ROW, text="b | 2", locator=Locator(sheet="Sheet1", range="A2:B2")),
            ElementModel(tenant_id="t", document_version_id="v", logical_unit_id=req.logical_unit.logical_unit_id,
                         element_type=ElementType.FORMULA, text="=A1", locator=Locator(sheet="Sheet1", range="C1"),
                         attributes={"formula": "=A1", "precedents": ["A1"]}),
        ]
        req.logical_unit.unit_type = "sheet"
        req.logical_unit.title = "Sheet1"
    health = adapter.health_check()
    assert "status" in health
    validation = adapter.validate(req)
    assert validation.valid
    chunks = adapter.chunk(req)
    if strategy_id != "skip_unit":
        assert isinstance(chunks, list)
        for c in chunks:
            assert c.schema_version == "1.0.0"
            assert c.canonical_strategy
            assert "provider_payload" in (c.extensions or {"provider_payload": {}})


def test_optional_adapters_report_unavailable_honestly():
    for sid in ["chunkr_external", "zchunk", "markdown_structure_chunker"]:
        d = get_registry().get_definition(sid)
        # zchunk disabled by default; chunkr needs URL
        assert d.health_status in ("unavailable", "disabled") or not d.enabled or not d.dependency_available


@pytest.mark.parametrize("fmt,file", [
    ("pdf", "sample.pdf"), ("docx", "sample.docx"), ("pptx", "sample.pptx"),
    ("xlsx", "sample.xlsx"), ("csv", "sample.csv"), ("md", "sample.md"), ("png", "sample.png"),
])
def test_parser_adapters(fmt, file):
    parser = get_parser_for(fmt)
    result = parser.parse(FIXTURES / file, tenant_id="t", document_version_id="v", filename=file)
    assert result.logical_units
    assert result.parser_manifest.provider


def test_list_parsers():
    assert len(list_parsers()) >= 8


@pytest.mark.asyncio
async def test_mock_llm_provider():
    p = MockLLMProvider(dimensions=32)
    chat = await p.chat(messages=[{"role": "user", "content": "hi"}], model="mock", response_json=True, task="qa_generation", context={"count": 2, "distribution": {"direct_fact": 2}, "elements": []})
    assert chat.provider == "mock"
    assert chat.structured
    emb = await p.embed(texts=["a", "b"], model="mock-emb", dimensions=32)
    assert len(emb.vectors) == 2
    assert len(emb.vectors[0]) == 32
    health = await p.health_check()
    assert health["available"]


@pytest.mark.asyncio
@respx.mock
async def test_openai_mock_http():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "id": "chatcmpl-1",
            "choices": [{"message": {"content": "{\"ok\":true}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    p = OpenAIProvider(api_key="sk-test")
    resp = await p.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini", response_json=True)
    assert resp.request_id == "chatcmpl-1"
    assert resp.structured == {"ok": True}


@pytest.mark.asyncio
@respx.mock
async def test_azure_openai_mock_http():
    respx.post(url__regex=r".*/openai/deployments/.*/chat/completions.*").mock(
        return_value=httpx.Response(200, json={
            "id": "azure-1",
            "choices": [{"message": {"content": "{\"ok\":true}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    p = AzureOpenAIProvider(endpoint="https://example.openai.azure.com", api_key="key")
    resp = await p.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o", response_json=True, deployment_name="gpt4")
    assert resp.provider == "azure_openai"
    assert resp.resolved_deployment == "gpt4"


@pytest.mark.asyncio
@respx.mock
async def test_azure_ai_search_contract():
    respx.get("https://search.example.net/indexes").mock(return_value=httpx.Response(200, json={"value": [{"name": "ace-chunks"}]}))
    respx.get("https://search.example.net/indexes/ace-chunks").mock(return_value=httpx.Response(404))
    respx.put("https://search.example.net/indexes/ace-chunks").mock(return_value=httpx.Response(201, json={"name": "ace-chunks"}))
    respx.post("https://search.example.net/indexes/ace-chunks/docs/index").mock(return_value=httpx.Response(200, json={"value": []}))
    respx.post("https://search.example.net/indexes/ace-chunks/docs/search").mock(return_value=httpx.Response(200, json={"@odata.count": 1, "value": [{"id": "1", "chunk_id": "c1", "@search.score": 1.0, "content": "hi", "content_modality": "text", "visual_artifact_id": ""}]}))
    sink = AzureAISearchSink(endpoint="https://search.example.net", index_name="ace-chunks", api_key="key")
    assert (await sink.validate_connection())["ok"]
    await sink.ensure_collection(vector_size=8)
    rec = CanonicalVectorRecord(
        chunk_id="c1", chunk_run_id="r1", document_id="d", document_version_id="v", tenant_id="t",
        content="hi", embedding_text="hi", vector=[0.1] * 8, content_modality="text", visual_artifact_id="va1",
    )
    await sink.upsert([rec])
    hits = await sink.search(query_vector=[0.1] * 8, top_k=1)
    assert hits
    # metadata mapping fields present in recommended schema
    from vector_adapters.azure_ai_search import RECOMMENDED_FIELDS
    assert "visual_artifact_id" in RECOMMENDED_FIELDS
    assert "content_modality" in RECOMMENDED_FIELDS


@pytest.mark.asyncio
@respx.mock
async def test_dify_contract():
    respx.get("https://dify.example/v1/datasets/ds1").mock(return_value=httpx.Response(200, json={"id": "ds1", "name": "kb"}))
    respx.post("https://dify.example/v1/datasets/ds1/document/create-by-text").mock(return_value=httpx.Response(200, json={"document": {"id": "doc1"}}))
    respx.post(url__regex=r".*/documents/.*/segments").mock(return_value=httpx.Response(200, json={"data": [{"id": "seg1"}]}))
    respx.get("https://dify.example/v1/datasets/ds1/documents/doc1").mock(return_value=httpx.Response(200, json={"indexing_status": "completed"}))
    respx.get("https://dify.example/v1/datasets/ds1/documents/doc1/segments").mock(return_value=httpx.Response(200, json={"data": [{"id": "seg1", "content": "[ace_chunk_id=c1] hi"}]}))
    respx.post("https://dify.example/v1/datasets/ds1/retrieve").mock(return_value=httpx.Response(200, json={"records": [{"score": 0.9, "segment": {"id": "seg1", "content": "[ace_chunk_id=c1] hi"}}]}))
    sink = DifyKnowledgeBaseSink(base_url="https://dify.example/v1", api_key="k", dataset_id="ds1")
    assert (await sink.validate_connection())["ok"]
    await sink.ensure_collection(vector_size=8)
    rec = CanonicalVectorRecord(
        chunk_id="c1", chunk_run_id="r1", document_id="d", document_version_id="v", tenant_id="t",
        content="hi", embedding_text="hi", content_modality="text",
    )
    result = await sink.upsert([rec])
    assert result["embedding_ownership"] == "sink_managed"
    assert result["upserted"] >= 1
    verify = await sink.verify(chunk_run_id="r1", expected_count=1)
    assert verify["ok"]
    hits = await sink.search(query_text="hi", top_k=3)
    assert hits[0].chunk_id == "c1"
    assert hits[0].metadata.get("not_directly_comparable") is True
