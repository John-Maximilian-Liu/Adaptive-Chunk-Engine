# Public benchmark results

Experiment design: [`../../datasets/EXPERIMENT_DESIGN.md`](../../datasets/EXPERIMENT_DESIGN.md)  
Stage A→D narrative: [`../STAGE_EXPERIMENTS.md`](../STAGE_EXPERIMENTS.md)

| Run | Path | Protocol |
|-----|------|----------|
| Offline smoke | [`offline_smoke/`](offline_smoke/) | hashed ICC/DCC + lexical RAG |
| OpenRouter smoke | [`openrouter_smoke/`](openrouter_smoke/) | `text-embedding-3-small` + `gpt-4o` (pre-rerank) |
| **OpenRouter full stage D** | [`openrouter_full_stage_d/`](openrouter_full_stage_d/) | **Qwen3-Embedding-8B + Cohere rerank-v3.5 + rag_microloop + gpt-4o** |

Prefer **stage D** for paper claims. ACE-advantage highlights: CLAIR intrinsic #1, Open RAG Bench RAG tied #1 vs `no_split` collapse, kit stage C 100/100 after rerank.

Each folder contains `tables.md`, `summary.json`, and per-dataset `*.json` (cache dirs are gitignored).
