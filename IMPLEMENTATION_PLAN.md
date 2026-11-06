# Adaptive Chunk Engine — Implementation Plan

## Status
**Complete for MVP Definition of Done** — see `FINAL_REPORT.md` for verification evidence.

## Milestones

### M0 — Repository scaffold
- [x] Feature branch `cursor/adaptive-chunk-engine-606a`
- [x] Directory layout (apps, workers, packages, contracts, infrastructure, scripts, tests)
- [x] Root docs, Makefile, `.env.example`, compose files

### M1 — Canonical contracts
- [x] Pydantic models + JSON Schema for Document / Chunk / QA / Visual / Audit
- [x] OpenAPI skeleton + event schemas
- [x] Generated TypeScript types (packages/typescript)

### M2 — Python domain packages
- [x] `canonical_schemas`, `document_parsers`, `chunk_adapters`
- [x] `llm_gateway`, `vector_adapters`, `evaluation_engine`, `audit_sdk`
- [x] Visual processing (OCR/SVG/scene graph)

### M3 — API + persistence
- [x] FastAPI `/api/v1` routes
- [x] SQLAlchemy 2.x models + Alembic migrations (`db_migrations/`)
- [x] Settings, auth hooks, observability
- [x] Seed command (`POST /api/v1/admin/seed` + startup seed)

### M4 — Workers
- [x] Celery app with queues: parse, chunk, qa, embedding, indexing, evaluation, optimization
- [x] Transactional outbox → automatic indexing

### M5 — Frontend
- [x] Next.js + Tailwind pages for required workflows
- [x] API client helpers
- [x] Failure Analysis + Visual Review workbenches

### M6 — Infrastructure
- [x] Docker Compose (dev/prod overlays)
- [x] Azure Bicep + parameter files
- [x] CI workflows

### M7 — Tests & verification
- [x] Unit / contract / integration / e2e / security / migration tests
- [x] `docker compose up -d --build` smoke
- [x] Coverage report captured
- [x] `FINAL_REPORT.md`

## Vertical slices (runnable)
1. Health + version + seed tenant
2. Upload → parse → logical units
3. Plan → chunk → outbox → Qdrant index
4. QA generate/upload/complete → evaluate → failures → proposal → next experiment
5. Visual processing + SVG sanitize
6. Connections (LLM / embedding / sinks)

## Constraints
- No silent fake success for external providers
- Deterministic mock LLM for offline/demo
- Optional adapters degrade with health reasons
- Human-triggered optimization only

## Environment notes discovered during verification
- Local object storage uses `adobe/s3mock` when `minio/minio` is unavailable.
- Some nested-VM hosts need `scripts/fix-docker-bridge-forwarding.sh` so Compose bridge traffic is not dropped by `iptables-legacy`.
- Alembic scripts live in `apps/api/db_migrations` (not `alembic/`) to avoid shadowing the `alembic` package on `PYTHONPATH=/app`.
