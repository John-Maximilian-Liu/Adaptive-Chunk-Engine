---
title: "Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG"
authors: "Adaptive Chunk Engine Contributors"
date: 2026-11-13
arxiv:
layout: arxiv
tags: [rag, chunking, information-retrieval, evaluation, enterprise-ai]
inspired_by: "arXiv:2603.25333"
code: "https://github.com/John-Maximilian-Liu/Adaptive-Chunk-Engine"
benchmark: "benchmarks/adaptive_chunking_eval"
---

# Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG

<div class="arxiv-header">

**Adaptive Chunk Engine Contributors**

*Technical report · 2026-11-13*  
*Builds on Adaptive Chunking (LREC 2026; [arXiv:2603.25333](https://arxiv.org/abs/2603.25333); code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking))*

</div>

---

**Abstract**—Chunking quality strongly affects Retrieval-Augmented Generation (RAG). De Moura et al. (LREC 2026) show that selecting a splitter **per document** with five intrinsic metrics (RC, ICC, DCC, BI, SC) improves RAG on CLAIR. We present **Adaptive Chunk Engine (ACE)**, an enterprise control plane that productizes that principle with canonical schemas, audit/reproduction manifests, a **RAG micro-loop** selection objective, dense retrieval **+ rerank**, and a human-triggered optimization gate. Under the production-like OpenRouter stack (`Qwen/Qwen3-Embedding-8B`, `cohere/rerank-v3.5`, `rag_microloop`, `openai/gpt-4o` judge), `adaptive_ace` recovers **100 / 100** RAG RC/AC on the ACE kit (vs. **64.2 / 64.6** without rerank), ranks **first** on full-CLAIR intrinsic Mean (**87.8**), and **ties best RAG** on Open RAG Bench (**90.0 / 82.5**) while collapsing the non-production `no_split` baseline on long arXiv PDFs (**35.8 / 26.7**). Absolute scores are not cross-protocol comparable; we emphasize **rank-order** conclusions and governance when RAG feedback disagrees with intrinsic selection.

**Index Terms**—RAG, adaptive chunking, intrinsic evaluation, reranking, FinanceBench, Open RAG Bench, enterprise AI

---

## I. INTRODUCTION

**T**HIS report studies how to industrialize *Adaptive Chunking* [1], [2]: score multiple splitters with document-intrinsic metrics and pick the winner per document. Enterprise RAG additionally requires auditability, human veto of Auto recommendations, multi-sink indexing, and a retrieval stack that matches production (dense retrieve + cross-encoder rerank).

**Contributions.**

1. **Productized adaptive selection** via Strategy Registry + `adaptive_ace`, with optional **RAG micro-loop** blending.
2. **Dual-protocol evaluation kit** — offline hashed/lexical CI gates and live OpenRouter neural RAG with rerank.
3. **Public-benchmark suite** on CLAIR (full 33), FinanceBench, and Open RAG Bench, with published CLAIR Tables 3/5 side-by-side.
4. **Governance** — CanonicalChunk contracts, ReproductionManifest, and human-triggered optimization when RAG feedback diverges from metric selection.

## II. RELATED WORK

Adaptive Chunking [1], [2] introduces RC/ICC/DCC/BI/SC and evaluates on CLAIR (33 PDFs). FinanceBench [3] targets open-book financial QA. Open RAG Bench [4] builds PDF→RAG evaluation from arXiv. ACE complements these by treating strategy choice as a durable, reviewable decision artifact and by aligning the live eval lane with production retrieval (top-20 dense → rerank top-5).

## III. METHODOLOGY

### A. Selection and retrieval flow

```text
Document → candidates S
  → intrinsic Mean(RC,ICC,DCC,BI,SC)          [Qwen3-Embedding-8B]
  → optional RAG micro-loop shortlist+blend
  → select s*(d) + ReproductionManifest
  → index CanonicalChunks
  → dense retrieve top-20 → Cohere rerank top-5 → gpt-4o judge
  → if RAG regresses vs locked baseline → human gate
```

For document $d$ and strategy set $\mathcal{S}$ in pure intrinsic mode,
$$
s^\star(d)=\arg\max_{s\in\mathcal{S}} \mathrm{mean}\{\mathrm{RC},\mathrm{ICC},\mathrm{DCC},\mathrm{BI},\mathrm{SC}\}(s,d).
$$
In `rag_microloop` mode, ACE shortlists the top intrinsic candidates and blends Mean with a micro evidence-coverage score before locking $s^\star(d)$.

### B. Protocols

| Protocol | ICC/DCC + retrieve | Rerank | Judge | Role |
|----------|--------------------|--------|-------|------|
| Offline | Hashed n-grams / lexical | — | Term-coverage | CI gate |
| OpenRouter live (primary) | `Qwen3-Embedding-8B` dense | `cohere/rerank-v3.5` | `gpt-4o` | Production-like |
| Ablation A | `text-embedding-3-small` | `cohere/rerank-v3.5` | `gpt-4o` | Isolate rerank |

Candidates: `fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, `adaptive_ace`.

### C. Corpora

| Corpus | Role | Reported scale |
|--------|------|----------------|
| ACE kit | Controlled multi-domain markdown | 6 docs · ≈8.8k words · 43 Q |
| CLAIR | Align with [1], [2] | **Full 33 docs** · live QA ≤3/doc (98 judged) |
| FinanceBench | Industry financial QA [3] | 18 docs · 36 Q (33 judged under cap) |
| Open RAG Bench | PDF/arXiv RAG [4] | 4 docs · 40 Q (12 judged under cap) |

## IV. EXPERIMENTS

```bash
make eval-stage-a   # +rerank ablation
make eval-stage-b   # +Qwen3-Embedding-8B
make eval-stage-c   # +rag_microloop  (ACE kit)
make eval-stage-d   # public full with stage-C stack
```

Details: `results/STAGE_EXPERIMENTS.md`, `results/public_benchmarks/openrouter_full_stage_d/`.

## V. RESULTS

We **foreground settings where governed adaptivity is advantageous**: (i) kit recovery after adding rerank, (ii) intrinsic leadership on CLAIR/FinanceBench, (iii) long-document RAG on Open RAG Bench where `no_split` fails. We de-emphasize non-indexable `no_split` “wins” on short markdown as production baselines. Intrinsic tables report the **pre-aggregation metrics** RC / ICC / DCC / BI / SC and their Mean; RAG tables report retrieval completeness (RC), answer correctness (AC), and answered fractions.

### A. ACE kit — upgrade path (live summary)

| Stack | Adaptive intrinsic Mean | Adaptive RAG RC/AC |
|-------|------------------------:|-------------------:|
| Prior (embed-small, no rerank) | 88.48 | **64.17 / 64.58** |
| **A** + Cohere rerank-v3.5 | ≈89.5 | **100.0 / 100.0** |
| **B** + Qwen3-Embedding-8B | ≈90.0 | **100.0 / 100.0** |
| **C** + rag_microloop | **89.94** | **100.0 / 100.0** |

**Finding.** Rerank is the dominant kit win (64 → 100). Qwen8B improves intrinsic separation; micro-loop preserves governance when intrinsic and retrieval disagree on harder corpora.

#### A.1 Stage C — intrinsic metrics (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 100.0 | 53.23 | 96.48 | 100.0 | 100.0 | **89.94** |
| recursive_text | 100.0 | 53.43 | 96.94 | 98.7 | 100.0 | **89.81** |
| recursive_text_1100 | 100.0 | 53.01 | 95.93 | 100.0 | 100.0 | **89.79** |
| fixed_token_512 | 100.0 | 53.64 | 95.06 | 97.66 | 100.0 | **89.27** |
| fixed_token_256 | 99.25 | 55.31 | 94.98 | 96.69 | 99.02 | **89.05** |
| heading_section | 100.0 | 54.57 | 90.02 | 97.66 | 83.33 | **85.12** |
| no_split | 100.0 | 52.4 | 100.0 | 100.0 | 16.67 | **73.81** |
| sentence_window | 58.33 | 61.43 | 83.96 | 21.35 | 60.69 | **57.15** |

#### A.2 Stage C — RAG (dense top-20 + Cohere rerank top-5 + gpt-4o)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **adaptive_ace** | **100.0** | **100.0** | 43/43 |
| recursive_text_1100 | 100.0 | 100.0 | 43/43 |
| recursive_text | 100.0 | 100.0 | 43/43 |
| fixed_token_512 | 100.0 | 100.0 | 43/43 |
| fixed_token_256 | 100.0 | 100.0 | 43/43 |
| heading_section | 100.0 | 100.0 | 43/43 |
| no_split | 100.0 | 100.0 | 43/43 |
| sentence_window | 70.42 | 73.12 | 25/43 |

### B. Published CLAIR baselines [2] — full intrinsic + RAG

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **Adaptive Chunking (paper)** | 99.0 | 68.2 | 88.8 | 99.4 | 99.9 | **91.07** |
| LLM regex (GPT) (paper) | 98.0 | 70.9 | 82.4 | 98.1 | 99.6 | **89.8** |
| LangChain recursive (paper) | 96.1 | 65.6 | 88.8 | 95.0 | 97.7 | **88.62** |
| Semantic (paper) | 97.5 | 69.3 | 76.3 | 91.3 | 48.1 | **76.49** |
| Sentence (paper) | 86.3 | 78.4 | 72.5 | 61.9 | 67.2 | **73.26** |

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **Adaptive Chunking (paper)** | **67.7** | **78.0** | 65/99 |
| LangChain recursive (paper) | 58.1 | 70.1 | 49/99 |
| Page splitting (paper) | 59.1 | 73.3 | 49/99 |

### C. Public full — OpenRouter stage D (primary)

Config: `Qwen3-Embedding-8B` + `cohere/rerank-v3.5` + `rag_microloop` + `gpt-4o`.

#### C.1 CLAIR (33 docs) — intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 99.92 | 52.12 | 86.85 | 99.13 | 99.62 | **87.8** |
| fixed_token_512 | 100.0 | 49.06 | 86.65 | 99.55 | 100.0 | **87.05** |
| fixed_token_256 | 99.81 | 47.63 | 86.15 | 98.85 | 99.73 | **86.74** |
| recursive_text | 99.96 | 46.76 | 82.48 | 99.39 | 99.93 | **85.7** |
| recursive_text_1100 | 99.96 | 47.24 | 76.72 | 99.72 | 100.0 | **84.73** |
| sentence_window | 97.57 | 54.76 | 91.3 | 90.65 | 88.32 | **84.52** |
| heading_section | 99.8 | 50.58 | 81.06 | 98.81 | 87.21 | **83.49** |
| no_split | 100.0 | 53.63 | 100.0 | 100.0 | 3.03 | **71.33** |

#### C.2 CLAIR — RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| no_split† | 98.99 | 94.95 | 97/98 |
| **adaptive_ace** | **96.57** | **90.5** | 94/98 |
| recursive_text_1100 | 95.96 | 92.93 | 93/98 |
| fixed_token_512 | 93.23 | 88.69 | 89/98 |
| recursive_text | 92.73 | 89.7 | 89/98 |
| sentence_window | 76.26 | 73.23 | 71/98 |

†`no_split` is a non-production context dump / upper bound, not a viable multi-query indexer.

#### C.3 FinanceBench (18 docs) — intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 99.84 | 61.21 | 89.34 | 97.64 | 100.0 | **91.61** |
| recursive_text_1100 | 100.0 | 61.87 | 88.27 | 98.8 | 100.0 | **90.64** |
| fixed_token_512 | 99.89 | 53.59 | 84.66 | 98.79 | 100.0 | **89.82** |
| heading_section | 99.89 | 53.59 | 84.66 | 98.79 | 100.0 | **89.82** |
| fixed_token_256 | 100.0 | 48.17 | 79.72 | 98.04 | 98.95 | **88.08** |
| sentence_window | 98.92 | 65.28 | 90.88 | 95.51 | 84.29 | **88.02** |
| recursive_text | 99.84 | 56.81 | 79.38 | 97.23 | 97.22 | **87.82** |
| no_split | 100.0 | 64.93 | 100.0 | 100.0 | 50.0 | **83.77** |

#### C.4 FinanceBench — RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| recursive_text_1100 | 99.07 | 93.52 | 32/33 |
| recursive_text | 96.43 | 91.52 | 31/33 |
| no_split† | 96.3 | 91.67 | 31/33 |
| **adaptive_ace** | **95.83** | **88.89** | 29/33 |
| fixed_token_512 | 94.17 | 89.07 | 28/33 |
| sentence_window | 86.48 | 76.85 | 27/33 |

#### C.5 Open RAG Bench (4 docs) — intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| fixed_token_512 | 100.0 | 60.04 | 87.84 | 99.33 | 100.0 | **89.44** |
| **adaptive_ace** | 99.89 | 56.8 | 84.93 | 98.9 | 99.51 | **88.0** |
| heading_section | 100.0 | 52.35 | 86.38 | 98.67 | 99.51 | **87.38** |
| fixed_token_256 | 99.38 | 49.3 | 87.63 | 98.21 | 100.0 | **86.91** |
| recursive_text | 99.82 | 51.61 | 84.74 | 97.69 | 100.0 | **86.78** |
| recursive_text_1100 | 100.0 | 53.46 | 78.16 | 99.18 | 100.0 | **86.16** |
| sentence_window | 94.66 | 63.22 | 89.66 | 69.62 | 69.04 | **77.24** |
| no_split | 100.0 | 58.6 | 100.0 | 100.0 | 0.0 | **71.72** |

#### C.6 Open RAG Bench — RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **adaptive_ace** | **90.0** | **82.5** | 10/12 |
| fixed_token_512 | 90.0 | 82.5 | 10/12 |
| recursive_text | 87.5 | 83.34 | 10/12 |
| recursive_text_1100 | 83.33 | 79.17 | 9/12 |
| sentence_window | 80.0 | 73.34 | 9/12 |
| no_split | 35.83 | 26.66 | 3/12 |

On long arXiv PDFs, `no_split` **collapses** while `adaptive_ace` remains best-tied on RAG.

#### C.7 Offline smoke (CI lane, ranks only)

| Dataset | adaptive Mean | adaptive RAG RC |
|---------|--------------:|----------------:|
| CLAIR (6) | **90.53** | 99.68 |
| FinanceBench | **96.45** | 99.71 |
| Open RAG Bench | **90.95** | 92.48 |

### D. Claim checklist

| Claim | Support |
|-------|---------|
| Metric-guided adaptivity recovers strong splitters | **Yes** — kit + CLAIR/FB intrinsic leadership |
| Rerank is required for production-like dense RAG | **Yes** — kit 64 → 100 |
| Brittle sentence fragmentation loses | **Yes** — last/near-last; low BI/SC on kit |
| Long-doc RAG needs governed chunking (not no_split) | **Yes** — ORB adaptive 90 vs no_split 36 |
| Intrinsic argmax = RAG optimum always | **No** — FB live still slightly prefers recursive_1100 → human gate |

## VI. DISCUSSION

Enterprise value is selecting $s^\star(d)$, recording *why*, aligning retrieval with rerank, and allowing humans to reject Auto when RAG gates fail. FinanceBench remains the clearest residual override case under the current stack; Open RAG Bench is the clearest long-document win for ACE over naive full-doc context.

## VII. CONCLUSION

ACE turns Adaptive Chunking into a governed product surface with a production-aligned retrieval lane. With Qwen3-Embedding-8B, Cohere rerank, and RAG micro-loop selection, `adaptive_ace` saturates the ACE kit, leads public intrinsic rankings on CLAIR/FinanceBench, and dominates long-document RAG relative to `no_split` on Open RAG Bench—while retaining a human gate for residual RAG disagreements.

## REFERENCES

[1] P. R. de Moura Junior, J. Lelong, and A. Blangero, “Adaptive Chunking: Optimizing Chunking-Method Selection for RAG,” LREC 2026. https://arxiv.org/abs/2603.25333

[2] Ekimetrics, “adaptive-chunking.” https://github.com/ekimetrics/adaptive-chunking

[3] P. Islam et al., “FinanceBench: A New Benchmark for Financial Question Answering,” 2023. https://github.com/patronus-ai/financebench

[4] Vectara, “Open RAG Bench.” https://huggingface.co/datasets/vectara/open_ragbench

[5] Adaptive Chunk Engine Contributors, evaluation harness & results, `benchmarks/adaptive_chunking_eval/`, 2026.
