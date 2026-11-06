"""Built-in deterministic chunk strategies."""
from __future__ import annotations

import re
from typing import Any

from canonical_schemas.chunk import CanonicalChunk, LocatorRef, SourceSpan, LogicalUnitSpan
from canonical_schemas.document import ElementModel
from shared.hashing import stable_json_hash
from shared.ids import new_id
from shared.tokens import count_tokens, truncate_to_tokens

from chunk_adapters.base import (
    ChunkAdapter,
    ChunkRequest,
    StrategyDefinition,
    StrategyRegistry,
    ValidationResult,
)


SIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "chunk_size": {"type": "integer", "minimum": 128, "maximum": 4096, "default": 512},
        "chunk_overlap": {"type": "integer", "minimum": 0, "default": 64},
    },
}


def _elements_text(elements: list[ElementModel]) -> str:
    return "\n".join(e.text for e in elements if e.text).strip()


def _validate_size_params(params: dict[str, Any], hard: dict[str, Any]) -> ValidationResult:
    errors: list[dict[str, Any]] = []
    size = params.get("chunk_size", hard.get("CHUNK_SIZE_DEFAULT", 512))
    overlap = params.get("chunk_overlap", hard.get("CHUNK_OVERLAP_DEFAULT", 64))
    size_min = hard.get("CHUNK_SIZE_MIN", 128)
    size_max = hard.get("CHUNK_SIZE_MAX", 4096)
    overlap_max_ratio = hard.get("CHUNK_OVERLAP_MAX_RATIO", 0.30)
    if not isinstance(size, int) or size < size_min or size > size_max:
        errors.append({
            "code": "INVALID_CHUNK_SIZE",
            "message": f"chunk_size must be between {size_min} and {size_max}",
            "field_path": "parameters.chunk_size",
            "allowed_range": [size_min, size_max],
            "value": size,
        })
    if not isinstance(overlap, int) or overlap < 0:
        errors.append({
            "code": "INVALID_CHUNK_OVERLAP",
            "message": "chunk_overlap must be a non-negative integer",
            "field_path": "parameters.chunk_overlap",
            "value": overlap,
        })
    elif isinstance(size, int) and size > 0 and overlap / size > overlap_max_ratio:
        errors.append({
            "code": "INVALID_CHUNK_OVERLAP_RATIO",
            "message": f"chunk_overlap/chunk_size must be <= {overlap_max_ratio}",
            "field_path": "parameters.chunk_overlap",
            "allowed_range": [0, overlap_max_ratio],
            "value": overlap / size if size else None,
        })
    return ValidationResult(valid=len(errors) == 0, errors=errors)


def _base_chunk(request: ChunkRequest, text: str, ordinal: int, strategy: str, adapter_id: str, params: dict) -> CanonicalChunk:
    elements = request.elements
    unit = request.logical_unit
    locators = []
    for e in elements:
        locators.append(LocatorRef(
            page=e.locator.page,
            slide=e.locator.slide,
            sheet=e.locator.sheet,
            range=e.locator.range,
            bbox=e.locator.bbox,
            element_id=e.element_id,
            heading_path=e.locator.heading_path,
            uri=e.locator.uri,
            locator_type=e.locator.locator_type,
        ))
    chunk = CanonicalChunk(
        chunk_run_id=request.chunk_run_id,
        document_id=request.document_id,
        document_version_id=request.document_version_id,
        experiment_id=request.experiment_id,
        tenant_id=request.tenant_id,
        ordinal=ordinal,
        text=text,
        embedding_text=text,
        logical_unit_ids=[unit.logical_unit_id],
        logical_unit_span=LogicalUnitSpan(
            start_ordinal=unit.ordinal,
            end_ordinal=unit.ordinal,
            unit_ids=[unit.logical_unit_id],
        ),
        region_ids=[request.region.region_id] if request.region else [r.region_id for r in unit.regions],
        element_ids=[e.element_id for e in elements],
        locators=locators,
        source_spans=[SourceSpan(element_id=e.element_id, char_start=0, char_end=len(e.text or ""), text_excerpt=(e.text or "")[:200]) for e in elements],
        heading_path=next((e.locator.heading_path or [] for e in elements if e.locator.heading_path), []),
        canonical_strategy=strategy,
        adapter_id=adapter_id,
        provider="builtin",
        provider_version="1.0.0",
        parameters=params,
        configuration_hash=stable_json_hash(params),
    )
    return chunk.finalize_measurements()


