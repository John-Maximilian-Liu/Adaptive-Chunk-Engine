"""Vector destination adapters."""
from typing import Optional

from vector_adapters.base import CanonicalVectorRecord, SearchHit, VectorSinkAdapter, VectorSinkProfile
from vector_adapters.qdrant_sink import QdrantSink
from vector_adapters.azure_ai_search import AzureAISearchSink
from vector_adapters.dify_sink import DifyKnowledgeBaseSink
from vector_adapters.stubs import (
    PgvectorSink, MilvusSink, OpenSearchSink, PineconeSink, WeaviateSink, GenericRestSink,
)


def create_sink(profile: VectorSinkProfile, secret: Optional[str] = None) -> VectorSinkAdapter:
    t = profile.sink_type
    conn = profile.connection or {}
    if t == "qdrant":
        return QdrantSink(url=conn.get("url", "http://localhost:6333"), collection=profile.collection_or_index, api_key=secret)
    if t == "azure_ai_search":
        return AzureAISearchSink(
            endpoint=conn.get("endpoint", ""),
            index_name=profile.collection_or_index,
            api_key=secret,
            auth_mode=conn.get("auth_mode", "api_key"),
        )
    if t == "dify":
        return DifyKnowledgeBaseSink(
            base_url=conn.get("base_url", ""),
            api_key=secret or "",
            dataset_id=conn.get("dataset_id", profile.collection_or_index),
        )
    mapping = {
        "pgvector": PgvectorSink,
        "milvus": MilvusSink,
        "opensearch": OpenSearchSink,
        "pinecone": PineconeSink,
        "weaviate": WeaviateSink,
        "generic_rest": GenericRestSink,
    }
    cls = mapping.get(t)
    if not cls:
        raise ValueError(f"Unknown sink type: {t}")
    return cls()


__all__ = [
    "CanonicalVectorRecord", "SearchHit", "VectorSinkAdapter", "VectorSinkProfile",
    "QdrantSink", "AzureAISearchSink", "DifyKnowledgeBaseSink",
    "PgvectorSink", "MilvusSink", "OpenSearchSink", "PineconeSink", "WeaviateSink", "GenericRestSink",
    "create_sink",
]
