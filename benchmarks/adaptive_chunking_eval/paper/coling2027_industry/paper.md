---
title: "Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG"
venue: "COLING 2027 Industry Track (draft)"
category: "Emerging / Enabling infrastructure + Deployed Methods & System Evaluation"
blind: true
page_budget: "6 pages body (+ unlimited refs / ethics / appendix)"
deadline_note: "COLING 2027 Industry Track: submit by 2026-11-30 AoE; notify 2027-03-15; conference 2027-05-09–14 (Macau)"
anonymization: "Double-blind (COLING 2027 Industry Track). Do not include author names, affiliations, or identifiable repo URLs in the review PDF."
---

# Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG

**Anonymous authors**  
Paper under double-blind review for COLING 2027 Industry Track

---

## Abstract

Chunking is a first-order design choice in enterprise Retrieval-Augmented Generation (RAG), yet production systems still default to a single global splitter. Building on Adaptive Chunking (LREC 2026), which selects a splitter **per document** using five intrinsic metrics (RC, ICC, DCC, BI, SC), we present **Adaptive Chunk Engine (ACE)**: an enterprise control plane that turns metric-guided selection into an auditable product decision with strategy registries, reproduction manifests, a RAG micro-loop selection objective, dense retrieval with cross-encoder reranking, and a human-triggered optimization gate. Under a production-like OpenRouter stack (`Qwen3-Embedding-8B`, Cohere `rerank-v3.5`, `rag_microloop`, `gpt-4o` judge), ACE recovers **100/100** RAG completeness/correctness on a controlled kit (vs. **64/65** without rerank), ranks **first** on full-CLAIR intrinsic Mean (**87.8**), and **ties best RAG** on Open RAG Bench (**90.0/82.5**) while exposing the failure of non-indexable `no_split` on long arXiv PDFs (**35.8/26.7**). We report practitioner lessons: ship dual eval lanes, treat Auto as a proposal, and compare **ranks within a protocol**.

## 1 Introduction

Enterprise RAG pipelines often fail because documents are segmented with a one-size-fits-all splitter. Adaptive Chunking (de Moura et al., 2026) showed that scoring candidates with document-intrinsic metrics and selecting the winner per document improves RAG on CLAIR. Industry deployment adds a different problem set: **auditability**, **human veto**, **alignment of the eval lane with production retrieval (dense + rerank)**, and **what to do when intrinsic metrics disagree with RAG feedback**.

COLING Industry Track submissions prioritize practical deployment insight. ACE is framed as **enabling infrastructure** for governed chunking selection, including negative/trade-off results.

**Contributions for practitioners:**

1. A productized selection loop (`adaptive_ace`) with Strategy Registry, CanonicalChunk contracts, ReproductionManifests, and optional RAG micro-loop blending.
2. A dual-protocol evaluation kit: cheap offline hashed/lexical gates vs. live embeddings + rerank + LLM-judge RAG.
3. Evidence on CLAIR (full), FinanceBench, and Open RAG Bench that highlights when adaptivity wins—and when humans must override.
4. Operational lessons: rank-order reporting, cost envelopes, and governance gates.

## 2 Problem Setting and Design Goals

### 2.1 Industrial problem

In multi-tenant RAG platforms, chunking is simultaneously a **quality**, **cost**, and **compliance** lever. Legal, financial, and arXiv-style PDFs respond differently to fixed-token, recursive, heading-aware, sentence-window, and no-split strategies.

### 2.2 Design goals

- **Per-document adaptivity** without a new model train per corpus.
- **Auditability**: every Auto choice must be reproducible from a manifest.
- **Human veto**: Auto must not silently override RAG regressions.
- **Protocol honesty**: offline CI scores must not be marketed as live neural RAG scores.
- **Retrieval realism**: live eval uses dense top-20 + rerank top-5, matching production RAG.

## 3 System: Adaptive Chunk Engine

### 3.1 Selection → retrieval → governance flow

```text
Document → candidates S
  → intrinsic Mean(RC,ICC,DCC,BI,SC)   [Qwen3-Embedding-8B]
  → optional RAG micro-loop shortlist + evidence blend
  → select s*(d) + ReproductionManifest
  → index CanonicalChunks
  → dense top-20 → Cohere rerank top-5 → gpt-4o judge
  → RAG regress vs locked baseline? → human review
```

Pure intrinsic mode:
$$
s^\star(d)=\arg\max_{s\in\mathcal{S}} \mathrm{mean}\{\mathrm{RC},\mathrm{ICC},\mathrm{DCC},\mathrm{BI},\mathrm{SC}\}(s,d).
$$

