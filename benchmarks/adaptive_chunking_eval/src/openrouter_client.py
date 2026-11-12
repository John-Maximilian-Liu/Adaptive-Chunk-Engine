"""Minimal OpenRouter OpenAI-compatible client with on-disk embedding cache."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional, Sequence

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CHAT_MODEL = "openai/gpt-4o"
DEFAULT_EMBED_MODEL = "openai/text-embedding-3-small"
DEFAULT_RERANK_MODEL = "cohere/rerank-v3.5"


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        chat_model: str = DEFAULT_CHAT_MODEL,
        embed_model: str = DEFAULT_EMBED_MODEL,
        rerank_model: str = DEFAULT_RERANK_MODEL,
        cache_dir: Optional[Path] = None,
        timeout: float = 120.0,
        batch_size: int = 16,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY (or OPENAI_API_KEY) is required for live eval")
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.rerank_model = rerank_model
        self.timeout = timeout
        self.batch_size = max(1, batch_size)
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parents[1] / "results" / "openrouter" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats: dict[str, Any] = {
            "embed_calls": 0,
            "embed_texts": 0,
            "embed_cache_hits": 0,
            "rerank_calls": 0,
            "rerank_docs": 0,
            "chat_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/John-Maximilian-Liu/Adaptive-Chunk-Engine",
            "X-Title": "ACE-adaptive-chunking-eval",
        }

    def _cache_path(self, text: str) -> Path:
        digest = hashlib.sha256(f"{self.embed_model}\n{text}".encode("utf-8")).hexdigest()
        return self.cache_dir / f"emb_{digest}.json"

    def _load_cached(self, text: str) -> Optional[list[float]]:
        path = self._cache_path(text)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            vec = data.get("embedding")
            if isinstance(vec, list) and vec:
                self.stats["embed_cache_hits"] += 1
                return vec
        except Exception:
            return None
        return None

    def _store_cached(self, text: str, embedding: list[float]) -> None:
        path = self._cache_path(text)
        path.write_text(json.dumps({"model": self.embed_model, "embedding": embedding}), encoding="utf-8")

    def _record_usage(self, usage: dict[str, Any]) -> None:
        self.stats["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        self.stats["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        self.stats["total_tokens"] += int(usage.get("total_tokens") or 0)
        cost = usage.get("cost")
        if cost is not None:
            self.stats["estimated_cost_usd"] += float(cost)

    @staticmethod
    def _sanitize_embed_text(text: str, max_chars: int = 6000) -> str:
        cleaned = (text or "").replace("\x00", " ").strip()
        if not cleaned:
            cleaned = " "
        if len(cleaned) > max_chars:
            head = max_chars * 2 // 3
            tail = max_chars - head
            cleaned = cleaned[:head] + "\n...\n" + cleaned[-tail:]
        return cleaned

    def _http_timeout(self) -> httpx.Timeout:
        # Separate connect/read so a stalled upstream cannot hang forever.
        read = float(self.timeout)
        return httpx.Timeout(connect=20.0, read=read, write=30.0, pool=20.0)

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.embed_model, "input": batch}
        self.stats["embed_calls"] += 1
        self.stats["embed_texts"] += len(batch)
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                with httpx.Client(timeout=self._http_timeout()) as client:
                    resp = client.post(
                        f"{self.base_url}/embeddings",
                        headers=self._headers(),
                        json=payload,
                    )
                    if resp.status_code in {408, 409, 429} or resp.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"{resp.status_code} embeddings retryable: {resp.text[:200]}",
                            request=resp.request,
                            response=resp,
                        )
                    if resp.status_code >= 400:
                        # Fall back to one-by-one with stronger truncation.
                        if len(batch) > 1:
                            vecs: list[list[float]] = []
                            for item in batch:
                                vecs.extend(self._embed_batch([item]))
                            return vecs
                        shorter = self._sanitize_embed_text(batch[0], max_chars=2000)
                        payload = {"model": self.embed_model, "input": [shorter]}
                        resp = client.post(
                            f"{self.base_url}/embeddings",
                            headers=self._headers(),
                            json=payload,
                        )
                        if resp.status_code >= 400:
                            raise httpx.HTTPStatusError(
                                f"{resp.status_code} embeddings error: {resp.text[:500]}",
                                request=resp.request,
                                response=resp,
                            )
                    data = resp.json()
                self._record_usage(data.get("usage") or {})
                rows = sorted(data["data"], key=lambda r: r["index"])
                return [row["embedding"] for row in rows]
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_err = exc
                # On timeout with a multi-item batch, split to isolate bad inputs.
                if isinstance(exc, httpx.TimeoutException) and len(batch) > 1:
                    mid = max(1, len(batch) // 2)
                    return self._embed_batch(batch[:mid]) + self._embed_batch(batch[mid:])
                time.sleep(min(30.0, 1.5 * (2**attempt)))
        assert last_err is not None
        raise last_err

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts with disk cache + batched OpenRouter calls."""
        if not texts:
            return []
        sanitized = [self._sanitize_embed_text(t) for t in texts]
        out: list[Optional[list[float]]] = [None] * len(sanitized)
        missing_idx: list[int] = []
        missing_texts: list[str] = []
        for i, text in enumerate(sanitized):
            cached = self._load_cached(text)
            if cached is not None:
                out[i] = cached
            else:
                missing_idx.append(i)
                missing_texts.append(text)

        for start in range(0, len(missing_texts), self.batch_size):
            batch = missing_texts[start : start + self.batch_size]
            batch_idx = missing_idx[start : start + self.batch_size]
            vectors = self._embed_batch(batch)
            for local_i, vec in enumerate(vectors):
                global_i = batch_idx[local_i]
                out[global_i] = vec
                self._store_cached(batch[local_i], vec)
            time.sleep(0.05)

        return [v if v is not None else [] for v in out]

    def rerank(self, query: str, documents: Sequence[str], *, top_n: Optional[int] = None) -> list[dict[str, Any]]:
        """Call OpenRouter /rerank. Returns results sorted by relevance_score desc."""
        docs = [d if d else " " for d in documents]
        if not docs:
            return []
        payload: dict[str, Any] = {
            "model": self.rerank_model,
            "query": query or " ",
            "documents": docs,
        }
        if top_n is not None:
            payload["top_n"] = max(1, min(int(top_n), len(docs)))
        self.stats["rerank_calls"] += 1
        self.stats["rerank_docs"] += len(docs)
        with httpx.Client(timeout=self._http_timeout()) as client:
            resp = client.post(f"{self.base_url}/rerank", headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} rerank error: {resp.text[:500]}",
                    request=resp.request,
                    response=resp,
                )
            data = resp.json()
        usage = data.get("usage") or {}
        self._record_usage(usage)
        results = list(data.get("results") or [])
        results.sort(key=lambda r: float(r.get("relevance_score") or 0.0), reverse=True)
        return results

    def rerank_texts(self, query: str, documents: Sequence[str], *, top_n: int = 5) -> list[str]:
        """Return top_n document strings after reranking (stable fallback to input order)."""
        docs = list(documents)
        if not docs:
            return []
        try:
            results = self.rerank(query, docs, top_n=top_n)
        except Exception:
            return docs[:top_n]
        out: list[str] = []
        for row in results:
            idx = row.get("index")
            if isinstance(idx, int) and 0 <= idx < len(docs):
                out.append(docs[idx])
            else:
                doc = row.get("document")
                if isinstance(doc, dict) and isinstance(doc.get("text"), str):
                    out.append(doc["text"])
                elif isinstance(doc, str):
                    out.append(doc)
            if len(out) >= top_n:
                break
        if not out:
            return docs[:top_n]
        return out

    def chat_json(self, *, system: str, user: str, temperature: float = 0.0) -> dict[str, Any]:
        payload = {
            "model": self.chat_model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        self.stats["chat_calls"] += 1
        with httpx.Client(timeout=self._http_timeout()) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        self._record_usage(data.get("usage") or {})
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content, "parse_error": True}
