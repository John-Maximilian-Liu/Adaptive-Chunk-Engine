"""Unified document + QA schema for public benchmark loaders."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class QAItem:
    qa_id: str
    question: str
    answer: str
    evidence_quote: str = ""
    key_terms: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocRecord:
    dataset: str
    doc_id: str
    domain: str
    text: str
    qa_pairs: list[QAItem] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def n_chars(self) -> int:
        return len(self.text or "")

    @property
    def approx_tokens(self) -> int:
        return max(1, (self.n_chars + 3) // 4)
