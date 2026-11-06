"""Parser registry with Docling preferred path."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from document_parsers.base import ParserAdapter, ParseResult
from document_parsers.fallbacks import (
    CsvParser,
    DocxParser,
    ImageParser,
    MarkdownParser,
    PdfParser,
    PlainTextParser,
    PptxParser,
    XlsxParser,
)


class DoclingPreferredParser(ParserAdapter):
    """Try Docling first; fall back to local parsers. Never requires network."""

    name = "docling-preferred"
    version = "1.0.0"

    def __init__(self, fallback: ParserAdapter, fmt: str):
        self.fallback = fallback
        self.fmt = fmt
        self.supported_extensions = list(fallback.supported_extensions)

    def health_check(self) -> dict[str, Any]:
        try:
            import docling  # noqa: F401
            return {"name": self.name, "available": True, "status": "healthy", "reason": None, "fallback": self.fallback.name}
        except Exception as exc:  # noqa: BLE001
            return {
                "name": self.name,
                "available": True,  # fallback keeps system operational
                "status": "degraded",
                "reason": f"docling unavailable ({exc}); using {self.fallback.name}",
                "fallback": self.fallback.name,
            }

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(str(path))
            # Minimal mapping: export markdown-ish text into fallback-compatible units via markdown parser path
            md = result.document.export_to_markdown() if hasattr(result.document, "export_to_markdown") else str(result.document)
            tmp = path.with_suffix(".docling.md")
            tmp.write_text(md, encoding="utf-8")
            parsed = MarkdownParser().parse(tmp, tenant_id=tenant_id, document_version_id=document_version_id, filename=filename)
            tmp.unlink(missing_ok=True)
            parsed.parser_manifest.provider = "docling"
            parsed.parser_manifest.fallback_used = False
            parsed.parser_manifest.version = getattr(__import__("docling"), "__version__", "unknown")
            return parsed
        except Exception as exc:  # noqa: BLE001
            parsed = self.fallback.parse(path, tenant_id=tenant_id, document_version_id=document_version_id, filename=filename)
            parsed.warnings.append(f"docling_fallback:{exc}")
            parsed.parser_manifest.fallback_used = True
            return parsed


_FALLBACKS: dict[str, ParserAdapter] = {
    "pdf": PdfParser(),
    "docx": DocxParser(),
    "pptx": PptxParser(),
    "xlsx": XlsxParser(),
    "xls": XlsxParser(),
    "csv": CsvParser(),
    "md": MarkdownParser(),
    "markdown": MarkdownParser(),
    "txt": PlainTextParser(),
    "png": ImageParser(),
    "jpeg": ImageParser(),
    "jpg": ImageParser(),
    "tiff": ImageParser(),
    "tif": ImageParser(),
}


def resolve_parser(fmt: str) -> ParserAdapter:
    key = fmt.lower().lstrip(".")
    fallback = _FALLBACKS.get(key, PlainTextParser())
    # Prefer Docling for supported office/pdf/md types
    if key in {"pdf", "docx", "pptx", "xlsx", "md", "markdown", "png", "jpeg", "jpg"}:
        return DoclingPreferredParser(fallback, key)
    return fallback


def list_parsers() -> list[dict[str, Any]]:
    out = []
    for fmt, fb in _FALLBACKS.items():
        adapter = resolve_parser(fmt)
        health = adapter.health_check()
        out.append({
            "format": fmt,
            "parser": adapter.name,
            "fallback": fb.name,
            **health,
        })
    return out
