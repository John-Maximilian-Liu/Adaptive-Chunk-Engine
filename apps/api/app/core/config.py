"""Pydantic Settings for Adaptive Chunk Engine."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Adaptive Chunk Engine"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    database_url: str = "postgresql+asyncpg://ace:ace@localhost:5432/ace"
    database_url_sync: str = "postgresql://ace:ace@localhost:5432/ace"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_bucket: str = "ace-documents"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ace_chunks"
    auth_mode: str = "development"  # development|entra_id — development is NOT production-safe
    max_upload_bytes: int = 50 * 1024 * 1024
    log_json: bool = True

    # Chunk constraints
    CHUNK_SIZE_DEFAULT: int = 512
    CHUNK_SIZE_MIN: int = 128
    CHUNK_SIZE_MAX: int = 4096
    CHUNK_OVERLAP_DEFAULT: int = 64
    CHUNK_OVERLAP_MAX_RATIO: float = 0.30
    CHUNK_HARD_TOKEN_LIMIT: int = 4096
    CHUNK_MAX_COUNT_PER_DOCUMENT: int = 100000
    CHUNK_MAX_CROSS_UNIT_SPAN: int = 2
    CHUNK_ALLOW_OVERSIZE_ATOMIC_BLOCK: bool = True

    QA_DEFAULT_COUNT: int = 50
    QA_MIN_COUNT: int = 1
    QA_MAX_COUNT: int = 1000

    EVAL_DEFAULT_TOP_K: int = 10
    EVAL_MAX_TOP_K: int = 100
    EVAL_TARGET_RECALL_AT_10: float = 0.95
    EVAL_MIN_COMPOSITE_RELATIVE_GAIN: float = 0.01
    EVAL_MIN_RECALL_ABSOLUTE_GAIN: float = 0.005
    EVAL_CRITICAL_SEGMENT_GAIN: float = 0.02

    OPTIMIZATION_MAX_ROUNDS: int = 10
    OPTIMIZATION_REQUIRE_HUMAN_TRIGGER: bool = True
    OPTIMIZATION_ALLOW_AUTOMATIC_EXECUTION: bool = False

    ALLOW_EXTERNAL_DOCUMENT_PROVIDER: bool = False
    ALLOW_EXTERNAL_LLM_FOR_SENSITIVE_DOCS: bool = False
    STORE_LLM_PROMPT_RESPONSE: bool = True

    # Visual
    VISUAL_PROCESSING_ENABLED: bool = True
    SVG_GENERATION_DEFAULT: str = "auto"
    SVG_MAX_SOURCE_IMAGE_PIXELS: int = 40_000_000
    SVG_MAX_FILE_SIZE_BYTES: int = 10_000_000
    SVG_MAX_ELEMENTS: int = 10_000
    SVG_MAX_PATH_COMMANDS: int = 200_000
    SVG_MAX_NESTING_DEPTH: int = 32
    SVG_ALLOW_EXTERNAL_REFERENCES: bool = False
    SVG_ALLOW_SCRIPTS: bool = False
    SVG_ALLOW_FOREIGN_OBJECT: bool = False
    SVG_MIN_CONFIDENCE: float = 0.80
    SVG_KEEP_ORIGINAL_RASTER: bool = True
    SVG_INDEX_RAW_XML: bool = False

    ZCHUNK_ENABLED: bool = False
    CHUNKR_BASE_URL: Optional[str] = None
    MARKDOWN_STRUCTURE_SIDECAR_URL: Optional[str] = None

    default_tenant_id: str = "tenant_dev"
    default_user_id: str = "user_dev"

    @field_validator("CHUNK_OVERLAP_MAX_RATIO")
    @classmethod
    def overlap_ratio(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("CHUNK_OVERLAP_MAX_RATIO must be between 0 and 1")
        return v

    def hard_constraints(self) -> dict:
        return {
            "CHUNK_SIZE_DEFAULT": self.CHUNK_SIZE_DEFAULT,
            "CHUNK_SIZE_MIN": self.CHUNK_SIZE_MIN,
            "CHUNK_SIZE_MAX": self.CHUNK_SIZE_MAX,
            "CHUNK_OVERLAP_DEFAULT": self.CHUNK_OVERLAP_DEFAULT,
            "CHUNK_OVERLAP_MAX_RATIO": self.CHUNK_OVERLAP_MAX_RATIO,
            "CHUNK_HARD_TOKEN_LIMIT": self.CHUNK_HARD_TOKEN_LIMIT,
            "CHUNK_MAX_COUNT_PER_DOCUMENT": self.CHUNK_MAX_COUNT_PER_DOCUMENT,
            "CHUNK_MAX_CROSS_UNIT_SPAN": self.CHUNK_MAX_CROSS_UNIT_SPAN,
            "CHUNK_ALLOW_OVERSIZE_ATOMIC_BLOCK": self.CHUNK_ALLOW_OVERSIZE_ATOMIC_BLOCK,
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
