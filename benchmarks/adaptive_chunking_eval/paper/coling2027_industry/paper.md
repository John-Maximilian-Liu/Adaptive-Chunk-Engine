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

Chunking is a first-order design choice in enterprise Retrieval-Augmented Generation (RAG), yet production systems still default to a single global splitter. Building on Adaptive Chunking (LREC 2026), which selects a splitter **per document** using five intrinsic metrics (RC, ICC, DCC, BI, SC), we present **Adaptive Chunk Engine (ACE)**: an enterprise control plane that turns metric-guided selection into an auditable product decision with strategy registries, reproduction manifests, and a human-triggered optimization gate. We evaluate ACE under two production-relevant protocols—(i) offline hashed embeddings with lexical RAG and (ii) live OpenRouter with `text-embedding-3-small` and `gpt-4o` as LLM judge—on an ACE kit corpus and three public benchmarks (CLAIR, FinanceBench, Open RAG Bench). Intrinsic tables consistently rank `adaptive_ace` first or tied for first and penalize brittle `sentence_window` splits. On public live RAG smoke runs, adaptive retrieval completeness reaches 91.67 (CLAIR), 92.5 (FinanceBench), and 88.0 (Open RAG Bench). Critically, on short ACE-kit documents, live RAG can prefer larger-context fixed splitters over intrinsic argmax—motivating governed human override rather than silent Auto lock-in. We report cost, rank-order interpretation guidance, and practitioner lessons for deploying adaptive chunking under enterprise audit constraints.

## 1 Introduction

Enterprise RAG pipelines rarely fail only because the LLM is weak; they often fail because documents are segmented with a one-size-fits-all splitter that ignores genre, length, and structure. Adaptive Chunking (de Moura et al., 2026) showed that scoring candidate splitters with document-intrinsic metrics and selecting the winner per document improves RAG on CLAIR. Translating that idea into industry systems, however, surfaces a different problem set: **who may accept Auto recommendations, how decisions are audited, how offline CI gates relate to live neural judges, and what to do when intrinsic metrics disagree with RAG feedback**.

COLING Industry Track submissions are judged less on research novelty than on practical deployment insight (COLING 2025/2027 Industry Track CFPs). ACE is therefore framed as **enabling infrastructure** for governed chunking selection, with evaluation lessons that include negative and trade-off results.

**Contributions for practitioners:**

1. A productized selection loop (`adaptive_ace`) with Strategy Registry, CanonicalChunk contracts, and ReproductionManifests.
2. A dual-protocol evaluation kit: cheap offline hashed/lexical gates vs. live embedding + LLM-judge RAG.
3. Evidence on CLAIR, FinanceBench, and Open RAG Bench that intrinsic adaptivity recovers strong splitters while exposing when human override is required.
4. Operational lessons: rank-order comparison across protocols, smoke-scale cost envelopes, and governance gates when intrinsic ≠ RAG optimum.

## 2 Problem Setting and Design Goals

### 2.1 Industrial problem

In multi-tenant RAG platforms, chunking strategy is simultaneously a **quality lever**, a **cost lever** (index size, embedding spend), and a **compliance artifact**. Legal, sustainability, technical, financial, and arXiv-style PDFs respond differently to fixed-token, recursive, heading-aware, sentence-window, and no-split strategies. A global default is easy to ship and hard to defend in audit reviews.

### 2.2 Design goals

ACE targets four non-negotiable enterprise properties:

- **Per-document adaptivity** without requiring a new model train per corpus.
- **Auditability**: every Auto choice must be reproducible from a manifest.
- **Human veto**: Auto must not silently override RAG regressions.
- **Protocol honesty**: offline CI scores must not be marketed as live neural RAG scores.

These map to COLING 2027 Industry themes of *Data & Model Governance*, *Evaluation & Quality Assurance*, *Human-in-the-Loop*, and *Negative Results & Trade-Offs*.

## 3 System: Adaptive Chunk Engine

### 3.1 Selection rule

For document $d$ and candidate strategy set $\mathcal{S}$,

$$
s^\star(d)=\arg\max_{s\in\mathcal{S}} \mathrm{mean}\{\mathrm{RC},\mathrm{ICC},\mathrm{DCC},\mathrm{BI},\mathrm{SC}\}(s,d).
$$

RC (reconstruction), ICC/DCC (intra-/inter-chunk coherence via embeddings), BI (boundary integrity), and SC (size consistency) follow Adaptive Chunking. ACE wraps this argmax behind a Strategy Registry so new splitters can be registered without rewriting the control plane.

### 3.2 Governance surface

Beyond picking $s^\star(d)$, ACE records:

