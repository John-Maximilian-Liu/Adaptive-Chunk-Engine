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

Production-oriented platform for **adaptive document chunking**, retrieval evaluation, optimization governance, and audit evidence for RAG systems.

> Evaluation kit + research article: **[`benchmarks/adaptive_chunking_eval/`](benchmarks/adaptive_chunking_eval/)**.  
> Method inspired by *Adaptive Chunking* ([arXiv:2603.25333](https://arxiv.org/abs/2603.25333), LREC 2026) and [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

## 中文简介

**ACE** 将 LREC 2026 Adaptive Chunking 的「按文档用 RC/ICC/DCC/BI/SC 选择最优切块」做成企业控制面，并提供独立测评包与论文：`benchmarks/adaptive_chunking_eval/`（含与原项目 CLAIR 结果的对比表）。

## What is Adaptive Chunk Engine?

No single chunking method wins on every document. Adaptive Chunking selects the best splitter **per document** using five intrinsic metrics [1], [2]. **ACE** industrializes that idea with canonical schemas, audit trails, human-triggered optimization, Excel-native strategies, and Azure-ready packaging.

| Research idea (LREC 2026) | ACE productization |
|---------------------------|--------------------|
| Per-document selection | `adaptive_ace` + Strategy Registry |
| Five intrinsic metrics | `benchmarks/adaptive_chunking_eval/src/intrinsic_metrics.py` (+ product `evaluation_engine`) |
| RAG evaluation | Product eval engine + offline RAG-lite kit |
| Research reproducibility | Audit + ReproductionManifest + Docker/Azure |

## Architecture overview

- **API** (FastAPI) owns durable state, OpenAPI `/api/v1`, and orchestration.
- **Workers** (Celery + Redis) run parse, chunk, QA, embedding, indexing, evaluation, and optimization queues.
- **Packages** provide canonical schemas, parsers, chunk adapters, LLM gateway, vector sinks, evaluation, audit, and visual/SVG processing.
- **Frontend** (Next.js) drives the full human-in-the-loop workflow. Browser calls same-origin `/api/v1/*`; the App Router proxy at `apps/web/src/app/api/v1/[...path]/route.ts` forwards to `API_INTERNAL_URL`.
- **Local stack**: PostgreSQL 17, Redis, object storage (adobe/s3mock fallback when MinIO is unavailable), Qdrant via Docker Compose.
- **Production target**: Azure Container Apps + Flexible Server + Blob + Key Vault + AI Search (+ Service Bus migration path).

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/adr](docs/adr).

## Prerequisites

- Docker + Docker Compose v2
- (Optional for local non-Docker) Python 3.12, uv, Node.js 22, pnpm

## One-command startup

```bash
cp -n .env.example .env
docker compose up -d --build
```

Or:

```bash
make start
# / scripts/bootstrap.sh
```

## Environment setup

```bash
cp .env.example .env
```

All chunk/QA/eval/visual constraint defaults are documented in `.env.example` and validated via Pydantic Settings.

Frontend routing env vars:

| Variable | Role |
|----------|------|
| `API_INTERNAL_URL` | Server-only upstream for the Next.js `/api/v1` proxy and SSR (Compose sets `http://api:8000/api/v1`) |
| `NEXT_PUBLIC_API_BASE_URL` | Fallback upstream / legacy direct API URL; browser traffic uses same-origin `/api/v1` |

## First-run workflow

1. Open http://localhost:3000
2. Open API docs http://localhost:8000/docs
3. `POST /api/v1/admin/seed` creates a local tenant, mock LLM/embedding profiles, Qdrant sink, evaluation profile, and demo document (no external API keys).
4. Upload a document → parse → auto plan → review → chunk run → automatic indexing outbox → QA → evaluate → review failures → accept optimization proposal → **manually** create next experiment.

## Local URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| API health | http://localhost:8000/api/v1/health/live |
| Object storage (S3 API) | http://localhost:9000 |
| Object storage admin | http://localhost:9001 |
| Qdrant | http://localhost:6333 |

## Sample API calls

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/seed | jq .
curl -s http://localhost:8000/api/v1/strategies | jq '.[].strategy_id'
curl -s -X POST http://localhost:8000/api/v1/documents \
  -H 'X-Tenant-Id: tenant_dev' \
  -F file=@tests/fixtures/sample.md
```

Same-origin proxy smoke (frontend → backend forwarding):

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/api/v1/health/live
curl -s -X POST http://localhost:3000/api/v1/admin/seed -H 'X-Tenant-Id: tenant_dev' | jq .
```

## Key Results (with published Adaptive Chunking baselines)

Reproduce:

```bash
make eval                 # offline hashed / lexical
make eval-openrouter      # requires OPENROUTER_API_KEY; gpt-4o + text-embedding-3-small
# → benchmarks/adaptive_chunking_eval/results[/openrouter]/tables.md
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

### ACE OpenRouter intrinsic metrics (%) — `text-embedding-3-small`

| Method | RC | ICC | DCC | BI | SC | **Mean** |
|--------|---:|----:|----:|---:|---:|--------:|
| **adaptive_ace** | 100.0 | 48.04 | 94.38 | 100.0 | 100.0 | **88.48** |
| recursive_text_1100 | 100.0 | 47.78 | 94.42 | 100.0 | 100.0 | 88.44 |
| recursive_text | 100.0 | 48.09 | 94.94 | 98.70 | 100.0 | 88.35 |
| fixed_token_512 | 100.0 | 49.23 | 92.73 | 97.66 | 100.0 | 87.92 |
| sentence_window | 58.33 | 56.26 | 81.58 | 21.35 | 60.69 | 55.64 |

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

### ACE OpenRouter RAG — dense retrieval + `gpt-4o` judge

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| no_split | **100.0** | **100.0** | 43/43 |
| fixed_token_512 | 93.75 | 93.75 | 40/43 |
| recursive_text_1100 | 82.92 | 83.33 | 35/43 |
| **adaptive_ace** | 64.17 | 64.58 | 26/43 |
| recursive_text | 54.17 | 54.17 | 21/43 |

### Published Adaptive Chunking RAG (CLAIR / Table 5) [2]

| Method | Retrieval Completeness | Answer Correctness | Answered |
|--------|-----------------------:|-------------------:|---------:|
| **Adaptive Chunking** | **67.7** | **78.0** | 65/99 |
| LangChain recursive | 58.1 | 70.1 | 49/99 |
| Page splitting | 59.1 | 73.3 | 49/99 |

> **Compare ranks, not absolute RAG magnitudes.** Paper = CLAIR + neural embeddings + LLM judge; ACE offline = hashed + lexical; ACE OpenRouter = `text-embedding-3-small` + `gpt-4o` on the same 6-doc kit.

**Takeaway:** offline and OpenRouter intrinsic runs both recover strong recursive splitters and avoid brittle sentence windows. Live LLM-judge RAG on this small corpus favors larger-context fixed splitters over pure intrinsic argmax — which is exactly why ACE keeps human-triggered optimization when RAG feedback disagrees with metric selection.

## Evaluation kit & paper

```text
benchmarks/adaptive_chunking_eval/
  run_eval.py
  run_eval_openrouter.py
  src/intrinsic_metrics.py
  src/openrouter_client.py
  corpus/
  results/tables.md
  results/openrouter/tables.md
  paper/paper.md
  paper/paper.html
```

- Kit README: [`benchmarks/adaptive_chunking_eval/README.md`](benchmarks/adaptive_chunking_eval/README.md)
- Research article: [`benchmarks/adaptive_chunking_eval/paper/paper.md`](benchmarks/adaptive_chunking_eval/paper/paper.md)

## Running tests

```bash
# Offline Adaptive Chunking–style eval
make eval
# Live OpenRouter (OPENROUTER_API_KEY + optional ACE_CHAT_MODEL / ACE_EMBED_MODEL)
make eval-openrouter

# Backend
cd apps/api && source .venv/bin/activate
export PYTHONPATH=../../packages/python:.:../../workers
pytest -q

# Frontend unit
cd apps/web && pnpm install && pnpm test

# E2E (stack must be up)
cd apps/web && pnpm e2e
```

## Enabling providers

### OpenAI
Create an LLM profile via UI **Connections** or `POST /api/v1/llm-profiles` with `provider=openai`, `api_key`, optional `base_url`. Secrets are write-only.

### Azure OpenAI
`provider=azure_openai`, `base_url` (endpoint), `deployment_name`, `auth_mode=api_key|entra_id|managed_identity`.

### Azure AI Search
`POST /api/v1/vector-sink-profiles` with `sink_type=azure_ai_search`, endpoint + API key (dev) or managed identity (prod).

### Dify Knowledge Base
`sink_type=dify`, `connection.base_url`, `dataset_id`, API key. Canonical chunks are pushed as segments (no re-chunking). Embeddings are sink-managed by default.

## Adapter status matrix

| Adapter | Status |
|---------|--------|
| Builtin strategies (fixed_token, recursive, heading, parent_child, tables, markdown, cross-unit, excel*) | Operational |
| Docling preferred parse | Preferred when installed; local fallbacks always available |
| Chonkie / Chunkana / markdown-chunker | Optional — unavailable until dependency installed |
| Chunkr | Optional external — requires `CHUNKR_BASE_URL` |
| MarkdownStructureChunker | Optional .NET sidecar — requires URL |
| ZeroEntropy zchunk | Optional, **disabled by default** |
| Qdrant | Operational (local) |
| Azure AI Search | Implemented + contract-tested (mock HTTP) |
| Dify KB | Implemented + contract-tested (mock HTTP) |
| Mock LLM / embeddings | Operational for offline/demo |

## Enterprise guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| No silent auto-optimization | Next experiment needs explicit human action |
| No silent clamping | Invalid manual params → structured errors |
| No fake provider success | Unhealthy adapters report reasons |
| Canonical API | CanonicalChunk v1.0.0 only |
| Reproducibility | ReproductionManifest required for production candidacy |

## Known limitations

- Live OpenAI / Azure / Dify / AI Search connectivity is not claimed without credentials.
- Optional chunk providers are honestly marked unavailable when dependencies/sidecars are missing.
- Local object storage uses **adobe/s3mock** when the official MinIO image cannot be pulled.
- Celery workers are wired for all queues; the API also processes the indexing outbox inline after successful chunk runs so Compose demos remain reliable without shared in-memory Engine state across processes.
- Development auth (`AUTH_MODE=development`) is **not** production-safe.
- The same-origin `/api/v1` proxy forwards request headers to the API; treat public tunnel exposure as a development/demo surface, not a hardened production edge.

## Troubleshooting

- Migrations race: only the `migration` service runs Alembic once (`python -m alembic upgrade head` from `db_migrations/`).
- Inter-container timeouts on nested VMs: run `./scripts/fix-docker-bridge-forwarding.sh` then restart Compose.
- Qdrant unhealthy: wait for healthcheck; indexing target may be `FAILED` until Qdrant is ready — use reindex.
- Frontend cannot reach API through the UI: confirm the web container has `API_INTERNAL_URL=http://api:8000/api/v1` and that `http://localhost:3000/api/v1/health/live` returns 200. Direct API checks still use `http://localhost:8000/api/v1/...`.

## Security

See [SECURITY.md](SECURITY.md).

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
