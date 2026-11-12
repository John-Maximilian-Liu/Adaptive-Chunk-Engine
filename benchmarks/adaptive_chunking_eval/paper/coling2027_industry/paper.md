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

Intrinsic Mean under stage C: **adaptive 89.94** (1st) vs sentence_window **57.15**.

**Lesson.** Without rerank, short-kit dense RAG favored oversized context; with production-like rerank, governed adaptivity saturates the kit.

### 5.2 Public full stage D — intrinsic leadership

| Dataset | **adaptive Mean** | Best fixed Mean |
|---------|------------------:|----------------:|
| CLAIR (33) | **87.8** | 87.05 |
| FinanceBench (18) | **91.61** | 90.64 |
| Open RAG Bench (4) | 88.0 | **89.44** |

### 5.3 Public full stage D — RAG (advantage-focused)

| Dataset | **adaptive RC/AC** | Highlighted contrast |
|---------|-------------------:|----------------------|
| CLAIR | **96.57 / 90.5** | vs sentence_window **76.3 / 73.2** |
| FinanceBench | **95.83 / 88.89** | Strong; recursive_1100 can edge RAG → override case |
| Open RAG Bench | **90.0 / 82.5** (**tied 1st**) | vs **no_split 35.8 / 26.7** on long PDFs |

Published Adaptive Chunking CLAIR anchors remain **91.07** intrinsic Mean and **67.7 / 78.0** RAG (different stack; cite, do not equate magnitudes).

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

## Appendix B: Full tables pointer

Complete tables: evaluation kit `results/openrouter_stage_{a,b,c}_*/`, `results/public_benchmarks/openrouter_full_stage_d/`, and `results/STAGE_EXPERIMENTS.md`.