def _split_by_tokens(text: str, size: int, overlap: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    if not words:
        return [text]
    # approximate: treat each word as ~1.3 tokens
    chunks: list[str] = []
    start = 0
    while start < len(words):
        # grow until token budget
        end = start
        while end < len(words) and count_tokens(" ".join(words[start:end + 1])) <= size:
            end += 1
        if end == start:
            end = start + 1
        piece = " ".join(words[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= len(words):
            break
        # overlap in words
        overlap_words = max(0, int(overlap / max(size, 1) * (end - start)))
        start = max(start + 1, end - overlap_words)
    return chunks or [text]


class FixedTokenAdapter(ChunkAdapter):
    adapter_id = "builtin.fixed_token"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="fixed_token",
            display_name="Fixed Token",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "pptx", "md", "txt", "csv", "xlsx", "png", "jpeg", "tiff"],
            supported_element_types=["heading", "paragraph", "list", "code", "ocr_text"],
            capabilities=["deterministic", "overlap"],
            parameter_schema=SIZE_SCHEMA,
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return _validate_size_params(request.parameters, request.hard_constraints)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        text = _elements_text(request.elements)
        size = int(request.parameters.get("chunk_size", 512))
        overlap = int(request.parameters.get("chunk_overlap", 64))
        parts = _split_by_tokens(text, size, overlap)
        return [_base_chunk(request, p, i, "fixed_token", self.adapter_id, request.parameters) for i, p in enumerate(parts)]


class RecursiveTextAdapter(ChunkAdapter):
    adapter_id = "builtin.recursive_text"
    SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="recursive_text",
            display_name="Recursive Text",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "md", "txt"],
            supported_element_types=["heading", "paragraph", "list", "code"],
            capabilities=["deterministic", "recursive_split"],
            parameter_schema=SIZE_SCHEMA,
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return _validate_size_params(request.parameters, request.hard_constraints)

    def _split(self, text: str, size: int, seps: list[str]) -> list[str]:
        if count_tokens(text) <= size or not seps:
            return [text] if text else []
        sep = seps[0]
        parts = text.split(sep) if sep else list(text)
        out: list[str] = []
        buf = ""
        for part in parts:
            candidate = (buf + sep + part) if buf else part
            if count_tokens(candidate) <= size:
                buf = candidate
            else:
                if buf:
                    out.extend(self._split(buf, size, seps[1:]))
                buf = part
        if buf:
            out.extend(self._split(buf, size, seps[1:]))
        return [o for o in out if o.strip()]

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        text = _elements_text(request.elements)
        size = int(request.parameters.get("chunk_size", 512))
        parts = self._split(text, size, self.SEPARATORS)
        return [_base_chunk(request, p, i, "recursive_text", self.adapter_id, request.parameters) for i, p in enumerate(parts)]


class SentenceWindowAdapter(ChunkAdapter):
    adapter_id = "builtin.sentence_window"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="sentence_window",
            display_name="Sentence Window",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "md", "txt"],
            supported_element_types=["paragraph", "heading"],
            capabilities=["deterministic", "window"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "window_size": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                    "chunk_size": {"type": "integer", "minimum": 128, "maximum": 4096, "default": 512},
                },
            },
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return _validate_size_params({**request.parameters, "chunk_overlap": 0}, {**request.hard_constraints, "CHUNK_OVERLAP_MAX_RATIO": 1.0})

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        text = _elements_text(request.elements)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        window = int(request.parameters.get("window_size", 3))
        parts = []
        for i in range(len(sentences)):
            start = max(0, i - window // 2)
            end = min(len(sentences), start + window)
            parts.append(" ".join(sentences[start:end]))
        # dedupe consecutive identical
        deduped = []
        for p in parts:
            if not deduped or deduped[-1] != p:
                deduped.append(p)
        return [_base_chunk(request, p, i, "sentence_window", self.adapter_id, request.parameters) for i, p in enumerate(deduped or [text])]


class HeadingSectionAdapter(ChunkAdapter):
    adapter_id = "builtin.heading_section"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="heading_section",
            display_name="Heading Section",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "md"],
            supported_element_types=["heading", "paragraph", "list", "table"],
            capabilities=["structure_aware"],
            parameter_schema=SIZE_SCHEMA,
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return _validate_size_params(request.parameters, request.hard_constraints)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        size = int(request.parameters.get("chunk_size", 512))
        sections: list[tuple[str, list[ElementModel]]] = []
        current_heading = ""
        buf: list[ElementModel] = []
        for e in request.elements:
            if e.element_type.value == "heading":
                if buf:
                    sections.append((current_heading, buf))
                current_heading = e.text
                buf = [e]
            else:
                buf.append(e)
        if buf:
            sections.append((current_heading, buf))
        results: list[CanonicalChunk] = []
        ordinal = 0
        for heading, elems in sections or [("", request.elements)]:
            text = _elements_text(elems)
            for part in _split_by_tokens(text, size, int(request.parameters.get("chunk_overlap", 64))):
                c = _base_chunk(request, part, ordinal, "heading_section", self.adapter_id, request.parameters)
                c.heading_path = [heading] if heading else c.heading_path
                c.element_ids = [e.element_id for e in elems]
                results.append(c)
                ordinal += 1
        return results


