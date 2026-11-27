#!/usr/bin/env python3
"""Held-out paired chunking experiment for COLING Industry review response (Stage E).

Per document (evidence-disjoint diagnostic vs hidden QA):
  1) strong_fixed   — leave-one-out corpus production splitter on diagnostic Cov
  2) intrinsic      — argmax intrinsic Mean (Stage-D candidate table)
  3) microloop      — Stage-D shortlist + blend using diagnostic evidence Cov only
  4) human_review   — diagnostic-only override when Auto lags strong_fixed

All four share embedder / reranker / top-Kc→K / context budget.
Indices are locked before hidden questions are scored (evidence-term recall).
Checkpoints per document under OUT_DIR/checkpoints/ for resume.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "datasets"))
sys.path.insert(0, str(ROOT / "packages" / "python"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from loaders.clair import load_clair  # noqa: E402
from loaders.financebench import load_financebench  # noqa: E402
from loaders.open_rag_bench import load_open_rag_bench  # noqa: E402
from openrouter_client import OpenRouterClient  # noqa: E402
from retrieval import (  # noqa: E402
    evidence_coverage,
    l2_normalize,
    retrieve_with_optional_rerank,
)
from run_public_benchmarks import FIXED_STRATEGIES, _chunk_with_strategy  # noqa: E402
from schema import DocRecord, QAItem  # noqa: E402

STAGE_D = HERE / "results" / "public_benchmarks" / "openrouter_full_stage_d"
OUT_DIR = HERE / "results" / "public_benchmarks" / "heldout_paired_stage_e"
CKPT_DIR = OUT_DIR / "checkpoints"
PROD_STRATEGIES = [s for s in FIXED_STRATEGIES if s[0] != "no_split"]
PROD_NAMES = [s[0] for s in PROD_STRATEGIES]
REVIEW_MINUTES_PER_ALERT = 4.0
DEGRADE_DELTA = 0.05  # absolute Cov drop vs strong_fixed on hidden
OVERRIDE_DELTA = 0.02  # diagnostic Cov gap that triggers human review
WALKTHROUGH_DOCS = {
    ("financebench", "AMD_2022_10K"),
    ("clair", "Norma (légal)_European Convention On Human Rights"),
}


def _ev_key(qa: QAItem) -> str:
    ev = re.sub(r"\s+", " ", (qa.evidence_quote or "").strip().lower())[:120]
    return ev or re.sub(r"\s+", " ", qa.question.strip().lower())[:80]


def split_diagnostic_hidden(qa_pairs: list[QAItem]) -> tuple[list[QAItem], list[QAItem]]:
    """Split by evidence paragraph groups; fall back to index split."""
    if len(qa_pairs) < 2:
        raise ValueError("need ≥2 QA")
    groups: dict[str, list[QAItem]] = {}
    order: list[str] = []
    for qa in qa_pairs:
        k = _ev_key(qa)
        if k not in groups:
            order.append(k)
            groups[k] = []
        groups[k].append(qa)
    if len(order) == 1:
        mid = max(1, len(qa_pairs) // 2)
        diag, hidden = qa_pairs[:mid], qa_pairs[mid:]
        if not hidden:
            hidden = [diag.pop()]
        return diag, hidden
    mid = max(1, len(order) // 2)
    diag, hidden = [], []
    for i, k in enumerate(order):
        (diag if i < mid else hidden).extend(groups[k])
    if not hidden:
        hidden = [diag.pop()]
    if not diag:
        diag = [hidden.pop(0)]
    return diag, hidden


def qa_to_dict(qa: QAItem) -> dict[str, Any]:
    return {
        "question": qa.question,
        "answer": qa.answer,
        "evidence_quote": qa.evidence_quote,
    }


def load_stage_d_intrinsics() -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for name in ("clair", "financebench", "open_rag_bench"):
        path = STAGE_D / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        by_doc: dict[str, dict[str, Any]] = {}
        for row in data["per_document"]:
            if row.get("method") != "adaptive_ace":
                continue
            by_doc[row["doc_id"]] = {
                "selected": row["selected"],
                "selection": row["selection"],
                "Mean": row.get("Mean"),
            }
        out[name] = by_doc
    return out


def truncate_text(text: str) -> str:
    if len(text) <= 80_000:
        return text
    return text[:50_000] + "\n\n...\n\n" + text[-20_000:]


def mean_cov(
    *,
    embed_fn,
    rerank_fn,
    chunks: list[str],
    qa_pairs: list[QAItem],
    top_k: int = 5,
    candidate_k: int = 20,
) -> float:
    if not qa_pairs or not chunks:
        return 0.0
    scores = []
    for qa in qa_pairs:
        hits = retrieve_with_optional_rerank(
            embed_fn=embed_fn,
            rerank_fn=rerank_fn,
            question=qa.question,
            chunks=chunks,
            top_k=top_k,
            candidate_k=candidate_k,
        )
        scores.append(evidence_coverage(qa.evidence_quote, hits))
    return float(sum(scores) / len(scores))


def load_docs_for_heldout() -> dict[str, list[DocRecord]]:
    stage = load_stage_d_intrinsics()
    clair = [d for d in load_clair(profile="full") if d.doc_id in stage["clair"] and len(d.qa_pairs) >= 2]

    fb_all = load_financebench(profile="full", max_questions=10**9)
    fb_ids = set(stage["financebench"])
    fb = [d for d in fb_all if d.doc_id in fb_ids and len(d.qa_pairs) >= 2]

    orb_ids = set(stage["open_rag_bench"])
    orb_all = load_open_rag_bench(profile="full", max_queries=10**9)
    orb = [d for d in orb_all if d.doc_id in orb_ids and len(d.qa_pairs) >= 2]

    return {"clair": clair, "financebench": fb, "open_rag_bench": orb}


def pick_strong_fixed(corpus_diag_cov: dict[str, list[float]]) -> str:
    means = {name: (sum(vs) / len(vs) if vs else -1.0) for name, vs in corpus_diag_cov.items()}
    return max(means, key=means.get)


def loo_strong_fixed(
    doc_id: str,
    diag_by_doc: dict[str, dict[str, float]],
) -> str:
    """Leave-one-out: mean diagnostic Cov over other docs in the same corpus."""
    pool: dict[str, list[float]] = defaultdict(list)
    for other_id, covs in diag_by_doc.items():
        if other_id == doc_id:
            continue
        for name, v in covs.items():
            pool[name].append(v)
    if not pool:
        return pick_strong_fixed({k: [v] for k, v in next(iter(diag_by_doc.values())).items()})
    return pick_strong_fixed(pool)


def bootstrap_ci(values: list[float], n_boot: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    import random

    rng = random.Random(42)
    n = len(values)
    means = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot) - 1]
    return (round(100.0 * lo, 2), round(100.0 * hi, 2))


def summarize(rows: list[dict], *, paired_base: str = "strong_fixed") -> dict[str, Any]:
    by_cond: dict[str, list[dict]] = defaultdict(list)
    by_doc: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by_cond[r["condition"]].append(r)
        by_doc[f"{r['dataset']}::{r['doc_id']}"][r["condition"]] = r

    table = []
    for cond in ("strong_fixed", "intrinsic", "microloop", "human_review"):
        rs = by_cond[cond]
        if not rs:
            continue
        covs = [r["hidden_cov"] for r in rs]
        deg = sum(1 for r in rs if r.get("degraded_vs_fixed"))
        overrides = sum(1 for r in rs if r.get("review_overrode"))
        alerts = sum(1 for r in rs if r.get("review_alert"))
        minutes = sum(float(r.get("review_minutes") or 0.0) for r in rs)
        # paired deltas vs strong_fixed on shared docs
        deltas = []
        for key, conds in by_doc.items():
            if cond in conds and paired_base in conds:
                deltas.append(conds[cond]["hidden_cov"] - conds[paired_base]["hidden_cov"])
        mean_delta = (sum(deltas) / len(deltas)) if deltas else 0.0
        se = (
            math.sqrt(sum((d - mean_delta) ** 2 for d in deltas) / (len(deltas) * (len(deltas) - 1)))
            if len(deltas) > 1
            else 0.0
        )
        ci = bootstrap_ci(covs)
        table.append(
            {
                "condition": cond,
                "n_docs": len(rs),
                "mean_hidden_evidence_recall": round(100.0 * sum(covs) / len(covs), 2),
                "hidden_recall_ci95": list(ci),
                "paired_delta_vs_fixed_pp": round(100.0 * mean_delta, 2),
                "paired_delta_se_pp": round(100.0 * se, 2),
                "degraded_docs": deg,
                "degraded_rate": round(100.0 * deg / len(rs), 1),
                "review_alerts": alerts,
                "review_overrides": overrides,
                "review_minutes_total": round(minutes, 1),
                "review_minutes_per_doc": round(minutes / len(rs), 2),
                "review_minutes_per_alert": REVIEW_MINUTES_PER_ALERT if alerts else None,
            }
        )
    return {"conditions": table, "n_docs": len({r["doc_id"] for r in rows})}


def ckpt_path(ds_name: str, doc_id: str) -> Path:
    safe = re.sub(r"[^\w.\-]+", "_", doc_id)[:180]
    return CKPT_DIR / f"{ds_name}__{safe}.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    stage = load_stage_d_intrinsics()
    corpus = load_docs_for_heldout()

    embed_model = os.environ.get("ACE_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B")
    rerank_model = os.environ.get("ACE_RERANK_MODEL", "cohere/rerank-v3.5")
    alpha = float(os.environ.get("ACE_MICRO_ALPHA", "0.55"))
    candidate_k = int(os.environ.get("ACE_RETRIEVE_CANDIDATE_K", "20"))
    top_k = int(os.environ.get("ACE_RETRIEVE_TOP_K", "5"))
    batch = int(os.environ.get("ACE_EMBED_BATCH", "16"))

    client = OpenRouterClient(
        embed_model=embed_model,
        rerank_model=rerank_model,
        cache_dir=OUT_DIR / "cache",
        batch_size=batch,
    )

    def embed_fn(texts):
        return l2_normalize(client.embed(list(texts)))

    def rerank_fn(query: str, docs: list[str], top_n: int) -> list[str]:
        return client.rerank_texts(query, docs, top_n=top_n)

    all_rows: list[dict] = []
    per_dataset: dict[str, Any] = {}
    walkthroughs: list[dict] = []
    t0 = time.time()

    for ds_name, docs in corpus.items():
        print(f"\n=== {ds_name}: {len(docs)} docs eligible for held-out ===", flush=True)
        doc_state: dict[str, dict[str, Any]] = {}
        diag_by_doc: dict[str, dict[str, float]] = {}
        corpus_diag: dict[str, list[float]] = defaultdict(list)

        for doc in docs:
            cp = ckpt_path(ds_name, doc.doc_id)
            if cp.exists():
                saved = json.loads(cp.read_text(encoding="utf-8"))
                print(f"  [resume] {doc.doc_id}", flush=True)
                doc_state[doc.doc_id] = saved
                diag_by_doc[doc.doc_id] = saved["diag_cov"]
                for name, cov in saved["diag_cov"].items():
                    corpus_diag[name].append(cov)
                continue

            text = truncate_text(doc.text)
            diag, hidden = split_diagnostic_hidden(list(doc.qa_pairs))
            print(
                f"  {doc.doc_id}: diag={len(diag)} hidden={len(hidden)} chars={len(text)}",
                flush=True,
            )
            chunks_by: dict[str, list[str]] = {}
            diag_cov: dict[str, float] = {}
            n_chunks: dict[str, int] = {}
            for name, sid, params in PROD_STRATEGIES:
                chunks = _chunk_with_strategy(text, sid, params)
                chunks_by[name] = chunks
                n_chunks[name] = len(chunks)
                cov = mean_cov(
                    embed_fn=embed_fn,
                    rerank_fn=rerank_fn,
                    chunks=chunks,
                    qa_pairs=diag,
                    top_k=top_k,
                    candidate_k=candidate_k,
                )
                diag_cov[name] = cov
                corpus_diag[name].append(cov)
                print(f"    diag cov {name}={cov:.3f} n_chunks={len(chunks)}", flush=True)

            meta = stage[ds_name].get(doc.doc_id) or {}
            cands = (meta.get("selection") or {}).get("candidates") or {}
            means = {
                k: float(v["Mean"])
                for k, v in cands.items()
                if isinstance(v, dict) and v.get("Mean") is not None and k in PROD_NAMES
            }
            if not means:
                means = {meta.get("selected") or "fixed_token_512": float(meta.get("Mean") or 0.0)}

            intrinsic_name = max(means, key=means.get)
            ranked = sorted(means.items(), key=lambda kv: kv[1], reverse=True)
            shortlist = [n for n, _ in ranked[:3]]
            blends: dict[str, float] = {}
            micros: dict[str, float] = {}
            for name in shortlist:
                micro = diag_cov.get(name, 0.0)
                mu = means[name] / 100.0
                blends[name] = alpha * mu + (1.0 - alpha) * micro
                micros[name] = micro
            micro_name = max(blends, key=blends.get)

            # Placeholder fixed; LOO applied in pass 2 once all diag are known
            state = {
                "dataset": ds_name,
                "doc_id": doc.doc_id,
                "domain": doc.domain,
                "diag_n": len(diag),
                "hidden_n": len(hidden),
                "diag_qa": [qa_to_dict(q) for q in diag],
                "hidden_qa": [qa_to_dict(q) for q in hidden],
                "n_chunks": n_chunks,
                "diag_cov": {k: round(v, 6) for k, v in diag_cov.items()},
                "means": means,
                "intrinsic_name": intrinsic_name,
                "micro_name": micro_name,
                "shortlist": shortlist,
                "blends": {k: round(v, 6) for k, v in blends.items()},
                "micros": {k: round(v, 6) for k, v in micros.items()},
                "stage_selected": meta.get("selected"),
                # keep chunk texts for pass-2 hidden scoring (large but needed for resume)
                "chunks_by": chunks_by,
            }
            # score hidden for all production strategies once (so LOO fixed is free later)
            hidden_cov_all: dict[str, float] = {}
            for name, chunks in chunks_by.items():
                hcov = mean_cov(
                    embed_fn=embed_fn,
                    rerank_fn=rerank_fn,
                    chunks=chunks,
                    qa_pairs=hidden,
                    top_k=top_k,
                    candidate_k=candidate_k,
                )
                hidden_cov_all[name] = round(hcov, 6)
                print(f"    hidden cov {name}={hcov:.3f}", flush=True)
            state["hidden_cov_all"] = hidden_cov_all
            # drop bulky chunks from disk checkpoint after scoring
            to_save = {k: v for k, v in state.items() if k != "chunks_by"}
            cp.write_text(json.dumps(to_save, indent=2), encoding="utf-8")
            doc_state[doc.doc_id] = to_save
            diag_by_doc[doc.doc_id] = diag_cov

        corpus_fixed = pick_strong_fixed(corpus_diag)
        print(f"  corpus_diag_best[{ds_name}] = {corpus_fixed}", flush=True)

        ds_rows: list[dict] = []
        for doc_id, st in doc_state.items():
            fixed_name = loo_strong_fixed(doc_id, diag_by_doc)
            intr_name = st["intrinsic_name"]
            micro_name = st["micro_name"]
            hidden_cov_all = st["hidden_cov_all"]

            auto_diag = st["diag_cov"].get(micro_name, 0.0)
            fixed_diag = st["diag_cov"].get(fixed_name, 0.0)
            alert = auto_diag + 1e-9 < fixed_diag - OVERRIDE_DELTA
            review_minutes = REVIEW_MINUTES_PER_ALERT if alert else 0.0
            if alert:
                pool = {fixed_name: fixed_diag}
                for n in st["shortlist"]:
                    pool[n] = st["diag_cov"].get(n, 0.0)
                human_name = max(pool, key=pool.get)
            else:
                human_name = micro_name
            overrode = human_name != micro_name

            locked = {
                "strong_fixed": fixed_name,
                "intrinsic": intr_name,
                "microloop": micro_name,
                "human_review": human_name,
            }
            fixed_hidden = hidden_cov_all.get(fixed_name, 0.0)
            for cond, sname in locked.items():
                hcov = hidden_cov_all.get(sname, 0.0)
                degraded = bool(cond != "strong_fixed" and hcov + 1e-9 < fixed_hidden - DEGRADE_DELTA)
                row = {
                    "dataset": ds_name,
                    "doc_id": doc_id,
                    "domain": st.get("domain"),
                    "condition": cond,
                    "locked_strategy": sname,
                    "diag_n": st["diag_n"],
                    "hidden_n": st["hidden_n"],
                    "diag_cov": round(st["diag_cov"].get(sname, 0.0), 4),
                    "hidden_cov": round(hcov, 4),
                    "degraded_vs_fixed": degraded,
                    "review_alert": alert if cond == "human_review" else False,
                    "review_overrode": overrode if cond == "human_review" else False,
                    "review_minutes": review_minutes if cond == "human_review" else 0.0,
                    "intrinsic_mean_selected": st["means"].get(sname),
                    "shortlist": st["shortlist"],
                    "stage_d_selected": st.get("stage_selected"),
                    "loo_strong_fixed": fixed_name,
                    "corpus_diag_best": corpus_fixed,
                }
                ds_rows.append(row)
                all_rows.append(row)
                print(
                    f"    {doc_id} {cond} -> {sname} hidden_cov={hcov:.3f} degraded={degraded}",
                    flush=True,
                )

            if (ds_name, doc_id) in WALKTHROUGH_DOCS:
                walkthroughs.append(
                    {
                        "dataset": ds_name,
                        "doc_id": doc_id,
                        "diag_qa": st.get("diag_qa"),
                        "hidden_qa": st.get("hidden_qa"),
                        "diag_cov": st["diag_cov"],
                        "hidden_cov_all": hidden_cov_all,
                        "means": st["means"],
                        "shortlist": st["shortlist"],
                        "blends": st["blends"],
                        "locked": locked,
                        "alert": alert,
                        "overrode": overrode,
                        "review_minutes": review_minutes,
                        "n_chunks": st.get("n_chunks"),
                    }
                )

        per_dataset[ds_name] = {
            "corpus_diag_best": corpus_fixed,
            "n_docs": len(doc_state),
            "summary": summarize(ds_rows),
            "diag_cov_means": {
                k: round(sum(v) / len(v), 4) if v else None for k, v in corpus_diag.items()
            },
            "eligible_note": (
                "FinanceBench: Stage-D has 18 docs; held-out requires ≥2 QA → "
                f"{len(doc_state)} docs"
                if ds_name == "financebench"
                else None
            ),
        }

    summary = {
        "protocol": {
            "embed_model": embed_model,
            "rerank_model": rerank_model,
            "retrieve_candidate_k": candidate_k,
            "retrieve_top_k": top_k,
            "micro_alpha": alpha,
            "split": "evidence-paragraph groups → diagnostic vs hidden",
            "metric": "hidden evidence-term recall after dense top-Kc + rerank top-K",
            "conditions": ["strong_fixed", "intrinsic", "microloop", "human_review"],
            "strong_fixed_rule": "leave-one-out argmax of mean diagnostic Cov over other docs",
            "human_policy": (
                f"alert if microloop diagnostic Cov < strong_fixed − {OVERRIDE_DELTA}; "
                "operator picks max diagnostic Cov among {strong_fixed}∪shortlist; "
                f"{REVIEW_MINUTES_PER_ALERT} min credited per alert (simulated operator budget)"
            ),
            "degrade_delta": DEGRADE_DELTA,
            "intrinsic_source": "Stage-D candidate Means (openrouter_full_stage_d)",
            "not_answer_accuracy": (
                "Primary metric is evidence-term recall on held-out questions; "
                "LLM-judge completeness is Stage-D only and is not answer correctness"
            ),
        },
        "elapsed_sec": round(time.time() - t0, 1),
        "overall": summarize(all_rows),
        "per_dataset": per_dataset,
        "usage": client.stats,
        "strategy_mix": {
            cond: dict(
                Counter(r["locked_strategy"] for r in all_rows if r["condition"] == cond)
            )
            for cond in ("strong_fixed", "intrinsic", "microloop", "human_review")
        },
    }

    (OUT_DIR / "per_document.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / "walkthroughs.json").write_text(
        json.dumps(walkthroughs, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Held-out paired chunking experiment (Stage E)",
        "",
        "Diagnostic vs hidden QA split by evidence paragraph. Shared dense+rerank stack.",
        "strong_fixed = leave-one-out diagnostic Cov winner. Human review is a simulated operator policy.",
        "",
        "## Overall",
        "",
        "| Condition | Docs | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides | Review min/doc |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in summary["overall"]["conditions"]:
        lines.append(
            f"| {r['condition']} | {r['n_docs']} | **{r['mean_hidden_evidence_recall']}** "
            f"(CI {r['hidden_recall_ci95'][0]}–{r['hidden_recall_ci95'][1]}) | "
            f"{r['paired_delta_vs_fixed_pp']} | {r['degraded_rate']} | "
            f"{r['review_overrides']} | {r['review_minutes_per_doc']} |"
        )
    lines += ["", "## Per dataset", ""]
    for ds, block in per_dataset.items():
        lines += [f"### {ds} (corpus_diag_best=`{block['corpus_diag_best']}`, n={block['n_docs']})", ""]
        if block.get("eligible_note"):
            lines += [block["eligible_note"], ""]
        lines += [
            "| Condition | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides |",
            "|---|---:|---:|---:|---:|",
        ]
        for r in block["summary"]["conditions"]:
            lines.append(
                f"| {r['condition']} | {r['mean_hidden_evidence_recall']} | "
                f"{r['paired_delta_vs_fixed_pp']} | {r['degraded_rate']} | {r['review_overrides']} |"
            )
        lines.append("")
    (OUT_DIR / "tables.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    print("Wrote", OUT_DIR)


if __name__ == "__main__":
    main()
