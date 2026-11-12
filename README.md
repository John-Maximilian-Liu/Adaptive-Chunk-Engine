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

<img src="docs/architecture/ace-selection-rag-flow.svg" alt="ACE adaptive selection and RAG governance flow" width="900">

</div>

---

Production-oriented platform for **adaptive document chunking**, retrieval evaluation, optimization governance, and audit evidence for RAG systems.

> Evaluation kit + research article: **[`benchmarks/adaptive_chunking_eval/`](benchmarks/adaptive_chunking_eval/)**.  
> Method inspired by *Adaptive Chunking* ([arXiv:2603.25333](https://arxiv.org/abs/2603.25333), LREC 2026) and [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking).

## 中文简介

**ACE** 将 LREC 2026 Adaptive Chunking 的「按文档用 RC/ICC/DCC/BI/SC 选择最优切块」做成企业控制面，并补齐生产检索链路：**dense top-20 → Cohere rerank → gpt-4o 评判**，以及可选的 **RAG micro-loop** 选择目标。测评覆盖 ACE kit 与 **CLAIR / FinanceBench / Open RAG Bench**；主结果栈为 `Qwen3-Embedding-8B` + `cohere/rerank-v3.5` + `rag_microloop`。详细流程与论文见 `ARCHITECTURE.md`、`docs/architecture/ace-selection-rag-flow.svg`、`benchmarks/adaptive_chunking_eval/`。

## What is Adaptive Chunk Engine?

No single chunking method wins on every document. Adaptive Chunking selects the best splitter **per document** using five intrinsic metrics [1], [2]. **ACE** industrializes that idea with canonical schemas, audit trails, RAG micro-loop selection, dense+rerank evaluation, human-triggered optimization, Excel-native strategies, Azure-ready packaging, and a public-benchmark suite.

| Research idea (LREC 2026) | ACE productization |
|---------------------------|--------------------|
| Per-document selection | `adaptive_ace` + Strategy Registry + optional RAG micro-loop |
| Five intrinsic metrics | eval kit + product `evaluation_engine` |
| RAG evaluation | Offline lexical + live dense → rerank → `gpt-4o` judge |
| Public corpora | CLAIR · FinanceBench · Open RAG Bench |
| Research reproducibility | Audit + ReproductionManifest + Docker/Azure |

### Headline live results (stage C/D stack)

| Study | Adaptive intrinsic Mean | Adaptive RAG RC/AC | Why it shows ACE |
|-------|------------------------:|-------------------:|------------------|
| ACE kit (C) | **89.94** (1st) | **100 / 100** | Rerank recovers kit (was 64/65) |
| CLAIR full 33 (D) | **87.8** (1st) | **96.6 / 90.5** | Beats sentence_window by ~20 pts RAG |
| Open RAG Bench (D) | 88.0 | **90.0 / 82.5** (tied 1st) | vs `no_split` **35.8 / 26.7** on long PDFs |
| FinanceBench (D) | **91.61** (1st) | 95.8 / 88.9 | Intrinsic lead; residual RAG override case |

## Architecture overview

- **API** (FastAPI) owns durable state, OpenAPI `/api/v1`, and orchestration.
- **Workers** (Celery + Redis) run parse, chunk, QA, embedding, indexing, evaluation, and optimization queues.
- **Packages** provide canonical schemas, parsers, chunk adapters, LLM gateway, vector sinks, evaluation, audit, and visual/SVG processing.
- **Frontend** (Next.js) drives the full human-in-the-loop workflow. Browser calls same-origin `/api/v1/*`; the App Router proxy at `apps/web/src/app/api/v1/[...path]/route.ts` forwards to `API_INTERNAL_URL`.
- **Local stack**: PostgreSQL 17, Redis, object storage (adobe/s3mock fallback when MinIO is unavailable), Qdrant via Docker Compose.
- **Production target**: Azure Container Apps + Flexible Server + Blob + Key Vault + AI Search (+ Service Bus migration path).

See [ARCHITECTURE.md](ARCHITECTURE.md) (includes the adaptive selection → RAG → governance loop), [docs/architecture/ace-selection-rag-flow.svg](docs/architecture/ace-selection-rag-flow.svg), and [docs/adr](docs/adr).

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

## Key Results

Full tables: [`results/tables.md`](benchmarks/adaptive_chunking_eval/results/tables.md) · [`results/openrouter/`](benchmarks/adaptive_chunking_eval/results/openrouter/) · [`results/public_benchmarks/`](benchmarks/adaptive_chunking_eval/results/public_benchmarks/) · paper: [`paper/paper.md`](benchmarks/adaptive_chunking_eval/paper/paper.md)

Reproduce:

```bash
make eval && make eval-openrouter
make download-public-benchmarks
make eval-public-smoke && make eval-public-openrouter-smoke
```

### Headline: `adaptive_ace` across studies

| Study / corpus | Protocol | Adaptive intrinsic Mean | Adaptive RAG RC |
|----------------|----------|------------------------:|----------------:|
| Adaptive Chunking CLAIR (paper) [2] | Neural + LLM judge | **91.07** | **67.7** |
| ACE kit (6 docs) | Offline hashed / lexical | **92.10** | **100.0** |
| ACE kit (6 docs) | OpenRouter `text-embedding-3-small` + `gpt-4o` | **88.48** | 64.17 |
| Public CLAIR smoke (6 docs) | Offline | **90.53** | 99.68 |
| Public CLAIR smoke | OpenRouter live | **84.89** | **91.67** |
| FinanceBench smoke | Offline | **96.45** | 99.71 |
| FinanceBench smoke | OpenRouter live | **94.76** | 92.5 |
| Open RAG Bench smoke | Offline | **90.95** | 92.48 |
| Open RAG Bench smoke | OpenRouter live | **86.00** | **88.0** |

> Compare **ranks** within a protocol. Absolute RAG numbers are not transferable across corpora or judges.

### ACE kit — offline intrinsic (excerpt)

| Method | Mean | Method | Mean |
|--------|-----:|--------|-----:|
| **adaptive_ace** / recursive_text_1100 | **92.10** | fixed_token_512 | 91.47 |
| recursive_text | 91.81 | sentence_window | 59.39 |

### ACE kit — OpenRouter live (excerpt)

| Method | Intrinsic Mean | RAG RC | RAG AC |
|--------|---------------:|-------:|-------:|
| **adaptive_ace** | **88.48** | 64.17 | 64.58 |
| recursive_text_1100 | 88.44 | 82.92 | 83.33 |
| fixed_token_512 | 87.92 | 93.75 | 93.75 |
| no_split | 72.37 | **100.0** | **100.0** |
| sentence_window | 55.64 | 90.83 | 92.71 |

### Published CLAIR baselines [2]

| Method | Intrinsic Mean | RAG RC | RAG AC |
|--------|---------------:|-------:|-------:|
| **Adaptive Chunking** | **91.07** | **67.7** | **78.0** |
| LangChain recursive | 88.62 | 58.1 | 70.1 |
| Sentence | 73.26 | — | — |

### Public OpenRouter smoke — adaptive vs brittle

| Dataset | adaptive Mean | sentence_window Mean | adaptive RAG RC/AC |
|---------|--------------:|---------------------:|-------------------:|
| CLAIR | **84.89** | 82.2 | **91.67 / 91.67** |
| FinanceBench | **94.76** | 90.49 | 92.5 / 86.25 |
| Open RAG Bench | **86.00** | 73.86 | **88.0 / 84.0** |

**Takeaways**

1. **Intrinsic:** `adaptive_ace` ranks first (or ties the best recursive) on the ACE kit and all three public smokes, offline and live; `sentence_window` stays weak.
2. **Public live RAG:** adaptive leads on CLAIR and Open RAG Bench; FinanceBench slightly prefers `recursive_text_1100` on RC.
3. **ACE-kit live RAG:** short documents can reward `no_split` / large fixed chunks over intrinsic argmax — ACE keeps **human-triggered optimization** for that gap.
4. Design notes: [`datasets/EXPERIMENT_DESIGN.md`](benchmarks/adaptive_chunking_eval/datasets/EXPERIMENT_DESIGN.md).

## Evaluation kit & paper

```text
benchmarks/adaptive_chunking_eval/
  run_eval.py / run_eval_openrouter.py / run_public_benchmarks.py
  datasets/          # CLAIR · FinanceBench · Open RAG Bench
  corpus/ results/ paper/
```

- Kit README: [`benchmarks/adaptive_chunking_eval/README.md`](benchmarks/adaptive_chunking_eval/README.md)
- Research article: [`benchmarks/adaptive_chunking_eval/paper/paper.md`](benchmarks/adaptive_chunking_eval/paper/paper.md)
- COLING 2027 Industry Track draft: [`benchmarks/adaptive_chunking_eval/paper/coling2027_industry/`](benchmarks/adaptive_chunking_eval/paper/coling2027_industry/)

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
[3] https://github.com/patronus-ai/financebench  
[4] https://huggingface.co/datasets/vectara/open_ragbench  
