#!/usr/bin/env python3
"""Bootstrap generator for Adaptive Chunk Engine core packages."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def w(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n") if content.startswith("\n") else content)
    print(f"wrote {rel}")


# ---------------------------------------------------------------------------
# shared utilities
# ---------------------------------------------------------------------------
w(
    "packages/python/shared/ids.py",
    '''
"""Stable ID generation using UUIDv7 when available, else time-ordered UUID."""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional


def new_id() -> str:
    """Return a UUIDv7-like string for externally stable identifiers."""
    try:
        # Python 3.13+
        return str(uuid.uuid7())  # type: ignore[attr-defined]
    except AttributeError:
        # Time-ordered UUID (UUIDv7-compatible layout for MVP)
        ts_ms = int(time.time() * 1000)
        rand = os.urandom(10)
        # 48-bit timestamp + version/variant + random
        b = bytearray(16)
        b[0:6] = ts_ms.to_bytes(6, "big")
        b[6] = (rand[0] & 0x0F) | 0x70  # version 7
        b[7] = rand[1]
        b[8] = (rand[2] & 0x3F) | 0x80  # RFC 4122 variant
        b[9:16] = rand[3:10]
        return str(uuid.UUID(bytes=bytes(b)))


def ensure_id(value: Optional[str] = None) -> str:
    return value or new_id()
''',
)

w(
    "packages/python/shared/hashing.py",
    '''
"""Content hashing helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_text(payload)
''',
)

w(
    "packages/python/shared/tokens.py",
    '''
"""Approximate token counting (tiktoken optional)."""
from __future__ import annotations

from typing import Optional


