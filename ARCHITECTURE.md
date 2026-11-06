# Architecture

## Component diagram

```mermaid
flowchart LR
  Web[Next.js Frontend] --> API[FastAPI API]
  API --> PG[(PostgreSQL)]
  API --> Redis[(Redis Broker)]
  API --> MinIO[(MinIO/Blob)]
  API --> Workers[Celery Workers]
  Workers --> PG
  Workers --> Qdrant[(Qdrant)]
  Workers --> AzureSearch[Azure AI Search]
  Workers --> Dify[Dify KB]
  API --> LLM[LLM Gateway]
  LLM --> Mock[Mock Provider]
  LLM --> OpenAI
  LLM --> AzureOpenAI
```

## Sequence: parse → chunk → index → evaluate → optimize

```mermaid
sequenceDiagram
  participant U as User
  participant API as API
  participant W as Workers
  participant OB as Outbox
  participant V as Vector Sink
  U->>API: Upload document
  U->>API: Parse
  API->>W: parse queue / inline
  U->>API: Auto plan (LLM)
  U->>API: Review/edit plan
  U->>API: Create chunk run
  API->>W: chunk
  W->>OB: CHUNK_RUN_COMPLETED
  OB->>W: indexing run
  W->>V: upsert + verify
  U->>API: Generate/upload QA
  U->>API: Evaluate
  API->>V: search Top-K
  API->>API: metrics + failures
  U->>API: Optimization proposal review
  U->>API: Create next experiment (manual)
```

## Canonical schema

`CanonicalChunk` v1.0.0 groups identity, content, measurements, source locators, relationships, strategy, decision evidence, quality, indexing, and extensions. Library-specific fields belong under `extensions.provider_payload`.

## Configuration precedence

1. Hard environment constraint  
2. Tenant policy  
3. Manual region override  
4. Manual logical-unit override  
5. Manual document configuration  
6. LLM Auto recommendation  
7. Environment default  

Invalid manual values are rejected with structured errors (never silently clamped).

## Evidence model

Append-only `AuditEvent` records plus `ProviderManifest` and `ReproductionManifest`. Production candidacy requires a complete reproduction manifest.

## Deployment architecture

Local: Docker Compose.  
Production: Azure Container Apps revisions consuming the same images, secrets via Key Vault references, managed identities where possible.

## Failure boundaries

- Optional sink failure does not roll back other sinks (`PARTIAL`).
- Parser / QA ground-truth / indexing integrity failures are not treated as chunk-size optimization opportunities.
- Optimization never auto-executes.
