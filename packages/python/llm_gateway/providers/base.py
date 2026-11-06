"""LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str
    structured: Optional[dict[str, Any]] = None
    provider: str = ""
    requested_model: str = ""
    resolved_deployment: Optional[str] = None
    request_id: Optional[str] = None
    latency_ms: float = 0.0
    usage: LLMUsage = field(default_factory=LLMUsage)
    fallback_used: bool = False
    structured_output_valid: Optional[bool] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    provider: str
    model: str
    request_id: Optional[str] = None
    latency_ms: float = 0.0
    usage: LLMUsage = field(default_factory=LLMUsage)
    dimensions: int = 0


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        response_json: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    async def embed(self, *, texts: list[str], model: str, dimensions: Optional[int] = None, **kwargs: Any) -> EmbeddingResponse:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        from shared.tokens import count_tokens
        return count_tokens(text)
