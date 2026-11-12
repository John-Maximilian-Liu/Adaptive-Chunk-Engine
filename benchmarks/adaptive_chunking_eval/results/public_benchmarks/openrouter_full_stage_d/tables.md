# ACE Public Benchmark Results

Mode: `openrouter` · profile: `full` · chat `openai/gpt-4o` · embed `Qwen/Qwen3-Embedding-8B` · rerank `cohere/rerank-v3.5` · adaptive `rag_microloop`

> ACE public-benchmark suite on CLAIR + FinanceBench + Open RAG Bench. CLAIR paper rows are published Adaptive Chunking results. Compare ranks within each dataset/protocol; absolute RAG scores are not cross-dataset comparable. Live config: embed=`Qwen/Qwen3-Embedding-8B`, rerank=`cohere/rerank-v3.5`, adaptive=`rag_microloop`.

## clair

Docs: **33** · queries: **130** · domains `['legal', 'social', 'technical']`

### Intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **adaptive_ace** | 99.92 | 52.12 | 86.85 | 99.13 | 99.62 | **87.8** |
| fixed_token_512 | 100.0 | 49.06 | 86.65 | 99.55 | 100.0 | **87.05** |
| fixed_token_256 | 99.81 | 47.63 | 86.15 | 98.85 | 99.73 | **86.74** |
| recursive_text | 99.96 | 46.76 | 82.48 | 99.39 | 99.93 | **85.7** |
| recursive_text_1100 | 99.96 | 47.24 | 76.72 | 99.72 | 100.0 | **84.73** |
| sentence_window | 97.57 | 54.76 | 91.3 | 90.65 | 88.32 | **84.52** |
| heading_section | 99.8 | 50.58 | 81.06 | 98.81 | 87.21 | **83.49** |
| no_split | 100.0 | 53.63 | 100.0 | 100.0 | 3.03 | **71.33** |

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
| no_split | 98.99 | 94.95 | 97/98 |
| **adaptive_ace** | 96.57 | 90.5 | 94/98 |
| recursive_text_1100 | 95.96 | 92.93 | 93/98 |
| fixed_token_512 | 93.23 | 88.69 | 89/98 |
| recursive_text | 92.73 | 89.7 | 89/98 |
| sentence_window | 76.26 | 73.23 | 71/98 |

### Published CLAIR RAG (paper Table 5)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **Adaptive Chunking (paper)** | 67.7 | 78.0 | 65/99 |
| LangChain recursive (paper) | 58.1 | 70.1 | 49/99 |
| Page splitting (paper) | 59.1 | 73.3 | 49/99 |

## financebench

Docs: **18** · queries: **36** · domains `['finance']`

### Intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **adaptive_ace** | 99.84 | 61.21 | 89.34 | 97.64 | 100.0 | **91.61** |
| recursive_text_1100 | 100.0 | 61.87 | 88.27 | 98.8 | 100.0 | **90.64** |
| fixed_token_512 | 99.89 | 53.59 | 84.66 | 98.79 | 100.0 | **89.82** |
| heading_section | 99.89 | 53.59 | 84.66 | 98.79 | 100.0 | **89.82** |
| fixed_token_256 | 100.0 | 48.17 | 79.72 | 98.04 | 98.95 | **88.08** |
| sentence_window | 98.92 | 65.28 | 90.88 | 95.51 | 84.29 | **88.02** |
| recursive_text | 99.84 | 56.81 | 79.38 | 97.23 | 97.22 | **87.82** |
| no_split | 100.0 | 64.93 | 100.0 | 100.0 | 50.0 | **83.77** |

### RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| recursive_text_1100 | 99.07 | 93.52 | 32/33 |
| recursive_text | 96.43 | 91.52 | 31/33 |
| no_split | 96.3 | 91.67 | 31/33 |
| **adaptive_ace** | 95.83 | 88.89 | 29/33 |
| fixed_token_512 | 94.17 | 89.07 | 28/33 |
| sentence_window | 86.48 | 76.85 | 27/33 |

## open_rag_bench

Docs: **4** · queries: **40** · domains `['arxiv']`

### Intrinsic (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| fixed_token_512 | 100.0 | 60.04 | 87.84 | 99.33 | 100.0 | **89.44** |
| **adaptive_ace** | 99.89 | 56.8 | 84.93 | 98.9 | 99.51 | **88.0** |
| heading_section | 100.0 | 52.35 | 86.38 | 98.67 | 99.51 | **87.38** |
| fixed_token_256 | 99.38 | 49.3 | 87.63 | 98.21 | 100.0 | **86.91** |
| recursive_text | 99.82 | 51.61 | 84.74 | 97.69 | 100.0 | **86.78** |
| recursive_text_1100 | 100.0 | 53.46 | 78.16 | 99.18 | 100.0 | **86.16** |
| sentence_window | 94.66 | 63.22 | 89.66 | 69.62 | 69.04 | **77.24** |
| no_split | 100.0 | 58.6 | 100.0 | 100.0 | 0.0 | **71.72** |

### RAG

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **adaptive_ace** | 90.0 | 82.5 | 10/12 |
| fixed_token_512 | 90.0 | 82.5 | 10/12 |
| recursive_text | 87.5 | 83.34 | 10/12 |
| recursive_text_1100 | 83.33 | 79.17 | 9/12 |
| sentence_window | 80.0 | 73.34 | 9/12 |
| no_split | 35.83 | 26.66 | 3/12 |
