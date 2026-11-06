"""Retrieval metrics and composite scoring."""
from __future__ import annotations

import math
from typing import Any, Optional

from canonical_schemas.evaluation import (
    EvaluationProfile,
    MetricDefinition,
    MetricResult,
    compute_composite,
    normalize_metric_value,
    normalize_weights,
    recommend_stopping,
)
from evaluation_engine.hits import determine_hit


def _dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def build_metric_results(
    raw_metrics: dict[str, float],
    profile: EvaluationProfile,
) -> tuple[list[MetricResult], float, bool]:
    weights = normalize_weights(profile.metrics)
    results: list[MetricResult] = []
    gates_ok = True
    for m in profile.metrics:
        if not m.enabled:
            continue
        raw = float(raw_metrics.get(m.name, 0.0))
        norm = normalize_metric_value(raw, m.direction, m.target)
        eff_w = weights[m.name]
        contrib = norm * eff_w
        gate_passed = None
        if m.hard_gate and m.target is not None:
            if m.direction == "higher":
                gate_passed = raw >= (m.target - m.gate_tolerance)
            else:
                gate_passed = raw <= (m.target + m.gate_tolerance)
            gates_ok = gates_ok and bool(gate_passed)
        results.append(MetricResult(
            name=m.name,
            raw_value=raw,
            normalized_value=norm,
            configured_weight=m.configured_weight,
            effective_weight=eff_w,
            contribution=contrib,
            direction=m.direction,
            hard_gate=m.hard_gate,
            gate_passed=gate_passed,
            target=m.target,
        ))
    composite = compute_composite(results)
    composite_ok = composite >= profile.composite_target
    accepted = gates_ok and composite_ok
    return results, composite, accepted


def evaluate_run(
    *,
    qa_items: list[dict[str, Any]],
    retrievals: dict[str, list[dict[str, Any]]],  # qa_id -> top-k chunks
    profile: EvaluationProfile,
    chunks: Optional[list[dict[str, Any]]] = None,
    previous: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    hits = []
    rr_sum = 0.0
    ndcg_sum = 0.0
    precision_sum = 0.0
    dup_sum = 0.0
    page_hits = 0
    element_hits = 0
    orphan = 0
    recall_at = {1: 0, 3: 0, 5: 0, 10: 0}

    for qa in qa_items:
        if not qa.get("enabled", True):
            continue
        qid = qa["qa_id"]
        retrieved = retrievals.get(qid) or []
        top10 = retrieved[: profile.top_k]
        hit = determine_hit(qa_item=qa, retrieved_chunks=top10, matching_policy=(qa.get("matching_policy") or {}))
        hits.append({"qa_id": qid, **hit.__dict__})

        # recall@k
        for k in (1, 3, 5, 10):
            sub = determine_hit(qa_item=qa, retrieved_chunks=top10[:k], matching_policy=(qa.get("matching_policy") or {}))
            if sub.is_hit:
                recall_at[k] += 1

        # MRR
        rank = None
        for i, ch in enumerate(top10):
            h = determine_hit(qa_item=qa, retrieved_chunks=[ch], matching_policy=(qa.get("matching_policy") or {}))
            if h.is_hit:
                rank = i + 1
                break
        rr_sum += (1.0 / rank) if rank else 0.0

        # nDCG
        rels = []
        for ch in top10:
            h = determine_hit(qa_item=qa, retrieved_chunks=[ch], matching_policy=(qa.get("matching_policy") or {}))
            rels.append(1.0 if h.is_hit else 0.0)
        ideal = sorted(rels, reverse=True)
        dcg = _dcg(rels)
        idcg = _dcg(ideal) or 1.0
        ndcg_sum += dcg / idcg

        # precision
        precision_sum += (sum(rels) / max(len(rels), 1))

        # duplicates
        ids = [c.get("content_hash") or c.get("text") for c in top10]
        dup_sum += 1.0 - (len(set(ids)) / max(len(ids), 1))

        # page/element recall
        expected_units = set(qa.get("expected_logical_unit_ids") or [])
        expected_els = set(qa.get("expected_element_ids") or [])
        got_units = set()
        got_els = set()
        for ch in top10:
            got_units.update(ch.get("logical_unit_ids") or [])
            got_els.update(ch.get("element_ids") or [])
        if expected_units and expected_units & got_units:
            page_hits += 1
        elif not expected_units and hit.is_hit:
            page_hits += 1
        if expected_els and expected_els & got_els:
            element_hits += 1
        elif not expected_els and hit.is_hit:
            element_hits += 1
        if expected_els and not (expected_els & got_els) and hit.is_hit is False:
            orphan += 1

    n = max(sum(1 for q in qa_items if q.get("enabled", True)), 1)
    chunks = chunks or []
    avg_tokens = (sum(c.get("token_count", 0) for c in chunks) / max(len(chunks), 1)) if chunks else 0.0
    raw = {
        "evidence_recall_at_1": recall_at[1] / n,
        "evidence_recall_at_3": recall_at[3] / n,
        "evidence_recall_at_5": recall_at[5] / n,
        "evidence_recall_at_10": recall_at[10] / n,
        "mrr_at_10": rr_sum / n,
        "ndcg_at_10": ndcg_sum / n,
        "logical_unit_recall_at_10": page_hits / n,
        "element_recall_at_10": element_hits / n,
        "precision_at_10": precision_sum / n,
        "duplicate_rate_at_10": dup_sum / n,
        "orphan_evidence_rate": orphan / n,
        "context_token_efficiency": min(1.0, (recall_at[10] / n) / max(avg_tokens / 512, 0.01)) if avg_tokens else 0.0,
        "average_chunk_tokens": avg_tokens,
        "chunk_count": float(len(chunks)),
    }
    results, composite, accepted = build_metric_results(raw, profile)
    stopping = recommend_stopping(
        current_composite=composite,
        previous_composite=(previous or {}).get("composite_retrieval_score"),
        current_recall_at_10=raw["evidence_recall_at_10"],
        previous_recall_at_10=(previous or {}).get("evidence_recall_at_10"),
        critical_segment_gains=(previous or {}).get("critical_segment_gains") or [],
        gates_passed=accepted,
        composite_target=profile.composite_target,
    )
    return {
        "metrics": [r.model_dump() for r in results],
        "raw_metrics": raw,
        "composite_retrieval_score": composite,  # API name
        "evaluation_accuracy": composite,  # frontend label source
        "accepted": accepted,
        "hits": hits,
        "stopping_recommendation": stopping.model_dump(),
    }
