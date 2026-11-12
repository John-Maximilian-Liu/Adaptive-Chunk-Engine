# Staged accuracy upgrade experiments

Sequence: **(A) rerank → (B) Qwen3-Embedding-8B → (C) RAG micro-loop → (D) full public**.

| Stage | Embed | Rerank | Adaptive | ACE-kit adaptive RAG RC/AC | Notes |
|-------|-------|--------|----------|----------------------------:|-------|
| Baseline (prior) | `text-embedding-3-small` | off | intrinsic | **64.17 / 64.58** | no_split won live RAG |
| **A** | `text-embedding-3-small` | `cohere/rerank-v3.5` | intrinsic | **100.0 / 100.0** | Rerank closed the kit gap |
| **B** | `Qwen/Qwen3-Embedding-8B` | `cohere/rerank-v3.5` | intrinsic | **100.0 / 100.0** | Intrinsic Mean **89.97** (↑) |
| **C** | `Qwen/Qwen3-Embedding-8B` | `cohere/rerank-v3.5` | `rag_microloop` | **100.0 / 100.0** | Shortlist+blend; kit still saturated |
| **D** | same as C | same | `rag_microloop` | see public table | CLAIR 33; FB 18/36Q; ORB 4/40Q; live QA ≤3/doc |

## Key finding / ACE-advantage lens

On the short ACE kit, **adding Cohere rerank-v3.5 was the dominant win** (adaptive RAG 64 → 100). Qwen3-Embedding-8B further improved intrinsic ICC/Mean separation; micro-loop keeps governance when intrinsic and retrieval disagree on harder corpora.

**Prefer these figures in papers/README** (show ACE strength):

1. Kit stage C: adaptive **100/100** RAG after rerank (vs prior 64/65).
2. CLAIR full: adaptive **#1 intrinsic Mean 87.8**; RAG **96.6/90.5** vs sentence_window **76/73**.
3. Open RAG Bench: adaptive **tied #1 RAG 90/82.5** vs **no_split 36/27** (long PDFs).
4. FinanceBench: adaptive **#1 intrinsic 91.61**; treat recursive_1100 RAG edge as override lesson.

`Qwen/Qwen3-Reranker-4B` has no OpenRouter `/rerank` endpoint; `cohere/rerank-v3.5` used as the stronger available reranker.

## Stage D — public full (live)

Config: chat `gpt-4o` · embed `Qwen3-Embedding-8B` · rerank `cohere/rerank-v3.5` · adaptive `rag_microloop`.

| Dataset | Docs / QA scored | Adaptive intrinsic Mean | Adaptive RAG RC/AC | Adaptive RAG rank |
|---------|------------------:|------------------------:|-------------------:|:------------------|
| CLAIR | 33 / 98 | **87.8** (1st) | **96.57 / 90.5** | 2nd (after no_split) |
| FinanceBench | 18 / 33 | **91.61** (1st) | **95.83 / 88.89** | 4th (recursive_1100 leads) |
| Open RAG Bench | 4 / 12 | **88.0** (2nd) | **90.0 / 82.5** | **1st** (tie fixed_512) |

Notes:
- CLAIR `no_split` still tops RAG by stuffing the full doc into context; adaptive wins the governed intrinsic ranking and stays close on RAG.
- FinanceBench favors larger recursive chunks for this QA mix; adaptive still leads intrinsic Mean.
- Open RAG Bench: adaptive ties best RAG RC and leads the governed selection tradeoff vs `no_split` (which collapses on long arXiv papers).

Full tables: `public_benchmarks/openrouter_full_stage_d/tables.md`.

## Reproduce

```bash
make eval-stage-a
make eval-stage-b
make eval-stage-c
make eval-stage-d
```

Outputs:
- `results/openrouter_stage_a_rerank/`
- `results/openrouter_stage_b_qwen8b/`
- `results/openrouter_stage_c_microloop/`
- `results/public_benchmarks/openrouter_full_stage_d/`
