"""Audit and reproduction manifests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProviderManifest(BaseModel):
    provider_manifest_id: str = Field(default_factory=new_id)
    provider: str
    version: str
    git_commit: Optional[str] = None
    runtime_image_digest: Optional[str] = None
    dependency_lock_hash: Optional[str] = None
    license: Optional[str] = None
    adapter_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=utcnow)


class ReproductionManifest(BaseModel):
    reproduction_manifest_id: str = Field(default_factory=new_id)
    experiment_id: str
    tenant_id: str
    document_version_id: str
    parser_profile: dict[str, Any] = Field(default_factory=dict)
    chunk_plan_version: Optional[str] = None
    provider_manifests: list[ProviderManifest] = Field(default_factory=list)
    qa_dataset_version: Optional[str] = None
    evaluation_profile_version: Optional[str] = None
    retrieval_profile: dict[str, Any] = Field(default_factory=dict)
    embedding_profile: dict[str, Any] = Field(default_factory=dict)
    embedding_model_revision: Optional[str] = None
    target_sink: Optional[str] = None
    index_namespace: Optional[str] = None
    random_seed: Optional[int] = None
    effective_environment_constraints: dict[str, Any] = Field(default_factory=dict)
    complete: bool = False
    created_at: datetime = Field(default_factory=utcnow)

    def mark_complete(self) -> "ReproductionManifest":
        required = [
            self.document_version_id,
            self.chunk_plan_version,
            self.qa_dataset_version,
            self.evaluation_profile_version,
            self.embedding_profile,
            self.target_sink,
        ]
        self.complete = all(bool(x) for x in required) and len(self.provider_manifests) > 0
        return self


class AuditEvent(BaseModel):
    audit_event_id: str = Field(default_factory=new_id)
    tenant_id: str
    actor_type: str  # human|llm|system
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    patch: Optional[list[dict[str, Any]]] = None
    timestamp: datetime = Field(default_factory=utcnow)
    correlation_id: Optional[str] = None
    source_ip: Optional[str] = None
    origin: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)
