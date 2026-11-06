"""Azure OpenAI provider adapter."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from llm_gateway.providers.base import EmbeddingResponse, LLMProvider, LLMResponse, LLMUsage


class AzureOpenAIProvider(LLMProvider):
    name = "azure_openai"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: Optional[str] = None,
        api_version: str = "2024-02-15-preview",
        auth_mode: str = "api_key",
        timeout: float = 60.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.api_version = api_version
        self.auth_mode = auth_mode
        self.timeout = timeout
        if auth_mode == "api_key" and not api_key:
            raise ValueError("Azure OpenAI API key required for api_key auth_mode")

    async def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_mode == "api_key":
            headers["api-key"] = self.api_key or ""
        elif self.auth_mode in ("entra_id", "managed_identity"):
            # Production design: acquire token via DefaultAzureCredential
            try:
                from azure.identity.aio import DefaultAzureCredential
                cred = DefaultAzureCredential()
                token = await cred.get_token("https://cognitiveservices.azure.com/.default")
                headers["Authorization"] = f"Bearer {token.token}"
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Failed to acquire Entra ID token: {exc}") from exc
        return headers

    async def chat(self, *, messages, model, temperature=0.0, response_json=False, deployment_name: Optional[str] = None, **kwargs) -> LLMResponse:
        start = time.perf_counter()
        deployment = deployment_name or model
        url = f"{self.endpoint}/openai/deployments/{deployment}/chat/completions"
        payload: dict[str, Any] = {"messages": messages, "temperature": temperature}
        if response_json:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, params={"api-version": self.api_version}, headers=await self._headers(), json=payload)
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
            resolved_deployment=deployment,
            request_id=data.get("id") or resp.headers.get("x-request-id") or resp.headers.get("apim-request-id"),
            latency_ms=(time.perf_counter() - start) * 1000,
            usage=LLMUsage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            ),
            structured_output_valid=valid,
            raw={"id": data.get("id")},
        )

    async def embed(self, *, texts, model, dimensions: Optional[int] = None, deployment_name: Optional[str] = None, **kwargs) -> EmbeddingResponse:
        start = time.perf_counter()
        deployment = deployment_name or model
        url = f"{self.endpoint}/openai/deployments/{deployment}/embeddings"
        payload: dict[str, Any] = {"input": texts}
        if dimensions:
            payload["dimensions"] = dimensions
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, params={"api-version": self.api_version}, headers=await self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        vectors = [row["embedding"] for row in data["data"]]
        usage_raw = data.get("usage") or {}
        return EmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            request_id=resp.headers.get("x-request-id") or resp.headers.get("apim-request-id"),
            latency_ms=(time.perf_counter() - start) * 1000,
            usage=LLMUsage(prompt_tokens=usage_raw.get("prompt_tokens", 0), total_tokens=usage_raw.get("total_tokens", 0)),
            dimensions=len(vectors[0]) if vectors else 0,
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            # Lightweight check: hit deployments list if possible; otherwise report configured
            return {
                "provider": self.name,
                "status": "configured",
                "available": bool(self.endpoint) and (bool(self.api_key) or self.auth_mode != "api_key"),
                "endpoint": self.endpoint,
                "auth_mode": self.auth_mode,
                "note": "Live probe requires valid credentials; not claiming success without a real response",
            }
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.name, "status": "unhealthy", "available": False, "reason": str(exc)}
