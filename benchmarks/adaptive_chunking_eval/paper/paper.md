---
title: "Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG"
authors: "Adaptive Chunk Engine Contributors"
date: 2026-11-11
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

*Technical report · 2026-11-11*  
*Builds on Adaptive Chunking (LREC 2026; [arXiv:2603.25333](https://arxiv.org/abs/2603.25333); code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking))*

</div>

---

**Abstract**—Chunking quality strongly affects Retrieval-Augmented Generation (RAG). De Moura et al. (LREC 2026) show that selecting a splitter **per document** with five intrinsic metrics (RC, ICC, DCC, BI, SC) improves RAG on the CLAIR corpus. We present **Adaptive Chunk Engine (ACE)**, an enterprise control plane that productizes that principle with canonical schemas, audit/reproduction manifests, human-triggered optimization, and multi-sink indexing. We evaluate `adaptive_ace` under two protocols—(i) offline hashed embeddings + lexical RAG and (ii) live OpenRouter with `openai/text-embedding-3-small` + `openai/gpt-4o` LLM judge—on an ACE kit corpus and on three public sets: **CLAIR**, **FinanceBench**, and **Open RAG Bench**. Across offline and live intrinsic tables, `adaptive_ace` ranks first (or tied for first) and consistently avoids brittle `sentence_window`. On public OpenRouter smoke runs, adaptive RAG retrieval completeness reaches **91.67** (CLAIR), **92.5** (FinanceBench), and **88.0** (Open RAG Bench). On the short ACE-kit corpus, live RAG can favor larger-context fixed splitters over intrinsic argmax, motivating ACE’s human gate when RAG feedback disagrees with metric selection. Absolute scores are not cross-protocol comparable; we emphasize **rank-order** conclusions against published CLAIR Tables 3 and 5.

**Index Terms**—RAG, adaptive chunking, intrinsic evaluation, FinanceBench, Open RAG Bench, enterprise AI

---

## I. INTRODUCTION

**T**HIS report studies how to industrialize *Adaptive Chunking* [1], [2]: score multiple splitters with document-intrinsic metrics and pick the winner per document. Enterprise RAG additionally requires auditability, human veto of Auto recommendations, non-prose artifacts, and multi-destination indexing.

**Contributions.**

1. **Productized adaptive selection** via Strategy Registry + `adaptive_ace` intrinsic argmax.
2. **Dual-protocol evaluation kit** — offline hashed/lexical and live OpenRouter (`text-embedding-3-small` / `gpt-4o`).
3. **Public-benchmark suite** on CLAIR, FinanceBench (Patronus), and Open RAG Bench (Vectara), with published CLAIR baselines side-by-side.
4. **Governance** — CanonicalChunk contracts, ReproductionManifest, and human-triggered optimization when RAG feedback diverges from intrinsic selection.

## II. RELATED WORK

Adaptive Chunking [1], [2] introduces RC/ICC/DCC/BI/SC and evaluates on CLAIR (33 PDFs, ~1.18M tokens). FinanceBench [3] targets open-book financial QA over SEC filings. Open RAG Bench [4] builds multimodal PDF→RAG evaluation from arXiv. ACE complements these by treating strategy choice as a durable, reviewable decision artifact inside an enterprise control plane.

## III. METHODOLOGY

### A. Selection rule

For document $d$ and strategy set $\mathcal{S}$,
$$
s^\star(d)=\arg\max_{s\in\mathcal{S}} \mathrm{mean}\{\mathrm{RC},\mathrm{ICC},\mathrm{DCC},\mathrm{BI},\mathrm{SC}\}(s,d).
$$

### B. Metrics and RAG protocols

| Protocol | ICC/DCC embeddings | Retrieval | Judge |
|----------|--------------------|-----------|-------|
| Offline | Hashed char n-grams | Lexical top-$k$ | Term-coverage proxy |
| OpenRouter live | `text-embedding-3-small` | Dense cosine | `gpt-4o` JSON scores |

Candidate methods: `fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, and `adaptive_ace`.

### C. Corpora

| Corpus | Role | Smoke scale (this report) |
|--------|------|---------------------------|
| ACE kit | Controlled multi-domain markdown | 6 docs · ≈8.8k words · 43 Q |
| CLAIR | Align with [1], [2] | 6 stratified docs · 24 Q (live RAG: 12) |
| FinanceBench | Industry financial QA [3] | 8 docs · 12 Q (evidence-page text) |
| Open RAG Bench | PDF/arXiv RAG [4] | 10 docs · 40 Q (live RAG: 20) |

Full CLAIR (33 docs) and FinanceBench (150 Q) remain available via `ACE_BENCH_PROFILE=full`.

## IV. EXPERIMENTS

Reproduce:

```bash
make eval                          # ACE kit offline
make eval-openrouter               # ACE kit live
make download-public-benchmarks
make eval-public-smoke             # public offline
make eval-public-openrouter-smoke  # public live
```

Live defaults: `ACE_CHAT_MODEL=openai/gpt-4o`, `ACE_EMBED_MODEL=openai/text-embedding-3-small`.

## V. RESULTS

### A. ACE kit — offline intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 100.0 | 60.58 | 99.94 | 100.0 | 100.0 | **92.10** |
| recursive_text_1100 | 100.0 | 60.58 | 99.94 | 100.0 | 100.0 | **92.10** |
| recursive_text | 100.0 | 60.49 | 99.88 | 98.70 | 100.0 | 91.81 |
| fixed_token_512 | 100.0 | 59.81 | 99.89 | 97.66 | 100.0 | 91.47 |
| sentence_window | 58.33 | 61.50 | 95.09 | 21.35 | 60.69 | 59.39 |

Offline RAG-lite: `adaptive_ace` **100.0 / 100.0** (43/43); `sentence_window` 91.48 / 89.84.

### B. ACE kit — OpenRouter live

| Method | Intrinsic Mean | RAG RC | RAG AC | Answered |
|--------|---------------:|-------:|-------:|---------:|
| **adaptive_ace** | **88.48** | 64.17 | 64.58 | 26/43 |
| recursive_text_1100 | 88.44 | 82.92 | 83.33 | 35/43 |
| fixed_token_512 | 87.92 | 93.75 | 93.75 | 40/43 |
| no_split | 72.37 | **100.0** | **100.0** | 43/43 |
| sentence_window | 55.64 | 90.83 | 92.71 | 38/43 |

**Finding.** Neural intrinsic still ranks adaptive first and keeps sentence windows last. On this short kit, dense+LLM-judge RAG prefers larger context (`no_split`, `fixed_token_512`) over pure intrinsic argmax—ACE therefore keeps a human-triggered optimization gate.

### C. Published CLAIR baselines [2]

| Method | Intrinsic Mean | RAG RC | RAG AC |
|--------|---------------:|-------:|-------:|
| **Adaptive Chunking** | **91.07** | **67.7** | **78.0** |
| LangChain recursive | 88.62 | 58.1 | 70.1 |
| Page splitting | — | 59.1 | 73.3 |
| Sentence | 73.26 | — | — |

### D. Public benchmarks — offline smoke

| Dataset | adaptive_ace Mean | Best non-adaptive Mean | adaptive RAG RC |
|---------|------------------:|-----------------------:|----------------:|
| CLAIR (6) | **90.53** | 89.74 (`recursive_text`) | 99.68 |
| FinanceBench | **96.45** | 95.76 (`fixed_token_512`) | 99.71 |
| Open RAG Bench | **90.95** | 90.74 (`recursive_text_1100`) | 92.48 |

### E. Public benchmarks — OpenRouter smoke

| Dataset | adaptive_ace Mean | adaptive RAG RC / AC | Answered |
|---------|------------------:|---------------------:|---------:|
| CLAIR | **84.89** | **91.67 / 91.67** | 11/12 |
| FinanceBench | **94.76** | 92.5 / 86.25 | 10/12 |
| Open RAG Bench | **86.00** | **88.0 / 84.0** | 17/20 |

On public CLAIR and Open RAG Bench live RAG, adaptive leads (or ties the best recursive). FinanceBench live RAG slightly prefers `recursive_text_1100` (100.0 RC) over adaptive (92.5)—again a case for governed override rather than silent Auto lock-in. Live public smoke cost ≈ \$1.10 (OpenRouter reported).

### F. Cross-study interpretation

| Claim | Support in this report |
|-------|------------------------|
| Metric-guided adaptivity recovers strong splitters | Yes — adaptive tops/ties intrinsic on ACE kit + all three public sets (offline & live) |
| Brittle sentence fragmentation loses | Yes — `sentence_window` last or near-last on intrinsic means |
| Intrinsic argmax = RAG optimum always | **No** — ACE-kit live RAG and FinanceBench live RAG show residual gaps |
| Absolute RAG scores transferable across protocols | **No** — compare ranks only |

## VI. DISCUSSION

Enterprise value is not only picking $s^\star(d)$, but recording *why*, allowing humans to reject Auto when RAG gates fail, and reproducing the decision. FinanceBench evidence-page assemblies and Open RAG section corpora are smoke-scale; full profiles should be used before claiming production readiness on those domains.

## VII. CONCLUSION

ACE turns Adaptive Chunking into a governed product surface and validates it on an ACE kit plus CLAIR, FinanceBench, and Open RAG Bench under offline and OpenRouter protocols. Intrinsic evidence consistently favors `adaptive_ace` over brittle splitters; live RAG results show when human-triggered optimization must complement metric selection.

## REFERENCES

[1] P. R. de Moura Junior, J. Lelong, and A. Blangero, “Adaptive Chunking: Optimizing Chunking-Method Selection for RAG,” LREC 2026. https://arxiv.org/abs/2603.25333

[2] Ekimetrics, “adaptive-chunking.” https://github.com/ekimetrics/adaptive-chunking

[3] P. Islam et al., “FinanceBench: A New Benchmark for Financial Question Answering,” 2023. https://github.com/patronus-ai/financebench

[4] Vectara, “Open RAG Bench.” https://huggingface.co/datasets/vectara/open_ragbench

[5] Adaptive Chunk Engine Contributors, evaluation harness & results, `benchmarks/adaptive_chunking_eval/`, 2026.
