"""Canonical Chunk Schema v1.0.0."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.ids import new_id

CHUNK_SCHEMA_VERSION = "1.0.0"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LocatorRef(BaseModel):
    page: Optional[int] = None
    slide: Optional[int] = None
    sheet: Optional[str] = None
    range: Optional[str] = None
    bbox: Optional[list[float]] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    element_id: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    heading_path: Optional[list[str]] = None
    uri: Optional[str] = None
    locator_type: Optional[str] = None


class SourceSpan(BaseModel):
    element_id: Optional[str] = None
    char_start: int = 0
    char_end: int = 0
    text_excerpt: Optional[str] = None


class LogicalUnitSpan(BaseModel):
    start_ordinal: int = 0
    end_ordinal: int = 0
    unit_ids: list[str] = Field(default_factory=list)


class CanonicalChunk(BaseModel):
    """Provider-neutral chunk schema. Library-specific fields go under extensions.provider_payload."""

    # Identity
    schema_version: str = CHUNK_SCHEMA_VERSION
    chunk_id: str = Field(default_factory=new_id)
    chunk_run_id: str
    document_id: str
    document_version_id: str
    experiment_id: Optional[str] = None
    tenant_id: str
    ordinal: int = 0
    status: str = "ready"
    chunk_type: str = "text"

    # Content
    text: str = ""
    embedding_text: Optional[str] = None
    content_format: str = "plain"
    language: Optional[str] = None
    summary: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)

    # Measurements
    character_count: int = 0
    word_count: int = 0
    token_count: int = 0
    tokenizer: str = "approx_cl100k"
    content_hash: str = ""
    embedding_text_hash: str = ""

    # Source
    logical_unit_ids: list[str] = Field(default_factory=list)
    logical_unit_span: Optional[LogicalUnitSpan] = None
    region_ids: list[str] = Field(default_factory=list)
    element_ids: list[str] = Field(default_factory=list)
    locators: list[LocatorRef] = Field(default_factory=list)
    source_spans: list[SourceSpan] = Field(default_factory=list)
    heading_path: list[str] = Field(default_factory=list)

    # Relationships
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: list[str] = Field(default_factory=list)
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    sibling_chunk_ids: list[str] = Field(default_factory=list)
    continuation_group_id: Optional[str] = None

    # Strategy
    canonical_strategy: str = "fixed_token"
    adapter_id: str = "builtin.fixed_token"
    provider: str = "builtin"
    provider_version: str = "1.0.0"
    parameters: dict[str, Any] = Field(default_factory=dict)
    effective_parameter_sources: dict[str, str] = Field(default_factory=dict)
    configuration_hash: str = ""

    # Decision evidence
    decision_id: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None
    confidence: Optional[float] = None
    profile_snapshot_id: Optional[str] = None
    supporting_element_ids: list[str] = Field(default_factory=list)
    llm_run_id: Optional[str] = None
    human_override_id: Optional[str] = None

    # Quality
    oversized: bool = False
    oversized_reason: Optional[str] = None
    source_coverage_ratio: Optional[float] = None
    duplicate_score: Optional[float] = None
    parser_confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)

    # Indexing
    indexable: bool = True
    embedding_profile_id: Optional[str] = None
    metadata_filter: dict[str, Any] = Field(default_factory=dict)

    # Visual extensions (optional)
    visual_artifact_id: Optional[str] = None
    svg_element_id: Optional[str] = None
    svg_group_id: Optional[str] = None

    # Extensions
    extensions: dict[str, Any] = Field(default_factory=lambda: {"provider_payload": {}})

    created_at: datetime = Field(default_factory=utcnow)
    modified_at: datetime = Field(default_factory=utcnow)

    def finalize_measurements(self) -> "CanonicalChunk":
        from shared.hashing import sha256_text
        from shared.tokens import count_tokens

        text = self.text or ""
        emb = self.embedding_text or text
        self.character_count = len(text)
        self.word_count = len(text.split())
        self.token_count = count_tokens(text, self.tokenizer)
        self.content_hash = sha256_text(text)
        self.embedding_text_hash = sha256_text(emb)
        return self
