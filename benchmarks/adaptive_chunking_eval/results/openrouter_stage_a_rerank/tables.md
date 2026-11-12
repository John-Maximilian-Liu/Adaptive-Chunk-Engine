# ACE OpenRouter Live Evaluation Results

Provider: **OpenRouter** · chat `openai/gpt-4o` · embed `openai/text-embedding-3-small` · rerank `cohere/rerank-v3.5` · adaptive `intrinsic`

Corpus: **6 documents** · domains `['legal', 'sustainability', 'technical']` · ≈8766 words.

Reference: [arXiv:2603.25333](https://arxiv.org/abs/2603.25333) · [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

> OpenRouter live ACE rows use `openai/text-embedding-3-small` for ICC/DCC + dense retrieval, `cohere/rerank-v3.5` rerank, adaptive_mode=`intrinsic`, and `openai/gpt-4o` as LLM judge. Paper CLAIR rows remain published baselines (33 docs, different embedder/judge). Compare ranks, not absolute magnitudes.

API usage (approx): embed_calls=1742, rerank_calls=286, chat_calls=344, tokens=787202, cost_usd≈1.7942

## A. ACE OpenRouter intrinsic metrics (%)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| recursive_text_1100 | 100.0 | 47.78 | 97.21 | 100.0 | 100.0 | **89.0** |
| **adaptive_ace** | 100.0 | 47.78 | 97.21 | 100.0 | 100.0 | **89.0** |
| recursive_text | 100.0 | 48.09 | 94.94 | 98.7 | 100.0 | **88.35** |
| fixed_token_512 | 100.0 | 49.23 | 92.64 | 97.66 | 100.0 | **87.91** |
| fixed_token_256 | 99.25 | 48.75 | 91.52 | 96.69 | 99.02 | **87.05** |
| heading_section | 100.0 | 49.41 | 87.57 | 97.66 | 83.33 | **83.59** |
| no_split | 100.0 | 47.61 | 100.0 | 100.0 | 16.67 | **72.86** |
| sentence_window | 58.33 | 56.26 | 81.59 | 21.35 | 60.69 | **55.65** |

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
| sentence_window | 70.62 | 71.46 | 22/43 |

## D. Published Adaptive Chunking RAG (CLAIR / paper Table 5)

| Method | Retrieval Completeness | Answer Correctness | Answered |
|---|---:|---:|---:|
| **Adaptive Chunking (paper)** | 67.7 | 78.0 | 65/99 |
| LangChain recursive (paper) | 58.1 | 70.1 | 49/99 |
| Page splitting (paper) | 59.1 | 73.3 | 49/99 |
