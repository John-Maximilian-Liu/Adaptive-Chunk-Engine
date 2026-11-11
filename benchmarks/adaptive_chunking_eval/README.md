# ACE Adaptive Chunking Evaluation Kit

Self-contained benchmark + paper for **Adaptive Chunk Engine**, aligned with:

- Paper: [*Adaptive Chunking: Optimizing Chunking-Method Selection for RAG*](https://arxiv.org/abs/2603.25333) (LREC 2026)
- Code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking)

## Layout

```text
benchmarks/adaptive_chunking_eval/
  run_eval.py               # offline evaluation entrypoint
  run_eval_openrouter.py    # live OpenRouter eval (gpt-4o + text-embedding-3-small)
  src/intrinsic_metrics.py
  src/openrouter_client.py
  corpus/                   # multi-domain documents
  results/                  # offline tables.md, summary.json, metrics.json
  results/openrouter/       # live OpenRouter tables + usage
  paper/
    paper.md                # arXiv-style research article
    paper.html              # web-friendly rendering
  README.md                 # this file
```

## Run

### Offline (hashed embeddings + lexical RAG-lite)

```bash
cd benchmarks/adaptive_chunking_eval
PYTHONPATH=../../apps/api:../../packages/python python run_eval.py
# or from repo root:
make eval
```

### Live OpenRouter (neural embeddings + gpt-4o LLM judge)

Requires `OPENROUTER_API_KEY`. Defaults: chat `openai/gpt-4o`, embed `openai/text-embedding-3-small`.

```bash
export OPENROUTER_API_KEY=...   # or inject as Cloud Agent runtime secret
export ACE_CHAT_MODEL=openai/gpt-4o
export ACE_EMBED_MODEL=openai/text-embedding-3-small
make eval-openrouter
# → benchmarks/adaptive_chunking_eval/results/openrouter/
```

## Key comparison (latest run)

See [`results/tables.md`](results/tables.md) (offline) and [`results/openrouter/tables.md`](results/openrouter/tables.md) (live).

| Study | Adaptive mean (intrinsic) | Notes |
|-------|---------------------------:|-------|
| Adaptive Chunking (CLAIR) | **91.07** | Neural embeddings, 33 docs |
| **ACE `adaptive_ace` (offline)** | **92.10** | Hashed embeddings, 6 docs |
| **ACE `adaptive_ace` (OpenRouter)** | **88.48** | `text-embedding-3-small` ICC/DCC, 6 docs |

| Study | Adaptive RAG completeness | Notes |
|-------|--------------------------:|-------|
| Adaptive Chunking (CLAIR) | **67.7** | LLM judge, 99 queries |
| **ACE `adaptive_ace` (offline)** | **100.0** | Lexical proxy — not absolute-comparable |
| **ACE `adaptive_ace` (OpenRouter)** | **64.17** | Dense retrieval + `gpt-4o` judge, 43 queries |

Compare **ranks** across studies; do not equate absolute RAG scores across protocols.

**OpenRouter takeaway:** with neural ICC/DCC, `adaptive_ace` still tops intrinsic mean and still avoids brittle `sentence_window` (55.64). Under dense+LLM-judge RAG on this small corpus, larger-context fixed splitters (`no_split`, `fixed_token_512`) outrank intrinsic argmax — motivating ACE’s human-triggered optimization loop when RAG feedback disagrees with intrinsic selection.

## Paper

- Markdown: [`paper/paper.md`](paper/paper.md)
- HTML: [`paper/paper.html`](paper/paper.html)
