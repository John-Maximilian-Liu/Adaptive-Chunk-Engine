"""Excel-native chunking strategies."""
from __future__ import annotations

import re
from typing import Any, Optional

from canonical_schemas.chunk import CanonicalChunk, LocatorRef, SourceSpan, LogicalUnitSpan
from canonical_schemas.document import ElementModel
from shared.hashing import stable_json_hash
from shared.tokens import count_tokens

from chunk_adapters.base import (
    ChunkAdapter,
    ChunkRequest,
    StrategyDefinition,
    StrategyRegistry,
    ValidationResult,
)


A1_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


def col_to_index(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def index_to_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_a1(cell: str) -> tuple[int, int]:
    m = A1_RE.match(cell.strip())
    if not m:
        raise ValueError(f"Invalid A1 cell: {cell}")
    return int(m.group(2)), col_to_index(m.group(1))


def parse_range(rng: str) -> tuple[int, int, int, int]:
    """Return (r1, c1, r2, c2) inclusive."""
    if "!" in rng:
        rng = rng.split("!", 1)[1]
    if ":" in rng:
        a, b = rng.split(":", 1)
    else:
        a = b = rng
    r1, c1 = parse_a1(a)
    r2, c2 = parse_a1(b)
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def range_intersection_coverage(evidence: str, retrieved: str) -> float:
    """Intersection of cells / evidence cells."""
    try:
        er1, ec1, er2, ec2 = parse_range(evidence)
        rr1, rc1, rr2, rc2 = parse_range(retrieved)
    except ValueError:
        return 0.0
    evidence_cells = (er2 - er1 + 1) * (ec2 - ec1 + 1)
    if evidence_cells <= 0:
        return 0.0
    ir1, ic1 = max(er1, rr1), max(ec1, rc1)
    ir2, ic2 = min(er2, rr2), min(ec2, rc2)
    if ir1 > ir2 or ic1 > ic2:
        return 0.0
    inter = (ir2 - ir1 + 1) * (ic2 - ic1 + 1)
    return inter / evidence_cells


def sheet_locator(filename: str, sheet: str, rng: str) -> str:
    return f"{filename}#{sheet}!{rng}"


def _make_chunk(
    request: ChunkRequest,
    text: str,
    ordinal: int,
    strategy: str,
    adapter_id: str,
    locator_uri: str,
    element_ids: list[str],
    sheet: Optional[str],
    rng: Optional[str],
) -> CanonicalChunk:
    unit = request.logical_unit
    chunk = CanonicalChunk(
        chunk_run_id=request.chunk_run_id,
        document_id=request.document_id,
        document_version_id=request.document_version_id,
        experiment_id=request.experiment_id,
        tenant_id=request.tenant_id,
        ordinal=ordinal,
        text=text,
        embedding_text=text,
        chunk_type="spreadsheet",
        logical_unit_ids=[unit.logical_unit_id],
        logical_unit_span=LogicalUnitSpan(start_ordinal=unit.ordinal, end_ordinal=unit.ordinal, unit_ids=[unit.logical_unit_id]),
        region_ids=[request.region.region_id] if request.region else [],
        element_ids=element_ids,
        locators=[LocatorRef(sheet=sheet, range=rng, uri=locator_uri, locator_type="spreadsheet_range")],
        source_spans=[SourceSpan(element_id=eid, char_start=0, char_end=0) for eid in element_ids],
        canonical_strategy=strategy,
        adapter_id=adapter_id,
        provider="builtin.excel",
        provider_version="1.0.0",
        parameters=request.parameters,
        configuration_hash=stable_json_hash(request.parameters),
    )
    return chunk.finalize_measurements()


def _sheet_name(unit) -> str:
    return unit.title or (unit.locator.sheet if unit.locator else None) or "Sheet1"


def _filename(request: ChunkRequest) -> str:
    return request.parameters.get("filename", "workbook.xlsx")


class ExcelTableRowGroupAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_table_row_group"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_table_row_group",
            display_name="Excel Table Row Group",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls", "csv"],
            supported_element_types=["table", "table_row"],
            capabilities=["excel", "row_group", "merged_cells", "repeated_headers"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "rows_per_chunk": {"type": "integer", "minimum": 1, "default": 20},
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
        header = rows[0]
        body = rows[1:] if len(rows) > 1 else []
        n = int(request.parameters.get("rows_per_chunk", 20))
        repeat = bool(request.parameters.get("repeat_header", True))
        sheet = _sheet_name(request.logical_unit)
        filename = _filename(request)
        results = []
        groups = [body[i:i + n] for i in range(0, len(body), n)] or [[header]]
        for gi, group in enumerate(groups):
            elems = ([header] + group) if repeat and body else group
            texts = [e.text for e in elems if e.text]
            # derive range from attributes if present
            ranges = [e.locator.range for e in group if e.locator and e.locator.range]
            rng = ranges[0] if len(ranges) == 1 else (f"{ranges[0].split(':')[0]}:{ranges[-1].split(':')[-1]}" if ranges else f"A{gi + 1}")
            uri = sheet_locator(filename, sheet, rng)
            results.append(_make_chunk(request, "\n".join(texts), gi, "excel_table_row_group", self.adapter_id, uri, [e.element_id for e in elems], sheet, rng))
        return results


class ExcelRecordPerRowAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_record_per_row"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_record_per_row",
            display_name="Excel Record Per Row",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls", "csv"],
            supported_element_types=["table_row"],
            capabilities=["excel", "record"],
            parameter_schema={
                "type": "object",
                "properties": {"include_header": {"type": "boolean", "default": True}},
            },
            # also register alias spreadsheet_record
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        rows = [e for e in request.elements if e.element_type.value in ("table_row", "table", "paragraph")]
        if not rows:
            return []
        header = rows[0].text if rows else ""
        include = bool(request.parameters.get("include_header", True))
        sheet = _sheet_name(request.logical_unit)
        filename = _filename(request)
        body = rows[1:] if len(rows) > 1 else rows
        results = []
        for i, row in enumerate(body):
            text = f"{header}\n{row.text}" if include and header and row is not rows[0] else row.text
            rng = row.locator.range or f"A{i + 2}"
            uri = sheet_locator(filename, sheet, rng)
            results.append(_make_chunk(request, text, i, "excel_record_per_row", self.adapter_id, uri, [row.element_id], sheet, rng))
        return results


class ExcelRegionAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_region"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_region",
            display_name="Excel Region",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls", "csv"],
            supported_element_types=["table", "table_row", "formula"],
            capabilities=["excel", "region", "named_ranges"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        sheet = _sheet_name(request.logical_unit)
        filename = _filename(request)
        # Prefer region grouping
        if request.region:
            text = "\n".join(e.text for e in request.elements if e.text)
            rng = request.region.locator.range or "A1"
            uri = sheet_locator(filename, sheet, rng)
            return [_make_chunk(request, text, 0, "excel_region", self.adapter_id, uri, [e.element_id for e in request.elements], sheet, rng)]
        # group by contiguous profile regions on elements
        groups: dict[str, list[ElementModel]] = {}
        for e in request.elements:
            key = (e.attributes or {}).get("region_key") or e.locator.range or "default"
            groups.setdefault(str(key), []).append(e)
        results = []
        for i, (key, elems) in enumerate(groups.items()):
            text = "\n".join(e.text for e in elems if e.text)
            rng = elems[0].locator.range if elems and elems[0].locator.range else key
            uri = sheet_locator(filename, sheet, rng)
            results.append(_make_chunk(request, text, i, "excel_region", self.adapter_id, uri, [e.element_id for e in elems], sheet, rng))
        return results


class ExcelFormulaDependencyAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_formula_dependency"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_formula_dependency",
            display_name="Excel Formula Dependency",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls"],
            supported_element_types=["formula", "table_row", "table"],
            capabilities=["excel", "formula", "dependency"],
            parameter_schema={"type": "object", "properties": {"include_precedents": {"type": "boolean", "default": True}}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        sheet = _sheet_name(request.logical_unit)
        filename = _filename(request)
        formulas = [e for e in request.elements if e.element_type.value == "formula" or (e.attributes or {}).get("formula")]
        if not formulas:
            # fall back to region of all elements with formula metadata
            formulas = [e for e in request.elements if "formula" in (e.attributes or {})]
        results = []
        for i, e in enumerate(formulas or request.elements[:1]):
            attrs = e.attributes or {}
            formula = attrs.get("formula") or e.text
            precedents = attrs.get("precedents") or []
            deps = attrs.get("dependency_values") or {}
            parts = [f"Formula at {e.locator.range or '?'}: {formula}"]
            if request.parameters.get("include_precedents", True):
                for p in precedents:
                    parts.append(f"Precedent {p}: {deps.get(p, '')}")
            text = "\n".join(parts)
            rng = e.locator.range or f"F{i + 1}"
            uri = sheet_locator(filename, sheet, rng)
            c = _make_chunk(request, text, i, "excel_formula_dependency", self.adapter_id, uri, [e.element_id], sheet, rng)
            c.extensions = {"provider_payload": {"formula": formula, "precedents": precedents}}
            results.append(c)
        return results


class SpreadsheetRecordAlias(ExcelRecordPerRowAdapter):
    """Alias strategy spreadsheet_record."""

    def capabilities(self) -> StrategyDefinition:
        d = super().capabilities()
        d.strategy_id = "spreadsheet_record"
        d.display_name = "Spreadsheet Record"
        d.adapter_id = "builtin.spreadsheet_record"
        return d

    @property
    def adapter_id(self) -> str:  # type: ignore[override]
        return "builtin.spreadsheet_record"


class SpreadsheetRowGroupAlias(ExcelTableRowGroupAdapter):
    def capabilities(self) -> StrategyDefinition:
        d = super().capabilities()
        d.strategy_id = "spreadsheet_row_group"
        d.display_name = "Spreadsheet Row Group"
        d.adapter_id = "builtin.spreadsheet_row_group"
        return d

    @property
    def adapter_id(self) -> str:  # type: ignore[override]
        return "builtin.spreadsheet_row_group"


class SpreadsheetRegionAlias(ExcelRegionAdapter):
    def capabilities(self) -> StrategyDefinition:
        d = super().capabilities()
        d.strategy_id = "spreadsheet_region"
        d.display_name = "Spreadsheet Region"
        d.adapter_id = "builtin.spreadsheet_region"
        return d

    @property
    def adapter_id(self) -> str:  # type: ignore[override]
        return "builtin.spreadsheet_region"


# Additional Excel strategies with working minimal implementations
class ExcelHeaderHierarchyAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_header_hierarchy"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_header_hierarchy",
            display_name="Excel Header Hierarchy",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls"],
            supported_element_types=["table", "table_row"],
            capabilities=["excel", "headers"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        return ExcelRegionAdapter().chunk(request)


class ExcelNamedRangeAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_named_range"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_named_range",
            display_name="Excel Named Range",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls"],
            supported_element_types=["table", "table_row", "formula"],
            capabilities=["excel", "named_ranges"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        named = {}
        for e in request.elements:
            name = (e.attributes or {}).get("named_range")
            if name:
                named.setdefault(name, []).append(e)
        if not named:
            return ExcelRegionAdapter().chunk(request)
        sheet = _sheet_name(request.logical_unit)
        filename = _filename(request)
        results = []
        for i, (name, elems) in enumerate(named.items()):
            text = f"Named range {name}\n" + "\n".join(e.text for e in elems if e.text)
            rng = elems[0].locator.range or name
            uri = sheet_locator(filename, sheet, rng)
            results.append(_make_chunk(request, text, i, "excel_named_range", self.adapter_id, uri, [e.element_id for e in elems], sheet, rng))
        return results


class ExcelChartContextAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_chart_context"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_chart_context",
            display_name="Excel Chart Context",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls"],
            supported_element_types=["chart", "table"],
            capabilities=["excel", "chart"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        charts = [e for e in request.elements if e.element_type.value == "chart"]
        sheet = _sheet_name(request.logical_unit)
        filename = _filename(request)
        results = []
        for i, e in enumerate(charts or request.elements[:1]):
            title = (e.attributes or {}).get("chart_title", "Chart")
            data_ref = (e.attributes or {}).get("data_range", e.locator.range or "A1")
            text = f"Chart: {title}\nData range: {data_ref}\n{e.text}"
            uri = sheet_locator(filename, sheet, data_ref)
            c = _make_chunk(request, text, i, "excel_chart_context", self.adapter_id, uri, [e.element_id], sheet, data_ref)
            c.chunk_type = "chart_description"
            results.append(c)
        return results


class ExcelSqlVirtualAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_sql_virtual"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_sql_virtual",
            display_name="Excel SQL Virtual",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls", "csv"],
            supported_element_types=["table", "table_row"],
            capabilities=["excel", "sql_virtual"],
            parameter_schema={"type": "object", "properties": {}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        # Represent sheet as SQL-like row documents
        return ExcelRecordPerRowAdapter().chunk(request)


class ExcelHybridSqlVectorAdapter(ChunkAdapter):
    adapter_id = "builtin.excel_hybrid_sql_vector"

    def capabilities(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="excel_hybrid_sql_vector",
            display_name="Excel Hybrid SQL+Vector",
            adapter_id=self.adapter_id,
            provider="builtin.excel",
            provider_version="1.0.0",
            supported_document_types=["xlsx", "xls", "csv"],
            supported_element_types=["table", "table_row", "formula"],
            capabilities=["excel", "hybrid"],
            parameter_schema={"type": "object", "properties": {"rows_per_chunk": {"type": "integer", "default": 20}}},
            license_metadata={"spdx": "Apache-2.0"},
        )

    def validate(self, request: ChunkRequest) -> ValidationResult:
        return ValidationResult(valid=True)

    def chunk(self, request: ChunkRequest) -> list[CanonicalChunk]:
        row_chunks = ExcelTableRowGroupAdapter().chunk(request)
        formula_chunks = ExcelFormulaDependencyAdapter().chunk(request)
        combined = row_chunks + formula_chunks
        for i, c in enumerate(combined):
            c.ordinal = i
            c.canonical_strategy = "excel_hybrid_sql_vector"
            c.adapter_id = self.adapter_id
        return combined


def register_excel_strategies(registry: StrategyRegistry) -> None:
    adapters = [
        ExcelTableRowGroupAdapter(),
        ExcelRecordPerRowAdapter(),
        ExcelRegionAdapter(),
        ExcelFormulaDependencyAdapter(),
        SpreadsheetRecordAlias(),
        SpreadsheetRowGroupAlias(),
        SpreadsheetRegionAlias(),
        ExcelHeaderHierarchyAdapter(),
        ExcelNamedRangeAdapter(),
        ExcelChartContextAdapter(),
        ExcelSqlVirtualAdapter(),
        ExcelHybridSqlVectorAdapter(),
    ]
    for a in adapters:
        registry.register(a)
