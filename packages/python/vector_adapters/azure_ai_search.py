"""Azure AI Search vector sink."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from vector_adapters.base import CanonicalVectorRecord, SearchHit, VectorSinkAdapter

logger = logging.getLogger(__name__)

RECOMMENDED_FIELDS = [
    "id", "content", "embedding_text", "content_vector",
    "tenant_id", "document_id", "document_version_id", "experiment_id", "chunk_run_id",
    "logical_unit_id", "chunk_type", "strategy", "source_locator_json",
    "allowed_user_ids", "allowed_group_ids",
    "content_modality", "visual_artifact_id", "svg_element_id", "svg_group_id",
    "visual_type", "generation_strategy",
]


class AzureAISearchSink(VectorSinkAdapter):
    sink_type = "azure_ai_search"

    def __init__(
        self,
        endpoint: str,
        index_name: str = "ace-chunks",
        api_key: Optional[str] = None,
        auth_mode: str = "api_key",
        api_version: str = "2024-07-01",
    ):
        self.endpoint = endpoint.rstrip("/")
        self.index_name = index_name
        self.api_key = api_key
        self.auth_mode = auth_mode
        self.api_version = api_version
        self._vector_size: Optional[int] = None

    async def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_mode == "api_key":
            if not self.api_key:
                raise ValueError("Azure AI Search API key required")
            headers["api-key"] = self.api_key
        elif self.auth_mode in ("entra_id", "managed_identity"):
            from azure.identity.aio import DefaultAzureCredential
            cred = DefaultAzureCredential()
            token = await cred.get_token("https://search.azure.com/.default")
            headers["Authorization"] = f"Bearer {token.token}"
        return headers

    def _index_url(self, path: str = "") -> str:
        return f"{self.endpoint}/indexes/{self.index_name}{path}"

    async def validate_connection(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.endpoint}/indexes",
                params={"api-version": self.api_version},
                headers=await self._headers(),
            )
            if resp.status_code >= 400:
                return {"ok": False, "http_status": resp.status_code, "body": resp.text[:500]}
            data = resp.json()
            names = [i.get("name") for i in data.get("value", [])]
            return {"ok": True, "indexes": names}

    def _index_schema(self, vector_size: int) -> dict[str, Any]:
        return {
            "name": self.index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {"name": "content", "type": "Edm.String", "searchable": True},
                {"name": "embedding_text", "type": "Edm.String", "searchable": True},
                {
                    "name": "content_vector",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "dimensions": vector_size,
                    "vectorSearchProfile": "vprofile",
                },
                {"name": "tenant_id", "type": "Edm.String", "filterable": True},
                {"name": "document_id", "type": "Edm.String", "filterable": True},
                {"name": "document_version_id", "type": "Edm.String", "filterable": True},
                {"name": "experiment_id", "type": "Edm.String", "filterable": True},
                {"name": "chunk_run_id", "type": "Edm.String", "filterable": True},
                {"name": "chunk_id", "type": "Edm.String", "filterable": True},
                {"name": "logical_unit_id", "type": "Edm.String", "filterable": True},
                {"name": "chunk_type", "type": "Edm.String", "filterable": True, "facetable": True},
                {"name": "strategy", "type": "Edm.String", "filterable": True},
                {"name": "source_locator_json", "type": "Edm.String"},
                {"name": "allowed_user_ids", "type": "Collection(Edm.String)", "filterable": True},
                {"name": "allowed_group_ids", "type": "Collection(Edm.String)", "filterable": True},
                {"name": "content_modality", "type": "Edm.String", "filterable": True},
                {"name": "visual_artifact_id", "type": "Edm.String", "filterable": True},
                {"name": "svg_element_id", "type": "Edm.String", "filterable": True},
                {"name": "svg_group_id", "type": "Edm.String", "filterable": True},
                {"name": "visual_type", "type": "Edm.String", "filterable": True},
                {"name": "generation_strategy", "type": "Edm.String", "filterable": True},
            ],
            "vectorSearch": {
                "algorithms": [{"name": "hnsw", "kind": "hnsw"}],
                "profiles": [{"name": "vprofile", "algorithm": "hnsw"}],
            },
        }

    async def ensure_collection(self, *, vector_size: int, distance: str = "Cosine") -> None:
        self._vector_size = vector_size
        async with httpx.AsyncClient(timeout=60) as client:
            # Check existing
            resp = await client.get(
                self._index_url(),
                params={"api-version": self.api_version},
                headers=await self._headers(),
            )
            if resp.status_code == 200:
                # validate dimensions; do not recreate by default
                return
            schema = self._index_schema(vector_size)
            create = await client.put(
                self._index_url(),
                params={"api-version": self.api_version},
                headers=await self._headers(),
                json=schema,
            )
            create.raise_for_status()

    async def validate_schema(self, *, expected_vector_size: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self._index_url(),
                params={"api-version": self.api_version},
                headers=await self._headers(),
            )
            if resp.status_code >= 400:
                return {"ok": False, "http_status": resp.status_code}
            data = resp.json()
            fields = {f["name"]: f for f in data.get("fields", [])}
            vec = fields.get("content_vector", {})
            dims = vec.get("dimensions")
            missing = [f for f in RECOMMENDED_FIELDS if f not in fields and f != "content_vector"]
            ok = dims == expected_vector_size
            return {"ok": ok, "vector_size": dims, "expected": expected_vector_size, "missing_fields": missing}

    async def upsert(self, records: list[CanonicalVectorRecord]) -> dict[str, Any]:
        import json
        docs = []
        for r in records:
            if r.vector is None:
                raise ValueError("Azure AI Search adapter expects engine-managed embeddings")
            docs.append({
                "@search.action": "mergeOrUpload",
                "id": r.record_id.replace("-", ""),
                "content": r.content,
                "embedding_text": r.embedding_text,
                "content_vector": r.vector,
                "tenant_id": r.tenant_id,
                "document_id": r.document_id,
                "document_version_id": r.document_version_id,
                "experiment_id": r.experiment_id or "",
                "chunk_run_id": r.chunk_run_id,
                "chunk_id": r.chunk_id,
                "logical_unit_id": (r.canonical_metadata or {}).get("logical_unit_id", ""),
                "chunk_type": (r.canonical_metadata or {}).get("chunk_type", "text"),
                "strategy": r.strategy,
                "source_locator_json": json.dumps(r.source_locator),
                "allowed_user_ids": (r.access_control or {}).get("allowed_user_ids", []),
                "allowed_group_ids": (r.access_control or {}).get("allowed_group_ids", []),
                "content_modality": r.content_modality,
                "visual_artifact_id": r.visual_artifact_id or "",
                "svg_element_id": r.svg_element_id or "",
                "svg_group_id": r.svg_group_id or "",
                "visual_type": r.visual_type or "",
                "generation_strategy": r.generation_strategy or "",
            })
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._index_url()}/docs/index",
                params={"api-version": self.api_version},
                headers=await self._headers(),
                json={"value": docs},
            )
            resp.raise_for_status()
            return {"upserted": len(docs), "response": resp.json()}

    async def delete_by_run(self, chunk_run_id: str) -> dict[str, Any]:
        # Search then delete
        async with httpx.AsyncClient(timeout=60) as client:
            search = await client.post(
                f"{self._index_url()}/docs/search",
                params={"api-version": self.api_version},
                headers=await self._headers(),
                json={"search": "*", "filter": f"chunk_run_id eq '{chunk_run_id}'", "select": "id", "top": 1000},
            )
            search.raise_for_status()
            ids = [d["id"] for d in search.json().get("value", [])]
            if not ids:
                return {"deleted": 0}
            payload = {"value": [{"@search.action": "delete", "id": i} for i in ids]}
            resp = await client.post(
                f"{self._index_url()}/docs/index",
                params={"api-version": self.api_version},
                headers=await self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return {"deleted": len(ids)}

    async def verify(self, *, chunk_run_id: str, expected_count: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._index_url()}/docs/search",
                params={"api-version": self.api_version},
                headers=await self._headers(),
                json={"search": "*", "filter": f"chunk_run_id eq '{chunk_run_id}'", "top": 0, "count": True},
            )
            resp.raise_for_status()
            count = int(resp.json().get("@odata.count") or 0)
            return {"ok": count == expected_count, "count": count, "expected": expected_count}

    async def search(self, *, query_vector=None, query_text=None, top_k=10, filters=None) -> list[SearchHit]:
        body: dict[str, Any] = {"top": top_k}
        filter_parts = []
        if filters:
            for k, v in filters.items():
                if v is not None:
                    filter_parts.append(f"{k} eq '{v}'")
        if filter_parts:
            body["filter"] = " and ".join(filter_parts)
        if query_vector is not None:
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": query_vector,
                "fields": "content_vector",
                "k": top_k,
            }]
        if query_text:
            body["search"] = query_text
            body["queryType"] = "simple"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._index_url()}/docs/search",
                params={"api-version": self.api_version},
                headers=await self._headers(),
                json=body,
            )
            resp.raise_for_status()
            hits = []
            for d in resp.json().get("value", []):
                hits.append(SearchHit(
                    record_id=d.get("id", ""),
                    chunk_id=d.get("chunk_id", ""),
                    score=float(d.get("@search.score", 0)),
                    content=d.get("content", ""),
                    metadata=d,
                ))
            return hits

    async def health_check(self) -> dict[str, Any]:
        try:
            result = await self.validate_connection()
            return {"sink": self.sink_type, "status": "healthy" if result.get("ok") else "unhealthy", "available": bool(result.get("ok")), **result}
        except Exception as exc:  # noqa: BLE001
            return {"sink": self.sink_type, "status": "unhealthy", "available": False, "reason": str(exc)}
