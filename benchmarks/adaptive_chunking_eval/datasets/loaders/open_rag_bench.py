"""Open RAG Bench (Vectara) arXiv PDF corpus loader."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from schema import DocRecord, QAItem

DATA = Path(__file__).resolve().parents[1].parent / "data" / "open_rag_bench"


def _section_text(sec: dict) -> str:
    text = sec.get("text") or ""
    tables = sec.get("tables") or {}
    if isinstance(tables, dict) and tables:
        extras = []
        for tid, md in tables.items():
            extras.append(f"\n[Table {tid}]\n{md}\n")
        text = text + "".join(extras)
    return text.strip()


def load_open_rag_bench(*, profile: str = "smoke", max_queries: int | None = None) -> list[DocRecord]:
    corpus_dir = DATA / "corpus"
    qrels_path = DATA / "qrels.json"
    queries_path = DATA / "queries.json"
    answers_path = DATA / "answers.json"
    selected_path = DATA / "selected_docs.json"
    for p in (corpus_dir, qrels_path, queries_path, answers_path):
        if not p.exists():
            raise FileNotFoundError(f"Open RAG Bench data missing ({p}); run datasets/download.py")

    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    qrels = json.loads(qrels_path.read_text(encoding="utf-8"))
    selected = json.loads(selected_path.read_text(encoding="utf-8")) if selected_path.exists() else [
        p.stem for p in sorted(corpus_dir.glob("*.json"))
    ]
    per_doc_cap = 4 if profile == "smoke" else 10**9
    if profile == "smoke":
        max_queries = max_queries or 40
    elif max_queries is None:
        max_queries = 10**9

    by_doc_qids: dict[str, list[str]] = defaultdict(list)
    for qid, rel in qrels.items():
        doc_id = rel.get("doc_id") if isinstance(rel, dict) else None
        if doc_id in selected:
            by_doc_qids[doc_id].append(qid)

    docs: list[DocRecord] = []
    total_q = 0
    for doc_id in selected:
        if total_q >= max_queries:
            break
        path = corpus_dir / f"{doc_id}.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        sections = raw.get("sections") or []
        parts = []
        title = raw.get("title") or doc_id
        parts.append(f"# {title}\n")
        if raw.get("abstract"):
            parts.append(raw["abstract"].strip() + "\n")
        for sec in sections:
            st = _section_text(sec)
            if st:
                parts.append(st)
        text = "\n\n".join(parts)
        if not text.strip():
            continue

        qa_pairs: list[QAItem] = []
        for qid in by_doc_qids.get(doc_id, [])[:per_doc_cap]:
            if total_q >= max_queries:
                break
            qobj = queries.get(qid) or {}
            question = qobj.get("query") if isinstance(qobj, dict) else str(qobj)
            answer = str(answers.get(qid) or "")
            sec_id = (qrels[qid].get("section_id") if isinstance(qrels[qid], dict) else None)
            evidence = ""
            if sec_id is not None and 0 <= int(sec_id) < len(sections):
                evidence = _section_text(sections[int(sec_id)])[:700]
            qa_pairs.append(
                QAItem(
                    qa_id=qid,
                    question=question or "",
                    answer=answer,
                    evidence_quote=evidence,
                    key_terms=[t.lower() for t in (question or "").split() if len(t) > 3][:5],
                    meta={
                        "type": qobj.get("type") if isinstance(qobj, dict) else None,
                        "source": qobj.get("source") if isinstance(qobj, dict) else None,
                        "section_id": sec_id,
                    },
                )
            )
            total_q += 1
        if not qa_pairs:
            continue
        docs.append(
            DocRecord(
                dataset="open_rag_bench",
                doc_id=doc_id,
                domain="arxiv",
                text=text,
                qa_pairs=qa_pairs,
                meta={
                    "title": title,
                    "categories": raw.get("categories") or [],
                    "n_sections": len(sections),
                    "source": "vectara/open_ragbench",
                },
            )
        )
    return docs
