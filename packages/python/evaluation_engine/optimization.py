"""Localized JSON Patch optimization proposals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from canonical_schemas.evaluation import recommend_stopping, StoppingRecommendation
from evaluation_engine.failures import FailureRecord, NOT_CHUNK_OPTIMIZABLE
from shared.ids import new_id


@dataclass
class StoppingDecision:
    recommendation: StoppingRecommendation


def generate_json_patch_proposal(
    *,
    plan: dict[str, Any],
    failures: list[FailureRecord],
    metrics: dict[str, Any],
    locked_paths: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Generate localized JSON Patch changes — never rewrite entire plan by default."""
    locked_paths = locked_paths or set()
    changes = []
    unit_strategies = plan.get("unit_strategies") or []

    for failure in failures:
        if not failure.safe_to_optimize_via_chunk_config:
            continue
        if any(c in NOT_CHUNK_OPTIMIZABLE for c in failure.reason_codes):
            continue
        # find affected unit index
        for unit_id in failure.affected_logical_units:
            idx = next((i for i, u in enumerate(unit_strategies) if u.get("logical_unit_id") == unit_id), None)
            if idx is None:
                continue
            current = unit_strategies[idx]
            params = dict(current.get("parameters") or {})
            path_size = f"/unit_strategies/{idx}/parameters/chunk_size"
            if path_size in locked_paths or current.get("locked"):
                continue

            before = params.get("chunk_size", 512)
            after = before
            reason = failure.reason_codes[0] if failure.reason_codes else "UNKNOWN"
            if reason in ("EVIDENCE_SPLIT_ACROSS_CHUNKS", "CHUNK_TOO_SMALL", "CROSS_UNIT_CONTINUATION_BROKEN"):
                after = min(4096, int(before * 1.5))
            elif reason in ("CHUNK_TOO_LARGE", "EXCESSIVE_OVERLAP"):
                after = max(128, int(before * 0.75))
            elif reason == "WRONG_STRATEGY_SELECTED":
                path_strat = f"/unit_strategies/{idx}/strategy_id"
                if path_strat not in locked_paths:
                    changes.append({
                        "change_id": new_id(),
                        "scope": "logical_unit",
                        "op": "replace",
                        "path": path_strat,
                        "before": current.get("strategy_id"),
                        "after": "heading_section",
                        "reason_codes": failure.reason_codes,
                        "supporting_qa_ids": failure.affected_qa_ids,
                        "supporting_failure_ids": [failure.failure_id],
                        "expected_metric_effect": {"evidence_recall_at_10": 0.02},
                        "expected_index_size_effect": "neutral",
                        "risk": "medium",
                        "confidence": failure.confidence,
                    })
                continue
            if after != before:
                changes.append({
                    "change_id": new_id(),
                    "scope": "logical_unit",
                    "op": "replace",
                    "path": path_size,
                    "before": before,
                    "after": after,
                    "reason_codes": failure.reason_codes,
                    "supporting_qa_ids": failure.affected_qa_ids,
                    "supporting_failure_ids": [failure.failure_id],
                    "expected_metric_effect": {"evidence_recall_at_10": 0.015},
                    "expected_index_size_effect": "slight_decrease" if after > before else "slight_increase",
                    "risk": "low",
                    "confidence": failure.confidence,
                })

    return {
        "proposal_id": new_id(),
        "status": "PROPOSED",
        "changes": changes,
        "summary": f"{len(changes)} localized patch operations",
        "automatic_execution": False,
    }


def apply_accepted_changes(plan: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply JSON-pointer-like paths under /unit_strategies/... only."""
    import copy
    new_plan = copy.deepcopy(plan)
    for ch in changes:
        if ch.get("status") in ("REJECTED",):
            continue
        path = ch["path"].strip("/").split("/")
        if path[0] != "unit_strategies":
            continue
        idx = int(path[1])
        target = new_plan["unit_strategies"][idx]
        if len(path) == 3 and path[2] == "strategy_id":
            target["strategy_id"] = ch.get("after", ch.get("value"))
        elif len(path) >= 4 and path[2] == "parameters":
            target.setdefault("parameters", {})[path[3]] = ch.get("after", ch.get("value"))
    return new_plan
