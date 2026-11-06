"""Visual processing schemas."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VisualProcessingPolicy(BaseModel):
    enabled: bool = True
    mode: str = "auto"  # disabled|auto|manual
    generate_ocr: bool = True
    generate_caption: bool = True
    generate_svg: bool = True
    generate_multimodal_embedding: bool = False
    svg_strategy: str = "auto"  # preserve_existing_svg|extract_native_vector|geometric_trace|semantic_reconstruction|auto|disabled
    svg_indexing_granularity: str = "group"  # summary|group|node|relationship
    minimum_confidence: float = 0.80
    fallback_behavior: str = "retain_raster"
    original_raster_retention: bool = True


class VisualNode(BaseModel):
    node_id: str = Field(default_factory=new_id)
    label: str = ""
    node_type: str = "shape"
    bbox: Optional[list[float]] = None
    source_element_id: Optional[str] = None
    svg_element_id: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class VisualEdge(BaseModel):
    edge_id: str = Field(default_factory=new_id)
    source_node_id: str
    target_node_id: str
    label: str = ""
    edge_type: str = "connects"
    svg_element_id: Optional[str] = None
    confidence: float = 1.0


class VisualGroup(BaseModel):
    group_id: str = Field(default_factory=new_id)
    label: str = ""
    node_ids: list[str] = Field(default_factory=list)
    svg_group_id: Optional[str] = None
    bbox: Optional[list[float]] = None


class VisualSceneGraph(BaseModel):
    scene_graph_id: str = Field(default_factory=new_id)
    nodes: list[VisualNode] = Field(default_factory=list)
    edges: list[VisualEdge] = Field(default_factory=list)
    groups: list[VisualGroup] = Field(default_factory=list)
    validated: bool = False
    validation_errors: list[str] = Field(default_factory=list)


class VisualArtifact(BaseModel):
    visual_artifact_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    source_element_id: Optional[str] = None
    artifact_type: str  # raster|ocr|caption|native_svg|geometric_svg|semantic_svg|scene_graph
    storage_uri: Optional[str] = None
    sanitized_storage_uri: Optional[str] = None
    content_text: Optional[str] = None
    mime_type: Optional[str] = None
    generation_strategy: Optional[str] = None
    provider: Optional[str] = None
    provider_version: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[list[float]] = None
    page: Optional[int] = None
    slide: Optional[int] = None
    sheet: Optional[str] = None
    region_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class VisualQualityResult(BaseModel):
    quality_id: str = Field(default_factory=new_id)
    visual_artifact_id: str
    confidence: float
    element_count: int = 0
    path_command_count: int = 0
    nesting_depth: int = 0
    byte_size: int = 0
    warnings: list[str] = Field(default_factory=list)
    passed: bool = True
    fallback_used: bool = False


class VisualProcessingRun(BaseModel):
    visual_run_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    status: str = "PENDING"
    policy: VisualProcessingPolicy = Field(default_factory=VisualProcessingPolicy)
    artifacts: list[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[dict[str, Any]] = None
    correlation_id: Optional[str] = None
