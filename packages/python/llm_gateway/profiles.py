"""LLM configuration profiles."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, SecretStr

from shared.ids import new_id


class DataPolicy(BaseModel):
    allow_external_llm_for_sensitive_docs: bool = False
    store_llm_prompt_response: bool = True
    redact_secrets_in_logs: bool = True
    sensitive: bool = False


class ProviderFailoverPolicy(BaseModel):
    enabled: bool = True
    max_failovers: int = 2
    prohibit_cross_provider_for_sensitive: bool = True
    retryable_status_codes: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])


class LLMProfile(BaseModel):
    llm_profile_id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str
    provider: str  # openai|azure_openai|mock
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"
    deployment_name: Optional[str] = None  # Azure
    api_version: Optional[str] = "2024-02-15-preview"
    credential_ref: Optional[str] = None  # never store raw secret in responses
    auth_mode: str = "api_key"  # api_key|entra_id|managed_identity
    temperature: float = 0.0
    timeout_seconds: float = 60.0
    max_retries: int = 3
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingProfile(BaseModel):
    embedding_profile_id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str
    provider: str  # openai|azure_openai|mock
    model: str = "text-embedding-3-small"
    deployment_name: Optional[str] = None
    base_url: Optional[str] = None
    credential_ref: Optional[str] = None
    auth_mode: str = "api_key"
    dimensions: int = 1536
    timeout_seconds: float = 60.0
    enabled: bool = True


class LLMRoutingProfile(BaseModel):
    routing_profile_id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str = "default"
    task_routes: dict[str, str] = Field(default_factory=lambda: {
        "document_classification": "",
        "page_profiling": "",
        "chunk_strategy_planning": "",
        "qa_generation": "",
        "qa_schema_completion": "",
        "failure_analysis": "",
        "optimization_proposal": "",
        "agentic_chunking": "",
        "embedding": "",
    })
    failover_policy: ProviderFailoverPolicy = Field(default_factory=ProviderFailoverPolicy)
    data_policy: DataPolicy = Field(default_factory=DataPolicy)
