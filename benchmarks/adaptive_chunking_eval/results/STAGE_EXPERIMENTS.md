# Staged accuracy upgrade experiments

Sequence: **(A) rerank → (B) Qwen3-Embedding-8B → (C) RAG micro-loop → (D) full public**.

| Stage | Embed | Rerank | Adaptive | ACE-kit adaptive RAG RC/AC | Notes |
|-------|-------|--------|----------|----------------------------:|-------|
| Baseline (prior) | `text-embedding-3-small` | off | intrinsic | **64.17 / 64.58** | no_split won live RAG |
| **A** | `text-embedding-3-small` | `cohere/rerank-v3.5` | intrinsic | **100.0 / 100.0** | Rerank closed the kit gap |
| **B** | `Qwen/Qwen3-Embedding-8B` | `cohere/rerank-v3.5` | intrinsic | **100.0 / 100.0** | Intrinsic Mean **89.97** (↑) |
| **C** | `Qwen/Qwen3-Embedding-8B` | `cohere/rerank-v3.5` | `rag_microloop` | **100.0 / 100.0** | Shortlist+blend; kit still saturated |
| **D** | same as C | same | `rag_microloop` | _(public full)_ | All docs; live QA ≤3/doc |

## Key finding

On the short ACE kit, **adding Cohere rerank-v3.5 was the dominant win** (adaptive RAG 64 → 100). Qwen3-Embedding-8B further improved intrinsic ICC/Mean separation; micro-loop keeps governance when intrinsic and retrieval disagree on harder corpora.

`Qwen/Qwen3-Reranker-4B` has no OpenRouter `/rerank` endpoint; `cohere/rerank-v3.5` used as the stronger available reranker (`Qwen/Qwen3-Reranker-0.6B` is the Qwen fallback).

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
