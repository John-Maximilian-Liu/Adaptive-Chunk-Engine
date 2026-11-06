"""Parser adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from canonical_schemas.document import (
    DocumentVersionModel,
    LogicalUnitModel,
    ParserManifest,
)


@dataclass
class ParseResult:
    logical_units: list[LogicalUnitModel]
    parser_manifest: ParserManifest
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ParserAdapter(ABC):
    name: str = "base"
    version: str = "1.0.0"
    supported_extensions: list[str] = []

    @abstractmethod
    def parse(
        self,
        path: Path,
        *,
        tenant_id: str,
        document_version_id: str,
        filename: str,
    ) -> ParseResult:
        raise NotImplementedError

    def health_check(self) -> dict[str, Any]:
        return {"name": self.name, "available": True, "status": "healthy", "reason": None}


def detect_format(filename: str, content_type: Optional[str] = None) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    mapping = {
        "pdf": "pdf",
        "docx": "docx",
        "pptx": "pptx",
        "xlsx": "xlsx",
        "xls": "xls",
        "csv": "csv",
        "md": "md",
        "markdown": "md",
        "txt": "txt",
        "png": "png",
        "jpg": "jpeg",
        "jpeg": "jpeg",
        "tif": "tiff",
        "tiff": "tiff",
    }
    return mapping.get(ext, ext or "txt")


def get_parser_for(fmt: str) -> ParserAdapter:
    from document_parsers.registry import resolve_parser

    return resolve_parser(fmt)
