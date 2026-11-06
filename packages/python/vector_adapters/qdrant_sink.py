"""Qdrant vector sink for local development."""
from __future__ import annotations

from typing import Any, Optional

from vector_adapters.base import CanonicalVectorRecord, SearchHit, VectorSinkAdapter


class QdrantSink(VectorSinkAdapter):
    sink_type = "qdrant"

    def __init__(self, url: str = "http://localhost:6333", collection: str = "ace_chunks", api_key: Optional[str] = None):
        self.url = url.rstrip("/")
        self.collection = collection
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=False,
                check_compatibility=False,
            )
        return self._client

    async def validate_connection(self) -> dict[str, Any]:
        client = self._get_client()
        info = client.get_collections()
        return {"ok": True, "collections": [c.name for c in info.collections]}

    async def ensure_collection(self, *, vector_size: int, distance: str = "Cosine") -> None:
        from qdrant_client.http import models as qm
        client = self._get_client()
        existing = [c.name for c in client.get_collections().collections]
        if self.collection not in existing:
            dist = getattr(qm.Distance, distance.upper(), qm.Distance.COSINE)
            client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=vector_size, distance=dist),
            )

    async def validate_schema(self, *, expected_vector_size: int) -> dict[str, Any]:
        client = self._get_client()
        info = client.get_collection(self.collection)
        size = info.config.params.vectors.size  # type: ignore[union-attr]
        ok = size == expected_vector_size
        return {"ok": ok, "vector_size": size, "expected": expected_vector_size}

    async def upsert(self, records: list[CanonicalVectorRecord]) -> dict[str, Any]:
        from qdrant_client.http import models as qm
        client = self._get_client()
        # Idempotent upserts: stable point IDs keyed by tenant/run/chunk so retries do not duplicate.
        points = []
        for r in records:
            if r.vector is None:
                raise ValueError("Qdrant requires engine-managed embeddings (vector must be set)")
            payload = {
                "chunk_id": r.chunk_id,
                "chunk_run_id": r.chunk_run_id,
                "document_id": r.document_id,
                "document_version_id": r.document_version_id,
                "experiment_id": r.experiment_id,
                "tenant_id": r.tenant_id,
                "content": r.content,
                "embedding_text": r.embedding_text,
                "strategy": r.strategy,
                "content_hash": r.content_hash,
                "embedding_text_hash": r.embedding_text_hash,
                "source_locator": r.source_locator,
                "canonical_metadata": r.canonical_metadata,
                "access_control": r.access_control,
                "content_modality": r.content_modality,
                "visual_artifact_id": r.visual_artifact_id,
                "svg_element_id": r.svg_element_id,
                "svg_group_id": r.svg_group_id,
                "visual_type": r.visual_type,
                "generation_strategy": r.generation_strategy,
                "record_id": r.record_id,
            }
            point_key = f"{r.tenant_id}:{r.chunk_run_id}:{r.chunk_id}"
            points.append(qm.PointStruct(id=_uuid_from(point_key), vector=r.vector, payload=payload))
        client.upsert(collection_name=self.collection, points=points)
        return {"upserted": len(points)}

    async def delete_by_run(self, chunk_run_id: str) -> dict[str, Any]:
        from qdrant_client.http import models as qm
        client = self._get_client()
        client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="chunk_run_id", match=qm.MatchValue(value=chunk_run_id))])
            ),
        )
        return {"deleted_run": chunk_run_id}

    async def verify(self, *, chunk_run_id: str, expected_count: int) -> dict[str, Any]:
        from qdrant_client.http import models as qm
        client = self._get_client()
        result = client.count(
            collection_name=self.collection,
            count_filter=qm.Filter(must=[qm.FieldCondition(key="chunk_run_id", match=qm.MatchValue(value=chunk_run_id))]),
            exact=True,
        )
        count = result.count
        return {"ok": count == expected_count, "count": count, "expected": expected_count}

    async def search(self, *, query_vector=None, query_text=None, top_k=10, filters=None) -> list[SearchHit]:
        from qdrant_client.http import models as qm
        client = self._get_client()
        if query_vector is None:
            raise ValueError("Qdrant search requires query_vector (engine-managed)")
        qfilter = None
        if filters:
            must = [qm.FieldCondition(key=k, match=qm.MatchValue(value=v)) for k, v in filters.items() if v is not None]
            qfilter = qm.Filter(must=must) if must else None
        hits = client.search(collection_name=self.collection, query_vector=query_vector, limit=top_k, query_filter=qfilter)
        out = []
        for h in hits:
            payload = h.payload or {}
            out.append(SearchHit(
                record_id=str(h.id),
                chunk_id=str(payload.get("chunk_id", "")),
                score=float(h.score),
                content=str(payload.get("content", "")),
                metadata=payload,
            ))
        return out

    async def health_check(self) -> dict[str, Any]:
        try:
            info = await self.validate_connection()
            return {"sink": self.sink_type, "status": "healthy", "available": True, **info}
        except Exception as exc:  # noqa: BLE001
            return {"sink": self.sink_type, "status": "unhealthy", "available": False, "reason": str(exc)}


def _is_uuid(value: str) -> bool:
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def _uuid_from(value: str) -> str:
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))
