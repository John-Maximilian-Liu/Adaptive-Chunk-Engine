# Adaptive Chunk Engine — Final Report

## Implemented functionality

End-to-end Adaptive Chunk Engine monorepo covering:

- Document upload/parse for PDF, DOCX, PPTX, XLSX, CSV, Markdown, plain text, PNG/JPEG/TIFF (Docling-preferred with local fallbacks)
- Canonical document + CanonicalChunk v1.0.0 schemas, JSON Schema contracts, SQLAlchemy models, Alembic migrations
- Strategy registry with builtin + Excel strategies; optional providers degrade with health reasons
- Configuration precedence (env → tenant → region → unit → document → LLM Auto → default)
- LLM gateway (OpenAI, Azure OpenAI, deterministic mock)
- Chunk planning, chunk runs, transactional outbox → automatic indexing
- Vector sinks: Qdrant (engine-managed), Azure AI Search, Dify KB (+ stubs for future sinks)
- QA generation/upload/schema-completion, evaluation metrics + composite score + hard gates
- Failure classification, localized JSON Patch optimization proposals, human-only next experiment
- Evidence/audit + reproduction manifests
- Visual/SVG pipeline with sanitization and scene-graph rendering
- Next.js frontend workflows, Celery workers, Docker Compose, Azure Bicep, CI

## Architecture summary

```
Frontend (Next.js) → API (FastAPI /api/v1) → Engine domain service
                              ↓
                    PostgreSQL + Redis + Object storage + Qdrant
                              ↓
              Celery workers (parse/chunk/qa/embedding/indexing/evaluation)
```

Canonical schemas stay provider-neutral. Provider fields live under `extensions.provider_payload`. Optimization never auto-executes the next round.

## Exact startup commands

```bash
cp -n .env.example .env
# If inter-container networking fails on nested VMs:
./scripts/fix-docker-bridge-forwarding.sh
docker compose up -d --build
```

Local URLs:

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health/live

## Exact test commands

```bash
# Backend
cd apps/api
export PYTHONPATH=.:../../packages/python
pytest -q --cov=app --cov=../../packages/python

# Frontend
cd apps/web && pnpm test && pnpm typecheck

# Compose smoke
docker compose up -d --build
curl -s http://localhost:8000/api/v1/health/ready
```

## Test results

| Suite | Result |
|-------|--------|
| Backend pytest (unit/contract/integration/security/migration) | **69 passed** |
| Frontend Vitest | **1 passed** |
| Frontend `tsc --noEmit` | **pass** |
| Live Docker API smoke (upload→parse→plan→chunk→Qdrant verify→QA→eval→proposal→next experiment) | **pass** |
| Multi-format parse (PDF/DOCX/PPTX/XLSX/MD/PNG) via live API | **pass** |

## Coverage results

- Combined measured coverage (app + packages/python via pytest-cov): **~77%** statements
- Strong coverage on core domain modules (canonical schemas, metrics, config, many adapters)
- Lower coverage on broad FastAPI router surface and optional visual pipeline branches
- Honest gap vs aspirational 85% core-domain gate: router and optional provider paths need more API-level tests before claiming 85%+ on all packages

## Container health results

After `docker compose up -d --build` (with bridge-forwarding fix applied in this environment):

| Service | Status |
|---------|--------|
| postgres | healthy |
| redis | healthy |
| minio (adobe/s3mock fallback) | healthy |
| qdrant | healthy |
| migration | exited 0 (Alembic upgrade head) |
| api | healthy |
| frontend | running (HTTP 200) |
| worker-* (parser/chunk/qa/embedding/indexing/evaluation) | running |

## Supported adapter matrix

| Adapter | Operational locally | Notes |
|---------|---------------------|-------|
| builtin fixed_token / recursive / sentence / heading / parent_child / table_* / no_split / skip / markdown / spreadsheet / cross_unit | Yes | Deterministic |
| excel_table_row_group / excel_record_per_row / excel_region / excel_formula_dependency | Yes | Locators `file.xlsx#Sheet!A1:F18` |
| Docling Hierarchical/Hybrid | Optional | Disabled with reason if package missing |
| Chunkana / Chonkie / Chunkr / markdown-chunker / MarkdownStructureChunker / zchunk | Optional | Contract + health; unavailable until enabled |
| OpenAI / Azure OpenAI | Implemented | Live not verified without keys; mock used in tests |
| Mock LLM | Yes | Default for seed/demo |
| Qdrant | Yes | Verified live in Compose |
| Azure AI Search | Implemented | Contract-tested with HTTP mocks |
| Dify KB | Implemented | Contract-tested with HTTP mocks |

