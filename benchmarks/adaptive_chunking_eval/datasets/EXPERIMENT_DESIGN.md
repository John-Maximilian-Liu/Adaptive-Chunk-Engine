# Public Benchmark Experiment Design

Compare **ACE `adaptive_ace`** against fixed chunkers (and published Adaptive Chunking CLAIR numbers) on three recognized corpora.

| Dataset | Role | Primary comparison |
|---------|------|--------------------|
| **CLAIR** | Academic alignment with LREC 2026 Adaptive Chunking | Intrinsic mean + RAG vs paper Tables 3/5 |
| **FinanceBench** | Industry financial long-doc QA (Patronus) | Intrinsic + dense/LLM-judge RAG on SEC-style evidence |
| **Open RAG Bench** | PDF→RAG multimodal arXiv corpus (Vectara) | Intrinsic + dense/LLM-judge RAG on section-grounded queries |

## Protocol (shared)

### Chunking methods

| Name | Strategy |
|------|----------|
| `adaptive_ace` | Per-doc argmax of intrinsic mean over candidates below |
| `recursive_text_1100` | recursive, size 1100 / overlap 100 |
| `recursive_text` | recursive, size 512 / overlap 64 |
| `fixed_token_512` | fixed token 512 / 64 |
| `fixed_token_256` | fixed token 256 / 32 |
| `heading_section` | heading-aware |
| `sentence_window` | sentence window (brittle baseline) |
| `no_split` | whole document |

### Metrics

1. **Intrinsic** — RC, ICC, DCC, BI, SC → Mean  
   - Offline: hashed n-gram embeddings  
   - Live: OpenRouter `openai/text-embedding-3-small` for ICC/DCC
2. **RAG** — dense cosine retrieval (same embed model) + OpenRouter `openai/gpt-4o` JSON judge  
   - Outputs: retrieval completeness, answer correctness, answered/N

Judge / models match the prior ACE OpenRouter run (`ACE_CHAT_MODEL`, `ACE_EMBED_MODEL`).

### Profiles

| Profile | CLAIR docs | FinanceBench Q | Open RAG Bench |
|---------|------------|----------------|----------------|
| `smoke` | 6 stratified (2 tech / 2 legal / 2 social) | 24 Q (~12 docs) | 10 docs / ≤40 Q |
| `full` | all 33 | all 150 Q | selected corpus + all their Q (extendable) |

Use `smoke` for iteration; `full` for paper-grade numbers (live cost scales with docs × methods × queries).

### Baselines reported alongside ACE

- Published Adaptive Chunking CLAIR intrinsic / RAG (paper)  
- ACE offline ACE-kit results (hashed) when available  
- Prior ACE OpenRouter ACE-kit results when available  

**Compare ranks within a dataset/protocol; do not equate absolute RAG scores across datasets.**

## Hypotheses

1. On CLAIR, neural-intrinsic `adaptive_ace` ranks near the top recursive method and above `sentence_window`, matching the paper’s qualitative claim.
2. On FinanceBench / Open RAG Bench, intrinsic argmax may diverge from LLM-judge RAG (as seen on the ACE kit)—documenting when human-triggered optimization should override Auto selection.
3. Larger-context methods help short/medium docs; very long SEC/legal docs favor mid-size recursive / adaptive selection.

## Reproduce

```bash
# Ensure data is present (idempotent)
python benchmarks/adaptive_chunking_eval/datasets/download.py

# Offline smoke (no API)
make eval-public-smoke

# Live OpenRouter smoke (OPENROUTER_API_KEY)
make eval-public-openrouter-smoke

# Full live (expensive)
ACE_BENCH_PROFILE=full make eval-public-openrouter
```

Outputs: `benchmarks/adaptive_chunking_eval/results/public_benchmarks/`

## Smoke results (latest)

### Offline (`hashed` + lexical)

| Dataset | adaptive_ace Mean | Notes |
|---------|------------------:|-------|
| CLAIR (6 docs) | **90.53** | Paper Adaptive mean 91.07 (full 33, neural) |
| FinanceBench (8 docs / 12 Q) | **96.45** | Evidence-page docs |
| Open RAG Bench (10 docs / 40 Q) | **90.95** | arXiv section text |

### OpenRouter live (`text-embedding-3-small` + `gpt-4o`)

| Dataset | adaptive_ace Mean | adaptive_ace RAG RC / AC |
|---------|------------------:|-------------------------:|
| CLAIR | **84.89** | **91.67 / 91.67** (11/12) |
| FinanceBench | **94.76** | 92.5 / 86.25 (10/12) |
| Open RAG Bench | **86.00** | **88.0 / 84.0** (17/20) |

Live smoke approx. cost ≈ \$1.10 (OpenRouter reported). Full profile remains available via `ACE_BENCH_PROFILE=full make eval-public-openrouter`.
