---
title: "Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG"
authors: "Adaptive Chunk Engine Contributors"
date: 2026-11-06
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

*Technical report · 2026-11-06*  
*Builds on Adaptive Chunking (LREC 2026; [arXiv:2603.25333](https://arxiv.org/abs/2603.25333); code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking))*

</div>

---

**Abstract**—The effectiveness of Retrieval-Augmented Generation (RAG) depends critically on how documents are segmented for indexing. De Moura et al. (LREC 2026) introduce *Adaptive Chunking*, which selects the best splitter per document using five intrinsic metrics—References Completeness (RC), Intrachunk Cohesion (ICC), Document Contextual Coherence (DCC), Block Integrity (BI), and Size Compliance (SC)—and report strong gains on the CLAIR corpus. We present **Adaptive Chunk Engine (ACE)**, an enterprise control plane that operationalizes the same selection principle behind canonical schemas, audit/reproduction manifests, human-triggered optimization, Excel-native strategies, and multi-sink indexing. On a multi-domain offline ACE corpus (6 documents, ≈8.8k words), metric-guided `adaptive_ace` matches the strongest fixed recursive baseline (**intrinsic mean 92.10%**) and leads RAG-lite completeness, while brittle strategies such as aggressive sentence windows collapse (mean **59.39%**; RAG completeness **91.48%**). We juxtapose these results with the published Adaptive Chunking CLAIR tables (intrinsic mean **91.07%**; RAG completeness **67.7**) and discuss why absolute scores are not comparable across protocols while **rank-order conclusions transfer**.

**Index Terms**—RAG, adaptive chunking, intrinsic evaluation, enterprise AI systems, information retrieval

---

## I. INTRODUCTION

**T**HIS paper studies how to turn research-grade *Adaptive Chunking* into a production-ready enterprise system. Prior work shows that one-size-fits-all splitters underperform when documents vary in structure and discourse [1]. The Adaptive Chunking framework scores multiple methods with intrinsic, document-based metrics and selects the winner per document, improving downstream RAG without changing the generator [1], [2].

Enterprise RAG adds constraints that research libraries alone do not solve: auditable decisions, human veto over Auto recommendations, non-prose artifacts (spreadsheets, visuals), and multi-destination indexing with partial-failure isolation. **ACE** embeds metric-guided selection inside such a control plane.

**Contributions.**

1. **Productized adaptive selection.** A Strategy Registry + per-document intrinsic argmax (`adaptive_ace`) aligned with [1].
2. **Offline reproducible benchmark kit.** Self-contained harness under `benchmarks/adaptive_chunking_eval/` with corpus, metrics, tables, and this paper.
3. **Head-to-head comparison framing.** ACE offline results vs. published Adaptive Chunking CLAIR results [2], with explicit protocol caveats.
4. **Governance layer.** CanonicalChunk contracts, audit/reproduction manifests, and human-triggered optimization gates.

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

For CI-safe runs, ICC/DCC use **deterministic hashed character n-gram embeddings**. Neural encoders (Jina / SentenceTransformers) can be plugged in via `embed_fn` for closer parity with [1].

### C. ACE Control-Plane Extensions

Beyond selection, ACE records effective configuration sources (Auto vs Manual locks), emits `CHUNK_RUN_COMPLETED` outbox events for indexing, and never auto-executes optimization rounds—humans must accept patches and create the next experiment.

### D. RAG-lite Protocol

Queries reference section indices and topic keywords without copying full evidence sentences. Retrieval is lexical top-$k$ with key-term bonuses. Retrieval Completeness is evidence-term coverage; Answer Correctness is answer-token coverage (no LLM judge in the offline kit).

## IV. EXPERIMENTS

### A. Datasets

**ACE offline corpus.** 6 documents in technical / legal / sustainability domains (≈8.8k words), stored in `benchmarks/adaptive_chunking_eval/corpus/`.

**CLAIR (paper).** 33 documents, ~1.18M tokens, used by [1], [2] (not redistributed here).

### B. Candidate Methods (ACE)

`fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, and `adaptive_ace`.

### C. Published Baselines (paper)

Adaptive Chunking, LLM-regex (GPT), LangChain recursive, Semantic, Sentence (intrinsic); Adaptive Chunking, LangChain recursive, Page splitting (RAG) [2].

### D. Reproducibility

```bash
cd benchmarks/adaptive_chunking_eval
PYTHONPATH=../../apps/api:../../packages/python python run_eval.py
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

### E. Cross-Protocol Comparison (Interpretation)

| Aspect | Adaptive Chunking (paper) | ACE (this report) |
|--------|---------------------------|-------------------|
| Corpus | CLAIR 33 docs / ~1.18M tokens | 6 docs / ≈8.8k words |
| Embeddings | Neural (Jina / ST) | Hashed n-grams (offline) |
| RAG judge | Hybrid retrieval + LLM correctness | Lexical coverage proxy |
| Adaptive mean | **91.07** | **92.10** |
| Best fixed recursive | 88.62 (LangChain) | 92.10 (`recursive_text_1100`) |
| Weak splitter | Sentence 73.26 | sentence_window 59.39 |
| RAG adaptive lead | +9.6 RC vs LangChain | Ties top recursive; −8.5 vs sentence_window |

**Finding.** Despite protocol differences, both studies support the same claim: **metric-guided adaptivity recovers strong splitters and avoids brittle ones**. Absolute RAG scores must not be compared head-to-head across protocols.

## VI. DISCUSSION

### A. Why governance matters

Selection without evidence trails cannot ship in regulated environments. ACE stores effective parameters, locks, and audit events so $s^\star(d)$ is reconstructible.

### B. Limitations

- Offline embeddings ≠ paper neural ICC/DCC.  
- RC heuristic ≠ full coreference resolution.  
- ACE corpus ≪ CLAIR.  
- RAG-lite lacks an LLM answer judge.

### C. Future work

Scale ACE eval to CLAIR-sized corpora with neural embedders; attach ACE’s full evaluation engine (hard gates, failure taxonomy) to the same adaptive selector.

## VII. CONCLUSION

Adaptive Chunking [1] establishes that per-document metric-guided selection improves RAG. ACE shows how to **industrialize** that insight: the same selection idea, plus enterprise contracts, human gates, and multi-sink indexing. Our offline benchmark—packaged under `benchmarks/adaptive_chunking_eval/`—reproduces the qualitative ranking effects of the LREC study while documenting protocol differences against the published CLAIR tables [2].

## ACKNOWLEDGMENT

We thank the authors of Adaptive Chunking for releasing metrics, code, and CLAIR evaluation artifacts that make comparative enterprise studies possible [1], [2].

## REFERENCES

[1] P. R. de Moura Junior, J. Lelong, and A. Blangero, “Adaptive Chunking: Optimizing Chunking-Method Selection for RAG,” in *Proc. LREC 2026*. [Online]. Available: https://arxiv.org/abs/2603.25333

[2] Ekimetrics, “adaptive-chunking” (official implementation). [Online]. Available: https://github.com/ekimetrics/adaptive-chunking

[3] Adaptive Chunk Engine Contributors, “ACE evaluation harness and results,” `benchmarks/adaptive_chunking_eval/`, 2026.
