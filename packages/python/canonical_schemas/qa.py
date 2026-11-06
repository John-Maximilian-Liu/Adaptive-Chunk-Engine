"""Canonical QA schema."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.ids import new_id

QA_SCHEMA_VERSION = "1.0.0"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceQuote(BaseModel):
    quote: str
    locator: dict[str, Any] = Field(default_factory=dict)
    element_id: Optional[str] = None
    logical_unit_id: Optional[str] = None
    region_id: Optional[str] = None
    confidence: Optional[float] = None


class MatchingPolicy(BaseModel):
    mode: str = "contains_any_evidence"  # contains_any_evidence|contains_all_evidence|minimum_evidence_count|weighted_evidence_coverage
    minimum_evidence_count: int = 1
    element_id_matching: bool = True
    min_text_coverage: float = 0.70
    min_source_span_iou: float = 0.50
    semantic_fallback: bool = True
    semantic_threshold: float = 0.85
    llm_judge_enabled: bool = False


class QAItem(BaseModel):
    schema_version: str = QA_SCHEMA_VERSION
    qa_id: str = Field(default_factory=new_id)
    qa_dataset_id: str
    document_version_id: str
    tenant_id: str
    source: str = "generated"  # generated|uploaded|human_edited|merged
    status: str = "draft"
    enabled: bool = True
    question: str
    answer: str = ""
    question_type: str = "direct_fact"
    difficulty: str = "medium"
    language: str = "en"
    answer_variants: list[str] = Field(default_factory=list)
    expected_logical_unit_ids: list[str] = Field(default_factory=list)
    expected_region_ids: list[str] = Field(default_factory=list)
    expected_element_ids: list[str] = Field(default_factory=list)
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list)
    matching_policy: MatchingPolicy = Field(default_factory=MatchingPolicy)
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    review_status: str = "pending"  # pending|approved|rejected|needs_review
    audit: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class QADistribution(BaseModel):
    mode: str = "percentage"  # percentage|absolute
    total: int = 50
    by_type: dict[str, float] = Field(
        default_factory=lambda: {
            "direct_fact": 25,
            "definition": 10,
            "conditional": 10,
            "cross_paragraph": 10,
            "cross_unit": 10,
            "table_lookup": 10,
            "table_aggregation": 5,
            "formula_reasoning": 5,
            "hard_negative": 5,
            "multi_hop": 10,
        }
    )


class QADataset(BaseModel):
    qa_dataset_id: str = Field(default_factory=new_id)
    tenant_id: str
    document_version_id: str
    name: str
    distribution: QADistribution = Field(default_factory=QADistribution)
    item_count: int = 0
    status: str = "draft"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
