# ACE Adaptive Chunking Evaluation Results

Corpus: **6 documents** across domains `['legal', 'sustainability', 'technical']` (~8766 words).

Reference protocol adapted from [arXiv:2603.25333](https://arxiv.org/abs/2603.25333) / [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

## Intrinsic metrics (Table 3 style, %)

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|---|---:|---:|---:|---:|---:|---:|
| recursive_text_1100 | 100.0 | 63.52 | 99.93 | 100.0 | 100.0 | **92.69** |
| **adaptive_ace** | 100.0 | 63.55 | 99.9 | 100.0 | 100.0 | **92.69** |
| recursive_text | 100.0 | 63.57 | 99.89 | 98.7 | 100.0 | **92.43** |
| fixed_token_512 | 100.0 | 62.94 | 99.91 | 97.66 | 100.0 | **92.1** |
| fixed_token_256 | 99.25 | 62.07 | 99.54 | 96.69 | 99.02 | **91.31** |
| heading_section | 100.0 | 62.5 | 93.73 | 97.66 | 83.33 | **87.44** |
| no_split | 100.0 | 63.48 | 100.0 | 100.0 | 16.67 | **76.03** |
| sentence_window | 58.33 | 63.93 | 95.05 | 21.35 | 60.69 | **59.87** |

## RAG-lite evaluation (Table 5 style)

| Method | Retrieval Completeness | Answer Correctness | Answered queries |
|---|---:|---:|---:|
| **adaptive_ace** | 100.0 | 100.0 | 43/43 |
| recursive_text_1100 | 100.0 | 100.0 | 43/43 |
| recursive_text | 100.0 | 100.0 | 43/43 |
| fixed_token_512 | 100.0 | 100.0 | 43/43 |
| heading_section | 100.0 | 100.0 | 43/43 |
| no_split | 100.0 | 100.0 | 43/43 |
| fixed_token_256 | 99.89 | 99.87 | 43/43 |
| sentence_window | 91.48 | 89.84 | 43/43 |

## Notes

- ICC/DCC use deterministic hashed n-gram embeddings (offline). Swap embed_fn for Jina/ST for semantic parity with the paper.
- RC uses a filtered pronoun–antecedent heuristic (no maverick-coref dependency).
- RAG metrics are lexical retrieval completeness / answer-token coverage without an LLM judge.
- adaptive_ace selects the per-document strategy with the best intrinsic mean among ACE builtins.
