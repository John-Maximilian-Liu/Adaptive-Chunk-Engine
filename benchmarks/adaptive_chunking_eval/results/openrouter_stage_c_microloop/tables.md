# ACE OpenRouter Live Evaluation Results

Provider: **OpenRouter** · chat `openai/gpt-4o` · embed `Qwen/Qwen3-Embedding-8B` · rerank `cohere/rerank-v3.5` · adaptive `rag_microloop`

Corpus: **6 documents** · domains `['legal', 'sustainability', 'technical']` · ≈8766 words.

Reference: [arXiv:2603.25333](https://arxiv.org/abs/2603.25333) · [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

> OpenRouter live ACE rows use `Qwen/Qwen3-Embedding-8B` for ICC/DCC + dense retrieval, `cohere/rerank-v3.5` rerank, adaptive_mode=`rag_microloop`, and `openai/gpt-4o` as LLM judge. Paper CLAIR rows remain published baselines (33 docs, different embedder/judge). Compare ranks, not absolute magnitudes.

API usage (approx): embed_calls=1027, rerank_calls=376, chat_calls=344, tokens=679920, cost_usd≈1.9433

## A. ACE OpenRouter intrinsic metrics (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **adaptive_ace** | 100.0 | 53.23 | 96.48 | 100.0 | 100.0 | **89.94** |
| recursive_text | 100.0 | 53.43 | 96.94 | 98.7 | 100.0 | **89.81** |
| recursive_text_1100 | 100.0 | 53.01 | 95.93 | 100.0 | 100.0 | **89.79** |
| fixed_token_512 | 100.0 | 53.64 | 95.06 | 97.66 | 100.0 | **89.27** |
| fixed_token_256 | 99.25 | 55.31 | 94.98 | 96.69 | 99.02 | **89.05** |
| heading_section | 100.0 | 54.57 | 90.02 | 97.66 | 83.33 | **85.12** |
| no_split | 100.0 | 52.4 | 100.0 | 100.0 | 16.67 | **73.81** |
| sentence_window | 58.33 | 61.43 | 83.96 | 21.35 | 60.69 | **57.15** |

## B. Published Adaptive Chunking intrinsic metrics (CLAIR / paper Table 3)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| **Adaptive Chunking (paper)** | 99.0 | 68.2 | 88.8 | 99.4 | 99.9 | **91.07** |
| LLM regex (GPT) (paper) | 98.0 | 70.9 | 82.4 | 98.1 | 99.6 | **89.8** |
| LangChain recursive (paper) | 96.1 | 65.6 | 88.8 | 95.0 | 97.7 | **88.62** |
| Semantic (paper) | 97.5 | 69.3 | 76.3 | 91.3 | 48.1 | **76.49** |
| Sentence (paper) | 86.3 | 78.4 | 72.5 | 61.9 | 67.2 | **73.26** |

## C. ACE OpenRouter RAG (dense retrieval top-20 + cohere/rerank-v3.5 rerank top-5 + openai/gpt-4o JSON LLM judge)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **adaptive_ace** | 100.0 | 100.0 | 43/43 |
| recursive_text_1100 | 100.0 | 100.0 | 43/43 |
| recursive_text | 100.0 | 100.0 | 43/43 |
| fixed_token_512 | 100.0 | 100.0 | 43/43 |
| fixed_token_256 | 100.0 | 100.0 | 43/43 |
| heading_section | 100.0 | 100.0 | 43/43 |
| no_split | 100.0 | 100.0 | 43/43 |
| sentence_window | 70.42 | 73.12 | 25/43 |

## D. Published Adaptive Chunking RAG (CLAIR / paper Table 5)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **Adaptive Chunking (paper)** | 67.7 | 78.0 | 65/99 |
| LangChain recursive (paper) | 58.1 | 70.1 | 49/99 |
| Page splitting (paper) | 59.1 | 73.3 | 49/99 |
