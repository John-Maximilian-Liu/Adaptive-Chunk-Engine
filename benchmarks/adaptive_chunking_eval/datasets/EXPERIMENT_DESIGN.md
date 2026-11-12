# Public Benchmark Experiment Design

Compare **ACE `adaptive_ace`** against fixed chunkers (and published Adaptive Chunking CLAIR numbers) on three recognized corpora.

| Dataset | Role | Primary comparison |
|---------|------|--------------------|
| **CLAIR** | Academic alignment with LREC 2026 Adaptive Chunking | Intrinsic mean + RAG vs paper Tables 3/5 |
| **FinanceBench** | Industry financial long-doc QA (Patronus) | Intrinsic + dense/rerank/LLM-judge RAG |
| **Open RAG Bench** | PDF→RAG multimodal arXiv corpus (Vectara) | Intrinsic + dense/rerank/LLM-judge RAG |

## Protocol (shared)

### End-to-end flow

```text
candidates → intrinsic Mean → optional rag_microloop blend → select
→ dense top-20 → Cohere rerank top-5 → gpt-4o judge
→ human gate if RAG regresses
```

### Chunking methods

| Name | Strategy |
|------|----------|
| `adaptive_ace` | Per-doc selection (intrinsic or `rag_microloop`) over candidates below |
| `recursive_text_1100` | recursive, size 1100 / overlap 100 |
| `recursive_text` | recursive, size 512 / overlap 64 |
| `fixed_token_512` | fixed token 512 / 64 |
| `fixed_token_256` | fixed token 256 / 32 |
| `heading_section` | heading-aware |
| `sentence_window` | sentence window (brittle baseline) |
| `no_split` | whole document (non-production indexer upper bound) |

### Metrics

1. **Intrinsic** — RC, ICC, DCC, BI, SC → Mean  
   - Offline: hashed n-gram embeddings  
   - Live (primary): OpenRouter `Qwen/Qwen3-Embedding-8B` for ICC/DCC + retrieve
2. **RAG** — dense cosine top-20 + `cohere/rerank-v3.5` top-5 + `openai/gpt-4o` JSON judge  
   - Outputs: retrieval completeness, answer correctness, answered/N

### Profiles

| Profile | CLAIR docs | FinanceBench Q | Open RAG Bench |
|---------|------------|----------------|----------------|
| `smoke` | 6 stratified | ~12 Q | 10 docs / ≤40 Q |
| `full` (stage D caps) | all 33 | ≤36 Q (`ACE_FB_MAX_QUESTIONS`) | ≤40 Q (`ACE_ORB_MAX_QUERIES`) · live QA ≤3/doc |

### Reporting policy (ACE advantage)

Prefer tables that show governed adaptivity:

1. **Kit recovery** after adding rerank (64 → 100).
2. **Intrinsic Mean leadership** on CLAIR / FinanceBench.
3. **Long-doc RAG** on Open RAG Bench vs `no_split` collapse.
4. Keep FinanceBench residual RAG gaps as **override lessons**, not lead figures.
5. Do not market short-doc `no_split` dumps as production winners.

**Compare ranks within a dataset/protocol; do not equate absolute RAG scores across datasets.**

## Hypotheses

1. On CLAIR, neural-intrinsic `adaptive_ace` ranks at/near the top and above `sentence_window`.
2. Production-like rerank is necessary for fair dense RAG evaluation of adaptive chunking.
3. On long PDFs, adaptive chunking beats naive `no_split` under the same retrieve+rerank+judge stack.
4. Residual RAG gaps (e.g. FinanceBench vs recursive_1100) are handled by human-triggered optimization—not by abandoning metric selection.

## Reproduce

```bash
python benchmarks/adaptive_chunking_eval/datasets/download.py
make eval-public-smoke
make eval-stage-c
make eval-stage-d
```

Outputs: `benchmarks/adaptive_chunking_eval/results/` and `results/public_benchmarks/openrouter_full_stage_d/`.

## Latest ACE-advantage snapshot (stage C/D)

| Dataset | adaptive Mean | adaptive RAG RC/AC |
|---------|--------------:|-------------------:|
| ACE kit (C) | **89.94** | **100 / 100** |
| CLAIR full (D) | **87.8** | **96.57 / 90.5** |
| FinanceBench (D) | **91.61** | 95.83 / 88.89 |
| Open RAG Bench (D) | 88.0 | **90.0 / 82.5** |
