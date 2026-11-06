"""OpenAI provider adapter."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from llm_gateway.providers.base import EmbeddingResponse, LLMProvider, LLMResponse, LLMUsage


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: float = 60.0):
        if not api_key:
            raise ValueError("OpenAI API key required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def chat(self, *, messages, model, temperature=0.0, response_json=False, **kwargs) -> LLMResponse:
        start = time.perf_counter()
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if response_json:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage_raw = data.get("usage") or {}
        structured = None
        valid = None
        if response_json:
            import json
            try:
                structured = json.loads(content)
                valid = True
            except Exception:
                valid = False
        return LLMResponse(
            content=content,
            structured=structured,
            provider=self.name,
            requested_model=model,
            resolved_deployment=model,
            request_id=data.get("id") or resp.headers.get("x-request-id"),
            latency_ms=(time.perf_counter() - start) * 1000,
            usage=LLMUsage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            ),
            structured_output_valid=valid,
            raw={"id": data.get("id")},
        )

    async def embed(self, *, texts, model, dimensions: Optional[int] = None, **kwargs) -> EmbeddingResponse:
        start = time.perf_counter()
        payload: dict[str, Any] = {"model": model, "input": texts}
        if dimensions:
            payload["dimensions"] = dimensions
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/embeddings", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        vectors = [row["embedding"] for row in data["data"]]
        usage_raw = data.get("usage") or {}
        return EmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            request_id=resp.headers.get("x-request-id"),
            latency_ms=(time.perf_counter() - start) * 1000,
            usage=LLMUsage(prompt_tokens=usage_raw.get("prompt_tokens", 0), total_tokens=usage_raw.get("total_tokens", 0)),
            dimensions=len(vectors[0]) if vectors else 0,
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                ok = resp.status_code < 400
                return {"provider": self.name, "status": "healthy" if ok else "unhealthy", "available": ok, "http_status": resp.status_code}
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.name, "status": "unhealthy", "available": False, "reason": str(exc)}
