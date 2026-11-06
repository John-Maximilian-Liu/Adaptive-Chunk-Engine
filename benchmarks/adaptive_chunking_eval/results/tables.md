# ACE Adaptive Chunking Evaluation Results

Corpus: **6 documents** · domains `['legal', 'sustainability', 'technical']` · ≈8766 words.

Reference: [arXiv:2603.25333](https://arxiv.org/abs/2603.25333) · [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

> Paper rows are published CLAIR results (33 docs, neural embeddings, LLM judge). ACE rows are offline hashed-embedding / lexical-RAG on this corpus—compare ranks, not absolute RAG magnitudes.

## A. ACE offline intrinsic metrics (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| recursive_text_1100 | 100.0 | 60.58 | 99.94 | 100.0 | 100.0 | **92.1** |
| **adaptive_ace** | 100.0 | 60.58 | 99.94 | 100.0 | 100.0 | **92.1** |
| recursive_text | 100.0 | 60.49 | 99.88 | 98.7 | 100.0 | **91.81** |
| fixed_token_512 | 100.0 | 59.81 | 99.89 | 97.66 | 100.0 | **91.47** |
| fixed_token_256 | 99.25 | 58.91 | 99.48 | 96.69 | 99.02 | **90.67** |
| heading_section | 100.0 | 59.45 | 94.07 | 97.66 | 83.33 | **86.9** |
| no_split | 100.0 | 60.62 | 100.0 | 100.0 | 16.67 | **75.46** |
| sentence_window | 58.33 | 61.5 | 95.09 | 21.35 | 60.69 | **59.39** |

## B. Published Adaptive Chunking intrinsic metrics (CLAIR / paper Table 3)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **Adaptive Chunking (paper)** | 99.0 | 68.2 | 88.8 | 99.4 | 99.9 | **91.07** |
| LLM regex (GPT) (paper) | 98.0 | 70.9 | 82.4 | 98.1 | 99.6 | **89.8** |
| LangChain recursive (paper) | 96.1 | 65.6 | 88.8 | 95.0 | 97.7 | **88.62** |
| Semantic (paper) | 97.5 | 69.3 | 76.3 | 91.3 | 48.1 | **76.49** |
| Sentence (paper) | 86.3 | 78.4 | 72.5 | 61.9 | 67.2 | **73.26** |

## C. ACE offline RAG-lite

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **adaptive_ace** | 100.0 | 100.0 | 43/43 |
| recursive_text_1100 | 100.0 | 100.0 | 43/43 |
| recursive_text | 100.0 | 100.0 | 43/43 |
| fixed_token_512 | 100.0 | 100.0 | 43/43 |
| heading_section | 100.0 | 100.0 | 43/43 |
| no_split | 100.0 | 100.0 | 43/43 |
| fixed_token_256 | 99.89 | 99.87 | 43/43 |
| sentence_window | 91.48 | 89.84 | 43/43 |

## D. Published Adaptive Chunking RAG (CLAIR / paper Table 5)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **Adaptive Chunking (paper)** | 67.7 | 78.0 | 65/99 |
| LangChain recursive (paper) | 58.1 | 70.1 | 49/99 |
| Page splitting (paper) | 59.1 | 73.3 | 49/99 |
