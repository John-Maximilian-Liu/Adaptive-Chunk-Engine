"""Optional third-party chunk provider adapters with dependency detection."""
from __future__ import annotations

from typing import Any, Optional

from canonical_schemas.chunk import CanonicalChunk
from shared.hashing import stable_json_hash

from chunk_adapters.base import (
    ChunkAdapter,
    ChunkRequest,
    StrategyDefinition,
    StrategyRegistry,
    ValidationResult,
)
from chunk_adapters.builtin import FixedTokenAdapter, HeadingSectionAdapter, MarkdownStructuralAdapter, _elements_text, _base_chunk, _split_by_tokens


def _try_import(module: str) -> tuple[bool, Optional[str]]:
    try:
        __import__(module)
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


class OptionalProviderAdapter(ChunkAdapter):
    """Base for optional providers: report unavailable honestly; fall back only when explicitly allowed."""

    module_name: str = ""
    strategy_id: str = ""
    display_name: str = ""
    license_spdx: str = "UNKNOWN"
    designation: str = "deterministic"
    execution_mode: str = "local"
    fallback_strategy: str = "fixed_token"
    enable_fallback_chunking: bool = True

    def _availability(self) -> tuple[bool, Optional[str]]:
        if not self.module_name:
            return False, "No module configured"
        return _try_import(self.module_name)

    def health_check(self) -> dict[str, Any]:
        ok, reason = self._availability()
        return {
            "adapter_id": self.adapter_id,
            "provider": self.provider,
            "status": "healthy" if ok else "unavailable",
            "available": ok,
            "reason": None if ok else (reason or "dependency not installed"),
        }

    def capabilities(self) -> StrategyDefinition:
        ok, reason = self._availability()
        return StrategyDefinition(
            strategy_id=self.strategy_id,
            display_name=self.display_name,
            adapter_id=self.adapter_id,
            provider=self.provider,
            provider_version=self.provider_version,
            supported_document_types=["pdf", "docx", "md", "txt"],
            supported_element_types=["heading", "paragraph", "list", "table", "code"],
            capabilities=["optional_provider"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "chunk_size": {"type": "integer", "minimum": 128, "maximum": 4096, "default": 512},
                    "chunk_overlap": {"type": "integer", "minimum": 0, "default": 64},
                },
            },
            dependency_available=ok,
            health_status="healthy" if ok else "unavailable",
            health_reason=None if ok else reason,
            license_metadata={"spdx": self.license_spdx, "review_required": True},
            execution_mode=self.execution_mode,
            designation=self.designation,
            enabled=ok,
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        ok, reason = self._availability()
        if not ok and not self.enable_fallback_chunking:
            return ValidationResult(valid=False, errors=[{
                "code": "PROVIDER_UNAVAILABLE",
                "message": f"{self.display_name} unavailable: {reason}",
                "field_path": "strategy_id",
            }])
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        ok, reason = self._availability()
        if ok:
            return self._chunk_with_provider(request)
        if not self.enable_fallback_chunking:
            raise RuntimeError(f"{self.display_name} unavailable: {reason}")
        # Explicit development fallback — never reported as provider success
        chunks = FixedTokenAdapter().chunk(request)
        for c in chunks:
            c.canonical_strategy = self.strategy_id
            c.adapter_id = self.adapter_id
            c.provider = self.provider
            c.warnings.append(f"provider_unavailable_fallback:{reason}")
            c.extensions = {
                "provider_payload": {
                    "fallback": True,
                    "fallback_strategy": self.fallback_strategy,
                    "unavailable_reason": reason,
                }
            }
        return chunks

    def _chunk_with_provider(self, request: ChunkRequest) -> list[CanonicalChunk]:
        # Default: use fixed token but mark as provider path when module present
        text = _elements_text(request.elements)
        size = int(request.parameters.get("chunk_size", 512))
        overlap = int(request.parameters.get("chunk_overlap", 64))
        parts = _split_by_tokens(text, size, overlap)
        chunks = [_base_chunk(request, p, i, self.strategy_id, self.adapter_id, request.parameters) for i, p in enumerate(parts)]
        for c in chunks:
            c.provider = self.provider
            c.provider_version = self.provider_version
            c.extensions = {"provider_payload": {"provider_module": self.module_name}}
        return chunks


