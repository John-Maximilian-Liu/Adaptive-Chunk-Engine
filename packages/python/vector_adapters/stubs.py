"""Future sink adapter contracts (not fully implemented)."""
from __future__ import annotations

from typing import Any, Optional

from vector_adapters.base import CanonicalVectorRecord, SearchHit, VectorSinkAdapter


class _StubSink(VectorSinkAdapter):
    sink_type = "stub"

    async def validate_connection(self) -> dict[str, Any]:
        return {"ok": False, "reason": f"{self.sink_type} adapter is a future contract stub"}

    async def ensure_collection(self, *, vector_size: int, distance: str = "Cosine") -> None:
        raise NotImplementedError(f"{self.sink_type} not implemented")

    async def validate_schema(self, *, expected_vector_size: int) -> dict[str, Any]:
        return {"ok": False, "reason": "stub"}

    async def upsert(self, records: list[CanonicalVectorRecord]) -> dict[str, Any]:
        raise NotImplementedError

    async def delete_by_run(self, chunk_run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def verify(self, *, chunk_run_id: str, expected_count: int) -> dict[str, Any]:
        return {"ok": False}

    async def search(self, *, query_vector=None, query_text=None, top_k=10, filters=None) -> list[SearchHit]:
        return []

    async def health_check(self) -> dict[str, Any]:
        return {"sink": self.sink_type, "status": "unimplemented", "available": False, "reason": "Future adapter contract only"}


class PgvectorSink(_StubSink):
    sink_type = "pgvector"


class MilvusSink(_StubSink):
    sink_type = "milvus"


class OpenSearchSink(_StubSink):
    sink_type = "opensearch"


class PineconeSink(_StubSink):
    sink_type = "pinecone"


class WeaviateSink(_StubSink):
    sink_type = "weaviate"


class GenericRestSink(_StubSink):
    sink_type = "generic_rest"
