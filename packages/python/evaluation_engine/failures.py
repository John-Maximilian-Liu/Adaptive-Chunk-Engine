"""Rule-based failure classification with optional LLM explanation hook."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


PARSER_CODES = {
    "PARSER_CONTENT_MISSING", "OCR_LOW_CONFIDENCE", "READING_ORDER_ERROR",
    "TABLE_STRUCTURE_LOST", "MERGED_CELL_CONTEXT_LOST", "FORMULA_DEPENDENCY_LOST",
    "IMAGE_CONTENT_NOT_EXTRACTED",
}
CHUNKING_CODES = {
    "EVIDENCE_SPLIT_ACROSS_CHUNKS", "CHUNK_TOO_SMALL", "CHUNK_TOO_LARGE",
    "HEADER_CONTEXT_LOST", "TABLE_HEADER_NOT_REPEATED", "CROSS_UNIT_CONTINUATION_BROKEN",
    "EXCESSIVE_OVERLAP", "ORPHAN_EVIDENCE", "WRONG_STRATEGY_SELECTED",
}
INDEXING_CODES = {
    "CHUNK_NOT_INDEXED", "METADATA_FILTER_MISMATCH", "DUPLICATE_INDEX_RECORD",
    "WRONG_EXPERIMENT_NAMESPACE", "EMBEDDING_FAILURE",
}
RETRIEVAL_CODES = {
    "SEMANTIC_MISMATCH", "EXACT_TERM_MISS", "CORRECT_RESULT_LOW_RANK",
    "DUPLICATE_RESULTS", "RERANKER_REGRESSION", "FILTER_TOO_RESTRICTIVE", "TOP_K_TOO_SMALL",
}
QA_CODES = {
    "EVIDENCE_NOT_FOUND", "EVIDENCE_AMBIGUOUS", "INCORRECT_ANSWER",
    "QUESTION_UNANSWERABLE", "MULTI_HOP_EVIDENCE_INCOMPLETE", "LLM_SCHEMA_FILL_LOW_CONFIDENCE",
}

# Failures that must NOT be treated as chunk-size optimization opportunities
NOT_CHUNK_OPTIMIZABLE = PARSER_CODES | QA_CODES | {
    "WRONG_EXPERIMENT_NAMESPACE", "CHUNK_NOT_INDEXED", "METADATA_FILTER_MISMATCH",
    "DUPLICATE_INDEX_RECORD", "EMBEDDING_FAILURE",
}


@dataclass
class FailureRecord:
    failure_id: str
    primary_category: str
    secondary_categories: list[str] = field(default_factory=list)
    severity: str = "medium"
    confidence: float = 0.6
    supporting_facts: list[str] = field(default_factory=list)
    affected_qa_ids: list[str] = field(default_factory=list)
    affected_logical_units: list[str] = field(default_factory=list)
    related_chunks: list[str] = field(default_factory=list)
    recommended_action: str = ""
    safe_to_optimize_via_chunk_config: bool = True
    reason_codes: list[str] = field(default_factory=list)


def _category_for(code: str) -> str:
    if code in PARSER_CODES:
        return "PARSER"
    if code in CHUNKING_CODES:
        return "CHUNKING"
    if code in INDEXING_CODES:
        return "INDEXING"
    if code in RETRIEVAL_CODES:
        return "RETRIEVAL"
    if code in QA_CODES:
        return "QA_GROUND_TRUTH"
    return "CHUNKING"


def classify_failures(
    *,
    hits: list[dict[str, Any]],
    qa_items: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    indexed_chunk_ids: Optional[set[str]] = None,
) -> list[FailureRecord]:
    from shared.ids import new_id

    qa_by_id = {q["qa_id"]: q for q in qa_items}
    chunk_by_id = {c.get("chunk_id"): c for c in chunks}
    indexed_chunk_ids = indexed_chunk_ids or {c.get("chunk_id") for c in chunks}
    failures: list[FailureRecord] = []

    for hit in hits:
        if hit.get("is_hit"):
            continue
        qa = qa_by_id.get(hit.get("qa_id"), {})
        codes: list[str] = []
        facts: list[str] = []
        related = []
        units = list(qa.get("expected_logical_unit_ids") or [])

        expected_els = set(qa.get("expected_element_ids") or [])
        # find chunks containing any expected element
        containing = []
        for c in chunks:
            if expected_els & set(c.get("element_ids") or []):
                containing.append(c)
        related = [c.get("chunk_id") for c in containing if c.get("chunk_id")]

        if qa.get("confidence") is not None and qa.get("confidence", 1) < 0.5:
            codes.append("LLM_SCHEMA_FILL_LOW_CONFIDENCE")
            facts.append("QA confidence below 0.5")
        if not expected_els and not (qa.get("evidence_quotes") or []):
            codes.append("EVIDENCE_NOT_FOUND")
            facts.append("No expected elements or evidence quotes")
        if containing and len(containing) > 1:
            codes.append("EVIDENCE_SPLIT_ACROSS_CHUNKS")
            facts.append(f"Evidence elements split across {len(containing)} chunks")
        if containing:
            sizes = [c.get("token_count", 0) for c in containing]
            if sizes and max(sizes) < 128:
                codes.append("CHUNK_TOO_SMALL")
            if sizes and min(sizes) > 3000:
                codes.append("CHUNK_TOO_LARGE")
        if related and any(cid not in indexed_chunk_ids for cid in related):
            codes.append("CHUNK_NOT_INDEXED")
            facts.append("Related chunk missing from index")
        details = hit.get("details") or {}
        per_chunk = details.get("per_chunk") or []
        if per_chunk and all(p.get("reason") == "no_stage_matched" for p in per_chunk):
            # check if evidence text appears nowhere
            quotes = [e.get("quote", "") for e in (qa.get("evidence_quotes") or [])]
            joined = " ".join(c.get("text", "") for c in chunks)
            if quotes and not any(q and q.lower() in joined.lower() for q in quotes):
                codes.append("ORPHAN_EVIDENCE")
            else:
                codes.append("SEMANTIC_MISMATCH")
                # low rank check
                codes.append("CORRECT_RESULT_LOW_RANK")

        if not codes:
            codes = ["SEMANTIC_MISMATCH"]
            facts.append(hit.get("reason") or "unknown")

        primary_code = codes[0]
        primary_cat = _category_for(primary_code)
        safe = primary_code not in NOT_CHUNK_OPTIMIZABLE and not any(c in NOT_CHUNK_OPTIMIZABLE for c in codes)

        action = "Review retrieval query and embeddings"
        if "EVIDENCE_SPLIT_ACROSS_CHUNKS" in codes:
            action = "Increase chunk size or switch to heading_section / cross_unit_continuation"
        elif "CHUNK_TOO_SMALL" in codes:
            action = "Increase chunk_size"
        elif "CHUNK_TOO_LARGE" in codes:
            action = "Decrease chunk_size or use parent_child"
        elif primary_cat == "PARSER":
            action = "Re-parse with alternate parser; do not optimize chunk size"
        elif primary_cat == "QA_GROUND_TRUTH":
            action = "Review/edit QA evidence; not a chunk-size issue"
        elif primary_cat == "INDEXING":
            action = "Fix indexing integrity before chunk optimization"

        failures.append(FailureRecord(
            failure_id=new_id(),
            primary_category=primary_cat,
            secondary_categories=[_category_for(c) for c in codes[1:]],
            severity="high" if primary_cat in ("PARSER", "INDEXING") else "medium",
            confidence=0.75,
            supporting_facts=facts,
            affected_qa_ids=[hit.get("qa_id")],
            affected_logical_units=units,
            related_chunks=related,
            recommended_action=action,
            safe_to_optimize_via_chunk_config=safe,
            reason_codes=codes,
        ))
    return failures
