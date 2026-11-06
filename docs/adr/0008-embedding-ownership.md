# ADR 0008: Engine-managed vs Sink-managed Embeddings

## Decision
Qdrant and Azure AI Search use engine-managed embeddings. Dify normally uses sink-managed embeddings. Scores are not directly comparable without normalization metadata.
