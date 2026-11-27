# Held-out paired chunking experiment (Stage E)

Diagnostic vs hidden QA split by evidence paragraph. Shared dense+rerank stack.
strong_fixed = leave-one-out diagnostic Cov winner. Human review is a simulated operator policy.

## Overall

| Condition | Docs | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides | Review min/doc |
|---|---:|---:|---:|---:|---:|---:|
| strong_fixed | 47 | **98.88** (CI 97.45–99.9) | 0.0 | 0.0 | 0 | 0.0 |
| intrinsic | 47 | **92.24** (CI 86.79–96.85) | -6.64 | 19.1 | 0 | 0.0 |
| microloop | 47 | **92.31** (CI 86.75–96.97) | -6.58 | 19.1 | 0 | 0.0 |
| human_review | 47 | **92.64** (CI 87.12–97.18) | -6.24 | 14.9 | 2 | 0.17 |

## Per dataset

### clair (corpus_diag_best=`recursive_text_1100`, n=33)

| Condition | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides |
|---|---:|---:|---:|---:|
| strong_fixed | 99.28 | 0.0 | 0.0 | 0 |
| intrinsic | 90.9 | -8.38 | 21.2 | 0 |
| microloop | 91.23 | -8.05 | 18.2 | 0 |
| human_review | 91.23 | -8.05 | 18.2 | 0 |

### financebench (corpus_diag_best=`fixed_token_512`, n=10)

FinanceBench: Stage-D has 18 docs; held-out requires ≥2 QA → 10 docs

| Condition | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides |
|---|---:|---:|---:|---:|
| strong_fixed | 99.69 | 0.0 | 0.0 | 0 |
| intrinsic | 96.95 | -2.74 | 10.0 | 0 |
| microloop | 96.95 | -2.74 | 10.0 | 0 |
| human_review | 96.95 | -2.74 | 10.0 | 0 |

### open_rag_bench (corpus_diag_best=`recursive_text_1100`, n=4)

| Condition | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides |
|---|---:|---:|---:|---:|
| strong_fixed | 93.57 | 0.0 | 0.0 | 0 |
| intrinsic | 91.55 | -2.02 | 25.0 | 0 |
| microloop | 89.57 | -4.01 | 50.0 | 0 |
| human_review | 93.49 | -0.08 | 0.0 | 2 |
