#!/usr/bin/env python3
"""ACE Adaptive Chunking live evaluation via OpenRouter.

Env overrides:
  ACE_CHAT_MODEL, ACE_EMBED_MODEL, ACE_RERANK_MODEL
  ACE_USE_RERANK=1|0
  ACE_ADAPTIVE_MODE=intrinsic|rag_microloop
  ACE_RESULTS_DIR=relative/or/absolute output dir

Requires OPENROUTER_API_KEY in the environment.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(ROOT / "packages" / "python"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from intrinsic_metrics import score_chunks  # noqa: E402
from openrouter_client import OpenRouterClient  # noqa: E402
from retrieval import adaptive_select, env_flags, l2_normalize, retrieve_with_optional_rerank  # noqa: E402
from canonical_schemas.document import ElementModel, LogicalUnitModel, Locator  # noqa: E402
from chunk_adapters import get_registry  # noqa: E402
from chunk_adapters.base import ChunkRequest  # noqa: E402
from shared.ids import new_id  # noqa: E402

FLAGS = env_flags()
_results_env = os.environ.get("ACE_RESULTS_DIR", "results/openrouter")
OUT = Path(_results_env) if Path(_results_env).is_absolute() else (HERE / _results_env)
CORPUS = HERE / "corpus"

CHAT_MODEL = FLAGS["chat_model"]
EMBED_MODEL = FLAGS["embed_model"]
RERANK_MODEL = FLAGS["rerank_model"]
USE_RERANK = FLAGS["use_rerank"]
ADAPTIVE_MODE = FLAGS["adaptive_mode"]
CANDIDATE_K = FLAGS["retrieve_candidate_k"]
TOP_K = FLAGS["retrieve_top_k"]
MICRO_ALPHA = FLAGS["micro_alpha"]

FIXED_STRATEGIES = [
    ("fixed_token_512", "fixed_token", {"chunk_size": 512, "chunk_overlap": 64}),
    ("fixed_token_256", "fixed_token", {"chunk_size": 256, "chunk_overlap": 32}),
    ("recursive_text", "recursive_text", {"chunk_size": 512, "chunk_overlap": 64}),
    ("recursive_text_1100", "recursive_text", {"chunk_size": 1100, "chunk_overlap": 100}),
    ("sentence_window", "sentence_window", {"chunk_size": 384, "chunk_overlap": 48}),
    ("heading_section", "heading_section", {"chunk_size": 512, "chunk_overlap": 64}),
    ("no_split", "no_split", {}),
]

PAPER_INTRINSIC = [
    {"method": "Adaptive Chunking (paper)", "RC": 99.0, "ICC": 68.2, "DCC": 88.8, "BI": 99.4, "SC": 99.9, "Mean": 91.07},
    {"method": "LLM regex (GPT) (paper)", "RC": 98.0, "ICC": 70.9, "DCC": 82.4, "BI": 98.1, "SC": 99.6, "Mean": 89.80},
    {"method": "LangChain recursive (paper)", "RC": 96.1, "ICC": 65.6, "DCC": 88.8, "BI": 95.0, "SC": 97.7, "Mean": 88.62},
    {"method": "Semantic (paper)", "RC": 97.5, "ICC": 69.3, "DCC": 76.3, "BI": 91.3, "SC": 48.1, "Mean": 76.49},
    {"method": "Sentence (paper)", "RC": 86.3, "ICC": 78.4, "DCC": 72.5, "BI": 61.9, "SC": 67.2, "Mean": 73.26},
]
PAPER_RAG = [
    {"method": "Adaptive Chunking (paper)", "retrieval_completeness": 67.7, "answer_correctness": 78.0, "answered_queries": "65/99"},
    {"method": "LangChain recursive (paper)", "retrieval_completeness": 58.1, "answer_correctness": 70.1, "answered_queries": "49/99"},
    {"method": "Page splitting (paper)", "retrieval_completeness": 59.1, "answer_correctness": 73.3, "answered_queries": "49/99"},
]


def _domain_corpus() -> list[dict]:
    mapping = {
        "technical_long.md": "technical",
        "ops_long.md": "technical",
        "legal_long.md": "legal",
        "finance_long.md": "legal",
        "sustainability_long.md": "sustainability",
        "sample.md": "technical",
    }
    docs = []
    for name, domain in mapping.items():
        path = CORPUS / name
        if not path.exists() and name == "sample.md":
            path = ROOT / "tests" / "fixtures" / "sample.md"
        if path.exists():
            docs.append({"doc_id": name, "domain": domain, "text": path.read_text(encoding="utf-8", errors="ignore")})
    return docs


def _chunk_with_strategy(text: str, strategy_id: str, params: dict) -> list[str]:
    reg = get_registry()
    try:
        adapter = reg.get_adapter(strategy_id)
    except KeyError:
        adapter = reg.get_adapter("fixed_token")
        strategy_id = "fixed_token"
        params = {"chunk_size": 512, "chunk_overlap": 64}
    tenant = "eval"
    doc_id, ver_id, run_id = new_id(), new_id(), new_id()
    unit = LogicalUnitModel(tenant_id=tenant, document_version_id=ver_id, unit_type="section", ordinal=0, title="unit-0")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()] or [text]
    elements = []
    for i, para in enumerate(paras):
        etype = "heading" if para.lstrip().startswith("#") else "paragraph"
        elements.append(
            ElementModel(
                tenant_id=tenant,
                document_version_id=ver_id,
                logical_unit_id=unit.logical_unit_id,
                element_type=etype,  # type: ignore[arg-type]
                text=para,
                order_index=i,
                locator=Locator(heading_path=[para[:40]] if etype == "heading" else []),
            )
        )
    hard = {
        "CHUNK_SIZE_MIN": 128,
        "CHUNK_SIZE_MAX": 4096,
        "CHUNK_SIZE_DEFAULT": 512,
        "CHUNK_OVERLAP_DEFAULT": 64,
        "CHUNK_OVERLAP_MAX_RATIO": 0.30,
        "CHUNK_HARD_TOKEN_LIMIT": 4096,
    }
    safe_params = dict(params)
    if "chunk_size" in safe_params and safe_params["chunk_size"] < 128:
        safe_params["chunk_size"] = 128
    req = ChunkRequest(
        tenant_id=tenant,
        document_id=doc_id,
        document_version_id=ver_id,
        chunk_run_id=run_id,
        experiment_id=new_id(),
        logical_unit=unit,
        region=None,
        elements=elements,
        strategy_id=strategy_id,
        parameters=safe_params,
        hard_constraints=hard,
    )
    if not adapter.validate(req).valid:
        req.parameters = {"chunk_size": 512, "chunk_overlap": 64}
        req.strategy_id = "fixed_token"
        adapter = reg.get_adapter("fixed_token")
    return [c.text for c in adapter.chunk(req) if (c.text or "").strip()]


def _qa_pairs_for(doc: dict) -> list[dict]:
    text = doc["text"]
    sections = re.findall(r"(Section\s+(\d+)\s+discusses\s+([^.]+)\.\s*([^.]+)\.)", text)
    pairs = []
    for i, (full, num, topic, follow) in enumerate(sections[:8]):
        pairs.append({
            "qa_id": f"{doc['doc_id']}-q{i}",
            "question": f"Which requirements apply in section {num} regarding {topic.split()[0]}?",
            "answer": f"{follow.strip()}. Cross-references to appendix {num} must remain intact across chunk boundaries.",
            "evidence_quote": full.strip(),
            "key_terms": [f"section {num}", topic.split()[0].lower(), f"appendix {num}"],
        })
    if not pairs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 40]
        for i, sent in enumerate(sentences[:4]):
            pairs.append({
                "qa_id": f"{doc['doc_id']}-q{i}",
                "question": f"What is stated about {' '.join(sent.split()[2:6])}?",
                "answer": sent,
                "evidence_quote": sent[:240],
                "key_terms": sent.lower().split()[2:6],
            })
    return pairs


def _llm_judge(client: OpenRouterClient, qa: dict, retrieved: list[str]) -> dict:
    context = "\n\n---\n\n".join(retrieved)[:12000]
    system = (
        "You are a strict RAG evaluation judge. "
        "Score whether the retrieved context supports answering the question. "
        "Return JSON only with keys: "
        "retrieval_completeness (0-1), answer_correctness (0-1), answered (boolean), rationale (short string)."
    )
    user = (
        f"Question: {qa['question']}\n\n"
        f"Gold answer: {qa['answer']}\n\n"
        f"Evidence quote: {qa['evidence_quote']}\n\n"
        f"Retrieved context:\n{context}\n"
    )
    raw = client.chat_json(system=system, user=user)
    def _clip(v, default=0.0):
        try:
            return max(0.0, min(1.0, float(v)))
        except Exception:
            return default
    return {
        "retrieval_completeness": _clip(raw.get("retrieval_completeness"), 0.0),
        "answer_correctness": _clip(raw.get("answer_correctness"), 0.0),
        "answered": bool(raw.get("answered")),
        "rationale": str(raw.get("rationale") or raw.get("raw") or "")[:400],
        "parse_error": bool(raw.get("parse_error")),
    }


def _rag_llm(
    client: OpenRouterClient,
    embed_fn,
    rerank_fn,
    chunks: list[str],
    qa_pairs: list[dict],
    top_k: int = TOP_K,
) -> dict:
    completeness_scores, correctness_scores = [], []
    answered = 0
    judgments = []
    for qa in qa_pairs:
        hits = retrieve_with_optional_rerank(
            embed_fn=embed_fn,
            rerank_fn=rerank_fn,
            question=qa["question"],
            chunks=chunks,
            top_k=top_k,
            candidate_k=CANDIDATE_K,
        )
        judge = _llm_judge(client, qa, hits)
        judgments.append({"qa_id": qa["qa_id"], **judge})
        completeness_scores.append(judge["retrieval_completeness"])
        correctness_scores.append(judge["answer_correctness"])
        if judge["answered"] or judge["retrieval_completeness"] >= 0.55:
            answered += 1
    n = max(1, len(qa_pairs))
    return {
        "retrieval_completeness": round(100.0 * sum(completeness_scores) / n, 2),
        "answer_correctness": round(100.0 * sum(correctness_scores) / n, 2),
        "answered_queries": f"{answered}/{len(qa_pairs)}",
        "n_queries": len(qa_pairs),
        "judgments": judgments,
    }


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = OpenRouterClient(
        chat_model=CHAT_MODEL,
        embed_model=EMBED_MODEL,
        rerank_model=RERANK_MODEL,
        cache_dir=OUT / "cache",
        batch_size=8 if "Qwen" in EMBED_MODEL or "qwen" in EMBED_MODEL else 16,
    )

    def embed_fn(texts):
        return l2_normalize(client.embed(list(texts)))

    def rerank_fn(query: str, docs: list[str], top_n: int) -> list[str]:
        return client.rerank_texts(query, docs, top_n=top_n)

    active_rerank = rerank_fn if USE_RERANK else None

    corpus = _domain_corpus()
    method_domain_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    method_overall: dict[str, list[dict]] = defaultdict(list)
    per_doc_rows = []
    methods = [(n, s, p) for n, s, p in FIXED_STRATEGIES] + [("adaptive_ace", "adaptive", {})]

    print(
        f"Live OpenRouter eval · chat={CHAT_MODEL} · embed={EMBED_MODEL} · "
        f"rerank={RERANK_MODEL if USE_RERANK else 'off'} · adaptive={ADAPTIVE_MODE} · docs={len(corpus)}"
    )

    for doc in corpus:
        text, domain = doc["text"], doc["domain"]
        qa_pairs = _qa_pairs_for(doc)
        print(f"  intrinsic: {doc['doc_id']} ({domain})")
        for name, sid, params in methods:
            if name == "adaptive_ace":
                selected, chunks, detail = adaptive_select(
                    text,
                    strategies=FIXED_STRATEGIES,
                    chunk_fn=_chunk_with_strategy,
                    embed_fn=embed_fn,
                    mode=ADAPTIVE_MODE,
                    qa_pairs=qa_pairs,
                    rerank_fn=active_rerank,
                    micro_alpha=MICRO_ALPHA,
                )
                score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
                meta = {"selected": selected, "selection": detail}
            else:
                chunks = _chunk_with_strategy(text, sid, params)
                score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
                meta = {}
            pct = score.as_percent_dict()
            method_overall[name].append(pct)
            if score.mean is not None:
                method_domain_scores[name][domain].append(score.mean * 100.0)
            per_doc_rows.append({"doc_id": doc["doc_id"], "domain": domain, "method": name, "n_chunks": len(chunks), **pct, **meta})

    intrinsic_table = []
    for name, _sid, _p in methods:
        rows = method_overall[name]

        def avg(key, rows=rows):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        intrinsic_table.append({"method": name, "RC": avg("RC"), "ICC": avg("ICC"), "DCC": avg("DCC"), "BI": avg("BI"), "SC": avg("SC"), "Mean": avg("Mean")})
    intrinsic_table.sort(key=lambda r: r["Mean"] or 0, reverse=True)

    # Persist intermediate so a mid-run failure still leaves intrinsic results.
    (OUT / "intrinsic_partial.json").write_text(json.dumps(intrinsic_table, indent=2), encoding="utf-8")
    print("Intrinsic done; starting LLM-judge RAG…")

    rag_methods = ["adaptive_ace", "recursive_text_1100", "recursive_text", "fixed_token_512", "fixed_token_256", "heading_section", "no_split", "sentence_window"]
    rag_table = []
    rag_details = {}
    for name in rag_methods:
        print(f"  rag: {name}")
        rc_scores, ac_scores, answered_n, total_n = [], [], 0, 0
        method_detail = []
        for doc in corpus:
            text = doc["text"]
            qa_pairs = _qa_pairs_for(doc)
            if name == "adaptive_ace":
                _, chunks, _ = adaptive_select(
                    text,
                    strategies=FIXED_STRATEGIES,
                    chunk_fn=_chunk_with_strategy,
                    embed_fn=embed_fn,
                    mode=ADAPTIVE_MODE,
                    qa_pairs=qa_pairs,
                    rerank_fn=active_rerank,
                    micro_alpha=MICRO_ALPHA,
                )
            else:
                sid, params = next((s, p) for n, s, p in FIXED_STRATEGIES if n == name)
                chunks = _chunk_with_strategy(text, sid, params)
            rag = _rag_llm(client, embed_fn, active_rerank, chunks, qa_pairs)
            method_detail.append({"doc_id": doc["doc_id"], **{k: v for k, v in rag.items() if k != "judgments"}, "judgments": rag["judgments"]})
            rc_scores.append(rag["retrieval_completeness"])
            ac_scores.append(rag["answer_correctness"])
            a, t = rag["answered_queries"].split("/")
            answered_n += int(a)
            total_n += int(t)
        row = {
            "method": name,
            "retrieval_completeness": round(sum(rc_scores) / len(rc_scores), 2),
            "answer_correctness": round(sum(ac_scores) / len(ac_scores), 2),
            "answered_queries": f"{answered_n}/{total_n}",
        }
        rag_table.append(row)
        rag_details[name] = method_detail
        (OUT / "rag_partial.json").write_text(json.dumps({"rag_table": rag_table, "usage": client.stats}, indent=2), encoding="utf-8")
    rag_table.sort(key=lambda r: r["retrieval_completeness"], reverse=True)

    summary = {
        "protocol": {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "chat_model": CHAT_MODEL,
            "embed_model": EMBED_MODEL,
            "rerank_model": RERANK_MODEL if USE_RERANK else None,
            "adaptive_mode": ADAPTIVE_MODE,
            "intrinsic": "RC/ICC/DCC/BI/SC with neural embeddings for ICC/DCC",
            "rag": (
                f"dense retrieval top-{CANDIDATE_K}"
                + (f" + {RERANK_MODEL} rerank top-{TOP_K}" if USE_RERANK else f" top-{TOP_K}")
                + f" + {CHAT_MODEL} JSON LLM judge"
            ),
        },
        "paper_reference": {
            "title": "Adaptive Chunking: Optimizing Chunking-Method Selection for RAG",
            "arxiv": "https://arxiv.org/abs/2603.25333",
            "code": "https://github.com/ekimetrics/adaptive-chunking",
            "venue": "LREC 2026",
        },
        "comparison_note": (
            f"OpenRouter live ACE rows use `{EMBED_MODEL}` for ICC/DCC + dense retrieval"
            + (f", `{RERANK_MODEL}` rerank" if USE_RERANK else "")
            + f", adaptive_mode=`{ADAPTIVE_MODE}`, and `{CHAT_MODEL}` as LLM judge. "
            "Paper CLAIR rows remain published baselines (33 docs, different embedder/judge). "
            "Compare ranks, not absolute magnitudes."
        ),
        "corpus": {
            "n_documents": len(corpus),
            "domains": sorted({d["domain"] for d in corpus}),
            "approx_words": sum(len(d["text"].split()) for d in corpus),
        },
        "ace_openrouter_intrinsic_table": intrinsic_table,
        "paper_intrinsic_table": PAPER_INTRINSIC,
        "ace_openrouter_rag_table": rag_table,
        "paper_rag_table": PAPER_RAG,
        "domain_breakdown": {
            name: {d: round(statistics.mean(vals), 2) for d, vals in domains.items()}
            for name, domains in method_domain_scores.items()
        },
        "usage": client.stats,
    }
    payload = {"per_document": per_doc_rows, "rag_details": rag_details, **summary}
    (OUT / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "usage.json").write_text(json.dumps(client.stats, indent=2), encoding="utf-8")

    lines = [
        "# ACE OpenRouter Live Evaluation Results",
        "",
        f"Provider: **OpenRouter** · chat `{CHAT_MODEL}` · embed `{EMBED_MODEL}` · "
        f"rerank `{RERANK_MODEL if USE_RERANK else 'off'}` · adaptive `{ADAPTIVE_MODE}`",
        "",
        f"Corpus: **{len(corpus)} documents** · domains `{summary['corpus']['domains']}` · ≈{summary['corpus']['approx_words']} words.",
        "",
        "Reference: [arXiv:2603.25333](https://arxiv.org/abs/2603.25333) · [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).",
        "",
        f"> {summary['comparison_note']}",
        "",
        f"API usage (approx): embed_calls={client.stats['embed_calls']}, rerank_calls={client.stats.get('rerank_calls', 0)}, "
        f"chat_calls={client.stats['chat_calls']}, tokens={client.stats['total_tokens']}, "
        f"cost_usd≈{client.stats['estimated_cost_usd']:.4f}",
        "",
        "## A. ACE OpenRouter intrinsic metrics (%)",
        "",
        "| Method | RC | ICC | DCC | BI | SC | **Mean** |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in intrinsic_table:
        mark = "**" if r["method"] == "adaptive_ace" else ""
        lines.append(f"| {mark}{r['method']}{mark} | {r['RC']} | {r['ICC']} | {r['DCC']} | {r['BI']} | {r['SC']} | **{r['Mean']}** |")
    lines += [
        "",
        "## B. Published Adaptive Chunking intrinsic metrics (CLAIR / paper Table 3)",
        "",
        "| Method | RC | ICC | DCC | BI | SC | **Mean** |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in PAPER_INTRINSIC:
        mark = "**" if r["method"].startswith("Adaptive Chunking") else ""
        lines.append(f"| {mark}{r['method']}{mark} | {r['RC']} | {r['ICC']} | {r['DCC']} | {r['BI']} | {r['SC']} | **{r['Mean']}** |")
    lines += [
        "",
        f"## C. ACE OpenRouter RAG ({summary['protocol']['rag']})",
        "",
        "| Method | Retrieval Completeness | Answer Correctness | Answered |",
        "|---|---:|---:|---:|",
    ]
    for r in rag_table:
        mark = "**" if r["method"] == "adaptive_ace" else ""
        lines.append(f"| {mark}{r['method']}{mark} | {r['retrieval_completeness']} | {r['answer_correctness']} | {r['answered_queries']} |")
    lines += [
        "",
        "## D. Published Adaptive Chunking RAG (CLAIR / paper Table 5)",
        "",
        "| Method | Retrieval Completeness | Answer Correctness | Answered |",
        "|---|---:|---:|---:|",
    ]
    for r in PAPER_RAG:
        mark = "**" if r["method"].startswith("Adaptive Chunking") else ""
        lines.append(f"| {mark}{r['method']}{mark} | {r['retrieval_completeness']} | {r['answer_correctness']} | {r['answered_queries']} |")
    (OUT / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((OUT / "tables.md").read_text())
    print("Wrote", OUT)


if __name__ == "__main__":
    asyncio.run(main())
