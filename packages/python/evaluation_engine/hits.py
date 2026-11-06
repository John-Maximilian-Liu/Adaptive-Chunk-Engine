"""Three-stage evidence matching for chunk hits."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from chunk_adapters.excel import range_intersection_coverage


@dataclass
class HitResult:
    is_hit: bool
    stage: Optional[str]  # element_id|source_span|semantic|none
    score: float = 0.0
    matched_element_ids: list[str] = field(default_factory=list)
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def _text_coverage(evidence: str, chunk_text: str) -> float:
    if not evidence:
        return 0.0
    ev = evidence.lower().strip()
    ch = chunk_text.lower()
    if ev in ch:
        return 1.0
    # token overlap coverage
    ev_tokens = set(ev.split())
    ch_tokens = set(ch.split())
    if not ev_tokens:
        return 0.0
    return len(ev_tokens & ch_tokens) / len(ev_tokens)


def _span_iou(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def determine_hit(
    *,
    qa_item: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
    matching_policy: Optional[dict[str, Any]] = None,
    semantic_scores: Optional[dict[str, float]] = None,
) -> HitResult:
    """
    Stages:
    1. Element ID matching
    2. Source-span / text-coverage matching
    3. Semantic fallback (only when no reliable exact locator)
    Never identify hits solely by chunk ID.
    """
    policy = {
        "mode": "contains_any_evidence",
        "minimum_evidence_count": 1,
        "element_id_matching": True,
        "min_text_coverage": 0.70,
        "min_source_span_iou": 0.50,
        "semantic_fallback": True,
        "semantic_threshold": 0.85,
        "llm_judge_enabled": False,
        **(matching_policy or {}),
    }
    expected_elements = set(qa_item.get("expected_element_ids") or [])
    evidence_quotes = qa_item.get("evidence_quotes") or []
    semantic_scores = semantic_scores or {}

    per_chunk_hits: list[HitResult] = []

    for chunk in retrieved_chunks:
        chunk_elements = set(chunk.get("element_ids") or [])
        chunk_text = chunk.get("text") or chunk.get("content") or ""

        # Stage 1: element ID
        if policy["element_id_matching"] and expected_elements:
            overlap = expected_elements & chunk_elements
            if overlap:
                per_chunk_hits.append(HitResult(
                    is_hit=True,
                    stage="element_id",
                    score=1.0,
                    matched_element_ids=list(overlap),
                    reason="element_id_match",
                ))
                continue

        # Stage 2: text coverage / source span / excel range
        best_cov = 0.0
        matched = []
        for eq in evidence_quotes:
            quote = eq.get("quote") or ""
            cov = _text_coverage(quote, chunk_text)
            # Excel range coverage when both have ranges
            loc = eq.get("locator") or {}
            chunk_locs = chunk.get("locators") or []
            for cl in chunk_locs:
                if loc.get("range") and cl.get("range"):
                    cov = max(cov, range_intersection_coverage(loc["range"], cl["range"]))
            # source span IoU
            for span in chunk.get("source_spans") or []:
                if eq.get("element_id") and span.get("element_id") == eq.get("element_id"):
                    iou = _span_iou(0, len(quote), span.get("char_start", 0), span.get("char_end", 0))
                    if iou >= policy["min_source_span_iou"]:
                        cov = max(cov, iou)
            if cov >= policy["min_text_coverage"]:
                matched.append(eq.get("element_id"))
            best_cov = max(best_cov, cov)

        if best_cov >= policy["min_text_coverage"]:
            per_chunk_hits.append(HitResult(
                is_hit=True,
                stage="source_span",
                score=best_cov,
                matched_element_ids=[m for m in matched if m],
                reason="text_or_span_coverage",
                details={"coverage": best_cov},
            ))
            continue

        # Stage 3: semantic fallback only when no reliable exact locator
        has_reliable_locator = bool(expected_elements) or any(
            (eq.get("locator") or {}).get("range") or eq.get("element_id") for eq in evidence_quotes
        )
        if policy["semantic_fallback"] and not has_reliable_locator:
            score = float(semantic_scores.get(chunk.get("chunk_id", ""), 0.0))
            if score >= policy["semantic_threshold"]:
                per_chunk_hits.append(HitResult(
                    is_hit=True,
                    stage="semantic",
                    score=score,
                    reason="semantic_fallback",
                ))
                continue

        per_chunk_hits.append(HitResult(
            is_hit=False,
            stage="none",
            score=best_cov,
            reason="no_stage_matched",
            details={"best_coverage": best_cov, "chunk_elements": list(chunk_elements)},
        ))

    hit_chunks = [h for h in per_chunk_hits if h.is_hit]
    mode = policy["mode"]
    if mode == "contains_any_evidence":
        ok = len(hit_chunks) >= 1
    elif mode == "contains_all_evidence":
        # all evidence element ids must appear across hits
        found = set()
        for h in hit_chunks:
            found.update(h.matched_element_ids)
        ok = expected_elements.issubset(found) if expected_elements else len(hit_chunks) > 0
    elif mode == "minimum_evidence_count":
        ok = len(hit_chunks) >= int(policy["minimum_evidence_count"])
    elif mode == "weighted_evidence_coverage":
        ok = (sum(h.score for h in hit_chunks) / max(len(retrieved_chunks), 1)) >= policy["min_text_coverage"]
    else:
        ok = len(hit_chunks) >= 1

    best = max(per_chunk_hits, key=lambda h: h.score) if per_chunk_hits else HitResult(False, "none", reason="no_results")
    return HitResult(
        is_hit=ok,
        stage=best.stage if ok else "none",
        score=best.score,
        matched_element_ids=best.matched_element_ids,
        reason="policy_satisfied" if ok else best.reason,
        details={"per_chunk": [h.__dict__ for h in per_chunk_hits], "mode": mode},
    )
