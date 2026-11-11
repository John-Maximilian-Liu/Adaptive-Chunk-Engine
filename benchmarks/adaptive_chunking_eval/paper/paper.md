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

**Abstract**—The effectiveness of Retrieval-Augmented Generation (RAG) depends critically on how documents are segmented for indexing. De Moura et al. (LREC 2026) introduce *Adaptive Chunking*, which selects the best splitter per document using five intrinsic metrics—References Completeness (RC), Intrachunk Cohesion (ICC), Document Contextual Coherence (DCC), Block Integrity (BI), and Size Compliance (SC)—and report strong gains on the CLAIR corpus. We present **Adaptive Chunk Engine (ACE)**, an enterprise control plane that operationalizes the same selection principle behind canonical schemas, audit/reproduction manifests, human-triggered optimization, Excel-native strategies, and multi-sink indexing. On a multi-domain ACE corpus (6 documents, ≈8.8k words), offline hashed-embedding `adaptive_ace` matches the strongest fixed recursive baseline (**intrinsic mean 92.10%**). A live OpenRouter replicate with **`openai/text-embedding-3-small`** ICC/DCC and **`openai/gpt-4o`** LLM-judge RAG yields adaptive intrinsic mean **88.48%** (still above brittle `sentence_window` at **55.64%**) while showing that larger-context fixed splitters can outrank intrinsic argmax under dense retrieval on short documents—motivating ACE’s human-triggered optimization when RAG feedback disagrees with metric selection. We juxtapose both protocols with published CLAIR tables (intrinsic mean **91.07%**; RAG completeness **67.7**).

**Index Terms**—RAG, adaptive chunking, intrinsic evaluation, enterprise AI systems, information retrieval

---

## I. INTRODUCTION

**T**HIS paper studies how to turn research-grade *Adaptive Chunking* into a production-ready enterprise system. Prior work shows that one-size-fits-all splitters underperform when documents vary in structure and discourse [1]. The Adaptive Chunking framework scores multiple methods with intrinsic, document-based metrics and selects the winner per document, improving downstream RAG without changing the generator [1], [2].

Enterprise RAG adds constraints that research libraries alone do not solve: auditable decisions, human veto over Auto recommendations, non-prose artifacts (spreadsheets, visuals), and multi-destination indexing with partial-failure isolation. **ACE** embeds metric-guided selection inside such a control plane.

**Contributions.**

1. **Productized adaptive selection.** A Strategy Registry + per-document intrinsic argmax (`adaptive_ace`) aligned with [1].
2. **Offline reproducible benchmark kit.** Self-contained harness under `benchmarks/adaptive_chunking_eval/` with corpus, metrics, tables, and this paper.
3. **Head-to-head comparison framing.** ACE offline + OpenRouter live results vs. published Adaptive Chunking CLAIR results [2], with explicit protocol caveats.
4. **Governance layer.** CanonicalChunk contracts, audit/reproduction manifests, and human-triggered optimization gates (especially when RAG feedback diverges from intrinsic argmax).

Section II reviews related work; Section III presents methodology; Section IV describes experiments; Section V reports results and comparison; Section VI discusses implications; Section VII concludes.

## II. RELATED WORK

### A. Adaptive Chunking (LREC 2026)

De Moura Junior, Lelong, and Blangero introduce five intrinsic metrics and an adaptive selector evaluated on 33 CLAIR documents (~1.18M tokens) across legal, technical, and social-science domains [1]. Their official implementation provides recursive splitters, metric computation, and a RAG evaluation pipeline [2].

### B. Enterprise RAG platforms

Industrial systems require tenant isolation, secret hygiene, configuration precedence, and evidence trails. ACE complements Adaptive Chunking by treating strategy choice as a durable, reviewable decision artifact rather than a one-off script.

### C. Comparison with Prior Art

| System | Year | Adaptive selection | Intrinsic metrics | Enterprise governance | Multi-sink indexing |
|--------|------|--------------------|-------------------|-----------------------|---------------------|
| Adaptive Chunking [1], [2] | 2026 | Yes | RC/ICC/DCC/BI/SC | Research library | Research RAG pipeline |
| LangChain recursive [2] | — | No | Evaluated as baseline | N/A | N/A |
| **ACE (this work)** | 2026 | Yes (`adaptive_ace`) | Same five (+ product RAG metrics) | Audit, locks, human gates | Qdrant / Azure AI Search / Dify |

## III. METHODOLOGY

### A. Problem Formulation

Let $\mathcal{S}$ be a set of chunking strategies and $d$ a document. For each $s\in\mathcal{S}$ we compute intrinsic scores
$$
m(s,d)=\mathrm{mean}\big\{\mathrm{RC},\mathrm{ICC},\mathrm{DCC},\mathrm{BI},\mathrm{SC}\big\}
$$
and select
$$
s^\star(d)=\arg\max_{s\in\mathcal{S}} m(s,d).
$$
This mirrors Adaptive Chunking’s per-document selection [1].

### B. Intrinsic Metrics