- **CanonicalChunk** schema for multi-sink indexing.
- **ReproductionManifest** capturing strategy id, metric vector, corpus hash, and model ids.
- **Human-triggered optimization** when RAG gates disagree with intrinsic ranking (reject Auto, lock a baseline, or re-run with constrained $\mathcal{S}$).

This is the industrial delta versus a research notebook that prints a table and stops.

### 3.3 Candidate methods

We evaluate: `fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, and `adaptive_ace` (per-document intrinsic argmax over the registry).

## 4 Evaluation Protocol

Industry reviewers expect transparent, replicable methodology even when proprietary data cannot ship. ACE therefore publishes a dual protocol and public-corpus adapters.

### 4.1 Protocols

| Protocol | Embeddings (ICC/DCC) | Retrieval | Judge | Role |
|----------|----------------------|-----------|-------|------|
| Offline | Hashed char n-grams | Lexical top-$k$ | Term-coverage proxy | CI / regression gate |
| OpenRouter live | `text-embedding-3-small` | Dense cosine | `gpt-4o` JSON scores | Production-like neural eval |

**Interpretation rule (enforced in reporting):** compare **ranks within a protocol**. Absolute RAG magnitudes are not transferable across corpora, judges, or offline vs live setups.

### 4.2 Corpora (smoke profile)

| Corpus | Industrial role | Smoke scale |
|--------|-----------------|-------------|
| ACE kit | Controlled multi-domain markdown | 6 docs · ≈8.8k words · 43 Q |
| CLAIR | Align with Adaptive Chunking paper | 6 stratified docs · 24 Q (live RAG: 12) |
| FinanceBench | Financial QA over filing evidence | 8 docs · 12 Q |
| Open RAG Bench | PDF/arXiv RAG sections | 10 docs · 40 Q (live RAG: 20) |

Full CLAIR (33 docs) and FinanceBench (150 Q) remain available via a `full` profile; this paper reports the smoke profile actually executed under live API cost constraints.

### 4.3 Cost envelope

ACE-kit OpenRouter run: ≈1.31 USD (≈1.7k embed calls, ≈340 chat calls, ≈0.79M tokens). Public live smoke across three datasets: ≈1.10 USD reported. Offline runs are essentially free after local compute—useful as a daily gate before spending live budget.

## 5 Results

### 5.1 ACE kit — offline intrinsic (excerpt)

| Method | Mean | Note |
|--------|-----:|------|
| **adaptive_ace** / recursive_text_1100 | **92.10** | Tied first |
| recursive_text | 91.81 | |
| fixed_token_512 | 91.47 | |
| sentence_window | 59.39 | Brittle |

Offline RAG-lite: adaptive **100.0 / 100.0** (43/43 answered); sentence_window 91.48 / 89.84.

### 5.2 ACE kit — live OpenRouter (the hard case)

| Method | Intrinsic Mean | RAG RC | RAG AC | Answered |
|--------|---------------:|-------:|-------:|---------:|
| **adaptive_ace** | **88.48** | 64.17 | 64.58 | 26/43 |
| recursive_text_1100 | 88.44 | 82.92 | 83.33 | 35/43 |
| fixed_token_512 | 87.92 | 93.75 | 93.75 | 40/43 |
| no_split | 72.37 | **100.0** | **100.0** | 43/43 |
| sentence_window | 55.64 | 90.83 | 92.71 | 38/43 |

**Lesson.** Neural intrinsic still ranks adaptive first and sentence windows last, but on this *short* kit, dense retrieval + LLM judge rewards larger context. Shipping Auto without a RAG gate would silently hurt answerability. ACE’s human-triggered optimization exists for exactly this disagreement.

### 5.3 Published CLAIR baselines (Adaptive Chunking)

Adaptive Chunking reports intrinsic Mean **91.07** and RAG RC/AC **67.7 / 78.0** on full CLAIR (33 docs, different embedder/judge). We cite these as external published anchors; we do **not** claim numerical parity with our smoke rows.

### 5.4 Public offline smoke

| Dataset | adaptive Mean | Best non-adaptive Mean | adaptive RAG RC |
|---------|--------------:|-----------------------:|----------------:|
| CLAIR | **90.53** | 89.74 (recursive_text) | 99.68 |
| FinanceBench | **96.45** | 95.76 (fixed_token_512) | 99.71 |
| Open RAG Bench | **90.95** | 90.74 (recursive_text_1100) | 92.48 |

### 5.5 Public live OpenRouter smoke

| Dataset | adaptive Mean | adaptive RAG RC / AC | Answered |
|---------|--------------:|---------------------:|---------:|
| CLAIR | **84.89** | **91.67 / 91.67** | 11/12 |
| FinanceBench | **94.76** | 92.5 / 86.25 | 10/12 |
| Open RAG Bench | **86.00** | **88.0 / 84.0** | 17/20 |

On CLAIR and Open RAG Bench live RAG, adaptive leads or ties strong recursives. FinanceBench live RAG slightly prefers `recursive_text_1100` (100.0 RC) over adaptive (92.5)—again an override case, not a reason to abandon metric selection.

### 5.6 Claim checklist

| Claim | Supported? |
|-------|------------|
| Metric-guided adaptivity recovers strong splitters | Yes — kit + three public sets, offline & live intrinsic |
| Brittle sentence fragmentation loses | Yes |
| Intrinsic argmax = RAG optimum always | **No** — ACE-kit live & FinanceBench live gaps |
| Absolute scores transfer across protocols | **No** — ranks only |

## 6 Practitioner Lessons

1. **Ship two evaluation lanes.** Use offline hashed/lexical gates for CI; reserve live embeddings + LLM judges for release candidates. Do not mix magnitudes in dashboards.
2. **Treat Auto as a proposal.** When RAG completeness drops vs. a locked baseline, route to human review with the metric vector attached.
3. **Budget for smoke before full.** Public live smoke ≈ \$1; ACE-kit live ≈ \$1.3. Full CLAIR/FinanceBench should be scheduled deliberately.
4. **Document genre matters.** Short multi-domain markdown (ACE kit) rewards large context under dense RAG; stratified public PDFs/filings reward adaptive more often.
5. **Governance is the product.** ReproductionManifests and CanonicalChunk contracts are what make per-document selection acceptable to security/compliance stakeholders.

## 7 Conclusion

ACE industrializes Adaptive Chunking as a governed control plane for enterprise RAG. Across offline and live protocols on an ACE kit plus CLAIR, FinanceBench, and Open RAG Bench, intrinsic evidence favors `adaptive_ace` over brittle splitters, while live RAG disagreements motivate human-triggered optimization. For COLING Industry Track audiences, the transferable artifact is not a single leaderboard number but a **deployable decision process**: measure, select, audit, and override when RAG reality diverges from intrinsic ranking.

## Limitations

Reported public and ACE-kit live numbers are **smoke-scale** under API cost constraints; full CLAIR (33 docs) and FinanceBench (150 Q) should be run before claiming domain production readiness. Offline lexical RAG is a CI proxy, not a substitute for neural retrieval. LLM-as-judge introduces judge variance; we report answered fractions alongside RC/AC. Absolute scores must not be compared across protocols. The system is evaluated as an evaluation/control plane; large-scale multi-tenant production telemetry (latency SLOs, index churn) is out of scope for this draft.

## Ethical Considerations

ACE evaluates document chunking for RAG and does not generate user-facing advice without retrieval. FinanceBench and legal CLAIR subsets can contain sensitive corporate or regulatory text; we use published benchmark subsets and do not redistribute proprietary filings beyond the adapters’ licensed sources. Live evaluations call third-party LLM/embedding APIs; operators must ensure contractual compliance and PII scrubbing before sending production documents. Human override is intentional: automated selection should not silently degrade retrieval quality in regulated workflows.

## References

de Moura Junior, P. R., Lelong, J., and Blangero, A. (2026). Adaptive Chunking: Optimizing Chunking-Method Selection for RAG. LREC 2026. https://arxiv.org/abs/2603.25333

Ekimetrics. adaptive-chunking. https://github.com/ekimetrics/adaptive-chunking

Islam, P., et al. (2023). FinanceBench: A New Benchmark for Financial Question Answering. https://github.com/patronus-ai/financebench

Vectara. Open RAG Bench. https://huggingface.co/datasets/vectara/open_ragbench

COLING 2025 Industry Track Call for Papers. https://coling2025.org/calls/industry_track/

COLING 2027 Industry Track Call for Papers (SIGDIAL redistribution / conference site). https://2027.coling-iccl.org/calls/industry_track/

Jain, A., Aggarwal, P., and Saladi, A. (2025). AutoChunker: Structured Text Chunking and its Evaluation. ACL 2025 Industry Track.

Darwish, K. and Agarwal, A. (2025). Preface / overview remarks in *Proceedings of COLING 2025: Industry Track*. ACL Anthology.

---

## Appendix A: Reproduction commands (non-counting)

```bash
make eval                          # ACE kit offline
make eval-openrouter               # ACE kit live
make download-public-benchmarks
make eval-public-smoke
make eval-public-openrouter-smoke
```

Live defaults: `ACE_CHAT_MODEL=openai/gpt-4o`, `ACE_EMBED_MODEL=openai/text-embedding-3-small`.

## Appendix B: Full tables pointer

Complete intrinsic/RAG tables live under the evaluation kit `results/` directories (offline, openrouter, public_benchmarks). Reviewers need only the main-body tables; appendices are optional under Industry Track rules.
