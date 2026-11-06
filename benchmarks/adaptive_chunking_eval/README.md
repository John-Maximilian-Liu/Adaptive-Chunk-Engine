# ACE Adaptive Chunking Evaluation Kit

Self-contained benchmark + paper for **Adaptive Chunk Engine**, aligned with:

- Paper: [*Adaptive Chunking: Optimizing Chunking-Method Selection for RAG*](https://arxiv.org/abs/2603.25333) (LREC 2026)
- Code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking)

## Layout

```text
benchmarks/adaptive_chunking_eval/
  run_eval.py          # evaluation entrypoint
  src/intrinsic_metrics.py
  corpus/              # multi-domain documents
  results/             # tables.md, summary.json, metrics.json
  paper/
    paper.md           # arXiv-style research article (HF paper-publisher template)
    paper.html         # web-friendly rendering
  README.md            # this file
```

## Run

```bash
cd benchmarks/adaptive_chunking_eval
PYTHONPATH=../../apps/api:../../packages/python python run_eval.py
# or from repo root:
make eval
```

## Key comparison (latest run)

See [`results/tables.md`](results/tables.md) for full tables including **published CLAIR numbers** from the Adaptive Chunking project.

| Study | Adaptive mean (intrinsic) | Notes |
|-------|---------------------------:|-------|
| Adaptive Chunking (CLAIR) | **91.07** | Neural embeddings, 33 docs |
| **ACE `adaptive_ace` (offline)** | **92.10** | Hashed embeddings, 6 docs |

| Study | Adaptive RAG completeness | Notes |
|-------|--------------------------:|-------|
| Adaptive Chunking (CLAIR) | **67.7** | LLM judge, 99 queries |
| **ACE `adaptive_ace` (offline)** | **100.0** | Lexical proxy — not absolute-comparable |

Compare **ranks** across studies; do not equate absolute RAG scores across protocols.

## Paper

- Markdown: [`paper/paper.md`](paper/paper.md)
- HTML: [`paper/paper.html`](paper/paper.html)