def count_tokens(text: str, tokenizer: str = "approx_cl100k") -> int:
    if not text:
        return 0
    if tokenizer.startswith("approx"):
        # ~4 chars per token heuristic
        return max(1, (len(text) + 3) // 4)
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, (len(text) + 3) // 4)


def truncate_to_tokens(text: str, max_tokens: int, tokenizer: str = "approx_cl100k") -> str:
    if count_tokens(text, tokenizer) <= max_tokens:
        return text
    # binary-ish shrink by characters
    approx_chars = max_tokens * 4
    return text[:approx_chars]
''',
)

w(
    "packages/python/shared/pyproject.toml",
    '''
[project]
name = "ace-shared"
version = "0.1.0"
description = "Shared utilities for Adaptive Chunk Engine"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
''',
)

# ---------------------------------------------------------------------------
# canonical_schemas
# ---------------------------------------------------------------------------
w(
    "packages/python/canonical_schemas/__init__.py",
    '''
"""Canonical schemas for Adaptive Chunk Engine."""
from .chunk import CanonicalChunk, CHUNK_SCHEMA_VERSION
from .document import (
    DocumentModel,
    DocumentVersionModel,
    LogicalUnitModel,
    RegionModel,
    ElementModel,
    ElementType,
    ParseRunModel,
    ParserManifest,
    Locator,
)
from .qa import QAItem, QADataset, QA_SCHEMA_VERSION
from .visual import (
    VisualArtifact,
    VisualSceneGraph,
    VisualNode,
    VisualEdge,
    VisualGroup,
    VisualProcessingRun,
    VisualQualityResult,
    VisualProcessingPolicy,
)
from .config_field import ConfigField, ConfigSource
from .evaluation import (
    EvaluationProfile,
    MetricDefinition,
    MetricResult,
    StoppingRecommendation,
)
from .audit import AuditEvent, ProviderManifest, ReproductionManifest

__all__ = [
    "CanonicalChunk",
    "CHUNK_SCHEMA_VERSION",
    "DocumentModel",
    "DocumentVersionModel",
    "LogicalUnitModel",
    "RegionModel",
    "ElementModel",
    "ElementType",
    "ParseRunModel",
    "ParserManifest",
    "Locator",
    "QAItem",
    "QADataset",
    "QA_SCHEMA_VERSION",
    "VisualArtifact",
    "VisualSceneGraph",
    "VisualNode",
    "VisualEdge",
    "VisualGroup",
    "VisualProcessingRun",
    "VisualQualityResult",
    "VisualProcessingPolicy",
    "ConfigField",
    "ConfigSource",
    "EvaluationProfile",
    "MetricDefinition",
    "MetricResult",
    "StoppingRecommendation",
    "AuditEvent",
    "ProviderManifest",
    "ReproductionManifest",
]
''',
)

w(
    "packages/python/canonical_schemas/config_field.py",
    '''
"""Configuration field with precedence metadata."""
from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ConfigSource(str, Enum):
    HARD_ENVIRONMENT = "hard_environment"
    TENANT_POLICY = "tenant_policy"
    MANUAL_REGION = "manual_region"
    MANUAL_LOGICAL_UNIT = "manual_logical_unit"
    MANUAL_DOCUMENT = "manual_document"
    LLM_AUTO = "llm_auto"
    ENVIRONMENT_DEFAULT = "environment_default"


# Precedence: lower number wins
SOURCE_PRECEDENCE: dict[ConfigSource, int] = {
    ConfigSource.HARD_ENVIRONMENT: 1,
    ConfigSource.TENANT_POLICY: 2,
    ConfigSource.MANUAL_REGION: 3,
    ConfigSource.MANUAL_LOGICAL_UNIT: 4,
    ConfigSource.MANUAL_DOCUMENT: 5,
    ConfigSource.LLM_AUTO: 6,
    ConfigSource.ENVIRONMENT_DEFAULT: 7,
}


class ConfigField(BaseModel, Generic[T]):
    effective: Any
    source: ConfigSource
    original_proposed: Optional[Any] = None
    locked: bool = False
    mode: str = Field(default="auto", pattern="^(auto|manual)$")
    validation_result: Optional[dict[str, Any]] = None
    field_path: Optional[str] = None


def resolve_precedence(candidates: list[ConfigField]) -> ConfigField:
    """Pick the winning ConfigField by SOURCE_PRECEDENCE (lowest wins)."""
    if not candidates:
        raise ValueError("No configuration candidates provided")
    return sorted(candidates, key=lambda c: SOURCE_PRECEDENCE[c.source])[0]
''',
)

w(
    "packages/python/canonical_schemas/document.py",
    '''
"""Canonical document model."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ElementType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    TABLE_ROW = "table_row"
    CODE = "code"
    FORMULA = "formula"
    IMAGE = "image"
    CHART = "chart"
    SPEAKER_NOTE = "speaker_note"
    METADATA = "metadata"
    OCR_TEXT = "ocr_text"


class Locator(BaseModel):
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
    locator_type: Optional[str] = None  # svg_element, svg_group, image_region, etc.


class ElementModel(BaseModel):
    element_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    logical_unit_id: str
    region_id: Optional[str] = None
    element_type: ElementType
    text: str = ""
    order_index: int = 0
    locator: Locator = Field(default_factory=Locator)
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    created_at: datetime = Field(default_factory=utcnow)


class RegionModel(BaseModel):
    region_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    logical_unit_id: str
    label: Optional[str] = None
    region_type: str = "default"
    locator: Locator = Field(default_factory=Locator)
    elements: list[ElementModel] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class LogicalUnitModel(BaseModel):
    logical_unit_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    unit_type: str  # page, section, slide, sheet, image_page, virtual_page
    ordinal: int = 0
    title: Optional[str] = None
    locator: Locator = Field(default_factory=Locator)
    regions: list[RegionModel] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)
    continuation_group_id: Optional[str] = None
    previous_unit_id: Optional[str] = None
    next_unit_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class DocumentVersionModel(BaseModel):
    document_version_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_id: str
    version_number: int = 1
    filename: str
    content_type: str
    extension: str
    source_hash: str
    storage_uri: str
    byte_size: int = 0
    status: str = "uploaded"
    created_at: datetime = Field(default_factory=utcnow)
    logical_units: list[LogicalUnitModel] = Field(default_factory=list)


class DocumentModel(BaseModel):
    document_id: str = Field(default_factory=new_id)
    tenant_id: str
    title: str
    source_format: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    latest_version_id: Optional[str] = None
    audit: dict[str, Any] = Field(default_factory=dict)


class ParserManifest(BaseModel):
    provider: str
    version: str
    adapter_version: str = "1.0.0"
    fallback_used: bool = False
    capabilities: list[str] = Field(default_factory=list)
    git_commit: Optional[str] = None
    license: Optional[str] = None


class ParseRunModel(BaseModel):
    parse_run_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    status: str = "PENDING"
    parser_manifest: Optional[ParserManifest] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[dict[str, Any]] = None
    progress_percent: float = 0.0
    correlation_id: Optional[str] = None
''',
)

print("partial write complete - continuing in part 2")
print("done phase 1")
