"""Chunk strategy adapters and registry."""
from chunk_adapters.base import (
    ChunkAdapter,
    ChunkRequest,
    StrategyDefinition,
    StrategyRegistry,
    ValidationResult,
    get_registry,
)
from chunk_adapters.excel import range_intersection_coverage, parse_range, sheet_locator

__all__ = [
    "ChunkAdapter",
    "ChunkRequest",
    "StrategyDefinition",
    "StrategyRegistry",
    "ValidationResult",
    "get_registry",
    "range_intersection_coverage",
    "parse_range",
    "sheet_locator",
]
