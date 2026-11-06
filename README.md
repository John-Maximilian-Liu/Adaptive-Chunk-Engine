<div align="center">

# Adaptive Chunk Engine

**Governed, per-document adaptive chunking for enterprise RAG**

[![arXiv inspiration](https://img.shields.io/badge/inspired%20by-arXiv%3A2603.25333-b31b1b.svg)](https://arxiv.org/abs/2603.25333)
[![LREC 2026 method](https://img.shields.io/badge/method-Adaptive%20Chunking%20(LREC%202026)-blue.svg)](https://github.com/ekimetrics/adaptive-chunking)
[![Eval kit](https://img.shields.io/badge/benchmark-adaptive__chunking__eval-0B3D91.svg)](benchmarks/adaptive_chunking_eval/)
[![Paper](https://img.shields.io/badge/paper-ACE%20technical%20report-green.svg)](benchmarks/adaptive_chunking_eval/paper/paper.md)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg)](https://www.python.org/downloads/)
[![Azure](https://img.shields.io/badge/Azure-Container%20Apps-0078D4.svg)](infrastructure/bicep/main.bicep)

<img src="docs/architecture/ace-architecture.svg" alt="Adaptive Chunk Engine enterprise architecture" width="900">

</div>

---

> Evaluation kit + research article live in **[`benchmarks/adaptive_chunking_eval/`](benchmarks/adaptive_chunking_eval/)**.  
> Method inspired by *Adaptive Chunking* ([arXiv:2603.25333](https://arxiv.org/abs/2603.25333), LREC 2026) and [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

## 中文简介

**ACE** 将 LREC 2026 Adaptive Chunking 的「按文档用 RC/ICC/DCC/BI/SC 选择最优切块」做成企业控制面，并提供独立测评包与论文：`benchmarks/adaptive_chunking_eval/`（含与原项目 CLAIR 结果的对比表）。

---

## What is Adaptive Chunk Engine?

No single chunking method wins on every document. Adaptive Chunking selects the best splitter **per document** using five intrinsic metrics [1], [2]. **ACE** industrializes that idea with canonical schemas, audit trails, human-triggered optimization, Excel-native strategies, and Azure-ready packaging.

| Research idea (LREC 2026) | ACE productization |
|---------------------------|--------------------|
| Per-document selection | `adaptive_ace` + Strategy Registry |
| Five intrinsic metrics | `benchmarks/.../src/intrinsic_metrics.py` |
| RAG evaluation | Product eval engine + offline RAG-lite kit |
| Research reproducibility | Audit + ReproductionManifest + Docker/Azure |

---

## Key Results (with published Adaptive Chunking baselines)

Reproduce:

```bash
make eval
# → benchmarks/adaptive_chunking_eval/results/tables.md
```

### ACE offline intrinsic metrics (%)

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

### Published Adaptive Chunking intrinsic metrics (CLAIR / Table 3) [2]

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **Adaptive Chunking** | 99.0 | 68.2 | 88.8 | 99.4 | 99.9 | **91.07** |
| LLM regex (GPT) | 98.0 | 70.9 | 82.4 | 98.1 | 99.6 | 89.80 |
| LangChain recursive | 96.1 | 65.6 | 88.8 | 95.0 | 97.7 | 88.62 |
| Semantic | 97.5 | 69.3 | 76.3 | 91.3 | 48.1 | 76.49 |
| Sentence | 86.3 | 78.4 | 72.5 | 61.9 | 67.2 | 73.26 |

### ACE offline RAG-lite

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **adaptive_ace** | **100.0** | **100.0** | 43/43 |
| recursive_text_1100 | 100.0 | 100.0 | 43/43 |
| fixed_token_256 | 99.89 | 99.87 | 43/43 |
| sentence_window | 91.48 | 89.84 | 43/43 |

### Published Adaptive Chunking RAG (CLAIR / Table 5) [2]

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **Adaptive Chunking** | **67.7** | **78.0** | 65/99 |
| LangChain recursive | 58.1 | 70.1 | 49/99 |
| Page splitting | 59.1 | 73.3 | 49/99 |

> **Compare ranks, not absolute RAG magnitudes.** Paper = CLAIR + neural embeddings + LLM judge; ACE offline = hashed embeddings + lexical proxy on a smaller corpus.

**Takeaway (both studies):** metric-guided adaptivity recovers strong recursive splitters and avoids brittle sentence-level fragmentation.

---

## Evaluation kit & paper

Everything for this study is under one folder:

```text
benchmarks/adaptive_chunking_eval/
  run_eval.py
  src/intrinsic_metrics.py
  corpus/
  results/tables.md
  paper/paper.md
  paper/paper.html
```

- Kit README: [`benchmarks/adaptive_chunking_eval/README.md`](benchmarks/adaptive_chunking_eval/README.md)  
- Research article: [`benchmarks/adaptive_chunking_eval/paper/paper.md`](benchmarks/adaptive_chunking_eval/paper/paper.md)

---

## 60-second start

```bash
cp -n .env.example .env
docker compose up -d --build
make eval
```

| Service | URL |
|---------|-----|
| Workbench | http://localhost:3000 |
| OpenAPI | http://localhost:8000/docs |

---

## Enterprise guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| No silent auto-optimization | Next experiment needs explicit human action |
| No silent clamping | Invalid manual params → structured errors |
| No fake provider success | Unhealthy adapters report reasons |
| Canonical API | CanonicalChunk v1.0.0 only |
| Reproducibility | ReproductionManifest required for production candidacy |

---

## Citation

```bibtex
@inproceedings{demoura2026adaptive,
  title={Adaptive Chunking: Optimizing Chunking-Method Selection for RAG},
  author={de Moura Junior, Paulo Roberto and Lelong, Jean and Blangero, Annabelle},
  booktitle={Proceedings of LREC 2026},
  year={2026},
  url={https://arxiv.org/abs/2603.25333}
}

@techreport{ace2026governed,
  title={Adaptive Chunk Engine: Governed Per-Document Chunking Selection for Enterprise RAG},
  author={{Adaptive Chunk Engine Contributors}},
  year={2026},
  url={https://github.com/John-Maximilian-Liu/Adaptive-Chunk-Engine},
  note={benchmarks/adaptive_chunking_eval/}
}
```

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [benchmarks/adaptive_chunking_eval/](benchmarks/adaptive_chunking_eval/) | Eval code, results, paper |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design |
| [SECURITY.md](SECURITY.md) | Security posture |
| [FINAL_REPORT.md](FINAL_REPORT.md) | Implementation verification |

## References

[1] https://arxiv.org/abs/2603.25333  
[2] https://github.com/ekimetrics/adaptive-chunking  