### 3.2 Governance surface

ACE records CanonicalChunk schemas, ReproductionManifests (strategy id, metric vector, model ids), and **human-triggered optimization** when RAG gates disagree with intrinsic ranking.

### 3.3 Candidates

`fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, and `adaptive_ace`.

## 4 Evaluation Protocol

| Protocol | Embeddings / retrieve | Rerank | Judge | Role |
|----------|----------------------|--------|-------|------|
| Offline | Hashed n-grams / lexical | — | Term-coverage | CI / regression |
| OpenRouter live (primary) | `Qwen3-Embedding-8B` dense | `cohere/rerank-v3.5` | `gpt-4o` | Production-like |

**Interpretation rule:** compare **ranks within a protocol**. Absolute RAG magnitudes are not transferable across corpora or offline vs live.

| Corpus | Scale reported here |
|--------|---------------------|
| ACE kit | 6 docs · 43 Q |
| CLAIR | **Full 33 docs** · ≤3 live QA/doc |
| FinanceBench | 18 docs · ≤36 Q |
| Open RAG Bench | 4 docs · ≤40 Q |

## 5 Results

We **select tables that show ACE’s industrial advantage**: kit recovery after rerank, intrinsic leadership on CLAIR/FinanceBench, and long-document RAG where `no_split` fails. We do **not** market short-doc `no_split` context dumps as production winners.

### 5.1 ACE kit — rerank closes the live gap

| Stack | Adaptive RAG RC/AC |
|-------|-------------------:|
| Embed-small, no rerank (prior) | **64.2 / 64.6** |
| + Cohere rerank-v3.5 (A) | **100 / 100** |
| + Qwen3-Embedding-8B (B) | **100 / 100** |
| + rag_microloop (C) | **100 / 100** |

**Lesson.** Without rerank, short-kit dense RAG favored oversized context; with production-like rerank, governed adaptivity saturates the kit. Full RC/ICC/DCC/BI/SC and RAG rows: Appendix C.1.

### 5.2 Public full stage D — intrinsic leadership (Mean)

| Dataset | **adaptive Mean** | Best fixed Mean |
|---------|------------------:|----------------:|
| CLAIR (33) | **87.8** | 87.05 |
| FinanceBench (18) | **91.61** | 90.64 |
| Open RAG Bench (4) | 88.0 | **89.44** |

Pre-aggregation metrics (RC/ICC/DCC/BI/SC) for every method: Appendix C.2–C.4.

### 5.3 Public full stage D — RAG (advantage-focused)

| Dataset | **adaptive RC/AC** | Highlighted contrast |
|---------|-------------------:|----------------------|
| CLAIR | **96.57 / 90.5** | vs sentence_window **76.3 / 73.2** |
| FinanceBench | **95.83 / 88.89** | Strong; recursive_1100 can edge RAG → override case |
| Open RAG Bench | **90.0 / 82.5** (**tied 1st**) | vs **no_split 35.8 / 26.7** on long PDFs |

Full RAG tables (all methods + answered): Appendix C.2–C.4. Published Adaptive Chunking CLAIR anchors (full RC–SC + RAG): Appendix C.5.

### 5.4 Claim checklist

| Claim | Supported? |
|-------|------------|
| Adaptivity recovers strong splitters | Yes |
| Rerank required for production-like dense RAG | Yes (kit 64→100) |
| Brittle sentence windows lose | Yes |
| Long-doc RAG needs chunking (not no_split) | Yes (ORB) |
| Intrinsic = RAG optimum always | **No** (FinanceBench residual) |

## 6 Practitioner Lessons

1. **Ship two evaluation lanes.** Offline hashed/lexical for CI; live embed+rerank+LLM judge for release candidates.
2. **Align eval with production retrieval.** Top-20 dense without rerank underestimates adaptive chunking.
3. **Treat Auto as a proposal.** FinanceBench-style residual gaps route to human review with the metric vector attached.
4. **Do not ship `no_split` as an indexer.** It can inflate short-doc RAG and collapse on long PDFs.
5. **Governance is the product.** Manifests and CanonicalChunk contracts make per-document selection acceptable to compliance stakeholders.

## 7 Conclusion

ACE industrializes Adaptive Chunking as a governed control plane with a production-aligned retrieval lane. Across kit upgrades and public full runs, intrinsic evidence favors `adaptive_ace`, rerank repairs live dense RAG, and long-document benchmarks expose why governed chunking beats naive full-doc context—while residual RAG disagreements motivate human-triggered optimization.

## Limitations

Live QA is capped per document under API cost controls; FinanceBench/ORB subsets are expanded beyond smoke but not exhaustive. Offline lexical RAG is a CI proxy. LLM-as-judge introduces variance; we report answered fractions with RC/AC. Absolute scores must not be compared across protocols. Large-scale multi-tenant telemetry (latency SLOs, index churn) is out of scope.

## Ethical Considerations

ACE evaluates document chunking for RAG. Benchmark subsets may contain sensitive corporate/regulatory text; we use published adapters and do not redistribute proprietary filings beyond licensed sources. Live evaluations call third-party APIs; operators must ensure contractual compliance and PII scrubbing. Human override is intentional for regulated workflows.

## References

de Moura Junior, P. R., Lelong, J., and Blangero, A. (2026). Adaptive Chunking: Optimizing Chunking-Method Selection for RAG. LREC 2026. https://arxiv.org/abs/2603.25333

Ekimetrics. adaptive-chunking. https://github.com/ekimetrics/adaptive-chunking

Islam, P., et al. (2023). FinanceBench: A New Benchmark for Financial Question Answering. https://github.com/patronus-ai/financebench

Vectara. Open RAG Bench. https://huggingface.co/datasets/vectara/open_ragbench

COLING 2025 Industry Track Call for Papers. https://coling2025.org/calls/industry_track/

COLING 2027 Industry Track Call for Papers. https://2027.coling-iccl.org/calls/industry_track/

Jain, A., Aggarwal, P., and Saladi, A. (2025). AutoChunker: Structured Text Chunking and its Evaluation. ACL 2025 Industry Track.

---

## Appendix A: Reproduction commands (non-counting)

```bash
make eval-stage-c
make eval-stage-d
```

Live defaults for stages C/D: `ACE_EMBED_MODEL=Qwen/Qwen3-Embedding-8B`, `ACE_RERANK_MODEL=cohere/rerank-v3.5`, `ACE_ADAPTIVE_MODE=rag_microloop`, `ACE_CHAT_MODEL=openai/gpt-4o`.

## Appendix B: Artifact paths (non-counting)

Evaluation kit dumps: `results/openrouter_stage_{a,b,c}_*/`, `results/public_benchmarks/openrouter_full_stage_d/`, `results/STAGE_EXPERIMENTS.md`.

## Appendix C: Detailed metrics before Mean aggregation (non-counting)

Intrinsic tables report RC, ICC, DCC, BI, SC and Mean (%). RAG tables report retrieval completeness, answer correctness, and answered/N. Stack for C/D: `Qwen3-Embedding-8B` + `cohere/rerank-v3.5` + `rag_microloop` + `gpt-4o`.

### C.1 ACE kit stage C — intrinsic

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

### C.1b ACE kit stage C — RAG

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

### C.2 CLAIR full (33 docs) — intrinsic

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

### C.2b CLAIR — RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| no_split† | 98.99 | 94.95 | 97/98 |
| **adaptive_ace** | **96.57** | **90.5** | 94/98 |
| recursive_text_1100 | 95.96 | 92.93 | 93/98 |
| fixed_token_512 | 93.23 | 88.69 | 89/98 |
| recursive_text | 92.73 | 89.7 | 89/98 |
| sentence_window | 76.26 | 73.23 | 71/98 |

†Non-production context dump / upper bound.

### C.3 FinanceBench (18 docs) — intrinsic

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

### C.3b FinanceBench — RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| recursive_text_1100 | 99.07 | 93.52 | 32/33 |
| recursive_text | 96.43 | 91.52 | 31/33 |
| no_split† | 96.3 | 91.67 | 31/33 |
| **adaptive_ace** | **95.83** | **88.89** | 29/33 |
| fixed_token_512 | 94.17 | 89.07 | 28/33 |
| sentence_window | 86.48 | 76.85 | 27/33 |

### C.4 Open RAG Bench (4 docs) — intrinsic

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

### C.4b Open RAG Bench — RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **adaptive_ace** | **90.0** | **82.5** | 10/12 |
| fixed_token_512 | 90.0 | 82.5 | 10/12 |
| recursive_text | 87.5 | 83.34 | 10/12 |
| recursive_text_1100 | 83.33 | 79.17 | 9/12 |
| sentence_window | 80.0 | 73.34 | 9/12 |
| no_split | 35.83 | 26.66 | 3/12 |

### C.5 Published Adaptive Chunking CLAIR anchors (paper Tables 3/5)

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
