"""Deterministic mock LLM provider for local tests and offline development."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from llm_gateway.providers.base import EmbeddingResponse, LLMProvider, LLMResponse, LLMUsage


class MockLLMProvider(LLMProvider):
    name = "mock"

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def _seed(self, text: str) -> int:
        return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        response_json: bool = False,
        task: str = "generic",
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        start = time.perf_counter()
        context = context or {}
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        structured: Optional[dict[str, Any]] = None
        content = ""

        if task == "chunk_strategy_planning" or "chunk plan" in user.lower() or "strategy plan" in user.lower():
            units = context.get("logical_units") or []
            strategies = []
            for u in units:
                unit_type = u.get("unit_type", "page")
                strategy = "heading_section"
                params: dict[str, Any] = {"chunk_size": 512, "chunk_overlap": 64}
                if unit_type in ("sheet",):
                    strategy = "excel_table_row_group"
                    params = {"rows_per_chunk": 20, "repeat_header": True}
                elif unit_type == "slide":
                    strategy = "no_split"
                    params = {}
                elif u.get("profile", {}).get("continuation_candidate"):
                    strategy = "cross_unit_continuation"
                strategies.append({
                    "logical_unit_id": u.get("logical_unit_id"),
                    "strategy_id": strategy,
                    "parameters": params,
                    "mode": "auto",
                    "confidence": 0.82,
                    "reason_codes": ["mock_heuristic"],
                    "explanation": f"Mock plan selected {strategy} for {unit_type}",
                })
            structured = {
                "plan_version": "1.0.0",
                "unit_strategies": strategies,
                "region_overrides": [],
                "warnings": [],
            }
            content = json.dumps(structured)
        elif task == "qa_generation" or "generate qa" in user.lower():
            count = int(context.get("count", 5))
            distribution = context.get("distribution") or {"direct_fact": count}
            elements = context.get("elements") or []
            items = []
            idx = 0
            for qtype, n in distribution.items():
                for _ in range(int(n)):
                    el = elements[idx % len(elements)] if elements else {"element_id": None, "text": "sample", "logical_unit_id": None}
                    quote = (el.get("text") or "sample")[:120]
                    items.append({
                        "question": f"[{qtype}] What does the document say about: {quote[:40]}?",
                        "answer": quote,
                        "question_type": qtype,
                        "expected_element_ids": [el["element_id"]] if el.get("element_id") else [],
                        "expected_logical_unit_ids": [el["logical_unit_id"]] if el.get("logical_unit_id") else [],
                        "evidence_quotes": [{"quote": quote, "element_id": el.get("element_id")}],
                        "confidence": 0.9,
                    })
                    idx += 1
                    if len(items) >= count:
                        break
                if len(items) >= count:
                    break
            structured = {"items": items}
            content = json.dumps(structured)
        elif task == "qa_schema_completion" or "complete qa schema" in user.lower():
            candidates = context.get("candidate_elements") or []
            question = context.get("question") or ""
            answer = context.get("answer") or ""
            # Only use provided candidates — never invent IDs
            chosen = candidates[:2]
            if not chosen:
                structured = {
                    "expected_element_ids": [],
                    "expected_logical_unit_ids": [],
                    "evidence_quotes": [],
                    "confidence": 0.2,
                    "warnings": ["no_valid_candidates"],
                    "review_status": "needs_review",
                    "question_type": "direct_fact",
                }
            else:
                structured = {
                    "expected_element_ids": [c["element_id"] for c in chosen if c.get("element_id")],
                    "expected_logical_unit_ids": list({c["logical_unit_id"] for c in chosen if c.get("logical_unit_id")}),
                    "evidence_quotes": [{"quote": (c.get("text") or "")[:160], "element_id": c.get("element_id")} for c in chosen],
                    "confidence": 0.75 if answer else 0.55,
                    "warnings": [],
                    "review_status": "pending",
                    "question_type": "direct_fact",
                    "difficulty": "medium",
                }
            # Reject invented IDs if somehow present
            valid_ids = {c.get("element_id") for c in candidates}
            structured["expected_element_ids"] = [i for i in structured["expected_element_ids"] if i in valid_ids]
            content = json.dumps(structured)
        elif task == "failure_analysis" or "classify failure" in user.lower():
            structured = {
                "primary_category": "CHUNKING",
                "secondary_categories": ["EVIDENCE_SPLIT_ACROSS_CHUNKS"],
                "severity": "medium",
                "confidence": 0.7,
                "explanation": "Mock failure analysis suggests evidence may be split across chunks.",
                "safe_to_optimize_via_chunk_config": True,
                "recommended_action": "Increase chunk size or use heading_section strategy",
            }
            content = json.dumps(structured)
        elif task == "optimization_proposal" or "optimization" in user.lower():
            structured = {
                "changes": [
                    {
                        "scope": "logical_unit",
                        "op": "replace",
                        "path": "/unit_strategies/0/parameters/chunk_size",
                        "before": 512,
                        "after": 768,
                        "reason_codes": ["EVIDENCE_SPLIT_ACROSS_CHUNKS"],
                        "supporting_qa_ids": context.get("qa_ids") or [],
                        "supporting_failure_ids": context.get("failure_ids") or [],
                        "expected_metric_effect": {"evidence_recall_at_10": 0.02},
                        "expected_index_size_effect": "slight_decrease",
                        "risk": "low",
                        "confidence": 0.7,
                    }
                ],
                "summary": "Increase chunk size for units with split evidence",
            }
            content = json.dumps(structured)
        elif task == "visual_scene_graph":
            structured = {
                "nodes": [
                    {"node_id": "n1", "label": "Start", "node_type": "process", "bbox": [10, 10, 80, 40], "source_element_id": context.get("source_element_id")},
                    {"node_id": "n2", "label": "End", "node_type": "process", "bbox": [10, 80, 80, 110], "source_element_id": context.get("source_element_id")},
                ],
                "edges": [
                    {"edge_id": "e1", "source_node_id": "n1", "target_node_id": "n2", "label": "next", "edge_type": "connects"},
                ],
                "groups": [
                    {"group_id": "g1", "label": "Flow", "node_ids": ["n1", "n2"]},
                ],
            }
            content = json.dumps(structured)
        else:
            structured = {"message": "mock_response", "echo": user[:200]}
            content = json.dumps(structured) if response_json else f"mock:{user[:200]}"

        latency = (time.perf_counter() - start) * 1000
        usage = LLMUsage(prompt_tokens=max(1, len(user) // 4), completion_tokens=max(1, len(content) // 4))
        usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        return LLMResponse(
            content=content,
            structured=structured,
            provider=self.name,
            requested_model=model,
            resolved_deployment="mock-deployment",
            request_id=f"mock-{self._seed(user)}",
            latency_ms=latency,
            usage=usage,
            structured_output_valid=structured is not None,
            raw={"mock": True},
        )

    async def embed(self, *, texts: list[str], model: str, dimensions: Optional[int] = None, **kwargs: Any) -> EmbeddingResponse:
        start = time.perf_counter()
        dims = dimensions or self.dimensions
        vectors = []
        for t in texts:
            seed = self._seed(t)
            # deterministic pseudo-embedding
            vec = []
            for i in range(dims):
                v = ((seed >> (i % 16)) ^ (i * 2654435761)) & 0xFFFF
                vec.append((v / 65535.0) * 2 - 1)
            # L2 normalize
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            vectors.append([x / norm for x in vec])
        latency = (time.perf_counter() - start) * 1000
        return EmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            request_id=f"mock-emb-{self._seed('|'.join(texts)[:64])}",
            latency_ms=latency,
            usage=LLMUsage(prompt_tokens=sum(len(t) // 4 for t in texts), total_tokens=sum(len(t) // 4 for t in texts)),
            dimensions=dims,
        )

    async def health_check(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "healthy", "available": True, "mock": True}
