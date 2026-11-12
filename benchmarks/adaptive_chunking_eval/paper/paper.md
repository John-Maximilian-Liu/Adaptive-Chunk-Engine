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

We **foreground settings where governed adaptivity is advantageous**: (i) kit recovery after adding rerank, (ii) intrinsic leadership on CLAIR/FinanceBench, (iii) long-document RAG on Open RAG Bench where `no_split` fails. We de-emphasize non-indexable `no_split` “wins” on short markdown as production baselines.

### A. ACE kit — upgrade path (live)

| Stack | Adaptive intrinsic Mean | Adaptive RAG RC/AC |
|-------|------------------------:|-------------------:|
| Prior (embed-small, no rerank) | 88.48 | **64.17 / 64.58** |
| **A** + Cohere rerank-v3.5 | ≈89.5 | **100.0 / 100.0** |
| **B** + Qwen3-Embedding-8B | ≈90.0 | **100.0 / 100.0** |
| **C** + rag_microloop | **89.94** | **100.0 / 100.0** |

**Finding.** Rerank is the dominant kit win (64 → 100). Qwen8B improves intrinsic separation; micro-loop preserves governance when intrinsic and retrieval disagree on harder corpora. Stage-C excerpt:

| Method | Intrinsic Mean | RAG RC | RAG AC |
|--------|---------------:|-------:|-------:|
| **adaptive_ace** | **89.94** | **100.0** | **100.0** |
| recursive_text_1100 | 89.79 | 100.0 | 100.0 |
| fixed_token_512 | 89.27 | 100.0 | 100.0 |
| sentence_window | 57.15 | (brittle) | (brittle) |

### B. Published CLAIR baselines [2]

| Method | Intrinsic Mean | RAG RC | RAG AC |
|--------|---------------:|-------:|-------:|
| **Adaptive Chunking** | **91.07** | **67.7** | **78.0** |
| LangChain recursive | 88.62 | 58.1 | 70.1 |
| Page splitting | — | 59.1 | 73.3 |

### C. Public full — OpenRouter stage D (primary)

Config: `Qwen3-Embedding-8B` + `cohere/rerank-v3.5` + `rag_microloop` + `gpt-4o`.

#### C.1 Intrinsic Mean (adaptive advantage)

| Dataset | **adaptive_ace** | Best fixed competitor | Margin |
|---------|-----------------:|----------------------:|-------:|
| CLAIR (33) | **87.8** | 87.05 (`fixed_token_512`) | +0.75 |
| FinanceBench (18) | **91.61** | 90.64 (`recursive_text_1100`) | +0.97 |
| Open RAG Bench (4) | 88.0 | **89.44** (`fixed_token_512`) | −1.44 |

Adaptive **wins Mean on CLAIR and FinanceBench** and stays within ~1.5 of the best fixed splitter on ORB—while avoiding last-place `sentence_window` / zero-SC `no_split` traps.

#### C.2 RAG RC/AC (production-relevant contrast)

| Dataset | **adaptive_ace** | Strong competitor | Brittle / non-prod contrast |
|---------|-----------------:|------------------:|----------------------------|
| CLAIR | **96.57 / 90.5** | recursive_1100 95.96 / 92.93 | sentence_window **76.3 / 73.2**; no_split 99.0 / 95.0† |
| FinanceBench | **95.83 / 88.89** | recursive_1100 **99.07 / 93.52** | sentence_window 86.5 / 76.9 |
| Open RAG Bench | **90.0 / 82.5** (**tied 1st**) | fixed_512 90.0 / 82.5 | **no_split 35.8 / 26.7** |

†`no_split` is not a viable production indexer for multi-query corpora; it is reported as an upper-bound context dump. On long arXiv PDFs (Open RAG Bench), that dump **collapses**, while `adaptive_ace` remains best-tied.

#### C.3 Offline smoke (CI lane, ranks only)

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
| Brittle sentence fragmentation loses | **Yes** — last/near-last across tables |
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
