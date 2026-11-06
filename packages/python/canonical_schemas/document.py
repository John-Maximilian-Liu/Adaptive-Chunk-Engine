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
    locator_type: Optional[str] = None


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
    unit_type: str
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
