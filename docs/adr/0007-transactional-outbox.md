# ADR 0007: Transactional Outbox for Indexing

## Decision
Successful chunk runs emit CHUNK_RUN_COMPLETED outbox events; indexing is asynchronous and never synchronous in the chunk API.
