# Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG

**Technical Report** — Adaptive Chunk Engine (ACE)  
**Companion evaluation** to *Adaptive Chunking: Optimizing Chunking-Method Selection for RAG* ([arXiv:2603.25333](https://arxiv.org/abs/2603.25333); LREC 2026; code: [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking))

---

## Abstract

Retrieval-Augmented Generation (RAG) quality is highly sensitive to document chunking, yet production systems rarely treat strategy selection as a first-class, auditable decision. Building on the Adaptive Chunking framework of de Moura et al. (LREC 2026), which selects per-document splitters using five intrinsic metrics—References Completeness (RC), Intrachunk Cohesion (ICC), Document Contextual Coherence (DCC), Block Integrity (BI), and Size Compliance (SC)—we present **Adaptive Chunk Engine (ACE)**: an enterprise control plane that embeds metric-guided selection inside a governed workflow with canonical schemas, human-in-the-loop optimization, multi-sink indexing, and Azure-ready packaging.

We reproduce the paper’s *evaluation spirit* on a multi-domain ACE corpus (technical, legal, sustainability; 6 documents, ≈8.8k words) using ACE built-in strategies. An offline adaptive selector (`adaptive_ace`) chooses, for each document, the strategy with the best intrinsic mean. Empirically, `adaptive_ace` matches the strongest fixed recursive baseline on intrinsic quality (**Mean 92.69%**) and leads or ties the RAG-lite leaderboard on retrieval completeness and answer correctness, while brittle strategies (e.g., aggressive sentence windows) degrade sharply on RC/BI and retrieval. We argue that **metric-guided adaptivity is necessary but not sufficient for enterprise RAG**: production systems also require evidence trails, configuration precedence, Excel-native locators, and human-triggered optimization gates.

---

## 1. Introduction

Chunking remains a “silent hyperparameter” of RAG. Uniform recursive or page-based splits ignore document heterogeneity; ad-hoc experiments are hard to reproduce. De Moura et al. challenge one-size-fits-all chunking by introducing **Adaptive Chunking**: score multiple methods with intrinsic, document-based metrics and select the best method per document, improving downstream RAG without changing the generator ([arXiv:2603.25333](https://arxiv.org/abs/2603.25333)).

Enterprise deployments add further constraints:

1. Decisions must be **auditable** and **reproducible**.  
2. Humans must **review** Auto recommendations and retain veto power.  
3. Strategies must span **tables, formulas, and visual artifacts**, not only prose.  
4. Vectors must land in **multiple sinks** (Qdrant, Azure AI Search, Dify) with partial-failure isolation.

ACE operationalizes Adaptive Chunking as a productized control plane rather than a research library alone.

---

## 2. Related Work

We adopt the metric definitions and adaptive selection paradigm of de Moura Junior, Lelong, and Blangero (LREC 2026). Their public implementation ([ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking)) provides recursive splitters, five intrinsic metrics, and a RAG evaluation pipeline. ACE differs by (i) a CanonicalChunk v1.0.0 contract, (ii) region/unit-level configuration precedence, (iii) transactional outbox indexing, (iv) failure taxonomy + JSON Patch optimization under human trigger, and (v) Azure Container Apps deployment templates.

---

## 3. Method

### 3.1 Intrinsic metrics (paper-aligned)

| Metric | Role in ACE |
|--------|-------------|
| **SC** | Fraction of chunks inside `[min_tokens, max_tokens]` |
| **ICC** | Mean similarity of sentence blocks to the chunk embedding |
| **DCC** | Mean similarity of chunks to a local context window |
| **BI** | Fraction of structural blocks not cut by predicted splits |
| **RC** | Filtered pronoun–antecedent pairs kept inside the same chunk |

For fully offline, CI-safe runs, ICC/DCC use **deterministic hashed character n-gram embeddings**. Production parity with the paper can swap in Jina / SentenceTransformer encoders via `embed_fn`. RC uses a pronoun–antecedent heuristic when `maverick-coref` is unavailable (documented limitation).

### 3.2 Adaptive selection in ACE

Given candidate strategies \(\mathcal{S}\) (fixed-token, recursive, sentence-window, heading-section, …), ACE computes the intrinsic mean \(m(s,d)\) for document \(d\) and selects

\[
s^\star(d)=\arg\max_{s\in\mathcal{S}} m(s,d).
\]

This mirrors the paper’s per-document selection while remaining pluggable through ACE’s Strategy Registry.

### 3.3 RAG-lite protocol

We generate grounded queries that reference section indices and topic keywords without copying full evidence sentences. Retrieval is lexical top-\(k\) with key-term bonuses. **Retrieval Completeness** is evidence-term coverage in the top-\(k\) context; **Answer Correctness** is answer-token coverage. No external LLM judge is required for the offline report (optional judge hooks exist in the ACE evaluation engine).

---

## 4. Experimental Setup

| Item | Value |
|------|-------|
| Documents | 6 (technical / legal / sustainability) |
| Approx. size | ≈8.8k words |
| Candidates | `fixed_token_{256,512}`, `recursive_text`, `recursive_text_1100`, `sentence_window`, `heading_section`, `no_split`, `adaptive_ace` |
| SC bounds | 50–1100 tokens (eval); ACE hard constraints remain 128–4096 in product |
| Code | `scripts/run_adaptive_chunking_eval.py` |
| Artifacts | `results/adaptive_chunking_eval/` |

---

## 5. Results

### 5.1 Intrinsic quality (Table 3 style)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 100.0 | 63.55 | 99.90 | 100.0 | 100.0 | **92.69** |
| recursive_text_1100 | 100.0 | 63.52 | 99.93 | 100.0 | 100.0 | **92.69** |
| recursive_text | 100.0 | 63.57 | 99.89 | 98.70 | 100.0 | 92.43 |
| fixed_token_512 | 100.0 | 62.94 | 99.91 | 97.66 | 100.0 | 92.10 |
| fixed_token_256 | 99.25 | 62.07 | 99.54 | 96.69 | 99.02 | 91.31 |
| heading_section | 100.0 | 62.50 | 93.73 | 97.66 | 83.33 | 87.44 |
| no_split | 100.0 | 63.48 | 100.0 | 100.0 | 16.67 | 76.03 |
| sentence_window | 58.33 | 63.93 | 95.05 | 21.35 | 60.69 | 59.87 |

**Finding.** Adaptive selection recovers the best fixed method’s intrinsic mean and avoids catastrophic strategies (sentence windows break BI/RC; `no_split` collapses SC).

### 5.2 RAG-lite (Table 5 style)

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

**Finding.** On this corpus, strong recursive/adaptive configurations dominate; over-fragmentation (`sentence_window`, smaller fixed tokens) reduces retrieval completeness—consistent with the paper’s thesis that method choice matters.

### 5.3 Comparison to published CLAIR-scale numbers

The LREC paper reports Adaptive Chunking at **91.07** mean intrinsic % and **67.7 / 78.0** RAG completeness / correctness on 33 CLAIR documents with neural embeddings and LLM judging ([README results](https://github.com/ekimetrics/adaptive-chunking)). Our offline ACE study is smaller and uses hashed embeddings + lexical RAG proxies; absolute RAG scores are therefore not directly comparable, but **rank-order effects** (adaptive ≈ best recursive ≫ brittle splitters) transfer.

---

## 6. Enterprise implications

1. **Selection is a decision artifact** — ACE stores effective configuration, source locks, and audit events.  
2. **Human gates beat auto-loops** — optimization proposals never auto-start the next experiment.  
3. **Metrics are product surfaces** — SC/BI/RC failures map into ACE’s failure taxonomy for the Failure Analysis Workbench.  
4. **Beyond prose** — Excel region locators and visual/SVG chunks extend Adaptive Chunking into enterprise document types underrepresented in prose-only corpora.

---

## 7. Limitations

- Offline ICC/DCC embeddings are not semantic equivalents of Jina/ST; treat absolute ICC/DCC as protocol-local.  
- RC heuristic ≠ full coreference resolution.  
- Corpus scale ≪ CLAIR (33 docs / ~1.18M tokens).  
- RAG-lite lacks an LLM answer judge; ACE’s full evaluation engine can attach one when credentials exist.

---

## 8. Reproducibility

```bash
export PYTHONPATH=apps/api:packages/python
python scripts/run_adaptive_chunking_eval.py
# → results/adaptive_chunking_eval/{summary.json,tables.md,metrics.json}
```

---

## 9. Conclusion

Metric-guided per-document chunking selection, as introduced by Adaptive Chunking (LREC 2026), is a powerful inductive bias for RAG. ACE shows how to **industrialize** that bias: same selection idea, plus canonical contracts, governance, multi-sink indexing, and human-controlled optimization. Our offline evaluation confirms that adaptive selection tracks the best intrinsic strategy and protects against brittle splitters—an essential property for enterprise RAG platforms.

---

## References

1. P. R. de Moura Junior, J. Lelong, A. Blangero. *Adaptive Chunking: Optimizing Chunking-Method Selection for RAG*. LREC 2026. https://arxiv.org/abs/2603.25333  
2. Ekimetrics. *adaptive-chunking* (official code). https://github.com/ekimetrics/adaptive-chunking  
3. Adaptive Chunk Engine — this repository. `results/adaptive_chunking_eval/`, `packages/python/evaluation_engine/intrinsic_metrics.py`
