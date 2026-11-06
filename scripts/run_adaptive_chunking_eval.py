#!/usr/bin/env python3
"""Run Adaptive-Chunking-style intrinsic (+ lightweight RAG) evaluation for ACE.

Inspired by de Moura et al., LREC 2026 / arXiv:2603.25333 and
https://github.com/ekimetrics/adaptive-chunking

Produces:
  results/adaptive_chunking_eval/metrics.json
  results/adaptive_chunking_eval/tables.md
  results/adaptive_chunking_eval/summary.json
"""
from __future__ import annotations

import asyncio
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "python"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from evaluation_engine.intrinsic_metrics import score_chunks  # noqa: E402
from app.services.engine import Engine  # noqa: E402
from canonical_schemas.document import ElementModel, LogicalUnitModel, Locator  # noqa: E402
from chunk_adapters import get_registry  # noqa: E402
from chunk_adapters.base import ChunkRequest  # noqa: E402
from shared.ids import new_id  # noqa: E402

OUT = ROOT / "results" / "adaptive_chunking_eval"
FIXTURES = ROOT / "tests" / "fixtures"

# Strategies comparable to paper baselines + ACE adaptive selection
FIXED_STRATEGIES = [
    ("fixed_token_512", "fixed_token", {"chunk_size": 512, "chunk_overlap": 64}),
    ("fixed_token_256", "fixed_token", {"chunk_size": 256, "chunk_overlap": 32}),
    ("recursive_text", "recursive_text", {"chunk_size": 512, "chunk_overlap": 64}),
    ("recursive_text_1100", "recursive_text", {"chunk_size": 1100, "chunk_overlap": 100}),
    ("sentence_window", "sentence_window", {"chunk_size": 384, "chunk_overlap": 48}),
    ("heading_section", "heading_section", {"chunk_size": 512, "chunk_overlap": 64}),
    ("no_split", "no_split", {}),
]


def _domain_corpus() -> list[dict]:
    """Multi-domain synthetic corpus (technical / legal / sustainability) + fixtures."""
    docs: list[dict] = []

    corpus_dir = FIXTURES / "eval_corpus"
    mapping = {
        "technical_long.md": "technical",
        "ops_long.md": "technical",
        "legal_long.md": "legal",
        "finance_long.md": "legal",
        "sustainability_long.md": "sustainability",
        "sample.md": "technical",
    }
    for name, domain in mapping.items():
        path = corpus_dir / name if (corpus_dir / name).exists() else FIXTURES / name
        if path.exists():
            docs.append({"doc_id": name, "domain": domain, "text": path.read_text(encoding="utf-8", errors="ignore")})
    return docs


def _chunk_with_strategy(engine: Engine, text: str, strategy_id: str, params: dict) -> list[str]:
    reg = get_registry()
    try:
        adapter = reg.get_adapter(strategy_id)
    except KeyError:
        adapter = reg.get_adapter("fixed_token")
        strategy_id = "fixed_token"
        params = {"chunk_size": 512, "chunk_overlap": 64}
    tenant = "eval"
    doc_id, ver_id, run_id = new_id(), new_id(), new_id()
    unit = LogicalUnitModel(
        tenant_id=tenant,
        document_version_id=ver_id,
        unit_type="section",
        ordinal=0,
        title="unit-0",
    )
    # Split into paragraph elements so heading/block metrics have structure
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
    unit.regions = []
    hard = {
        "CHUNK_SIZE_MIN": 128,
        "CHUNK_SIZE_MAX": 4096,
        "CHUNK_SIZE_DEFAULT": 512,
        "CHUNK_OVERLAP_DEFAULT": 64,
        "CHUNK_OVERLAP_MAX_RATIO": 0.30,
        "CHUNK_HARD_TOKEN_LIMIT": 4096,
    }
    # Clamp tiny sizes used only for intrinsic scoring experiments
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
    validation = adapter.validate(req)
    if not validation.valid:
        # retry with safe defaults
        req.parameters = {"chunk_size": 512, "chunk_overlap": 64}
        req.strategy_id = "fixed_token"
        adapter = reg.get_adapter("fixed_token")
    chunks = adapter.chunk(req)
    return [c.text for c in chunks if (c.text or "").strip()]


async def _adaptive_select(engine: Engine, text: str) -> tuple[str, list[str], dict]:
    """Score all fixed strategies with intrinsic metrics; pick best mean (paper-style adaptive)."""
    best_name = None
    best_chunks: list[str] = []
    best_score = -1.0
    details = {}
    for name, sid, params in FIXED_STRATEGIES:
        chunks = _chunk_with_strategy(engine, text, sid, params)
        score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100)
        details[name] = score.as_percent_dict()
        m = score.mean or 0.0
        if m > best_score:
            best_score = m
            best_name = name
            best_chunks = chunks
    return best_name or "fixed_token_512", best_chunks, details


