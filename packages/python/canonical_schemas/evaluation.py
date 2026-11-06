"""Evaluation schemas and scoring helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from shared.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_METRICS: list[dict[str, Any]] = [
    {"name": "evidence_recall_at_1", "label": "Evidence Recall@1", "direction": "higher", "default_weight": 0.05, "default_enabled": True, "hard_gate": False, "target": 0.80},
    {"name": "evidence_recall_at_3", "label": "Evidence Recall@3", "direction": "higher", "default_weight": 0.10, "default_enabled": True, "hard_gate": False, "target": 0.90},
    {"name": "evidence_recall_at_5", "label": "Evidence Recall@5", "direction": "higher", "default_weight": 0.10, "default_enabled": True, "hard_gate": False, "target": 0.93},
    {"name": "evidence_recall_at_10", "label": "Evidence Recall@10", "direction": "higher", "default_weight": 0.25, "default_enabled": True, "hard_gate": True, "target": 0.95},
    {"name": "mrr_at_10", "label": "MRR@10", "direction": "higher", "default_weight": 0.10, "default_enabled": True, "hard_gate": False, "target": 0.70},
    {"name": "ndcg_at_10", "label": "nDCG@10", "direction": "higher", "default_weight": 0.10, "default_enabled": True, "hard_gate": False, "target": 0.75},
    {"name": "logical_unit_recall_at_10", "label": "Logical Unit Recall@10", "direction": "higher", "default_weight": 0.05, "default_enabled": True, "hard_gate": False, "target": 0.90},
    {"name": "element_recall_at_10", "label": "Element Recall@10", "direction": "higher", "default_weight": 0.05, "default_enabled": True, "hard_gate": False, "target": 0.85},
    {"name": "precision_at_10", "label": "Precision@10", "direction": "higher", "default_weight": 0.05, "default_enabled": True, "hard_gate": False, "target": 0.40},
    {"name": "duplicate_rate_at_10", "label": "Duplicate Rate@10", "direction": "lower", "default_weight": 0.05, "default_enabled": True, "hard_gate": False, "target": 0.10},
    {"name": "orphan_evidence_rate", "label": "Orphan Evidence Rate", "direction": "lower", "default_weight": 0.05, "default_enabled": True, "hard_gate": False, "target": 0.05},
    {"name": "context_token_efficiency", "label": "Context Token Efficiency", "direction": "higher", "default_weight": 0.05, "default_enabled": False, "hard_gate": False, "target": 0.50},
    {"name": "average_chunk_tokens", "label": "Average Chunk Tokens", "direction": "lower", "default_weight": 0.0, "default_enabled": False, "hard_gate": False, "target": 512},
    {"name": "chunk_count", "label": "Chunk Count", "direction": "lower", "default_weight": 0.0, "default_enabled": False, "hard_gate": False, "target": 1000},
]


class MetricDefinition(BaseModel):
    name: str
    label: str
    enabled: bool = True
    configured_weight: float = Field(ge=0)
    direction: str = "higher"  # higher|lower
    hard_gate: bool = False
    target: Optional[float] = None
    gate_tolerance: float = 0.0


class MetricResult(BaseModel):
    name: str
    raw_value: float
    normalized_value: float
    configured_weight: float
    effective_weight: float
    contribution: float
    direction: str
    hard_gate: bool = False
    gate_passed: Optional[bool] = None
    target: Optional[float] = None


class EvaluationProfile(BaseModel):
    evaluation_profile_id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str = "default"
    top_k: int = 10
    metrics: list[MetricDefinition] = Field(default_factory=list)
    composite_target: float = 0.90
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def ensure_metrics(self) -> "EvaluationProfile":
        if not self.metrics:
            self.metrics = [
                MetricDefinition(
                    name=m["name"],
                    label=m["label"],
                    enabled=m["default_enabled"],
                    configured_weight=m["default_weight"],
                    direction=m["direction"],
                    hard_gate=m["hard_gate"],
                    target=m["target"],
                )
                for m in DEFAULT_METRICS
            ]
        return self


class StoppingRecommendation(BaseModel):
    recommendation: str  # ACCEPT|STOP_NO_MEANINGFUL_HEADROOM|REGRESSION|CONTINUE
    relative_composite_gain: Optional[float] = None
    absolute_recall_gain: Optional[float] = None
    critical_segment_gain: Optional[float] = None
    reasons: list[str] = Field(default_factory=list)
    automatic: bool = False  # always False — never auto-stop


def normalize_weights(metrics: list[MetricDefinition]) -> dict[str, float]:
    enabled = [m for m in metrics if m.enabled and m.configured_weight >= 0]
    if not enabled:
        raise ValueError("At least one metric must be enabled")
    total = sum(m.configured_weight for m in enabled)
    if total <= 0:
        raise ValueError("Sum of enabled metric weights must be > 0")
    return {m.name: m.configured_weight / total for m in enabled}


def normalize_metric_value(raw: float, direction: str, target: Optional[float] = None) -> float:
    """Map raw metric to [0,1] contribution-friendly score. Higher is better after transform."""
    if direction == "lower":
        # For rates in [0,1], invert; for unbounded, use 1/(1+raw)
        if 0 <= raw <= 1:
            return max(0.0, min(1.0, 1.0 - raw))
        return 1.0 / (1.0 + max(0.0, raw))
    return max(0.0, min(1.0, raw if raw <= 1.5 else raw / (target or raw or 1.0)))


def compute_composite(results: list[MetricResult]) -> float:
    return sum(r.contribution for r in results)


def recommend_stopping(
    current_composite: float,
    previous_composite: Optional[float],
    current_recall_at_10: float,
    previous_recall_at_10: Optional[float],
    critical_segment_gains: list[float],
    gates_passed: bool,
    composite_target: float,
    min_composite_rel_gain: float = 0.01,
    min_recall_abs_gain: float = 0.005,
    critical_segment_gain: float = 0.02,
) -> StoppingRecommendation:
    if gates_passed and current_composite >= composite_target:
        return StoppingRecommendation(
            recommendation="ACCEPT",
            relative_composite_gain=None,
            absolute_recall_gain=None,
            reasons=["All hard gates passed and composite target met"],
            automatic=False,
        )
    if previous_composite is None or previous_recall_at_10 is None:
        return StoppingRecommendation(
            recommendation="CONTINUE",
            reasons=["No prior run for comparison"],
            automatic=False,
        )
    rel_gain = (current_composite - previous_composite) / max(abs(previous_composite), 1e-9)
    abs_recall = current_recall_at_10 - previous_recall_at_10
    max_crit = max(critical_segment_gains) if critical_segment_gains else 0.0

    if current_composite < previous_composite:
        return StoppingRecommendation(
            recommendation="REGRESSION",
            relative_composite_gain=rel_gain,
            absolute_recall_gain=abs_recall,
            critical_segment_gain=max_crit,
            reasons=["Composite score declined"],
            automatic=False,
        )
    if (
        rel_gain < min_composite_rel_gain
        and abs_recall < min_recall_abs_gain
        and max_crit < critical_segment_gain
    ):
        return StoppingRecommendation(
            recommendation="STOP_NO_MEANINGFUL_HEADROOM",
            relative_composite_gain=rel_gain,
            absolute_recall_gain=abs_recall,
            critical_segment_gain=max_crit,
            reasons=[
                f"Relative composite gain {rel_gain:.4f} < {min_composite_rel_gain}",
                f"Recall@10 absolute gain {abs_recall:.4f} < {min_recall_abs_gain}",
                f"No critical segment gain >= {critical_segment_gain}",
            ],
            automatic=False,
        )
    return StoppingRecommendation(
        recommendation="CONTINUE",
        relative_composite_gain=rel_gain,
        absolute_recall_gain=abs_recall,
        critical_segment_gain=max_crit,
        reasons=["Meaningful improvement headroom remains"],
        automatic=False,
    )
