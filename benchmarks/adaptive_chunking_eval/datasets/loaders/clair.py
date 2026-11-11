"""CLAIR corpus loader (Adaptive Chunking / LREC 2026)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from schema import DocRecord, QAItem

DATA = Path(__file__).resolve().parents[1].parent / "data" / "clair"


def _domain(name: str) -> str:
    low = name.lower()
    if "norma (légal)" in low or "norma (legal)" in low or "légal" in low:
        return "legal"
    if "sophia" in low or "sciences sociales" in low:
        return "social"
    if "ada (technique)" in low or "technique" in low:
        return "technical"
    return "other"


def _synthetic_qa(doc_id: str, text: str, max_q: int = 4) -> list[QAItem]:
    """CLAIR paper uses a separate RAG set; we synthesize section-anchored probes for ACE harness."""
    headings = re.findall(r"(?m)^#{1,3}\s+(.+)$", text)
    pairs: list[QAItem] = []
    for i, h in enumerate(headings[:max_q]):
        # Grab following paragraph as evidence.
        m = re.search(rf"(?ms)^#{{1,3}}\s+{re.escape(h)}\s*\n+(.{{40,600}}?)(?:\n\n|\n#|\Z)", text)
        evidence = (m.group(1).strip() if m else h)[:500]
        pairs.append(
            QAItem(
                qa_id=f"{doc_id}-h{i}",
                question=f"What does the document state under the section '{h.strip()}'?",
                answer=evidence.split(".")[0][:300] + ".",
                evidence_quote=evidence,
                key_terms=[t.lower() for t in re.findall(r"[A-Za-z0-9]{4,}", h)[:4]],
            )
        )
    if not pairs:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 60][:max_q]
        for i, sent in enumerate(sents):
            pairs.append(
                QAItem(
                    qa_id=f"{doc_id}-s{i}",
                    question=f"What is stated about {' '.join(sent.split()[2:7])}?",
                    answer=sent,
                    evidence_quote=sent[:400],
                    key_terms=sent.lower().split()[2:6],
                )
            )
    return pairs


def load_clair(*, profile: str = "smoke", max_qa_per_doc: int = 4) -> list[DocRecord]:
    parsed = DATA / "adi_parsed"
    if not parsed.exists():
        raise FileNotFoundError(f"CLAIR data missing at {parsed}; run datasets/download.py")

    docs: list[DocRecord] = []
    for path in sorted(parsed.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        text = raw.get("full_text") or ""
        if not text.strip():
            continue
        doc_id = path.stem
        domain = _domain(doc_id)
        docs.append(
            DocRecord(
                dataset="clair",
                doc_id=doc_id,
                domain=domain,
                text=text,
                qa_pairs=_synthetic_qa(doc_id, text, max_q=max_qa_per_doc),
                meta={
                    "n_pages": len(raw.get("pages") or []),
                    "n_split_points": len(raw.get("split_points") or []),
                    "source": "ekimetrics/adaptive-chunking data/clair",
                },
            )
        )

    if profile == "smoke":
        # Stratified: 2 technical, 2 legal, 2 social — prefer mid-size docs for cost.
        picked: list[DocRecord] = []
        for domain, need in [("technical", 2), ("legal", 2), ("social", 2)]:
            cand = sorted(
                [d for d in docs if d.domain == domain],
                key=lambda d: abs(d.n_chars - 80_000),
            )
            picked.extend(cand[:need])
        return picked
    return docs
