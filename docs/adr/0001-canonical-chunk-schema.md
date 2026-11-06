# ADR 0001: Canonical Chunk Schema

## Status
Accepted

## Context
Multiple chunking libraries return incompatible shapes.

## Decision
All adapters normalize to CanonicalChunk v1.0.0. Provider fields live under extensions.provider_payload.

## Consequences
API never returns unnormalized library chunks as the primary response.
