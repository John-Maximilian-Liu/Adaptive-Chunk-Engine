
"""Canonical schemas for Adaptive Chunk Engine."""
from .chunk import CanonicalChunk, CHUNK_SCHEMA_VERSION
from .document import (
    DocumentModel, DocumentVersionModel, LogicalUnitModel, RegionModel,
    ElementModel, ElementType, ParseRunModel, ParserManifest, Locator,
)
from .qa import QAItem, QADataset, QA_SCHEMA_VERSION, QADistribution, MatchingPolicy
from .visual import (
    VisualArtifact, VisualSceneGraph, VisualNode, VisualEdge, VisualGroup,
    VisualProcessingRun, VisualQualityResult, VisualProcessingPolicy,
)
from .config_field import ConfigField, ConfigSource, SOURCE_PRECEDENCE, resolve_precedence
from .evaluation import (
    EvaluationProfile, MetricDefinition, MetricResult, StoppingRecommendation,
    normalize_weights, normalize_metric_value, compute_composite, recommend_stopping,
    DEFAULT_METRICS,
)
from .audit import AuditEvent, ProviderManifest, ReproductionManifest

__all__ = [
    "CanonicalChunk", "CHUNK_SCHEMA_VERSION",
    "DocumentModel", "DocumentVersionModel", "LogicalUnitModel", "RegionModel",
    "ElementModel", "ElementType", "ParseRunModel", "ParserManifest", "Locator",
    "QAItem", "QADataset", "QA_SCHEMA_VERSION", "QADistribution", "MatchingPolicy",
    "VisualArtifact", "VisualSceneGraph", "VisualNode", "VisualEdge", "VisualGroup",
    "VisualProcessingRun", "VisualQualityResult", "VisualProcessingPolicy",
    "ConfigField", "ConfigSource", "SOURCE_PRECEDENCE", "resolve_precedence",
    "EvaluationProfile", "MetricDefinition", "MetricResult", "StoppingRecommendation",
    "normalize_weights", "normalize_metric_value", "compute_composite", "recommend_stopping",
    "DEFAULT_METRICS",
    "AuditEvent", "ProviderManifest", "ReproductionManifest",
]