class ParentChildAdapter(ChunkAdapter):
    adapter_id = "builtin.parent_child"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="parent_child",
            display_name="Parent-Child",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "md"],
            supported_element_types=["heading", "paragraph"],
            capabilities=["hierarchy"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "parent_size": {"type": "integer", "minimum": 128, "maximum": 4096, "default": 1024},
                    "child_size": {"type": "integer", "minimum": 128, "maximum": 4096, "default": 256},
                    "chunk_overlap": {"type": "integer", "minimum": 0, "default": 32},
                },
            },
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        params = {
            "chunk_size": request.parameters.get("parent_size", 1024),
            "chunk_overlap": request.parameters.get("chunk_overlap", 32),
        }
        return _validate_size_params(params, request.hard_constraints)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        text = _elements_text(request.elements)
        parent_size = int(request.parameters.get("parent_size", 1024))
        child_size = int(request.parameters.get("child_size", 256))
        overlap = int(request.parameters.get("chunk_overlap", 32))
        parents = _split_by_tokens(text, parent_size, overlap)
        results: list[CanonicalChunk] = []
        ordinal = 0
        for parent_text in parents:
            parent = _base_chunk(request, parent_text, ordinal, "parent_child", self.adapter_id, request.parameters)
            parent.chunk_type = "parent"
            parent_id = parent.chunk_id
            results.append(parent)
            ordinal += 1
            children = _split_by_tokens(parent_text, child_size, overlap // 2)
            child_ids = []
            for child_text in children:
                child = _base_chunk(request, child_text, ordinal, "parent_child", self.adapter_id, request.parameters)
                child.chunk_type = "child"
                child.parent_chunk_id = parent_id
                child_ids.append(child.chunk_id)
                results.append(child)
                ordinal += 1
            parent.child_chunk_ids = child_ids
        return results


class TableAtomicAdapter(ChunkAdapter):
    adapter_id = "builtin.table_atomic"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="table_atomic",
            display_name="Table Atomic",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "xlsx", "csv"],
            supported_element_types=["table"],
            capabilities=["table", "atomic"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        tables = [e for e in request.elements if e.element_type.value in ("table", "table_row")]
        if not tables:
            text = _elements_text(request.elements)
            return [_base_chunk(request, text, 0, "table_atomic", self.adapter_id, request.parameters)] if text else []
        # group contiguous table elements as one atomic block
        text = _elements_text(tables)
        c = _base_chunk(request, text, 0, "table_atomic", self.adapter_id, request.parameters)
        hard_limit = int(request.hard_constraints.get("CHUNK_HARD_TOKEN_LIMIT", 4096))
        allow_oversize = bool(request.hard_constraints.get("CHUNK_ALLOW_OVERSIZE_ATOMIC_BLOCK", True))
        if c.token_count > hard_limit:
            c.oversized = True
            c.oversized_reason = "atomic_table_exceeds_hard_token_limit"
            if not allow_oversize:
                c.text = truncate_to_tokens(c.text, hard_limit)
                c.finalize_measurements()
        c.chunk_type = "table"
        return [c]


class TableRowGroupAdapter(ChunkAdapter):
    adapter_id = "builtin.table_row_group"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="table_row_group",
            display_name="Table Row Group",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "xlsx", "csv"],
            supported_element_types=["table", "table_row"],
            capabilities=["table", "row_group"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "rows_per_chunk": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                    "repeat_header": {"type": "boolean", "default": True},
                },
            },
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        rows = [e for e in request.elements if e.element_type.value in ("table_row", "table")]
        if not rows:
            return []
        header = rows[0].text if rows else ""
        n = int(request.parameters.get("rows_per_chunk", 10))
        repeat = bool(request.parameters.get("repeat_header", True))
        body = rows[1:] if len(rows) > 1 else rows
        results = []
        for i in range(0, max(len(body), 1), n):
            group = body[i:i + n] if body else rows
            parts = [header] if repeat and header else []
            parts.extend(e.text for e in group)
            text = "\n".join(p for p in parts if p)
            c = _base_chunk(request, text, len(results), "table_row_group", self.adapter_id, request.parameters)
            c.chunk_type = "table_row_group"
            c.element_ids = [e.element_id for e in group]
            results.append(c)
        return results


