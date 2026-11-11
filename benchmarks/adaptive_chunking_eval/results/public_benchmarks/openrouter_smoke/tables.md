# ACE Public Benchmark Results

Mode: `openrouter` · profile: `smoke` · chat `openai/gpt-4o` · embed `openai/text-embedding-3-small`

> ACE public-benchmark suite on CLAIR + FinanceBench + Open RAG Bench. CLAIR paper rows are published Adaptive Chunking results. Compare ranks within each dataset/protocol; absolute RAG scores are not cross-dataset comparable.

## clair

Docs: **6** · queries: **24** · domains `['legal', 'social', 'technical']`

### Intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **adaptive_ace** | 100.0 | 39.39 | 85.79 | 99.69 | 99.59 | **84.89** |
| fixed_token_512 | 100.0 | 36.39 | 86.49 | 99.69 | 100.0 | **84.52** |
| recursive_text | 100.0 | 37.09 | 85.38 | 99.69 | 99.59 | **84.35** |
| recursive_text_1100 | 99.87 | 36.29 | 84.08 | 99.72 | 100.0 | **83.99** |
| sentence_window | 98.42 | 47.03 | 86.15 | 92.04 | 87.35 | **82.2** |
| no_split | 100.0 | 40.79 | 100.0 | 100.0 | 0.0 | **68.16** |

### Published CLAIR intrinsic (paper Table 3)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **Adaptive Chunking (paper)** | 99.0 | 68.2 | 88.8 | 99.4 | 99.9 | **91.07** |
| LLM regex (GPT) (paper) | 98.0 | 70.9 | 82.4 | 98.1 | 99.6 | **89.8** |
| LangChain recursive (paper) | 96.1 | 65.6 | 88.8 | 95.0 | 97.7 | **88.62** |
| Semantic (paper) | 97.5 | 69.3 | 76.3 | 91.3 | 48.1 | **76.49** |
| Sentence (paper) | 86.3 | 78.4 | 72.5 | 61.9 | 67.2 | **73.26** |

### RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **adaptive_ace** | 91.67 | 91.67 | 11/12 |
| recursive_text_1100 | 91.67 | 91.67 | 11/12 |
| fixed_token_512 | 75.0 | 75.0 | 9/12 |
| sentence_window | 71.67 | 71.67 | 9/12 |

### Published CLAIR RAG (paper Table 5)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **Adaptive Chunking (paper)** | 67.7 | 78.0 | 65/99 |
| LangChain recursive (paper) | 58.1 | 70.1 | 49/99 |
| Page splitting (paper) | 59.1 | 73.3 | 49/99 |

## financebench

Docs: **8** · queries: **12** · domains `['finance']`

### Intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **adaptive_ace** | 100.0 | 67.85 | 94.32 | 100.0 | 100.0 | **94.76** |
| recursive_text_1100 | 100.0 | 69.69 | 95.2 | 100.0 | 100.0 | **94.49** |
| fixed_token_512 | 100.0 | 58.13 | 89.2 | 99.46 | 100.0 | **93.35** |
| sentence_window | 100.0 | 69.14 | 92.92 | 98.51 | 84.15 | **90.49** |
| recursive_text | 100.0 | 58.36 | 85.91 | 97.5 | 93.75 | **90.01** |
| no_split | 100.0 | 72.51 | 100.0 | 100.0 | 50.0 | **85.88** |

### RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| recursive_text_1100 | 100.0 | 87.5 | 12/12 |
| fixed_token_512 | 93.75 | 87.5 | 10/12 |
| **adaptive_ace** | 92.5 | 86.25 | 10/12 |
| sentence_window | 75.0 | 62.5 | 10/12 |

## open_rag_bench

Docs: **10** · queries: **40** · domains `['arxiv']`

### Intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **adaptive_ace** | 99.93 | 46.24 | 84.51 | 99.34 | 100.0 | **86.0** |
| fixed_token_512 | 99.93 | 45.9 | 84.8 | 99.34 | 100.0 | **85.99** |
| recursive_text | 99.79 | 44.48 | 83.11 | 97.92 | 100.0 | **85.06** |
| recursive_text_1100 | 100.0 | 45.52 | 80.66 | 99.0 | 99.44 | **84.92** |
| sentence_window | 94.88 | 55.8 | 84.25 | 68.47 | 65.9 | **73.86** |
| no_split | 100.0 | 35.7 | 100.0 | 100.0 | 0.0 | **67.14** |

### RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **adaptive_ace** | 88.0 | 84.0 | 17/20 |
| fixed_token_512 | 86.5 | 82.5 | 17/20 |
| sentence_window | 80.0 | 81.0 | 16/20 |
| recursive_text_1100 | 79.0 | 74.0 | 15/20 |
