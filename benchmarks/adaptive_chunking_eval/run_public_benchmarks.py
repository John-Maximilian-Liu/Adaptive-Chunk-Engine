#!/usr/bin/env python3
"""Run ACE chunking eval on CLAIR + FinanceBench + Open RAG Bench.

Modes:
  --mode offline     hashed embeddings + lexical RAG proxy
  --mode openrouter  text-embedding-3-small + gpt-4o LLM judge

Profiles:
  --profile smoke    small stratified subsets (default)
  --profile full     larger / full open releases

Examples:
  PYTHONPATH=apps/api:packages/python python benchmarks/adaptive_chunking_eval/run_public_benchmarks.py --mode offline --profile smoke
  PYTHONPATH=apps/api:packages/python python benchmarks/adaptive_chunking_eval/run_public_benchmarks.py --mode openrouter --profile smoke
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "datasets"))
sys.path.insert(0, str(ROOT / "packages" / "python"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from intrinsic_metrics import score_chunks  # noqa: E402
from loaders.clair import load_clair  # noqa: E402
from loaders.financebench import load_financebench  # noqa: E402
from loaders.open_rag_bench import load_open_rag_bench  # noqa: E402
from schema import DocRecord, QAItem  # noqa: E402
from canonical_schemas.document import ElementModel, LogicalUnitModel, Locator  # noqa: E402
from chunk_adapters import get_registry  # noqa: E402
from chunk_adapters.base import ChunkRequest  # noqa: E402
from shared.ids import new_id  # noqa: E402

OUT_ROOT = HERE / "results" / "public_benchmarks"

FIXED_STRATEGIES = [
    ("fixed_token_512", "fixed_token", {"chunk_size": 512, "chunk_overlap": 64}),
    ("fixed_token_256", "fixed_token", {"chunk_size": 256, "chunk_overlap": 32}),
    ("recursive_text", "recursive_text", {"chunk_size": 512, "chunk_overlap": 64}),
    ("recursive_text_1100", "recursive_text", {"chunk_size": 1100, "chunk_overlap": 100}),
    ("sentence_window", "sentence_window", {"chunk_size": 384, "chunk_overlap": 48}),
    ("heading_section", "heading_section", {"chunk_size": 512, "chunk_overlap": 64}),
    ("no_split", "no_split", {}),
]

# Slimmer set for RAG to control cost; intrinsic still uses full set for adaptive.
RAG_METHODS = [
    "adaptive_ace",
    "recursive_text_1100",
    "recursive_text",
    "fixed_token_512",
    "sentence_window",
    "no_split",
]

# Even leaner for OpenRouter smoke.
RAG_METHODS_SMOKE_LIVE = [
    "adaptive_ace",
    "recursive_text_1100",
    "fixed_token_512",
    "sentence_window",
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
    # Cap pathological page counts for very long docs.
    if len(paras) > 4000:
        paras = paras[:4000]
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


def _cosine(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _l2_normalize(vecs: list[list[float]]) -> list[list[float]]:
    out = []
    for v in vecs:
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def _adaptive_select(text: str, embed_fn) -> tuple[str, list[str], dict]:
    best_name, best_chunks, best_score, details = None, [], -1.0, {}
    for name, sid, params in FIXED_STRATEGIES:
        chunks = _chunk_with_strategy(text, sid, params)
        score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
        details[name] = score.as_percent_dict()
        m = score.mean or 0.0
        if m > best_score:
            best_score, best_name, best_chunks = m, name, chunks
    return best_name or "fixed_token_512", best_chunks, details


def _lexical_rag(chunks: list[str], qa_pairs: list[QAItem], top_k: int = 5) -> dict:
    answered = 0
    completeness_scores, correctness_scores = [], []

    def retrieve(question: str, key_terms: list[str]) -> list[str]:
        q_terms = set(re.findall(r"[a-z0-9]+", question.lower())) | {t.lower() for t in key_terms}
        ranked = []
        for c in chunks:
            terms = set(re.findall(r"[a-z0-9]+", c.lower()))
            bonus = sum(0.15 for t in key_terms if t.lower() in c.lower())
            overlap = len(q_terms & terms) / max(1, len(q_terms))
            ranked.append((overlap + bonus, c))
        ranked.sort(reverse=True)
        return [c for _, c in ranked[:top_k]]

    for qa in qa_pairs:
        hits = retrieve(qa.question, qa.key_terms or [])
        ev_terms = set(re.findall(r"[a-z0-9]+", qa.evidence_quote.lower()))
        ctx_terms = set(re.findall(r"[a-z0-9]+", " ".join(hits).lower()))
        cov = len(ev_terms & ctx_terms) / max(1, len(ev_terms)) if ev_terms else 0.0
        completeness_scores.append(cov)
        ans_terms = set(re.findall(r"[a-z0-9]+", qa.answer.lower()))
        correctness_scores.append(len(ans_terms & ctx_terms) / max(1, len(ans_terms)) if ans_terms else 0.0)
        if cov >= 0.55:
            answered += 1
    n = max(1, len(qa_pairs))
    return {
        "retrieval_completeness": round(100.0 * sum(completeness_scores) / n, 2),
        "answer_correctness": round(100.0 * sum(correctness_scores) / n, 2),
        "answered_queries": f"{answered}/{len(qa_pairs)}",
        "n_queries": len(qa_pairs),
    }


def _dense_retrieve(embed_fn, question: str, chunks: list[str], top_k: int = 5) -> list[str]:
    if not chunks:
        return []
    q_emb = embed_fn([question])[0]
    c_embs = embed_fn(chunks)
    ranked = sorted(((_cosine(q_emb, ce), c) for ce, c in zip(c_embs, chunks)), reverse=True)
    return [c for _, c in ranked[:top_k]]


def _llm_judge(client, qa: QAItem, retrieved: list[str]) -> dict:
    context = "\n\n---\n\n".join(retrieved)[:12000]
    system = (
        "You are a strict RAG evaluation judge. "
        "Score whether the retrieved context supports answering the question. "
        "Return JSON only with keys: "
        "retrieval_completeness (0-1), answer_correctness (0-1), answered (boolean), rationale (short string)."
    )
    user = (
        f"Question: {qa.question}\n\n"
        f"Gold answer: {qa.answer}\n\n"
        f"Evidence quote: {qa.evidence_quote}\n\n"
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
    }


def _llm_rag(client, embed_fn, chunks: list[str], qa_pairs: list[QAItem], top_k: int = 5) -> dict:
    completeness_scores, correctness_scores = [], []
    answered = 0
    for qa in qa_pairs:
        hits = _dense_retrieve(embed_fn, qa.question, chunks, top_k=top_k)
        judge = _llm_judge(client, qa, hits)
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
    }


def _avg_rows(rows: list[dict], keys: list[str]) -> dict:
    out = {}
    for k in keys:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = round(sum(vals) / len(vals), 2) if vals else None
    return out


def eval_dataset(
    name: str,
    docs: list[DocRecord],
    *,
    mode: str,
    profile: str,
    embed_fn,
    client=None,
    out_dir: Path,
) -> dict:
    print(f"\n=== {name}: {len(docs)} docs / {sum(len(d.qa_pairs) for d in docs)} QA ===")
    # Live smoke: fewer intrinsic candidates to contain embedding cost.
    strategies = FIXED_STRATEGIES
    if mode == "openrouter" and profile == "smoke":
        strategies = [s for s in FIXED_STRATEGIES if s[0] in {
            "fixed_token_512", "recursive_text", "recursive_text_1100", "sentence_window", "no_split"
        }]
    methods = [(n, s, p) for n, s, p in strategies] + [("adaptive_ace", "adaptive", {})]
    method_overall: dict[str, list[dict]] = defaultdict(list)
    per_doc = []
    rag_methods = RAG_METHODS_SMOKE_LIVE if (mode == "openrouter" and profile == "smoke") else RAG_METHODS

    for doc in docs:
        # Truncate extreme docs for live cost (keep head+tail signal).
        text = doc.text
        if mode == "openrouter" and len(text) > 80_000:
            text = text[:50_000] + "\n\n...\n\n" + text[-20_000:]
            print(f"  truncate {doc.doc_id} → {len(text)} chars")
        print(f"  intrinsic: {doc.doc_id} ({doc.domain})")
        for mname, sid, params in methods:
            if mname == "adaptive_ace":
                # Adaptive over the active candidate set only.
                best_name, best_chunks, best_score, detail = None, [], -1.0, {}
                for cname, csid, cparams in strategies:
                    cchunks = _chunk_with_strategy(text, csid, cparams)
                    cscore = score_chunks(cchunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
                    detail[cname] = cscore.as_percent_dict()
                    m = cscore.mean or 0.0
                    if m > best_score:
                        best_score, best_name, best_chunks = m, cname, cchunks
                chunks = best_chunks
                score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
                meta = {"selected": best_name or "fixed_token_512", "candidates": detail}
            else:
                chunks = _chunk_with_strategy(text, sid, params)
                score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
                meta = {}
            pct = score.as_percent_dict()
            method_overall[mname].append(pct)
            per_doc.append(
                {
                    "doc_id": doc.doc_id,
                    "domain": doc.domain,
                    "method": mname,
                    "n_chunks": len(chunks),
                    **pct,
                    **meta,
                }
            )

    intrinsic_table = []
    for mname, _s, _p in methods:
        row = {"method": mname, **_avg_rows(method_overall[mname], ["RC", "ICC", "DCC", "BI", "SC", "Mean"])}
        intrinsic_table.append(row)
    intrinsic_table.sort(key=lambda r: r["Mean"] or 0, reverse=True)

    rag_table = []
    for mname in rag_methods:
        print(f"  rag: {mname}")
        rc_scores, ac_scores, answered_n, total_n = [], [], 0, 0
        for doc in docs:
            text = doc.text
            if mode == "openrouter" and len(text) > 80_000:
                text = text[:50_000] + "\n\n...\n\n" + text[-20_000:]
            qa_pairs = doc.qa_pairs
            if mode == "openrouter" and profile == "smoke":
                qa_pairs = qa_pairs[:2]
            if mname == "adaptive_ace":
                # Reuse selection among smoke candidates.
                best_name, best_chunks, best_score = None, [], -1.0
                for cname, csid, cparams in strategies:
                    cchunks = _chunk_with_strategy(text, csid, cparams)
                    cscore = score_chunks(cchunks, text, min_tokens=50, max_tokens=1100, embed_fn=embed_fn)
                    m = cscore.mean or 0.0
                    if m > best_score:
                        best_score, best_name, best_chunks = m, cname, cchunks
                chunks = best_chunks
            else:
                sid, params = next((s, p) for n, s, p in FIXED_STRATEGIES if n == mname)
                chunks = _chunk_with_strategy(text, sid, params)
            if not qa_pairs:
                continue
            if mode == "openrouter":
                assert client is not None
                rag = _llm_rag(client, embed_fn, chunks, qa_pairs)
            else:
                rag = _lexical_rag(chunks, qa_pairs)
            rc_scores.append(rag["retrieval_completeness"])
            ac_scores.append(rag["answer_correctness"])
            a, t = rag["answered_queries"].split("/")
            answered_n += int(a)
            total_n += int(t)
        if not rc_scores:
            continue
        rag_table.append(
            {
                "method": mname,
                "retrieval_completeness": round(sum(rc_scores) / len(rc_scores), 2),
                "answer_correctness": round(sum(ac_scores) / len(ac_scores), 2),
                "answered_queries": f"{answered_n}/{total_n}",
            }
        )
    rag_table.sort(key=lambda r: r["retrieval_completeness"], reverse=True)

    result = {
        "dataset": name,
        "n_documents": len(docs),
        "n_queries": sum(len(d.qa_pairs) for d in docs),
        "domains": sorted({d.domain for d in docs}),
        "approx_chars": sum(d.n_chars for d in docs),
        "intrinsic_table": intrinsic_table,
        "rag_table": rag_table,
        "per_document": per_doc,
    }
    if name == "clair":
        result["paper_intrinsic_table"] = PAPER_INTRINSIC
        result["paper_rag_table"] = PAPER_RAG
    (out_dir / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _write_tables(summary: dict, out_dir: Path) -> None:
    lines = [
        "# ACE Public Benchmark Results",
        "",
        f"Mode: `{summary['mode']}` · profile: `{summary['profile']}` · chat `{summary.get('chat_model')}` · embed `{summary.get('embed_model')}`",
        "",
        f"> {summary['comparison_note']}",
        "",
    ]
    for ds in summary["datasets"]:
        name = ds["dataset"]
        lines += [
            f"## {name}",
            "",
            f"Docs: **{ds['n_documents']}** · queries: **{ds['n_queries']}** · domains `{ds['domains']}`",
            "",
            "### Intrinsic (%)",
            "",
            "| Method | RC | ICC | DCC | BI | SC | **Mean** |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in ds["intrinsic_table"]:
            mark = "**" if r["method"] == "adaptive_ace" else ""
            lines.append(
                f"| {mark}{r['method']}{mark} | {r['RC']} | {r['ICC']} | {r['DCC']} | {r['BI']} | {r['SC']} | **{r['Mean']}** |"
            )
        if ds.get("paper_intrinsic_table"):
            lines += [
                "",
                "### Published CLAIR intrinsic (paper Table 3)",
                "",
                "| Method | RC | ICC | DCC | BI | SC | **Mean** |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
            for r in ds["paper_intrinsic_table"]:
                mark = "**" if str(r["method"]).startswith("Adaptive Chunking") else ""
                lines.append(
                    f"| {mark}{r['method']}{mark} | {r['RC']} | {r['ICC']} | {r['DCC']} | {r['BI']} | {r['SC']} | **{r['Mean']}** |"
                )
        lines += [
            "",
            "### RAG",
            "",
            "| Method | Retrieval Completeness | Answer Correctness | Answered |",
            "|---|---:|---:|---:|",
        ]
        for r in ds["rag_table"]:
            mark = "**" if r["method"] == "adaptive_ace" else ""
            lines.append(
                f"| {mark}{r['method']}{mark} | {r['retrieval_completeness']} | {r['answer_correctness']} | {r['answered_queries']} |"
            )
        if ds.get("paper_rag_table"):
            lines += [
                "",
                "### Published CLAIR RAG (paper Table 5)",
                "",
                "| Method | Retrieval Completeness | Answer Correctness | Answered |",
                "|---|---:|---:|---:|",
            ]
            for r in ds["paper_rag_table"]:
                mark = "**" if str(r["method"]).startswith("Adaptive Chunking") else ""
                lines.append(
                    f"| {mark}{r['method']}{mark} | {r['retrieval_completeness']} | {r['answer_correctness']} | {r['answered_queries']} |"
                )
        lines.append("")
    (out_dir / "tables.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline", "openrouter"], default="offline")
    ap.add_argument("--profile", choices=["smoke", "full"], default=os.environ.get("ACE_BENCH_PROFILE", "smoke"))
    ap.add_argument(
        "--datasets",
        default="clair,financebench,open_rag_bench",
        help="Comma-separated: clair,financebench,open_rag_bench",
    )
    args = ap.parse_args()

    out_dir = OUT_ROOT / f"{args.mode}_{args.profile}"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = None
    chat_model = os.environ.get("ACE_CHAT_MODEL", "openai/gpt-4o")
    embed_model = os.environ.get("ACE_EMBED_MODEL", "openai/text-embedding-3-small")

    if args.mode == "openrouter":
        from openrouter_client import OpenRouterClient

        client = OpenRouterClient(
            chat_model=chat_model,
            embed_model=embed_model,
            cache_dir=out_dir / "cache",
        )

        def embed_fn(texts):
            return _l2_normalize(client.embed(list(texts)))

    else:

        def embed_fn(texts):  # hashed path via score_chunks default when None — wrap for RAG dense fallback
            # For offline intrinsic we pass None-equivalent by using hashed inside score_chunks;
            # provide a deterministic hashed embed for dense retrieval consistency.
            from intrinsic_metrics import _hash_embed

            return _hash_embed(list(texts))

        # Use default hashed inside score_chunks by passing None through a lambda that score_chunks accepts.
        def embed_fn_intrinsic(texts):
            from intrinsic_metrics import _hash_embed

            return _hash_embed(list(texts))

        embed_fn = embed_fn_intrinsic

    wanted = {x.strip() for x in args.datasets.split(",") if x.strip()}
    corpus: dict[str, list[DocRecord]] = {}
    if "clair" in wanted:
        corpus["clair"] = load_clair(profile=args.profile)
    if "financebench" in wanted:
        corpus["financebench"] = load_financebench(profile=args.profile)
    if "open_rag_bench" in wanted:
        corpus["open_rag_bench"] = load_open_rag_bench(profile=args.profile)

    dataset_results = []
    for name, docs in corpus.items():
        dataset_results.append(
            eval_dataset(
                name,
                docs,
                mode=args.mode,
                profile=args.profile,
                embed_fn=embed_fn,
                client=client,
                out_dir=out_dir,
            )
        )

    summary = {
        "mode": args.mode,
        "profile": args.profile,
        "chat_model": chat_model if args.mode == "openrouter" else None,
        "embed_model": embed_model if args.mode == "openrouter" else "hashed_ngram",
        "comparison_note": (
            "ACE public-benchmark suite on CLAIR + FinanceBench + Open RAG Bench. "
            "CLAIR paper rows are published Adaptive Chunking results. "
            "Compare ranks within each dataset/protocol; absolute RAG scores are not cross-dataset comparable."
        ),
        "datasets": [
            {k: v for k, v in ds.items() if k != "per_document"} for ds in dataset_results
        ],
        "usage": getattr(client, "stats", None),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_tables(summary, out_dir)
    print("\n" + (out_dir / "tables.md").read_text(encoding="utf-8"))
    print("Wrote", out_dir)


if __name__ == "__main__":
    main()