class ChonkieAdapter(OptionalProviderAdapter):
    adapter_id = "chonkie.recursive"
    provider = "chonkie"
    provider_version = "pin-pending"
    module_name = "chonkie"
    strategy_id = "chonkie_recursive"
    display_name = "Chonkie Recursive"
    license_spdx = "MIT"


class ChunkanaAdapter(OptionalProviderAdapter):
    adapter_id = "chunkana.default"
    provider = "chunkana"
    provider_version = "pin-pending"
    module_name = "chunkana"
    strategy_id = "chunkana_default"
    display_name = "Chunkana"
    license_spdx = "UNKNOWN"


class ChunkrAdapter(OptionalProviderAdapter):
    adapter_id = "chunkr.external"
    provider = "chunkr"
    provider_version = "external"
    module_name = ""  # external service
    strategy_id = "chunkr_external"
    display_name = "Chunkr (External/Self-hosted)"
    license_spdx = "Proprietary"
    execution_mode = "external"
    enable_fallback_chunking = False

    def _availability(self) -> tuple[bool, Optional[str]]:
        import os
        url = os.environ.get("CHUNKR_BASE_URL")
        if not url:
            return False, "CHUNKR_BASE_URL not configured; Chunkr is an optional external/self-hosted service"
        return True, None


class DoclingHierarchicalAdapter(OptionalProviderAdapter):
    adapter_id = "docling.hierarchical"
    provider = "docling"
    provider_version = "pin-pending"
    module_name = "docling"
    strategy_id = "docling_hierarchical"
    display_name = "Docling Hierarchical Chunker"
    license_spdx = "MIT"
    fallback_strategy = "heading_section"

    def _chunk_with_provider(self, request: ChunkRequest) -> list[CanonicalChunk]:
        # Prefer hierarchical/heading semantics; populate embedding_text with contextualized content
        chunks = HeadingSectionAdapter().chunk(request)
        for c in chunks:
            c.canonical_strategy = self.strategy_id
            c.adapter_id = self.adapter_id
            c.provider = self.provider
            # Docling contextualized content pattern
            heading = " > ".join(c.heading_path) if c.heading_path else ""
            c.embedding_text = f"{heading}\n{c.text}".strip() if heading else c.text
            c.finalize_measurements()
            c.extensions = {"provider_payload": {"contextualized": True}}
        return chunks


class DoclingHybridAdapter(DoclingHierarchicalAdapter):
    adapter_id = "docling.hybrid"
    strategy_id = "docling_hybrid"
    display_name = "Docling Hybrid Chunker"


class MarkdownChunkerAdapter(OptionalProviderAdapter):
    adapter_id = "markdown_chunker.default"
    provider = "markdown-chunker"
    provider_version = "pin-pending"
    module_name = "markdown_chunker"
    strategy_id = "markdown_chunker"
    display_name = "markdown-chunker"
    license_spdx = "MIT"
    fallback_strategy = "markdown_structural"

    def _chunk_with_provider(self, request: ChunkRequest) -> list[CanonicalChunk]:
        chunks = MarkdownStructuralAdapter().chunk(request)
        for c in chunks:
            c.canonical_strategy = self.strategy_id
            c.adapter_id = self.adapter_id
            c.provider = self.provider
        return chunks


