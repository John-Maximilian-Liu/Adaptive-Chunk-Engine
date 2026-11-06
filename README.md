# Adaptive Chunk Engine

Production-oriented platform for **adaptive document chunking**, retrieval evaluation, optimization governance, and audit evidence for RAG systems.

## Architecture overview

- **API** (FastAPI) owns durable state, OpenAPI `/api/v1`, and orchestration.
- **Workers** (Celery + Redis) run parse, chunk, QA, embedding, indexing, evaluation, and optimization queues.
- **Packages** provide canonical schemas, parsers, chunk adapters, LLM gateway, vector sinks, evaluation, audit, and visual/SVG processing.
- **Frontend** (Next.js) drives the full human-in-the-loop workflow.
- **Local stack**: PostgreSQL 17, Redis, MinIO, Qdrant via Docker Compose.
- **Production target**: Azure Container Apps + Flexible Server + Blob + Key Vault + AI Search (+ Service Bus migration path).

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/adr](docs/adr).

## Prerequisites

- Docker + Docker Compose v2
- (Optional for local non-Docker) Python 3.12, uv, Node.js 22, pnpm

## One-command startup

```bash
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
| MinIO console | http://localhost:9001 |
| Qdrant | http://localhost:6333 |

## Sample API calls

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/seed | jq .
curl -s http://localhost:8000/api/v1/strategies | jq '.[].strategy_id'
curl -s -X POST http://localhost:8000/api/v1/documents \
  -H 'X-Tenant-Id: tenant_dev' \
  -F file=@tests/fixtures/sample.md
```

## Running tests

```bash
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

## Known limitations

- Live OpenAI / Azure / Dify / AI Search connectivity is not claimed without credentials.
- Optional chunk providers are honestly marked unavailable when dependencies/sidecars are missing.
- Local object storage uses **adobe/s3mock** when the official MinIO image cannot be pulled.
- Celery workers are wired for all queues; the API also processes the indexing outbox inline after successful chunk runs so Compose demos remain reliable without shared in-memory Engine state across processes.
- Development auth (`AUTH_MODE=development`) is **not** production-safe.

## Troubleshooting

- Migrations race: only the `migration` service runs Alembic once (`python -m alembic upgrade head` from `db_migrations/`).
- Inter-container timeouts on nested VMs: run `./scripts/fix-docker-bridge-forwarding.sh` then restart Compose.
- Qdrant unhealthy: wait for healthcheck; indexing target may be `FAILED` until Qdrant is ready — use reindex.
- Frontend cannot reach API: ensure `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`.

## Security

See [SECURITY.md](SECURITY.md).
