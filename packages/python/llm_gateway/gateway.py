"""LLM Gateway with routing, retries, failover, and usage capture."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from llm_gateway.profiles import DataPolicy, EmbeddingProfile, LLMProfile, LLMRoutingProfile, ProviderFailoverPolicy
from llm_gateway.providers.base import EmbeddingResponse, LLMProvider, LLMResponse
from llm_gateway.providers.mock import MockLLMProvider
from shared.ids import new_id

logger = logging.getLogger(__name__)


class LLMGateway:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {"mock": MockLLMProvider()}
        self._profiles: dict[str, LLMProfile] = {}
        self._embedding_profiles: dict[str, EmbeddingProfile] = {}
        self._routing: Optional[LLMRoutingProfile] = None
        self._secrets: dict[str, str] = {}  # credential_ref -> secret (backend only)
        self._runs: list[dict[str, Any]] = []

    def store_secret(self, credential_ref: str, secret: str) -> None:
        self._secrets[credential_ref] = secret

    def get_secret(self, credential_ref: Optional[str]) -> Optional[str]:
        if not credential_ref:
            return None
        return self._secrets.get(credential_ref)

    def register_profile(self, profile: LLMProfile, secret: Optional[str] = None) -> LLMProfile:
        if secret and profile.credential_ref:
            self.store_secret(profile.credential_ref, secret)
        elif secret:
            profile.credential_ref = f"cred_{profile.llm_profile_id}"
            self.store_secret(profile.credential_ref, secret)
        self._profiles[profile.llm_profile_id] = profile
        self._ensure_provider(profile)
        return profile

    def register_embedding_profile(self, profile: EmbeddingProfile, secret: Optional[str] = None) -> EmbeddingProfile:
        if secret and profile.credential_ref:
            self.store_secret(profile.credential_ref, secret)
        elif secret:
            profile.credential_ref = f"cred_{profile.embedding_profile_id}"
            self.store_secret(profile.credential_ref, secret)
        self._embedding_profiles[profile.embedding_profile_id] = profile
        return profile

    def set_routing(self, routing: LLMRoutingProfile) -> None:
        self._routing = routing

    def _ensure_provider(self, profile: LLMProfile) -> LLMProvider:
        key = f"{profile.provider}:{profile.llm_profile_id}"
        if key in self._providers:
            return self._providers[key]
        secret = self.get_secret(profile.credential_ref) or ""
        if profile.provider == "mock":
            provider: LLMProvider = MockLLMProvider()
        elif profile.provider == "openai":
            from llm_gateway.providers.openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key=secret, base_url=profile.base_url or "https://api.openai.com/v1", timeout=profile.timeout_seconds)
        elif profile.provider == "azure_openai":
            from llm_gateway.providers.azure_openai import AzureOpenAIProvider
            provider = AzureOpenAIProvider(
                endpoint=profile.base_url or "",
                api_key=secret if profile.auth_mode == "api_key" else None,
                api_version=profile.api_version or "2024-02-15-preview",
                auth_mode=profile.auth_mode,
                timeout=profile.timeout_seconds,
            )
        else:
            raise ValueError(f"Unknown provider: {profile.provider}")
        self._providers[key] = provider
        return provider

    def _resolve_profile(self, task: str, profile_id: Optional[str] = None) -> LLMProfile:
        if profile_id and profile_id in self._profiles:
            return self._profiles[profile_id]
        if self._routing and self._routing.task_routes.get(task):
            rid = self._routing.task_routes[task]
            if rid in self._profiles:
                return self._profiles[rid]
        # default mock
        for p in self._profiles.values():
            if p.provider == "mock" and p.enabled:
                return p
        # create ephemeral mock
        p = LLMProfile(tenant_id="system", name="ephemeral-mock", provider="mock", model="mock-gpt")
        self.register_profile(p)
        return p

    async def complete(
        self,
        *,
        task: str,
        messages: list[dict[str, str]],
        response_json: bool = True,
        context: Optional[dict[str, Any]] = None,
        profile_id: Optional[str] = None,
        prompt_template_version: str = "1.0.0",
        data_policy: Optional[DataPolicy] = None,
    ) -> LLMResponse:
        profile = self._resolve_profile(task, profile_id)
        data_policy = data_policy or (self._routing.data_policy if self._routing else DataPolicy())
        failover = self._routing.failover_policy if self._routing else ProviderFailoverPolicy()

        if data_policy.sensitive and not data_policy.allow_external_llm_for_sensitive_docs and profile.provider != "mock":
            # force mock / local only
            profile = self._resolve_profile(task, None)
            if profile.provider != "mock":
                profile = LLMProfile(tenant_id=profile.tenant_id, name="forced-mock", provider="mock", model="mock-gpt")
                self.register_profile(profile)

        provider = self._ensure_provider(profile)
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= profile.max_retries:
            try:
                kwargs: dict[str, Any] = {}
                if profile.provider == "azure_openai":
                    kwargs["deployment_name"] = profile.deployment_name or profile.model
                if profile.provider == "mock":
                    kwargs["task"] = task
                    kwargs["context"] = context
                resp = await provider.chat(
                    messages=messages,
                    model=profile.model,
                    temperature=profile.temperature,
                    response_json=response_json,
                    **kwargs,
                )
                run = {
                    "llm_run_id": new_id(),
                    "task": task,
                    "provider": resp.provider,
                    "requested_model": resp.requested_model,
                    "resolved_deployment": resp.resolved_deployment,
                    "prompt_template_version": prompt_template_version,
                    "temperature": profile.temperature,
                    "token_counts": {
                        "prompt": resp.usage.prompt_tokens,
                        "completion": resp.usage.completion_tokens,
                        "total": resp.usage.total_tokens,
                    },
                    "request_id": resp.request_id,
                    "fallback_status": resp.fallback_used,
                    "latency_ms": resp.latency_ms,
                    "structured_output_validation_status": resp.structured_output_valid,
                }
                if data_policy.store_llm_prompt_response:
                    run["messages_redacted"] = [{"role": m["role"], "content": "[stored]"} for m in messages]
                self._runs.append(run)
                resp.raw["llm_run_id"] = run["llm_run_id"]
                return resp
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                attempt += 1
                if attempt > profile.max_retries:
                    break
                await asyncio.sleep(min(2 ** attempt, 8))

        # Failover
        if failover.enabled and not (data_policy.sensitive and failover.prohibit_cross_provider_for_sensitive):
            for p in self._profiles.values():
                if p.llm_profile_id == profile.llm_profile_id or not p.enabled:
                    continue
                try:
                    alt = self._ensure_provider(p)
                    resp = await alt.chat(messages=messages, model=p.model, temperature=p.temperature, response_json=response_json)
                    resp.fallback_used = True
                    return resp
                except Exception:
                    continue
        raise RuntimeError(f"LLM completion failed after retries: {last_exc}")

    async def embed(
        self,
        *,
        texts: list[str],
        embedding_profile_id: Optional[str] = None,
    ) -> EmbeddingResponse:
        profile = None
        if embedding_profile_id:
            profile = self._embedding_profiles.get(embedding_profile_id)
        if profile is None:
            for p in self._embedding_profiles.values():
                if p.provider == "mock":
                    profile = p
                    break
        if profile is None:
            profile = EmbeddingProfile(tenant_id="system", name="mock-emb", provider="mock", model="mock-emb", dimensions=1536)
            self.register_embedding_profile(profile)

        if profile.provider == "mock":
            provider: LLMProvider = MockLLMProvider(dimensions=profile.dimensions)
        elif profile.provider == "openai":
            from llm_gateway.providers.openai_provider import OpenAIProvider
            secret = self.get_secret(profile.credential_ref) or ""
            provider = OpenAIProvider(api_key=secret, base_url=profile.base_url or "https://api.openai.com/v1")
        elif profile.provider == "azure_openai":
            from llm_gateway.providers.azure_openai import AzureOpenAIProvider
            secret = self.get_secret(profile.credential_ref) or ""
            provider = AzureOpenAIProvider(endpoint=profile.base_url or "", api_key=secret, auth_mode=profile.auth_mode)
        else:
            provider = MockLLMProvider(dimensions=profile.dimensions)

        kwargs: dict[str, Any] = {}
        if profile.provider == "azure_openai":
            kwargs["deployment_name"] = profile.deployment_name or profile.model
        return await provider.embed(texts=texts, model=profile.model, dimensions=profile.dimensions, **kwargs)

    def public_profile(self, profile: LLMProfile) -> dict[str, Any]:
        """Return profile without secrets."""
        data = profile.model_dump()
        data.pop("credential_ref", None)
        data["has_credential"] = bool(profile.credential_ref and profile.credential_ref in self._secrets)
        data["credential_ref"] = profile.credential_ref  # reference only, never secret value
        return data


_GATEWAY: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = LLMGateway()
    return _GATEWAY