| Metric | Definition (ACE offline implementation) |
|--------|-----------------------------------------|
| SC | Fraction of chunks with tokens in $[t_{\min}, t_{\max}]$ |
| ICC | Mean cosine similarity of sentence blocks to the chunk embedding |
| DCC | Mean similarity of each chunk embedding to a local window embedding |
| BI | Fraction of paragraph/section blocks not cut by predicted splits |
| RC | Filtered pronoun–antecedent pairs kept inside the same chunk |

For CI-safe runs, ICC/DCC use **deterministic hashed character n-gram embeddings**. Neural encoders can be plugged in via `embed_fn`; the live kit uses OpenRouter `openai/text-embedding-3-small`.

### C. ACE Control-Plane Extensions

Beyond selection, ACE records effective configuration sources (Auto vs Manual locks), emits `CHUNK_RUN_COMPLETED` outbox events for indexing, and never auto-executes optimization rounds—humans must accept patches and create the next experiment.

### D. RAG Protocols

**Offline RAG-lite.** Queries reference section indices and topic keywords without copying full evidence sentences. Retrieval is lexical top-$k$ with key-term bonuses. Completeness/correctness are term-coverage proxies (no LLM judge).

**OpenRouter live RAG.** The same queries use dense cosine retrieval over `text-embedding-3-small` chunk vectors. `openai/gpt-4o` returns a JSON judgment with `retrieval_completeness`, `answer_correctness`, and `answered` flags given question, gold answer, evidence quote, and retrieved context.

## IV. EXPERIMENTS

### A. Datasets

**ACE corpus.** 6 documents in technical / legal / sustainability domains (≈8.8k words), stored in `benchmarks/adaptive_chunking_eval/corpus/`.

**CLAIR (paper).** 33 documents, ~1.18M tokens, used by [1], [2] (not redistributed here).

### B. Candidate Methods (ACE)

`fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, and `adaptive_ace`.

### C. Published Baselines (paper)

Adaptive Chunking, LLM-regex (GPT), LangChain recursive, Semantic, Sentence (intrinsic); Adaptive Chunking, LangChain recursive, Page splitting (RAG) [2].

### D. Reproducibility

```bash
# Offline
make eval
# Live OpenRouter (OPENROUTER_API_KEY; defaults gpt-4o + text-embedding-3-small)
make eval-openrouter
```

## V. RESULTS

### A. ACE Offline Intrinsic Metrics (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 100.0 | 60.58 | 99.94 | 100.0 | 100.0 | **92.10** |
| recursive_text_1100 | 100.0 | 60.58 | 99.94 | 100.0 | 100.0 | **92.10** |
| recursive_text | 100.0 | 60.49 | 99.88 | 98.70 | 100.0 | 91.81 |
| fixed_token_512 | 100.0 | 59.81 | 99.89 | 97.66 | 100.0 | 91.47 |
| fixed_token_256 | 99.25 | 58.91 | 99.48 | 96.69 | 99.02 | 90.67 |
| heading_section | 100.0 | 59.45 | 94.07 | 97.66 | 83.33 | 86.90 |
| no_split | 100.0 | 60.62 | 100.0 | 100.0 | 16.67 | 75.46 |
| sentence_window | 58.33 | 61.50 | 95.09 | 21.35 | 60.69 | 59.39 |

### B. Published Adaptive Chunking Intrinsic Metrics (CLAIR / Table 3) [2]

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **Adaptive Chunking** | 99.0 | 68.2 | 88.8 | 99.4 | 99.9 | **91.07** |
| LLM regex (GPT) | 98.0 | 70.9 | 82.4 | 98.1 | 99.6 | 89.80 |
| LangChain recursive | 96.1 | 65.6 | 88.8 | 95.0 | 97.7 | 88.62 |
| Semantic | 97.5 | 69.3 | 76.3 | 91.3 | 48.1 | 76.49 |
| Sentence | 86.3 | 78.4 | 72.5 | 61.9 | 67.2 | 73.26 |

### C. ACE Offline RAG-lite

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **adaptive_ace** | **100.0** | **100.0** | 43/43 |
| recursive_text_1100 | 100.0 | 100.0 | 43/43 |
| recursive_text | 100.0 | 100.0 | 43/43 |
| fixed_token_512 | 100.0 | 100.0 | 43/43 |
| heading_section | 100.0 | 100.0 | 43/43 |
| no_split | 100.0 | 100.0 | 43/43 |
| fixed_token_256 | 99.89 | 99.87 | 43/43 |
| sentence_window | 91.48 | 89.84 | 43/43 |

### D. Published Adaptive Chunking RAG (CLAIR / Table 5) [2]

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **Adaptive Chunking** | **67.7** | **78.0** | 65/99 |
| LangChain recursive | 58.1 | 70.1 | 49/99 |
| Page splitting | 59.1 | 73.3 | 49/99 |

### E. ACE OpenRouter Intrinsic Metrics (%) — `text-embedding-3-small`

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 100.0 | 48.04 | 94.38 | 100.0 | 100.0 | **88.48** |
| recursive_text_1100 | 100.0 | 47.78 | 94.42 | 100.0 | 100.0 | 88.44 |
| recursive_text | 100.0 | 48.09 | 94.94 | 98.70 | 100.0 | 88.35 |
| fixed_token_512 | 100.0 | 49.23 | 92.73 | 97.66 | 100.0 | 87.92 |
| fixed_token_256 | 99.25 | 48.75 | 91.52 | 96.69 | 99.02 | 87.05 |
| heading_section | 100.0 | 49.41 | 87.66 | 97.66 | 83.33 | 83.61 |
| no_split | 100.0 | 45.19 | 100.0 | 100.0 | 16.67 | 72.37 |
| sentence_window | 58.33 | 56.26 | 81.58 | 21.35 | 60.69 | 55.64 |

Per-document selections: `recursive_text_1100` on technical/legal/sustainability long docs; `recursive_text` on ops/finance/sample.

### F. ACE OpenRouter RAG — dense retrieval + `gpt-4o` judge

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| no_split | **100.0** | **100.0** | 43/43 |
| fixed_token_512 | 93.75 | 93.75 | 40/43 |
| heading_section | 93.75 | 93.75 | 40/43 |
| sentence_window | 90.83 | 92.71 | 38/43 |
| recursive_text_1100 | 82.92 | 83.33 | 35/43 |
| fixed_token_256 | 71.46 | 71.88 | 28/43 |
| **adaptive_ace** | 64.17 | 64.58 | 26/43 |
| recursive_text | 54.17 | 54.17 | 21/43 |

Approx. API usage for the published live run: ~1.7k embedding calls, 344 chat calls, ≈0.79M tokens, ≈\$1.31 (OpenRouter reported cost).

### G. Cross-Protocol Comparison (Interpretation)

| Aspect | Adaptive Chunking (paper) | ACE offline | ACE OpenRouter |
|--------|---------------------------|-------------|----------------|
| Corpus | CLAIR 33 docs / ~1.18M tokens | 6 docs / ≈8.8k words | same ACE corpus |
| Embeddings | Neural (Jina / ST) | Hashed n-grams | `text-embedding-3-small` |
| RAG judge | Hybrid retrieval + LLM | Lexical coverage proxy | Dense + `gpt-4o` JSON judge |
| Adaptive mean | **91.07** | **92.10** | **88.48** |
| Weak splitter | Sentence 73.26 | sentence_window 59.39 | sentence_window 55.64 |
| Adaptive RAG RC | **67.7** | 100.0 (proxy) | 64.17 |

**Finding.** Intrinsic rank-order is stable: adaptivity recovers strong recursive splitters and avoids brittle sentence windows under both hashed and OpenAI embeddings. Live LLM-judge RAG on short documents, however, favors larger-context fixed strategies (`no_split`, `fixed_token_512`) over pure intrinsic argmax—especially when selection falls back to `recursive_text` on half the corpus. Absolute RAG scores must not be compared head-to-head across protocols.

## VI. DISCUSSION

### A. Why governance matters

Selection without evidence trails cannot ship in regulated environments. ACE stores effective parameters, locks, and audit events so $s^\star(d)$ is reconstructible. The OpenRouter RAG/intrinsic disagreement is precisely the case for **human-triggered optimization**: accept an intrinsic proposal only when downstream eval gates improve.

### B. Limitations

- ACE corpus ≪ CLAIR; short documents inflate `no_split` RAG.  
- RC heuristic ≠ full coreference resolution.  
- LLM-judge variance and prompt sensitivity remain.  
- Live cost/latency preclude default CI execution.

### C. Future work

Scale ACE eval to CLAIR-sized corpora; jointly optimize intrinsic + RAG objectives; attach ACE’s full evaluation engine (hard gates, failure taxonomy) to the same adaptive selector.

## VII. CONCLUSION

Adaptive Chunking [1] establishes that per-document metric-guided selection improves RAG. ACE shows how to **industrialize** that insight: the same selection idea, plus enterprise contracts, human gates, and multi-sink indexing. Offline and OpenRouter live kits under `benchmarks/adaptive_chunking_eval/` reproduce the qualitative intrinsic ranking effects of the LREC study, quantify protocol gaps against published CLAIR tables [2], and surface when RAG feedback should override intrinsic argmax.

## ACKNOWLEDGMENT

We thank the authors of Adaptive Chunking for releasing metrics, code, and CLAIR evaluation artifacts that make comparative enterprise studies possible [1], [2].

## REFERENCES

[1] P. R. de Moura Junior, J. Lelong, and A. Blangero, “Adaptive Chunking: Optimizing Chunking-Method Selection for RAG,” in *Proc. LREC 2026*. [Online]. Available: https://arxiv.org/abs/2603.25333

[2] Ekimetrics, “adaptive-chunking” (official implementation). [Online]. Available: https://github.com/ekimetrics/adaptive-chunking

[3] Adaptive Chunk Engine Contributors, “ACE evaluation harness and results,” `benchmarks/adaptive_chunking_eval/`, 2026.
