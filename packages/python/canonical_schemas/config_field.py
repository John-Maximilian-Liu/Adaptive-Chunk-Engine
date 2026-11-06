"""Configuration field with precedence metadata."""
from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ConfigSource(str, Enum):
    HARD_ENVIRONMENT = "hard_environment"
    TENANT_POLICY = "tenant_policy"
    MANUAL_REGION = "manual_region"
    MANUAL_LOGICAL_UNIT = "manual_logical_unit"
    MANUAL_DOCUMENT = "manual_document"
    LLM_AUTO = "llm_auto"
    ENVIRONMENT_DEFAULT = "environment_default"


SOURCE_PRECEDENCE: dict[ConfigSource, int] = {
    ConfigSource.HARD_ENVIRONMENT: 1,
    ConfigSource.TENANT_POLICY: 2,
    ConfigSource.MANUAL_REGION: 3,
    ConfigSource.MANUAL_LOGICAL_UNIT: 4,
    ConfigSource.MANUAL_DOCUMENT: 5,
    ConfigSource.LLM_AUTO: 6,
    ConfigSource.ENVIRONMENT_DEFAULT: 7,
}


class ConfigField(BaseModel, Generic[T]):
    effective: Any
    source: ConfigSource
    original_proposed: Optional[Any] = None
    locked: bool = False
    mode: str = Field(default="auto", pattern="^(auto|manual)$")
    validation_result: Optional[dict[str, Any]] = None
    field_path: Optional[str] = None


def resolve_precedence(candidates: list[ConfigField]) -> ConfigField:
    if not candidates:
        raise ValueError("No configuration candidates provided")
    return sorted(candidates, key=lambda c: SOURCE_PRECEDENCE[c.source])[0]
