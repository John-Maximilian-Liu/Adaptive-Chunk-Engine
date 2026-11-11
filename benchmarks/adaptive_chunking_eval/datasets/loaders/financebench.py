"""FinanceBench open-source loader (Patronus)."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from schema import DocRecord, QAItem

DATA = Path(__file__).resolve().parents[1].parent / "data" / "financebench"


def load_financebench(*, profile: str = "smoke", max_questions: int | None = None) -> list[DocRecord]:
    q_path = DATA / "financebench_open_source.jsonl"
    docs_dir = DATA / "docs_from_evidence"
    if not q_path.exists() or not docs_dir.exists():
        raise FileNotFoundError(f"FinanceBench data missing under {DATA}; run datasets/download.py")

    questions = [json.loads(line) for line in q_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if profile == "smoke":
        max_questions = max_questions or 12
    elif max_questions is None:
        max_questions = len(questions)

    # Prefer diverse companies while capping questions.
    selected: list[dict] = []
    per_company: dict[str, int] = defaultdict(int)
    for q in questions:
        if len(selected) >= max_questions:
            break
        company = q.get("company") or "unknown"
        if per_company[company] >= (2 if profile == "smoke" else 10**9):
            continue
        selected.append(q)
        per_company[company] += 1
    # If diversity filter under-filled, top up.
    if len(selected) < max_questions:
        seen = {q["financebench_id"] for q in selected}
        for q in questions:
            if q["financebench_id"] in seen:
                continue
            selected.append(q)
            if len(selected) >= max_questions:
                break

    by_doc: dict[str, list[dict]] = defaultdict(list)
    for q in selected:
        by_doc[q["doc_name"]].append(q)

    docs: list[DocRecord] = []
    for doc_name, items in by_doc.items():
        text_path = docs_dir / f"{doc_name}.md"
        text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
        if not text.strip():
            # Fallback: stitch evidence pages from selected questions.
            pages: dict[int, str] = {}
            for q in items:
                for ev in q.get("evidence") or []:
                    pnum = int(ev.get("evidence_page_num") or 0)
                    full = ev.get("evidence_text_full_page") or ev.get("evidence_text") or ""
                    if full:
                        pages[pnum] = full
            text = "\n\n".join(pages[k] for k in sorted(pages))
        if not text.strip():
            continue
        qa_pairs = []
        for q in items:
            ev0 = (q.get("evidence") or [{}])[0]
            evidence = (ev0.get("evidence_text") or "")[:800]
            qa_pairs.append(
                QAItem(
                    qa_id=str(q.get("financebench_id")),
                    question=q.get("question") or "",
                    answer=str(q.get("answer") or ""),
                    evidence_quote=evidence,
                    key_terms=[t for t in str(q.get("company") or "").split() if t][:3],
                    meta={
                        "question_type": q.get("question_type"),
                        "doc_name": doc_name,
                        "company": q.get("company"),
                    },
                )
            )
        docs.append(
            DocRecord(
                dataset="financebench",
                doc_id=doc_name,
                domain="finance",
                text=text,
                qa_pairs=qa_pairs,
                meta={
                    "n_questions": len(qa_pairs),
                    "source": "patronus-ai/financebench",
                    "note": "Document text assembled from annotated evidence pages (open-source release).",
                },
            )
        )
    return docs
