"""Excel cell-range coverage helpers."""
from __future__ import annotations

from chunk_adapters.excel import range_intersection_coverage, parse_range


def cell_range_coverage(evidence_range: str, retrieved_range: str) -> float:
    """intersection(retrieved, evidence) / evidence cells."""
    return range_intersection_coverage(evidence_range, retrieved_range)


def ranges_overlap(a: str, b: str) -> bool:
    return cell_range_coverage(a, b) > 0
