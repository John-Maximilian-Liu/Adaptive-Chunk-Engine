"""Vector sink adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.ids import new_id


class CanonicalVectorRecord(BaseModel):
    record_id: str = Field(default_factory=new_id)
    chunk_id: str
    chunk_run_id: str
    document_id: str
    document_version_id: str
    experiment_id: Optional[str] = None
    tenant_id: str
    content: str
    embedding_text: str
    vector: Optional[list[float]] = None
    canonical_metadata: dict[str, Any] = Field(default_factory=dict)
    source_locator: dict[str, Any] = Field(default_factory=dict)
    strategy: str = ""
    access_control: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    embedding_text_hash: str = ""
    # Visual metadata
    content_modality: str = "text"
    visual_artifact_id: Optional[str] = None
    svg_element_id: Optional[str] = None
    svg_group_id: Optional[str] = None
    visual_type: Optional[str] = None
    generation_strategy: Optional[str] = None


class VectorSinkProfile(BaseModel):
    vector_sink_profile_id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str
    sink_type: str  # qdrant|azure_ai_search|dify|pgvector|milvus|opensearch|pinecone|weaviate|generic_rest
    embedding_ownership: str = "engine_managed"  # engine_managed|sink_managed
    connection: dict[str, Any] = Field(default_factory=dict)
    credential_ref: Optional[str] = None
    collection_or_index: str = "ace_chunks"
    required: bool = True
    enabled: bool = True
    schema_version: str = "1.0.0"


class SearchHit(BaseModel):
    record_id: str
    chunk_id: str
    score: float
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorSinkAdapter(ABC):
    sink_type: str = "base"

    @abstractmethod
    async def validate_connection(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def ensure_collection(self, *, vector_size: int, distance: str = "Cosine") -> None:
        raise NotImplementedError

    @abstractmethod
    async def validate_schema(self, *, expected_vector_size: int) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, records: list[CanonicalVectorRecord]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def delete_by_run(self, chunk_run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def verify(self, *, chunk_run_id: str, expected_count: int) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        *,
        query_vector: Optional[list[float]] = None,
        query_text: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[SearchHit]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        raise NotImplementedError