def _qa_pairs_for(doc: dict) -> list[dict]:
    """Harder grounded QA: query uses section index + topic keywords, not the full sentence."""
    text = doc["text"]
    sections = re.findall(r"(Section\s+(\d+)\s+discusses\s+([^.]+)\.\s*([^.]+)\.)", text)
    pairs = []
    for i, (full, num, topic, follow) in enumerate(sections[:8]):
        evidence = full.strip()
        # Intentionally short / paraphrased query to stress chunk locality
        q = f"Which requirements apply in section {num} regarding {topic.split()[0]}?"
        answer = f"{follow.strip()}. Cross-references to appendix {num} must remain intact across chunk boundaries."
        pairs.append({
            "qa_id": f"{doc['doc_id']}-q{i}",
            "question": q,
            "answer": answer,
            "evidence_quote": evidence,
            "key_terms": [f"section {num}", topic.split()[0].lower(), f"appendix {num}"],
        })
    if not pairs:
        # fallback for short fixture docs
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


def _retrieval_completeness(chunks: list[str], qa_pairs: list[dict], top_k: int = 5) -> dict:
    """Lexical retrieval completeness with key-term ranking (offline, no LLM judge)."""
    answered = 0
    completeness_scores = []
    correctness_scores = []

    def retrieve(question: str, key_terms: list[str]) -> list[str]:
        q_terms = set(re.findall(r"[a-z0-9]+", question.lower())) | {t.lower() for t in key_terms}
        ranked = []
        for c in chunks:
            terms = set(re.findall(r"[a-z0-9]+", c.lower()))
            # Prefer chunks that contain section/appendix anchors
            bonus = 0.0
            cl = c.lower()
            for t in key_terms:
                if t.lower() in cl:
                    bonus += 0.15
            overlap = len(q_terms & terms) / max(1, len(q_terms))
            ranked.append((overlap + bonus, c))
        ranked.sort(reverse=True)
        return [c for _, c in ranked[:top_k]]

    for qa in qa_pairs:
        hits = retrieve(qa["question"], qa.get("key_terms") or [])
        evidence = qa["evidence_quote"]
        ev_terms = set(re.findall(r"[a-z0-9]+", evidence.lower()))
        # completeness: fraction of evidence terms recovered in top-k
        ctx = " ".join(hits).lower()
        ctx_terms = set(re.findall(r"[a-z0-9]+", ctx))
        cov = len(ev_terms & ctx_terms) / max(1, len(ev_terms))
        ok = cov >= 0.55
        completeness_scores.append(cov)
        ans_terms = set(re.findall(r"[a-z0-9]+", qa["answer"].lower()))
        corr = len(ans_terms & ctx_terms) / max(1, len(ans_terms))
        correctness_scores.append(corr)
        if ok:
            answered += 1

    n = max(1, len(qa_pairs))
    return {
        "retrieval_completeness": round(100.0 * sum(completeness_scores) / n, 2),
        "answer_correctness": round(100.0 * sum(correctness_scores) / n, 2),
        "answered_queries": f"{answered}/{len(qa_pairs)}",
        "n_queries": len(qa_pairs),
    }


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = Engine(storage_root=OUT / "storage")
    engine.seed_development()
    corpus = _domain_corpus()

    # Intrinsic eval per method × document
    method_domain_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    method_overall: dict[str, list[dict]] = defaultdict(list)
    per_doc_rows = []

    methods = [(n, s, p) for n, s, p in FIXED_STRATEGIES] + [("adaptive_ace", "adaptive", {})]

    for doc in corpus:
        text = doc["text"]
        domain = doc["domain"]
        for name, sid, params in methods:
            if name == "adaptive_ace":
                selected, chunks, detail = await _adaptive_select(engine, text)
                score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100)
                meta = {"selected": selected, "candidates": detail}
            else:
                chunks = _chunk_with_strategy(engine, text, sid, params)
                score = score_chunks(chunks, text, min_tokens=50, max_tokens=1100)
                meta = {}
            pct = score.as_percent_dict()
            method_overall[name].append(pct)
            if score.mean is not None:
                method_domain_scores[name][domain].append(score.mean * 100.0)
            per_doc_rows.append({
                "doc_id": doc["doc_id"],
                "domain": domain,
                "method": name,
                "n_chunks": len(chunks),
                **pct,
                **meta,
            })

    # Aggregate intrinsic table (Table-3 style)
    intrinsic_table = []
    for name, _sid, _p in methods:
        rows = method_overall[name]
        def avg(key):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None
        intrinsic_table.append({
            "method": name,
            "RC": avg("RC"),
            "ICC": avg("ICC"),
            "DCC": avg("DCC"),
            "BI": avg("BI"),
            "SC": avg("SC"),
            "Mean": avg("Mean"),
        })
    intrinsic_table.sort(key=lambda r: r["Mean"] or 0, reverse=True)

    # RAG-lite eval for adaptive vs recursive vs fixed_token vs heading vs no_split
    rag_methods = [
        "adaptive_ace",
        "recursive_text_1100",
        "recursive_text",
        "fixed_token_512",
        "fixed_token_256",
        "heading_section",
        "no_split",
        "sentence_window",
    ]
    rag_table = []
    for name in rag_methods:
        rc_scores, ac_scores, answered_n, total_n = [], [], 0, 0
        for doc in corpus:
            text = doc["text"]
            if name == "adaptive_ace":
                _, chunks, _ = await _adaptive_select(engine, text)
            else:
                sid, params = next((s, p) for n, s, p in FIXED_STRATEGIES if n == name)
                chunks = _chunk_with_strategy(engine, text, sid, params)
            qa = _qa_pairs_for(doc)
            rag = _retrieval_completeness(chunks, qa)
            rc_scores.append(rag["retrieval_completeness"])
            ac_scores.append(rag["answer_correctness"])
            a, t = rag["answered_queries"].split("/")
            answered_n += int(a)
            total_n += int(t)
        rag_table.append({
            "method": name,
            "retrieval_completeness": round(sum(rc_scores) / len(rc_scores), 2),
            "answer_correctness": round(sum(ac_scores) / len(ac_scores), 2),
            "answered_queries": f"{answered_n}/{total_n}",
        })
    rag_table.sort(key=lambda r: r["retrieval_completeness"], reverse=True)

    # Domain means for adaptive
    domain_breakdown = {
        name: {d: round(statistics.mean(vals), 2) for d, vals in domains.items()}
        for name, domains in method_domain_scores.items()
    }

    summary = {
        "paper_reference": {
            "title": "Adaptive Chunking: Optimizing Chunking-Method Selection for RAG",
            "arxiv": "https://arxiv.org/abs/2603.25333",
            "code": "https://github.com/ekimetrics/adaptive-chunking",
            "venue": "LREC 2026",
        },
        "corpus": {
            "n_documents": len(corpus),
            "domains": sorted({d["domain"] for d in corpus}),
            "approx_tokens": sum(len(d["text"].split()) for d in corpus),
        },
        "notes": [
            "ICC/DCC use deterministic hashed n-gram embeddings (offline). Swap embed_fn for Jina/ST for semantic parity with the paper.",
            "RC uses a filtered pronoun–antecedent heuristic (no maverick-coref dependency).",
            "RAG metrics are lexical retrieval completeness / answer-token coverage without an LLM judge.",
            "adaptive_ace selects the per-document strategy with the best intrinsic mean among ACE builtins.",
        ],
        "intrinsic_table": intrinsic_table,
        "rag_table": rag_table,
        "domain_breakdown": domain_breakdown,
    }

    (OUT / "metrics.json").write_text(json.dumps({"per_document": per_doc_rows, **summary}, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Markdown tables
    lines = [
        "# ACE Adaptive Chunking Evaluation Results",
        "",
        f"Corpus: **{len(corpus)} documents** across domains `{summary['corpus']['domains']}` (~{summary['corpus']['approx_tokens']} words).",
        "",
        "Reference protocol adapted from [arXiv:2603.25333](https://arxiv.org/abs/2603.25333) / [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).",
        "",
        "## Intrinsic metrics (Table 3 style, %)",
        "",
        "| Method | RC | ICC | DCC | BI | SC | **Mean** |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in intrinsic_table:
        mark = "**" if r["method"] == "adaptive_ace" else ""
        lines.append(
            f"| {mark}{r['method']}{mark} | {r['RC']} | {r['ICC']} | {r['DCC']} | {r['BI']} | {r['SC']} | **{r['Mean']}** |"
        )
    lines += [
        "",
        "## RAG-lite evaluation (Table 5 style)",
        "",
        "| Method | Retrieval Completeness | Answer Correctness | Answered queries |",
        "|---|---:|---:|---:|",
    ]
    for r in rag_table:
        mark = "**" if r["method"] == "adaptive_ace" else ""
        lines.append(
            f"| {mark}{r['method']}{mark} | {r['retrieval_completeness']} | {r['answer_correctness']} | {r['answered_queries']} |"
        )
    lines += ["", "## Notes", ""] + [f"- {n}" for n in summary["notes"]]
    (OUT / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((OUT / "tables.md").read_text())
    print("Wrote", OUT)


if __name__ == "__main__":
    asyncio.run(main())
