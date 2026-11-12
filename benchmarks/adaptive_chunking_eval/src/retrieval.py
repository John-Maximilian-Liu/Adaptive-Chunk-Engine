"""Shared dense retrieval + rerank + adaptive selection helpers."""
from __future__ import annotations

import math
import os
import re
from typing import Any, Callable, Optional, Sequence

from intrinsic_metrics import score_chunks

EmbedFn = Callable[[Sequence[str]], list[list[float]]]


def cosine(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def l2_normalize(vecs: list[list[float]]) -> list[list[float]]:
    out = []
    for v in vecs:
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def dense_retrieve(
    embed_fn: EmbedFn,
    question: str,
    chunks: list[str],
    *,
    top_k: int = 20,
) -> list[str]:
    if not chunks:
        return []
    q_emb = embed_fn([question])[0]
    c_embs = embed_fn(chunks)
    ranked = sorted(
        ((cosine(q_emb, ce), c) for ce, c in zip(c_embs, chunks)),
        reverse=True,
    )
    return [c for _, c in ranked[: min(top_k, len(ranked))]]


def retrieve_with_optional_rerank(
    *,
    embed_fn: EmbedFn,
    rerank_fn: Optional[Callable[[str, list[str], int], list[str]]],
    question: str,
    chunks: list[str],
    top_k: int = 5,
    candidate_k: int = 20,
) -> list[str]:
    """Dense retrieve top ``candidate_k``, optionally rerank to ``top_k``."""
    if not chunks:
        return []
    pool = dense_retrieve(embed_fn, question, chunks, top_k=max(candidate_k, top_k))
    if rerank_fn is None or len(pool) <= 1:
        return pool[:top_k]
    return rerank_fn(question, pool, top_k)


def evidence_coverage(evidence_quote: str, retrieved: list[str]) -> float:
    ev_terms = set(re.findall(r"[a-z0-9]+", (evidence_quote or "").lower()))
    if not ev_terms:
        return 0.0
    ctx_terms = set(re.findall(r"[a-z0-9]+", " ".join(retrieved).lower()))
    return len(ev_terms & ctx_terms) / max(1, len(ev_terms))


def micro_rag_score(
    *,
    embed_fn: EmbedFn,
    rerank_fn: Optional[Callable[[str, list[str], int], list[str]]],
    chunks: list[str],
    qa_pairs: list[dict],
    top_k: int = 5,
    max_q: int = 3,
) -> float:
    """Cheap selection proxy: evidence-term coverage after dense(+rerank). No LLM judge."""
    if not qa_pairs or not chunks:
        return 0.0
    scores = []
    for qa in qa_pairs[:max_q]:
        q = qa.get("question") if isinstance(qa, dict) else getattr(qa, "question", "")
        ev = qa.get("evidence_quote") if isinstance(qa, dict) else getattr(qa, "evidence_quote", "")
        hits = retrieve_with_optional_rerank(
            embed_fn=embed_fn,
            rerank_fn=rerank_fn,
            question=q,
            chunks=chunks,
            top_k=top_k,
        )
        scores.append(evidence_coverage(ev, hits))
    return float(sum(scores) / max(1, len(scores)))


def adaptive_select(
    text: str,
    *,
    strategies: Sequence[tuple[str, str, dict]],
    chunk_fn: Callable[[str, str, dict], list[str]],
    embed_fn: EmbedFn,
    mode: str = "intrinsic",
    qa_pairs: Optional[list[Any]] = None,
    rerank_fn: Optional[Callable[[str, list[str], int], list[str]]] = None,
    intrinsic_shortlist: int = 3,
    micro_alpha: float = 0.55,
    min_tokens: int = 50,
    max_tokens: int = 1100,
) -> tuple[str, list[str], dict]:
    """Select a chunker per document.

    Modes:
      - intrinsic: argmax mean(RC/ICC/DCC/BI/SC)
      - rag_microloop: shortlist by intrinsic, then blend with micro RAG coverage
    """
    details: dict[str, Any] = {"mode": mode, "candidates": {}}
    scored: list[tuple[str, list[str], float, dict]] = []
    for name, sid, params in strategies:
        chunks = chunk_fn(text, sid, params)
        score = score_chunks(chunks, text, min_tokens=min_tokens, max_tokens=max_tokens, embed_fn=embed_fn)
        pct = score.as_percent_dict()
        details["candidates"][name] = pct
        scored.append((name, chunks, float(score.mean or 0.0), pct))

    if not scored:
        return "fixed_token_512", [], details

    scored.sort(key=lambda x: x[2], reverse=True)

    if mode != "rag_microloop" or not qa_pairs:
        best_name, best_chunks, best_mean, _ = scored[0]
        details["selected_by"] = "intrinsic"
        details["selected_intrinsic_mean"] = best_mean
        return best_name, best_chunks, details

    shortlist = scored[: max(1, intrinsic_shortlist)]
    blended: list[tuple[str, list[str], float, float, float]] = []
    for name, chunks, mean, _pct in shortlist:
        micro = micro_rag_score(
            embed_fn=embed_fn,
            rerank_fn=rerank_fn,
            chunks=chunks,
            qa_pairs=list(qa_pairs),
            top_k=5,
            max_q=3,
        )
        final = micro_alpha * mean + (1.0 - micro_alpha) * micro
        details["candidates"][name]["micro_rag"] = round(100.0 * micro, 2)
        details["candidates"][name]["blend"] = round(100.0 * final, 2)
        blended.append((name, chunks, mean, micro, final))

    blended.sort(key=lambda x: x[4], reverse=True)
    best_name, best_chunks, best_mean, best_micro, best_final = blended[0]
    details["selected_by"] = "rag_microloop"
    details["selected_intrinsic_mean"] = best_mean
    details["selected_micro_rag"] = best_micro
    details["selected_blend"] = best_final
    details["micro_alpha"] = micro_alpha
    details["shortlist"] = [b[0] for b in blended]
    return best_name, best_chunks, details


def env_flags() -> dict[str, Any]:
    return {
        "chat_model": os.environ.get("ACE_CHAT_MODEL", "openai/gpt-4o"),
        "embed_model": os.environ.get("ACE_EMBED_MODEL", "openai/text-embedding-3-small"),
        "rerank_model": os.environ.get("ACE_RERANK_MODEL", "cohere/rerank-v3.5"),
        "use_rerank": os.environ.get("ACE_USE_RERANK", "1") not in {"0", "false", "False"},
        "adaptive_mode": os.environ.get("ACE_ADAPTIVE_MODE", "intrinsic"),
        "retrieve_candidate_k": int(os.environ.get("ACE_RETRIEVE_CANDIDATE_K", "20")),
        "retrieve_top_k": int(os.environ.get("ACE_RETRIEVE_TOP_K", "5")),
        "micro_alpha": float(os.environ.get("ACE_MICRO_ALPHA", "0.55")),
    }