class NoSplitAdapter(ChunkAdapter):
    adapter_id = "builtin.no_split"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="no_split",
            display_name="No Split",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "pptx", "md", "txt", "png", "jpeg"],
            supported_element_types=["heading", "paragraph", "list", "code", "image", "ocr_text"],
            capabilities=["atomic"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        text = _elements_text(request.elements)
        if not text:
            return []
        c = _base_chunk(request, text, 0, "no_split", self.adapter_id, request.parameters)
        hard_limit = int(request.hard_constraints.get("CHUNK_HARD_TOKEN_LIMIT", 4096))
        if c.token_count > hard_limit:
            c.oversized = True
            c.oversized_reason = "no_split_exceeds_hard_token_limit"
            if request.hard_constraints.get("CHUNK_ALLOW_OVERSIZE_ATOMIC_BLOCK", True):
                pass
            else:
                c.text = truncate_to_tokens(c.text, hard_limit)
                c.finalize_measurements()
        return [c]


class SkipUnitAdapter(ChunkAdapter):
    adapter_id = "builtin.skip_unit"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="skip_unit",
            display_name="Skip Unit",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "pptx", "md", "txt", "xlsx", "csv", "png", "jpeg"],
            supported_element_types=["heading", "paragraph", "list", "table", "image", "metadata"],
            capabilities=["skip"],
            parameter_schema={"type": "object", "properties": {"reason": {"type": "string"}}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        return []


class MarkdownStructuralAdapter(ChunkAdapter):
    adapter_id = "builtin.markdown_structural"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="markdown_structural",
            display_name="Markdown Structural",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["md", "markdown"],
            supported_element_types=["heading", "paragraph", "list", "code", "table"],
            capabilities=["structure_aware", "markdown"],
            parameter_schema=SIZE_SCHEMA,
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return _validate_size_params(request.parameters, request.hard_constraints)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        return HeadingSectionAdapter().chunk(request)


class CrossUnitContinuationAdapter(ChunkAdapter):
    adapter_id = "builtin.cross_unit_continuation"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="cross_unit_continuation",
            display_name="Cross-Unit Continuation",
            adapter_id=self.adapter_id,
            provider="builtin",
            provider_version="1.0.0",
            supported_document_types=["pdf", "docx", "md", "txt"],
            supported_element_types=["paragraph", "heading", "list"],
            capabilities=["cross_unit", "continuation"],
            parameter_schema={
                **SIZE_SCHEMA,
                "properties": {
                    **SIZE_SCHEMA["properties"],
                    "max_cross_unit_span": {"type": "integer", "minimum": 1, "maximum": 10, "default": 2},
                },
            },
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        result = _validate_size_params(request.parameters, request.hard_constraints)
        max_span = int(request.parameters.get("max_cross_unit_span", 2))
        hard_max = int(request.hard_constraints.get("CHUNK_MAX_CROSS_UNIT_SPAN", 2))
        if max_span > hard_max:
            result.errors.append({
                "code": "CROSS_UNIT_SPAN_EXCEEDED",
                "message": f"max_cross_unit_span must be <= {hard_max}",
                "field_path": "parameters.max_cross_unit_span",
                "allowed_range": [1, hard_max],
                "value": max_span,
            })
            result.valid = False
        return result

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        text = _elements_text(request.elements)
        ctx = request.continuation_context or {}
        prev_text = ctx.get("previous_unit_tail", "")
        next_text = ctx.get("next_unit_head", "")
        combined = "\n".join(t for t in [prev_text, text, next_text] if t)
        size = int(request.parameters.get("chunk_size", 512))
        overlap = int(request.parameters.get("chunk_overlap", 64))
        parts = _split_by_tokens(combined, size, overlap)
        group_id = ctx.get("continuation_group_id") or new_id()
        results = []
        for i, p in enumerate(parts):
            c = _base_chunk(request, p, i, "cross_unit_continuation", self.adapter_id, request.parameters)
            c.continuation_group_id = group_id
            extra_units = [u for u in [ctx.get("previous_unit_id"), ctx.get("next_unit_id")] if u]
            c.logical_unit_ids = list(dict.fromkeys(c.logical_unit_ids + extra_units))
            results.append(c)
        return results


def register_builtin_strategies(registry: StrategyRegistry) -> None:
    for adapter in [
        FixedTokenAdapter(),
        RecursiveTextAdapter(),
        SentenceWindowAdapter(),
        HeadingSectionAdapter(),
        ParentChildAdapter(),
        TableAtomicAdapter(),
        TableRowGroupAdapter(),
        NoSplitAdapter(),
        SkipUnitAdapter(),
        MarkdownStructuralAdapter(),
        CrossUnitContinuationAdapter(),
    ]:
        registry.register(adapter)