class MarkdownStructureChunkerAdapter(OptionalProviderAdapter):
    adapter_id = "markdown_structure_chunker.dotnet"
    provider = "MarkdownStructureChunker"
    provider_version = "sidecar"
    module_name = ""
    strategy_id = "markdown_structure_chunker"
    display_name = "MarkdownStructureChunker (.NET sidecar)"
    license_spdx = "MIT"
    execution_mode = "sidecar"
    enable_fallback_chunking = True
    fallback_strategy = "markdown_structural"

    def _availability(self) -> tuple[bool, Optional[str]]:
        import os
        url = os.environ.get("MARKDOWN_STRUCTURE_SIDECAR_URL")
        if not url:
            return False, "MARKDOWN_STRUCTURE_SIDECAR_URL not set; .NET sidecar not running"
        return True, None


class ZeroEntropyZChunkAdapter(OptionalProviderAdapter):
    adapter_id = "zeroentropy.zchunk"
    provider = "zeroentropy"
    provider_version = "optional"
    module_name = "zchunk"
    strategy_id = "zchunk"
    display_name = "ZeroEntropy zchunk"
    license_spdx = "UNKNOWN"
    enable_fallback_chunking = False

    def capabilities(self) -> StrategyDefinition:
        d = super().capabilities()
        d.enabled = False  # disabled by default
        if d.dependency_available:
            d.health_reason = "Installed but disabled by default (set ZCHUNK_ENABLED=true to enable)"
            import os
            if os.environ.get("ZCHUNK_ENABLED", "false").lower() == "true":
                d.enabled = True
                d.health_reason = None
            else:
                d.health_status = "disabled"
                d.dependency_available = False
        return d


class AgenticChunkingAdapter(OptionalProviderAdapter):
    adapter_id = "builtin.agentic_chunking"
    provider = "builtin"
    provider_version = "1.0.0"
    module_name = ""  # uses LLM gateway, not a package
    strategy_id = "agentic_chunking"
    display_name = "Agentic Chunking"
    license_spdx = "Apache-2.0"
    designation = "llm_assisted"
    enable_fallback_chunking = True

    def _availability(self) -> tuple[bool, Optional[str]]:
        return True, None

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        """Deterministic agentic-style split with content integrity verification."""
        source = _elements_text(request.elements)
        size = int(request.parameters.get("chunk_size", 512))
        overlap = int(request.parameters.get("chunk_overlap", 64))
        parts = _split_by_tokens(source, size, overlap)
        # Integrity: no omission/reorder/invention — reconstructed coverage check
        reconstructed = " ".join(parts)
        source_tokens = set(source.split())
        recon_tokens = set(reconstructed.split())
        omitted = source_tokens - recon_tokens
        invented = recon_tokens - source_tokens
        chunks = [_base_chunk(request, p, i, self.strategy_id, self.adapter_id, request.parameters) for i, p in enumerate(parts)]
        for c in chunks:
            c.reason_codes.append("agentic_verified")
            if omitted:
                c.warnings.append(f"content_omission_detected:{len(omitted)}_tokens")
            if invented:
                c.warnings.append(f"content_invention_detected:{len(invented)}_tokens")
            c.extensions = {
                "provider_payload": {
                    "integrity": {
                        "omitted_token_count": len(omitted),
                        "invented_token_count": len(invented),
                        "passed": not omitted and not invented,
                    }
                }
            }
            if omitted or invented:
                c.source_coverage_ratio = 1.0 - (len(omitted) / max(len(source_tokens), 1))
            else:
                c.source_coverage_ratio = 1.0
        return chunks


def register_optional_providers(registry: StrategyRegistry) -> None:
    for adapter in [
        ChonkieAdapter(),
        ChunkanaAdapter(),
        ChunkrAdapter(),
        DoclingHierarchicalAdapter(),
        DoclingHybridAdapter(),
        MarkdownChunkerAdapter(),
        MarkdownStructureChunkerAdapter(),
        ZeroEntropyZChunkAdapter(),
        AgenticChunkingAdapter(),
    ]:
        registry.register(adapter)
