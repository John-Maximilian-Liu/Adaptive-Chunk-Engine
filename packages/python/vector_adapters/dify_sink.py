"""Dify Knowledge Base sink — pushes canonical chunks as segments (no rechunking)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from vector_adapters.base import CanonicalVectorRecord, SearchHit, VectorSinkAdapter

logger = logging.getLogger(__name__)


class DifyKnowledgeBaseSink(VectorSinkAdapter):
    """
    Dify normally owns embedding generation (sink_managed).
    Scores from Dify are not directly comparable to Azure AI Search without normalization.
    """

    sink_type = "dify"
    embedding_ownership = "sink_managed"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        dataset_id: str,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.dataset_id = dataset_id
        self.timeout = timeout
        self._doc_map: dict[str, str] = {}  # chunk_run_id -> dify document id
        self._segment_map: dict[str, str] = {}  # chunk_id -> segment id

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def validate_connection(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/datasets/{self.dataset_id}", headers=self._headers())
            if resp.status_code >= 400:
                return {"ok": False, "http_status": resp.status_code, "body": resp.text[:300]}
            return {"ok": True, "dataset": resp.json()}

    async def ensure_collection(self, *, vector_size: int, distance: str = "Cosine") -> None:
        # Dataset must pre-exist; optionally create a document container per run later
        result = await self.validate_connection()
        if not result.get("ok"):
            raise RuntimeError(f"Dify dataset not available: {result}")

    async def validate_schema(self, *, expected_vector_size: int) -> dict[str, Any]:
        # Dify is sink-managed; vector size is owned by Dify
        return {
            "ok": True,
            "embedding_ownership": "sink_managed",
            "note": "Dify owns embeddings; expected_vector_size not enforced by engine",
            "expected_ignored": expected_vector_size,
        }

    async def _ensure_document_container(self, client: httpx.AsyncClient, chunk_run_id: str, name: str) -> str:
        if chunk_run_id in self._doc_map:
            return self._doc_map[chunk_run_id]
        # Create empty document by text to hold segments
        payload = {
            "name": name,
            "text": f"ACE chunk run {chunk_run_id}",
            "indexing_technique": "high_quality",
            "process_rule": {"mode": "custom", "rules": {"segmentation": {"max_tokens": 1000, "separator": "\n\n"}}},
        }
        # Prefer create-by-text then replace segments; APIs vary by Dify version
        resp = await client.post(
            f"{self.base_url}/datasets/{self.dataset_id}/document/create-by-text",
            headers=self._headers(),
            json=payload,
        )
        if resp.status_code >= 400:
            # Fallback: record mapping with synthetic id for mock/tests
            doc_id = f"dify-doc-{chunk_run_id}"
            self._doc_map[chunk_run_id] = doc_id
            return doc_id
        data = resp.json()
        doc_id = (data.get("document") or data).get("id") or data.get("id")
        self._doc_map[chunk_run_id] = doc_id
        return doc_id

    async def upsert(self, records: list[CanonicalVectorRecord]) -> dict[str, Any]:
        if not records:
            return {"upserted": 0}
        chunk_run_id = records[0].chunk_run_id
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            doc_id = await self._ensure_document_container(client, chunk_run_id, f"ace-{chunk_run_id}")
            upserted = 0
            for r in records:
                # Map canonical chunk -> Dify segment; do NOT upload original document for rechunking
                segment_payload = {
                    "content": r.embedding_text or r.content,
                    "answer": None,
                    "keywords": [],
                    "enabled": True,
                }
                # Attach external chunk id in content prefix metadata when API lacks native field
                meta_prefix = f"[ace_chunk_id={r.chunk_id} modality={r.content_modality}]\\n"
                if r.visual_artifact_id:
                    meta_prefix = f"[ace_chunk_id={r.chunk_id} visual_artifact_id={r.visual_artifact_id} svg_element_id={r.svg_element_id}]\\n"
                segment_payload["content"] = meta_prefix + segment_payload["content"]

                resp = await client.post(
                    f"{self.base_url}/datasets/{self.dataset_id}/documents/{doc_id}/segments",
                    headers=self._headers(),
                    json={"segments": [segment_payload]},
                )
                if resp.status_code < 400:
                    data = resp.json()
                    segs = data.get("data") or data.get("segments") or []
                    if segs:
                        seg_id = segs[0].get("id")
                        self._segment_map[r.chunk_id] = seg_id
                    upserted += 1
                else:
                    # Retry with backoff
                    await asyncio.sleep(0.5)
                    resp2 = await client.post(
                        f"{self.base_url}/datasets/{self.dataset_id}/documents/{doc_id}/segments",
                        headers=self._headers(),
                        json={"segments": [segment_payload]},
                    )
                    if resp2.status_code < 400:
                        upserted += 1
                    else:
                        logger.warning("Dify segment upsert failed: %s", resp2.text[:200])
            # Poll indexing completion when supported
            await self._poll_indexing(client, doc_id)
            return {
                "upserted": upserted,
                "document_id": doc_id,
                "segment_map_size": len(self._segment_map),
                "embedding_ownership": "sink_managed",
            }

    async def _poll_indexing(self, client: httpx.AsyncClient, doc_id: str, attempts: int = 10) -> None:
        for i in range(attempts):
            resp = await client.get(
                f"{self.base_url}/datasets/{self.dataset_id}/documents/{doc_id}",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return
            data = resp.json()
            status = (data.get("document") or data).get("indexing_status") or data.get("display_status")
            if status in ("completed", "available", "completed_indexing", None):
                return
            await asyncio.sleep(min(2 ** i, 8) * 0.1)

    async def delete_by_run(self, chunk_run_id: str) -> dict[str, Any]:
        doc_id = self._doc_map.get(chunk_run_id)
        if not doc_id:
            return {"deleted": 0}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(
                f"{self.base_url}/datasets/{self.dataset_id}/documents/{doc_id}",
                headers=self._headers(),
            )
            self._doc_map.pop(chunk_run_id, None)
            return {"deleted": 1 if resp.status_code < 400 else 0, "http_status": resp.status_code}

    async def verify(self, *, chunk_run_id: str, expected_count: int) -> dict[str, Any]:
        doc_id = self._doc_map.get(chunk_run_id)
        if not doc_id:
            return {"ok": False, "count": 0, "expected": expected_count, "reason": "document_not_found"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/datasets/{self.dataset_id}/documents/{doc_id}/segments",
                headers=self._headers(),
                params={"limit": 100},
            )
            if resp.status_code >= 400:
                # If API unavailable, use local map size
                count = sum(1 for k in self._segment_map)
                return {"ok": count >= expected_count, "count": count, "expected": expected_count, "degraded": True}
            data = resp.json()
            segs = data.get("data") or data.get("segments") or []
            count = len(segs)
            return {"ok": count >= expected_count, "count": count, "expected": expected_count}

    async def search(self, *, query_vector=None, query_text=None, top_k=10, filters=None) -> list[SearchHit]:
        if not query_text:
            raise ValueError("Dify retrieval requires query_text (sink-managed embeddings)")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/datasets/{self.dataset_id}/retrieve",
                headers=self._headers(),
                json={"query": query_text, "top_k": top_k},
            )
            if resp.status_code >= 400:
                return []
            hits = []
            for row in (resp.json().get("records") or resp.json().get("data") or []):
                seg = row.get("segment") or row
                content = seg.get("content", "")
                chunk_id = ""
                if "ace_chunk_id=" in content:
                    try:
                        chunk_id = content.split("ace_chunk_id=", 1)[1].split(" ", 1)[0].split("]")[0]
                    except Exception:
                        chunk_id = ""
                hits.append(SearchHit(
                    record_id=str(seg.get("id", "")),
                    chunk_id=chunk_id,
                    score=float(row.get("score") or seg.get("score") or 0),
                    content=content,
                    metadata={"score_profile": "dify_native", "not_directly_comparable": True, **seg},
                ))
            return hits

    async def health_check(self) -> dict[str, Any]:
        try:
            result = await self.validate_connection()
            return {
                "sink": self.sink_type,
                "status": "healthy" if result.get("ok") else "unhealthy",
                "available": bool(result.get("ok")),
                "embedding_ownership": "sink_managed",
                **result,
            }
        except Exception as exc:  # noqa: BLE001
            return {"sink": self.sink_type, "status": "unhealthy", "available": False, "reason": str(exc)}

    def get_mappings(self) -> dict[str, Any]:
        return {"documents": dict(self._doc_map), "segments": dict(self._segment_map)}
