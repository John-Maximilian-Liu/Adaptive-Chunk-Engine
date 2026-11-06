"""Retrieval evaluation, hit determination, failure classification, optimization."""
from evaluation_engine.metrics import evaluate_run, build_metric_results
from evaluation_engine.hits import determine_hit, HitResult
from evaluation_engine.failures import classify_failures, FailureRecord
from evaluation_engine.optimization import generate_json_patch_proposal, StoppingDecision
from evaluation_engine.excel_coverage import cell_range_coverage

__all__ = [
    "evaluate_run",
    "build_metric_results",
    "determine_hit",
    "HitResult",
    "classify_failures",
    "FailureRecord",
    "generate_json_patch_proposal",
    "StoppingDecision",
    "cell_range_coverage",
]
