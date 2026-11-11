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
  results/openrouter/       # live ACE kit
  results/public_benchmarks/
  paper/paper.md + paper.html
```

## Run

```bash
make eval                          # ACE kit offline
make eval-openrouter               # ACE kit live (OPENROUTER_API_KEY)
make download-public-benchmarks
make eval-public-smoke             # public offline smoke
make eval-public-openrouter-smoke  # public live smoke
```

Defaults for live: `ACE_CHAT_MODEL=openai/gpt-4o`, `ACE_EMBED_MODEL=openai/text-embedding-3-small`.

## Latest results (adaptive_ace)

| Study | Intrinsic Mean | RAG RC | Protocol |
|-------|---------------:|-------:|----------|
| Adaptive Chunking CLAIR (paper) | **91.07** | **67.7** | published |
| ACE kit offline | **92.10** | **100.0** | hashed / lexical |
| ACE kit OpenRouter | **88.48** | 64.17 | neural + gpt-4o |
| Public CLAIR smoke offline | **90.53** | 99.68 | hashed / lexical |
| Public CLAIR smoke live | **84.89** | **91.67** | neural + gpt-4o |
| FinanceBench smoke offline | **96.45** | 99.71 | hashed / lexical |
| FinanceBench smoke live | **94.76** | 92.5 | neural + gpt-4o |
| Open RAG Bench smoke offline | **90.95** | 92.48 | hashed / lexical |
| Open RAG Bench smoke live | **86.00** | **88.0** | neural + gpt-4o |

Full tables: [`results/tables.md`](results/tables.md), [`results/openrouter/tables.md`](results/openrouter/tables.md), [`results/public_benchmarks/`](results/public_benchmarks/).

**Takeaway:** intrinsic selection recovers strong splitters and avoids brittle sentence windows across kits. Live RAG on short ACE-kit docs can favor larger-context fixed splitters; public CLAIR / Open RAG live RAG favor adaptive. Compare ranks, not absolute scores across protocols.

## Paper

- Markdown: [`paper/paper.md`](paper/paper.md)
- HTML: [`paper/paper.html`](paper/paper.html)
- Experiment design: [`datasets/EXPERIMENT_DESIGN.md`](datasets/EXPERIMENT_DESIGN.md)
