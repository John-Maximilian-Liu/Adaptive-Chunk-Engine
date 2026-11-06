
"""SQLAlchemy 2.x models for Adaptive Chunk Engine."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base
from shared.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Use JSON which works on SQLite and Postgres; Postgres can cast to JSONB in migration
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActorRef(Base):
    __tablename__ = "actors"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="human")
    display_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    source_format: Mapped[str] = mapped_column(String(32))
    latest_version_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    audit: Mapped[dict] = mapped_column(JSONType, default=dict)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_id: Mapped[str] = mapped_column(String(64), ForeignKey("documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    extension: Mapped[str] = mapped_column(String(32))
    source_hash: Mapped[str] = mapped_column(String(128))
    storage_uri: Mapped[str] = mapped_column(String(1024))
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_doc_version"),)


class LogicalUnit(Base):
    __tablename__ = "logical_units"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("document_versions.id"), index=True)
    unit_type: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    locator: Mapped[dict] = mapped_column(JSONType, default=dict)
    profile: Mapped[dict] = mapped_column(JSONType, default=dict)
    continuation_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    previous_unit_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    next_unit_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    logical_unit_id: Mapped[str] = mapped_column(String(64), ForeignKey("logical_units.id"), index=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    region_type: Mapped[str] = mapped_column(String(64), default="default")
    locator: Mapped[dict] = mapped_column(JSONType, default=dict)
    profile: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Element(Base):
    __tablename__ = "elements"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    logical_unit_id: Mapped[str] = mapped_column(String(64), ForeignKey("logical_units.id"), index=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("regions.id"), nullable=True)
    element_type: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    locator: Mapped[dict] = mapped_column(JSONType, default=dict)
    attributes: Mapped[dict] = mapped_column(JSONType, default=dict)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ParseRun(Base):
    __tablename__ = "parse_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    parser_manifest: Mapped[dict] = mapped_column(JSONType, default=dict)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    worker_identity: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class PageProfile(Base):
    __tablename__ = "page_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    logical_unit_id: Mapped[str] = mapped_column(String(64), index=True)
    profile: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StrategyDefinitionRow(Base):
    __tablename__ = "strategy_definitions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255))
    adapter_id: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(128))
    provider_version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class StrategyParameterSchema(Base):
    __tablename__ = "strategy_parameter_schemas"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    strategy_id: Mapped[str] = mapped_column(String(64), index=True)
    schema_json: Mapped[dict] = mapped_column(JSONType, default=dict)


class ChunkPlan(Base):
    __tablename__ = "chunk_plans"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    proposed_plan: Mapped[dict] = mapped_column(JSONType, default=dict)
    effective_plan: Mapped[dict] = mapped_column(JSONType, default=dict)
    validation: Mapped[dict] = mapped_column(JSONType, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LogicalUnitStrategyConfig(Base):
    __tablename__ = "logical_unit_strategy_configs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("chunk_plans.id"), index=True)
    logical_unit_id: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)


class RegionStrategyConfig(Base):
    __tablename__ = "region_strategy_configs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("chunk_plans.id"), index=True)
    region_id: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)


class StrategyChangeEvent(Base):
    __tablename__ = "strategy_change_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    before: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    after: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    chunk_plan_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parent_experiment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChunkRun(Base):
    __tablename__ = "chunk_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    experiment_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_plan_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    worker_identity: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChunkRow(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("chunk_runs.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    experiment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    content_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    embedding_text_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_chunks_run_ordinal", "chunk_run_id", "ordinal"),)


class ChunkSourceMapping(Base):
    __tablename__ = "chunk_source_mappings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    chunk_id: Mapped[str] = mapped_column(String(64), index=True)
    element_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    logical_unit_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    locator: Mapped[dict] = mapped_column(JSONType, default=dict)


class QADatasetRow(Base):
    __tablename__ = "qa_datasets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    distribution: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QAItemRow(Base):
    __tablename__ = "qa_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    qa_dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("qa_datasets.id"), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QAEvidenceMapping(Base):
    __tablename__ = "qa_evidence_mappings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    qa_id: Mapped[str] = mapped_column(String(64), index=True)
    element_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quote: Mapped[str] = mapped_column(Text, default="")
    locator: Mapped[dict] = mapped_column(JSONType, default=dict)


class EvaluationProfileRow(Base):
    __tablename__ = "evaluation_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    experiment_id: Mapped[str] = mapped_column(String(64), index=True)
    evaluation_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    result: Mapped[dict] = mapped_column(JSONType, default=dict)
    composite_retrieval_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), index=True)
    qa_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class MetricResultRow(Base):
    __tablename__ = "metric_results"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class FailureAnalysis(Base):
    __tablename__ = "failure_analyses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class OptimizationProposal(Base):
    __tablename__ = "optimization_proposals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProposalChange(Base):
    __tablename__ = "proposal_changes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    proposal_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(Text, default="")
    actor_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LLMProfileRow(Base):
    __tablename__ = "llm_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    credential_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class EmbeddingProfileRow(Base):
    __tablename__ = "embedding_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    credential_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class LLMRun(Base):
    __tablename__ = "llm_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VectorSinkProfileRow(Base):
    __tablename__ = "vector_sink_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    credential_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class IndexingRun(Base):
    __tablename__ = "indexing_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_run_id: Mapped[str] = mapped_column(String(64), index=True)
    experiment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class IndexingTargetRun(Base):
    __tablename__ = "indexing_target_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    indexing_run_id: Mapped[str] = mapped_column(String(64), index=True)
    sink_profile_id: Mapped[str] = mapped_column(String(64))
    sink_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    result: Mapped[dict] = mapped_column(JSONType, default=dict)
    error: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)


class VectorSinkRecordMapping(Base):
    __tablename__ = "vector_sink_record_mappings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    sink_profile_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    __table_args__ = (UniqueConstraint("sink_profile_id", "chunk_id", name="uq_sink_chunk"),)


class ProviderManifestRow(Base):
    __tablename__ = "provider_manifests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReproductionManifestRow(Base):
    __tablename__ = "reproduction_manifests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64))
    aggregate_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_outbox_status_created", "status", "created_at"),)


class VisualArtifactRow(Base):
    __tablename__ = "visual_artifacts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class VisualProcessingRunRow(Base):
    __tablename__ = "visual_processing_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")


class CredentialSecret(Base):
    """Backend-only secrets — never returned by API."""
    __tablename__ = "credential_secrets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    credential_ref: Mapped[str] = mapped_column(String(128), unique=True)
    secret_value: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
