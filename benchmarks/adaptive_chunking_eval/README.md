# ACE Adaptive Chunking Evaluation Kit

Self-contained benchmark + paper for **Adaptive Chunk Engine**, aligned with:

- Paper: [*Adaptive Chunking: Optimizing Chunking-Method Selection for RAG*](https://arxiv.org/abs/2603.25333) (LREC 2026)
- Code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking)
- Public corpora: CLAIR · [FinanceBench](https://github.com/patronus-ai/financebench) · [Open RAG Bench](https://huggingface.co/datasets/vectara/open_ragbench)

## Layout

```text
benchmarks/adaptive_chunking_eval/
  run_eval.py / run_eval_openrouter.py / run_public_benchmarks.py
  datasets/EXPERIMENT_DESIGN.md
  datasets/download.py + loaders/
  data/                     # CLAIR / FinanceBench / Open RAG Bench
  corpus/                   # ACE kit documents
  results/                  # offline ACE kit
  results/openrouter_stage_*  # A/B/C live kit upgrades
  results/public_benchmarks/openrouter_full_stage_d/
  paper/paper.md + paper.html
  paper/coling2027_industry/
```

## Run

```bash
make eval                          # ACE kit offline
make eval-stage-a                  # + Cohere rerank
make eval-stage-b                  # + Qwen3-Embedding-8B
make eval-stage-c                  # + rag_microloop (primary kit stack)
make eval-stage-d                  # public full with stage-C stack
make download-public-benchmarks
make eval-public-smoke             # public offline smoke
```

Primary live defaults (C/D): `ACE_CHAT_MODEL=openai/gpt-4o`, `ACE_EMBED_MODEL=Qwen/Qwen3-Embedding-8B`, `ACE_RERANK_MODEL=cohere/rerank-v3.5`, `ACE_ADAPTIVE_MODE=rag_microloop`.

## Latest results — ACE-advantage view (`adaptive_ace`)

| Study | Intrinsic Mean | RAG RC/AC | Protocol / note |
|-------|---------------:|----------:|-----------------|
| Adaptive Chunking CLAIR (paper) | **91.07** | **67.7 / 78.0** | published anchor |
| ACE kit offline | **92.10** | **100 / 100** | hashed / lexical |
| ACE kit live **prior** (no rerank) | 88.48 | 64.2 / 64.6 | dense only |
| ACE kit live **stage C** | **89.94** | **100 / 100** | Qwen8B + rerank + micro-loop |
| CLAIR full 33 (stage D) | **87.8** (1st) | **96.6 / 90.5** | vs sentence_window 76/73 |
| FinanceBench (stage D) | **91.61** (1st) | 95.8 / 88.9 | intrinsic lead |
| Open RAG Bench (stage D) | 88.0 | **90.0 / 82.5** (tied 1st) | vs no_split **36 / 27** |

Full tables: [`results/STAGE_EXPERIMENTS.md`](results/STAGE_EXPERIMENTS.md), [`results/public_benchmarks/openrouter_full_stage_d/`](results/public_benchmarks/openrouter_full_stage_d/).

**Takeaway:** production-like rerank is required for fair dense RAG; governed adaptivity leads intrinsic rankings on CLAIR/FinanceBench and wins long-document RAG vs naive `no_split`. Compare ranks, not absolute scores across protocols.

## Paper

- Technical report: [`paper/paper.md`](paper/paper.md) · [`paper/paper.html`](paper/paper.html)
- **COLING 2027 Industry Track standalone draft:** [`paper/coling2027_industry/`](paper/coling2027_industry/)
- Experiment design: [`datasets/EXPERIMENT_DESIGN.md`](datasets/EXPERIMENT_DESIGN.md)
- Flow diagram: [`../../docs/architecture/ace-selection-rag-flow.svg`](../../docs/architecture/ace-selection-rag-flow.svg)
