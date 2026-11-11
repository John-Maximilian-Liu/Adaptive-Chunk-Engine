#!/usr/bin/env python3
"""Download / refresh CLAIR, FinanceBench, and Open RAG Bench evaluation data.

Idempotent. Writes under benchmarks/adaptive_chunking_eval/data/.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def download_clair() -> None:
    out = DATA / "clair" / "adi_parsed"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "adaptive-chunking"
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                "https://github.com/ekimetrics/adaptive-chunking.git",
                str(root),
            ]
        )
        _run(["git", "sparse-checkout", "set", "data/clair"], cwd=root)
        src = root / "data" / "clair" / "adi_parsed"
        for f in sorted(src.glob("*.json")):
            shutil.copy2(f, out / f.name)
    rows = []
    for f in sorted(out.glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        name = f.stem.lower()
        if "norma" in name or "légal" in name:
            domain = "legal"
        elif "sophia" in name:
            domain = "social"
        elif "ada" in name:
            domain = "technical"
        else:
            domain = "other"
        rows.append({"doc_id": f.stem, "domain": domain, "n_chars": len(raw.get("full_text") or "")})
    (DATA / "clair" / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"CLAIR: {len(rows)} docs → {out}")


def download_financebench() -> None:
    out = DATA / "financebench"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "financebench"
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                "https://github.com/patronus-ai/financebench.git",
                str(root),
            ]
        )
        _run(["git", "sparse-checkout", "set", "data"], cwd=root)
        for name in ("financebench_open_source.jsonl", "financebench_document_information.jsonl"):
            shutil.copy2(root / "data" / name, out / name)
    questions = [
        json.loads(line)
        for line in (out / "financebench_open_source.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    docs_dir = out / "docs_from_evidence"
    docs_dir.mkdir(exist_ok=True)
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        by_doc[q["doc_name"]].append(q)
    for doc_name, items in by_doc.items():
        pages: dict[int, str] = {}
        for q in items:
            for ev in q.get("evidence") or []:
                pnum = int(ev.get("evidence_page_num") or 0)
                full = ev.get("evidence_text_full_page") or ev.get("evidence_text") or ""
                if full:
                    pages[pnum] = full
        (docs_dir / f"{doc_name}.md").write_text("\n\n".join(pages[k] for k in sorted(pages)), encoding="utf-8")
    print(f"FinanceBench: {len(questions)} Q / {len(by_doc)} docs → {out}")


def download_open_rag_bench(n_docs: int = 10) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SystemExit("huggingface_hub required: pip install huggingface_hub") from exc

    out = DATA / "open_rag_bench"
    out.mkdir(parents=True, exist_ok=True)
    corpus_dir = out / "corpus"
    corpus_dir.mkdir(exist_ok=True)
    for name in ("answers.json", "queries.json", "qrels.json", "pdf_urls.json"):
        hf_hub_download(
            "vectara/open_ragbench",
            f"pdf/arxiv/{name}",
            repo_type="dataset",
            local_dir=str(out / "_hf"),
        )
        src = out / "_hf" / "pdf" / "arxiv" / name
        shutil.copy2(src, out / name)
    qrels = json.loads((out / "qrels.json").read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    for rel in qrels.values():
        if isinstance(rel, dict) and rel.get("doc_id"):
            counts[rel["doc_id"]] += 1
    selected = [d for d, _ in counts.most_common(n_docs)]
    for did in selected:
        hf_hub_download(
            "vectara/open_ragbench",
            f"pdf/arxiv/corpus/{did}.json",
            repo_type="dataset",
            local_dir=str(out / "_hf"),
        )
        shutil.copy2(out / "_hf" / "pdf" / "arxiv" / "corpus" / f"{did}.json", corpus_dir / f"{did}.json")
    (out / "selected_docs.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
    # Drop bulky HF cache tree from committed layout if present
    cache = out / "_hf"
    if cache.exists():
        shutil.rmtree(cache, ignore_errors=True)
    print(f"Open RAG Bench: {len(selected)} docs → {out}")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    download_clair()
    download_financebench()
    download_open_rag_bench()
    print("Done. Data root:", DATA)


if __name__ == "__main__":
    main()
