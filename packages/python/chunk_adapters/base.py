"""Chunk adapter interface and strategy registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from canonical_schemas.chunk import CanonicalChunk
from canonical_schemas.document import LogicalUnitModel, RegionModel, ElementModel


@dataclass
class StrategyDefinition:
    strategy_id: str
    display_name: str
    adapter_id: str
    provider: str
    provider_version: str
    runtime: str = "python"
    supported_document_types: list[str] = field(default_factory=list)
    supported_element_types: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    parameter_schema: dict[str, Any] = field(default_factory=dict)
    dependency_available: bool = True
    health_status: str = "healthy"
    health_reason: Optional[str] = None
    license_metadata: dict[str, Any] = field(default_factory=dict)
    execution_mode: str = "local"  # local|external|sidecar
    designation: str = "deterministic"  # deterministic|llm_assisted
    enabled: bool = True


@dataclass
class ChunkRequest:
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_run_id: str
    experiment_id: Optional[str]
    logical_unit: LogicalUnitModel
    region: Optional[RegionModel]
    elements: list[ElementModel]
    strategy_id: str
    parameters: dict[str, Any]
    hard_constraints: dict[str, Any] = field(default_factory=dict)
    continuation_context: Optional[dict[str, Any]] = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


class ChunkAdapter(ABC):
    adapter_id: str = "base"
    provider: str = "builtin"
    provider_version: str = "1.0.0"

    @abstractmethod
    def capabilities(self) -> StrategyDefinition:
        raise NotImplementedError

    @abstractmethod
    def validate(self, request: ChunkRequest) -> ValidationResult:
        raise NotImplementedError

    @abstractmethod
    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        raise NotImplementedError

    def normalize(self, provider_chunk: Any, request: ChunkRequest) -> CanonicalChunk:
        if isinstance(provider_chunk, CanonicalChunk):
            return provider_chunk
        raise TypeError("Provider chunk must be CanonicalChunk or overridden normalize()")

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "provider": self.provider,
            "status": "healthy",
            "available": True,
            "reason": None,
        }


class StrategyRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ChunkAdapter] = {}
        self._by_strategy: dict[str, str] = {}

    def register(self, adapter: ChunkAdapter) -> None:
        definition = adapter.capabilities()
        self._adapters[adapter.adapter_id] = adapter
        self._by_strategy[definition.strategy_id] = adapter.adapter_id

    def get_adapter(self, strategy_id: str) -> ChunkAdapter:
        adapter_id = self._by_strategy.get(strategy_id)
        if not adapter_id or adapter_id not in self._adapters:
            raise KeyError(f"Unknown strategy: {strategy_id}")
        return self._adapters[adapter_id]

    def list_strategies(self) -> list[StrategyDefinition]:
        defs: list[StrategyDefinition] = []
        for adapter in self._adapters.values():
            d = adapter.capabilities()
            health = adapter.health_check()
            d.dependency_available = bool(health.get("available", True))
            d.health_status = health.get("status", "unknown")
            d.health_reason = health.get("reason")
            defs.append(d)
        return defs

    def get_definition(self, strategy_id: str) -> StrategyDefinition:
        return self.get_adapter(strategy_id).capabilities()


_GLOBAL_REGISTRY: Optional[StrategyRegistry] = None


def get_registry() -> StrategyRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = StrategyRegistry()
        from chunk_adapters.builtin import register_builtin_strategies
        from chunk_adapters.excel import register_excel_strategies
        from chunk_adapters.optional_providers import register_optional_providers

        register_builtin_strategies(_GLOBAL_REGISTRY)
        register_excel_strategies(_GLOBAL_REGISTRY)
        register_optional_providers(_GLOBAL_REGISTRY)
    return _GLOBAL_REGISTRY