## Provider integrations tested with mocks

- Deterministic mock LLM (planning, QA, completion)
- Azure AI Search sink contract (respx/httpx mock)
- Dify Knowledge Base sink contract (mock)
- OpenAI / Azure OpenAI provider modules with mock/offline paths

## Provider integrations tested live

- **Qdrant** upsert + filtered verify against Compose Qdrant
- **PostgreSQL** Alembic migrations
- **Redis** Celery broker connectivity
- **S3Mock** object-storage health (MinIO image unavailable here)

No live OpenAI, Azure OpenAI, Azure AI Search, or Dify calls were made (no credentials).

## Known limitations

1. **Object storage**: `docker.io/minio/minio` was unavailable; Compose uses `adobe/s3mock` as the functioning local S3 API fallback.
2. **In-memory Engine MVP**: durable SQLAlchemy models + migrations exist; the request path primarily uses an in-process Engine store seeded at startup. Workers share Celery queues but not the API process memory — inline outbox processing in the API path is the verified automatic-indexing path for MVP demos.
3. **Nested-VM Docker networking**: some hosts drop Compose bridge traffic via `iptables-legacy`; run `scripts/fix-docker-bridge-forwarding.sh`.
4. **Optional chunk providers** are not falsely marked healthy when dependencies are missing.
5. **zchunk** disabled by default.
6. **Development auth** (`AUTH_MODE=development`) is explicitly not production-safe.
7. **Frontend Playwright e2e** is scaffolded; primary E2E proof for this run is the live API smoke against Compose.
8. Overall statement coverage ~77%; expand router/API tests to raise the gate.

## Security items still required before production

- Replace development auth with Microsoft Entra ID
- Key Vault–backed secrets only; no write-through secret reads
- Harden object-storage credentials and private networking
- Network policies / private endpoints for Postgres, Redis, AI Search
- Production CORS allowlists, rate limits, WAF
- Complete threat model for uploaded documents and LLM data residency
- Container image signing + continuous vulnerability scanning gates

## Azure deployment instructions

1. Build/push images tagged with immutable Git SHA to ACR.
2. Deploy `infrastructure/bicep/main.bicep` with `infrastructure/environments/{dev,test,prod}.bicepparam`.
3. Wire Key Vault references for DB, Redis, storage, OpenAI, AI Search, Dify.
4. Use managed identity for Azure OpenAI / AI Search / Blob where possible.
5. Do **not** deploy Compose to production; use Container Apps revisions.

Validate templates:

```bash
az bicep build -f infrastructure/bicep/main.bicep
```

## Files and modules changed

Primary tree under repository root:

- `apps/api` — FastAPI, Engine, Alembic `db_migrations`, Dockerfiles
- `apps/web` — Next.js UI
- `workers/*` — Celery task modules
- `packages/python/*` — domain packages
- `packages/typescript/*` — client/schema/ui packages
- `contracts/` — JSON Schema / OpenAPI / events
- `infrastructure/bicep` — Azure templates
- `compose.yaml`, `compose.dev.yaml`, `compose.prod.yaml`
- `scripts/`, docs, ADRs, CI workflows, fixtures, tests

Notable fixes during verification:

- Renamed Alembic dir to `db_migrations` (package shadowing)
- Added `psycopg[binary]` for sync migrations
- Idempotent Qdrant point IDs + delete-before-upsert; attach `indexing_run_id` on chunk runs
- S3Mock fallback; Docker bridge forwarding helper

## Recommended next steps

1. Persist Engine state fully through async SQLAlchemy sessions (replace in-memory maps).
2. Shared durable outbox processor as the sole indexing trigger across API replicas.
3. Raise API router coverage with FastAPI TestClient route suites to ≥85% core-domain.
4. Expand Playwright critical-path coverage against Compose.
5. Enable optional chunk providers behind documented feature flags once licenses reviewed.
6. Activate real Azure OpenAI + AI Search in a non-prod environment and record live verification.
