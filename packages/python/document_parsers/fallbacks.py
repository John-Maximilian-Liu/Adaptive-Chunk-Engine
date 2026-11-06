"""Local fallback parsers — no external network required."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any, Optional

from canonical_schemas.document import (
    ElementModel,
    ElementType,
    Locator,
    LogicalUnitModel,
    ParserManifest,
    RegionModel,
)
from shared.ids import new_id

from document_parsers.base import ParseResult, ParserAdapter


def _unit(
    tenant_id: str,
    document_version_id: str,
    unit_type: str,
    ordinal: int,
    title: str,
    elements: list[ElementModel],
    locator: Optional[Locator] = None,
) -> LogicalUnitModel:
    region = RegionModel(
        tenant_id=tenant_id,
        document_version_id=document_version_id,
        logical_unit_id="pending",
        label="default",
        elements=elements,
        locator=locator or Locator(),
    )
    unit = LogicalUnitModel(
        tenant_id=tenant_id,
        document_version_id=document_version_id,
        unit_type=unit_type,
        ordinal=ordinal,
        title=title,
        locator=locator or Locator(),
        regions=[region],
        profile={"element_count": len(elements), "char_count": sum(len(e.text or "") for e in elements)},
    )
    region.logical_unit_id = unit.logical_unit_id
    for e in elements:
        e.logical_unit_id = unit.logical_unit_id
        e.region_id = region.region_id
    return unit


def _link_continuations(units: list[LogicalUnitModel]) -> None:
    group = new_id()
    for i, u in enumerate(units):
        if i > 0:
            u.previous_unit_id = units[i - 1].logical_unit_id
        if i + 1 < len(units):
            u.next_unit_id = units[i + 1].logical_unit_id
        # mark potential continuations when page ends mid-sentence
        text = " ".join(e.text for r in u.regions for e in r.elements)
        if text and not text.rstrip().endswith((".", "!", "?", ":")):
            u.continuation_group_id = group
            u.profile["continuation_candidate"] = True


class PlainTextParser(ParserAdapter):
    name = "plaintext"
    version = "1.0.0"
    supported_extensions = ["txt"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        text = path.read_text(encoding="utf-8", errors="replace")
        # virtual pages ~3000 chars
        page_size = 3000
        units = []
        for i in range(0, max(len(text), 1), page_size):
            chunk = text[i:i + page_size]
            el = ElementModel(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                logical_unit_id="pending",
                element_type=ElementType.PARAGRAPH,
                text=chunk,
                order_index=0,
                locator=Locator(page=i // page_size + 1, char_start=i, char_end=i + len(chunk)),
            )
            units.append(_unit(tenant_id, document_version_id, "virtual_page", len(units), f"Page {len(units)+1}", [el], Locator(page=len(units)+1)))
        _link_continuations(units)
        return ParseResult(
            logical_units=units,
            parser_manifest=ParserManifest(provider=self.name, version=self.version, adapter_version="1.0.0"),
        )


class MarkdownParser(ParserAdapter):
    name = "markdown-it-py-fallback"
    version = "1.0.0"
    supported_extensions = ["md", "markdown"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            from markdown_it import MarkdownIt
            md = MarkdownIt()
            tokens = md.parse(text)
            # still use heading-based split below; dependency presence recorded
            provider = "markdown-it-py"
            version = getattr(__import__("markdown_it"), "__version__", "unknown")
        except Exception:
            provider = self.name
            version = self.version
            tokens = []

        sections: list[tuple[str, list[str]]] = []
        current = "Introduction"
        buf: list[str] = []
        for line in text.splitlines():
            if line.startswith("#"):
                if buf:
                    sections.append((current, buf))
                current = line.lstrip("#").strip() or current
                buf = [line]
            else:
                buf.append(line)
        if buf or not sections:
            sections.append((current, buf))

        units = []
        for i, (title, lines) in enumerate(sections):
            elements = []
            for j, line in enumerate(lines):
                et = ElementType.HEADING if line.startswith("#") else ElementType.PARAGRAPH
                if line.strip().startswith("|") and "|" in line.strip()[1:]:
                    et = ElementType.TABLE
                if line.strip().startswith("```"):
                    et = ElementType.CODE
                elements.append(ElementModel(
                    tenant_id=tenant_id,
                    document_version_id=document_version_id,
                    logical_unit_id="pending",
                    element_type=et,
                    text=line,
                    order_index=j,
                    locator=Locator(heading_path=[title], line_start=j + 1, line_end=j + 1),
                ))
            units.append(_unit(tenant_id, document_version_id, "section", i, title, elements, Locator(heading_path=[title])))
        _link_continuations(units)
        return ParseResult(
            logical_units=units,
            parser_manifest=ParserManifest(provider=provider, version=version, adapter_version="1.0.0", fallback_used=provider == self.name),
            metadata={"token_count": len(tokens) if tokens else 0},
        )


class PdfParser(ParserAdapter):
    name = "pymupdf-fallback"
    version = "1.0.0"
    supported_extensions = ["pdf"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        units = []
        warnings = []
        provider = self.name
        version = self.version
        fallback = True
        try:
            import fitz  # PyMuPDF
            provider = "pymupdf"
            version = getattr(fitz, "version", ("unknown",))[0] if isinstance(getattr(fitz, "version", None), tuple) else str(getattr(fitz, "__doc__", "unknown"))[:20]
            fallback = False
            doc = fitz.open(path)
            for i, page in enumerate(doc):
                text = page.get_text("text")
                elements = []
                # crude heading detection
                for j, para in enumerate([p for p in text.split("\n\n") if p.strip()]):
                    et = ElementType.HEADING if len(para) < 80 and para.isupper() else ElementType.PARAGRAPH
                    if "|" in para and para.count("|") >= 2:
                        et = ElementType.TABLE
                    elements.append(ElementModel(
                        tenant_id=tenant_id,
                        document_version_id=document_version_id,
                        logical_unit_id="pending",
                        element_type=et,
                        text=para.strip(),
                        order_index=j,
                        locator=Locator(page=i + 1),
                    ))
                if not elements:
                    elements.append(ElementModel(
                        tenant_id=tenant_id,
                        document_version_id=document_version_id,
                        logical_unit_id="pending",
                        element_type=ElementType.PARAGRAPH,
                        text=text.strip(),
                        locator=Locator(page=i + 1),
                    ))
                units.append(_unit(tenant_id, document_version_id, "page", i, f"Page {i+1}", elements, Locator(page=i + 1)))
            doc.close()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"pymupdf_unavailable:{exc}")
            # binary-safe text extraction fallback
            raw = path.read_bytes()
            text = raw.decode("latin-1", errors="replace")
            # extract readable strings
            readable = "\n".join(m.group(0) for m in re.finditer(r"[\x20-\x7E]{4,}", text))[:20000]
            el = ElementModel(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                logical_unit_id="pending",
                element_type=ElementType.PARAGRAPH,
                text=readable or "[empty pdf fallback]",
                locator=Locator(page=1),
            )
            units.append(_unit(tenant_id, document_version_id, "page", 0, "Page 1", [el], Locator(page=1)))
        _link_continuations(units)
        return ParseResult(
            logical_units=units,
            parser_manifest=ParserManifest(provider=provider, version=str(version), adapter_version="1.0.0", fallback_used=fallback),
            warnings=warnings,
        )


class DocxParser(ParserAdapter):
    name = "python-docx-fallback"
    version = "1.0.0"
    supported_extensions = ["docx"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        warnings = []
        try:
            from docx import Document
            doc = Document(str(path))
            elements: list[ElementModel] = []
            for i, p in enumerate(doc.paragraphs):
                style = (p.style.name or "").lower() if p.style else ""
                et = ElementType.HEADING if "heading" in style else ElementType.PARAGRAPH
                if not p.text.strip():
                    continue
                elements.append(ElementModel(
                    tenant_id=tenant_id,
                    document_version_id=document_version_id,
                    logical_unit_id="pending",
                    element_type=et,
                    text=p.text,
                    order_index=i,
                    locator=Locator(heading_path=[p.style.name] if p.style else []),
                ))
            for ti, table in enumerate(doc.tables):
                rows = []
                for row in table.rows:
                    rows.append(" | ".join(cell.text for cell in row.cells))
                elements.append(ElementModel(
                    tenant_id=tenant_id,
                    document_version_id=document_version_id,
                    logical_unit_id="pending",
                    element_type=ElementType.TABLE,
                    text="\n".join(rows),
                    order_index=1000 + ti,
                    locator=Locator(),
                    attributes={"table_index": ti},
                ))
            # section as logical unit; also virtual pages of ~20 paras
            page_size = 20
            units = []
            if not elements:
                elements = [ElementModel(
                    tenant_id=tenant_id, document_version_id=document_version_id, logical_unit_id="pending",
                    element_type=ElementType.PARAGRAPH, text="",
                )]
            for i in range(0, len(elements), page_size):
                chunk = elements[i:i + page_size]
                units.append(_unit(tenant_id, document_version_id, "section", len(units), f"Section {len(units)+1}", chunk, Locator(page=len(units)+1)))
            _link_continuations(units)
            return ParseResult(
                logical_units=units,
                parser_manifest=ParserManifest(provider="python-docx", version="1.0.0", adapter_version="1.0.0"),
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(str(exc))
            text = path.read_bytes().decode("utf-8", errors="replace")
            el = ElementModel(
                tenant_id=tenant_id, document_version_id=document_version_id, logical_unit_id="pending",
                element_type=ElementType.PARAGRAPH, text=text[:20000],
            )
            return ParseResult(
                logical_units=[_unit(tenant_id, document_version_id, "section", 0, "Document", [el])],
                parser_manifest=ParserManifest(provider=self.name, version=self.version, adapter_version="1.0.0", fallback_used=True),
                warnings=warnings,
            )


class PptxParser(ParserAdapter):
    name = "python-pptx-fallback"
    version = "1.0.0"
    supported_extensions = ["pptx"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        try:
            from pptx import Presentation
            prs = Presentation(str(path))
            units = []
            for i, slide in enumerate(prs.slides):
                elements = []
                order = 0
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        elements.append(ElementModel(
                            tenant_id=tenant_id,
                            document_version_id=document_version_id,
                            logical_unit_id="pending",
                            element_type=ElementType.PARAGRAPH if order else ElementType.HEADING,
                            text=shape.text.strip(),
                            order_index=order,
                            locator=Locator(slide=i + 1),
                        ))
                        order += 1
                    # native vector shapes metadata
                    if shape.shape_type is not None:
                        elements.append(ElementModel(
                            tenant_id=tenant_id,
                            document_version_id=document_version_id,
                            logical_unit_id="pending",
                            element_type=ElementType.IMAGE,
                            text=f"[shape:{getattr(shape, 'shape_type', '')}]",
                            order_index=order,
                            locator=Locator(slide=i + 1),
                            attributes={"native_vector_candidate": True, "shape_name": getattr(shape, "name", None)},
                        ))
                        order += 1
                notes = ""
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text or ""
                if notes.strip():
                    elements.append(ElementModel(
                        tenant_id=tenant_id,
                        document_version_id=document_version_id,
                        logical_unit_id="pending",
                        element_type=ElementType.SPEAKER_NOTE,
                        text=notes.strip(),
                        order_index=order,
                        locator=Locator(slide=i + 1),
                    ))
                units.append(_unit(tenant_id, document_version_id, "slide", i, f"Slide {i+1}", elements or [
                    ElementModel(tenant_id=tenant_id, document_version_id=document_version_id, logical_unit_id="pending",
                                 element_type=ElementType.PARAGRAPH, text="", locator=Locator(slide=i+1))
                ], Locator(slide=i + 1)))
            return ParseResult(
                logical_units=units,
                parser_manifest=ParserManifest(provider="python-pptx", version="1.0.0", adapter_version="1.0.0"),
            )
        except Exception as exc:  # noqa: BLE001
            el = ElementModel(
                tenant_id=tenant_id, document_version_id=document_version_id, logical_unit_id="pending",
                element_type=ElementType.PARAGRAPH, text=f"[pptx parse error: {exc}]",
            )
            return ParseResult(
                logical_units=[_unit(tenant_id, document_version_id, "slide", 0, "Slide 1", [el], Locator(slide=1))],
                parser_manifest=ParserManifest(provider=self.name, version=self.version, adapter_version="1.0.0", fallback_used=True),
                warnings=[str(exc)],
            )


class XlsxParser(ParserAdapter):
    name = "openpyxl-fallback"
    version = "1.0.0"
    supported_extensions = ["xlsx", "xls"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        units = []
        warnings = []
        try:
            if path.suffix.lower() == ".xls":
                # try pandas for xls
                import pandas as pd
                sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
                for si, (name, df) in enumerate(sheets.items()):
                    elements = self._df_to_elements(df, tenant_id, document_version_id, name)
                    units.append(_unit(tenant_id, document_version_id, "sheet", si, name, elements, Locator(sheet=name)))
                return ParseResult(
                    logical_units=units,
                    parser_manifest=ParserManifest(provider="pandas", version="1.0.0", adapter_version="1.0.0"),
                )

            from openpyxl import load_workbook
            wb = load_workbook(path, data_only=False)
            for si, sheet_name in enumerate(wb.sheetnames):
                ws = wb[sheet_name]
                elements: list[ElementModel] = []
                # detect merged cells
                merged = {str(r): True for r in ws.merged_cells.ranges}
                # named ranges
                named = {}
                try:
                    for dn in wb.defined_names.definedName:
                        named[dn.name] = dn.attr_text
                except Exception:
                    pass

                # header row
                rows = list(ws.iter_rows(values_only=False))
                for ri, row in enumerate(rows):
                    cells = []
                    formulas = []
                    first = None
                    last = None
                    for cell in row:
                        if cell.value is None:
                            continue
                        addr = cell.coordinate
                        if first is None:
                            first = addr
                        last = addr
                        val = cell.value
                        if isinstance(val, str) and val.startswith("="):
                            formulas.append((addr, val))
                            cells.append(f"{addr}={val}")
                        else:
                            cells.append(str(val))
                    if not cells:
                        continue
                    rng = f"{first}:{last}" if first and last else f"A{ri+1}"
                    et = ElementType.TABLE_ROW
                    attrs: dict[str, Any] = {"row_index": ri + 1}
                    if formulas:
                        et = ElementType.FORMULA if len(formulas) == len(cells) else ElementType.TABLE_ROW
                        attrs["formula"] = formulas[0][1] if formulas else None
                        attrs["precedents"] = re.findall(r"[A-Za-z]+\\d+", formulas[0][1]) if formulas else []
                        attrs["formulas"] = formulas
                    if any(rng in m or str(m).startswith(first or "") for m in merged):
                        attrs["merged_cells"] = True
                    for n, ref in named.items():
                        if sheet_name in str(ref):
                            attrs.setdefault("named_range", n)
                    elements.append(ElementModel(
                        tenant_id=tenant_id,
                        document_version_id=document_version_id,
                        logical_unit_id="pending",
                        element_type=et if ri > 0 else ElementType.TABLE_ROW,
                        text=" | ".join(cells),
                        order_index=ri,
                        locator=Locator(sheet=sheet_name, range=rng, uri=f"{filename}#{sheet_name}!{rng}"),
                        attributes=attrs,
                    ))
                # charts
                try:
                    for ci, chart in enumerate(getattr(ws, "_charts", []) or []):
                        elements.append(ElementModel(
                            tenant_id=tenant_id,
                            document_version_id=document_version_id,
                            logical_unit_id="pending",
                            element_type=ElementType.CHART,
                            text=f"Chart {ci+1}",
                            order_index=10000 + ci,
                            locator=Locator(sheet=sheet_name),
                            attributes={"chart_title": f"Chart {ci+1}", "data_range": "A1"},
                        ))
                except Exception:
                    pass
                profile = {
                    "row_count": len(elements),
                    "formula_count": sum(1 for e in elements if e.attributes.get("formula")),
                    "merged_cell_regions": len(merged),
                    "named_ranges": list(named.keys()),
                    "formula_heavy": sum(1 for e in elements if e.attributes.get("formula")) > max(3, len(elements) * 0.1),
                }
                unit = _unit(tenant_id, document_version_id, "sheet", si, sheet_name, elements, Locator(sheet=sheet_name))
                unit.profile.update(profile)
                units.append(unit)
            return ParseResult(
                logical_units=units,
                parser_manifest=ParserManifest(provider="openpyxl", version="1.0.0", adapter_version="1.0.0"),
                warnings=warnings,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(str(exc))
            # pandas fallback
            try:
                import pandas as pd
                df = pd.read_excel(path, header=None, dtype=str)
                elements = self._df_to_elements(df, tenant_id, document_version_id, "Sheet1")
                units = [_unit(tenant_id, document_version_id, "sheet", 0, "Sheet1", elements, Locator(sheet="Sheet1"))]
                return ParseResult(
                    logical_units=units,
                    parser_manifest=ParserManifest(provider="pandas", version="1.0.0", adapter_version="1.0.0", fallback_used=True),
                    warnings=warnings,
                )
            except Exception as exc2:  # noqa: BLE001
                warnings.append(str(exc2))
                el = ElementModel(
                    tenant_id=tenant_id, document_version_id=document_version_id, logical_unit_id="pending",
                    element_type=ElementType.PARAGRAPH, text="[xlsx unreadable]",
                )
                return ParseResult(
                    logical_units=[_unit(tenant_id, document_version_id, "sheet", 0, "Sheet1", [el], Locator(sheet="Sheet1"))],
                    parser_manifest=ParserManifest(provider=self.name, version=self.version, adapter_version="1.0.0", fallback_used=True),
                    warnings=warnings,
                )

    def _df_to_elements(self, df, tenant_id, document_version_id, sheet):
        elements = []
        for ri, row in df.iterrows():
            vals = [str(v) for v in row.tolist() if str(v) != "nan"]
            if not vals:
                continue
            rng = f"A{int(ri)+1}:{chr(64+min(len(vals),26))}{int(ri)+1}"
            elements.append(ElementModel(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                logical_unit_id="pending",
                element_type=ElementType.TABLE_ROW,
                text=" | ".join(vals),
                order_index=int(ri),
                locator=Locator(sheet=sheet, range=rng, uri=f"workbook.xlsx#{sheet}!{rng}"),
            ))
        return elements


class CsvParser(ParserAdapter):
    name = "csv-pandas-fallback"
    version = "1.0.0"
    supported_extensions = ["csv"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        text = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        elements = []
        for ri, row in enumerate(reader):
            if not row:
                continue
            rng = f"A{ri+1}:{chr(64+min(len(row),26))}{ri+1}"
            elements.append(ElementModel(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                logical_unit_id="pending",
                element_type=ElementType.TABLE_ROW,
                text=" | ".join(row),
                order_index=ri,
                locator=Locator(sheet="Sheet1", range=rng, uri=f"{filename}#Sheet1!{rng}"),
            ))
        unit = _unit(tenant_id, document_version_id, "sheet", 0, "Sheet1", elements, Locator(sheet="Sheet1"))
        return ParseResult(
            logical_units=[unit],
            parser_manifest=ParserManifest(provider="csv", version=self.version, adapter_version="1.0.0"),
        )


class ImageParser(ParserAdapter):
    name = "pillow-ocr-fallback"
    version = "1.0.0"
    supported_extensions = ["png", "jpeg", "jpg", "tiff", "tif"]

    def parse(self, path: Path, *, tenant_id: str, document_version_id: str, filename: str) -> ParseResult:
        warnings = []
        ocr_text = ""
        width = height = 0
        try:
            from PIL import Image
            img = Image.open(path)
            width, height = img.size
            # OCR adapter interface — try pytesseract if present, else empty
            try:
                import pytesseract
                ocr_text = pytesseract.image_to_string(img) or ""
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"ocr_unavailable:{exc}")
                ocr_text = ""
        except Exception as exc:  # noqa: BLE001
            warnings.append(str(exc))

        elements = [
            ElementModel(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                logical_unit_id="pending",
                element_type=ElementType.IMAGE,
                text=f"[image {width}x{height}]",
                order_index=0,
                locator=Locator(page=1, bbox=[0, 0, float(width), float(height)]),
                attributes={"width": width, "height": height, "path": str(path)},
            )
        ]
        if ocr_text.strip():
            elements.append(ElementModel(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                logical_unit_id="pending",
                element_type=ElementType.OCR_TEXT,
                text=ocr_text.strip(),
                order_index=1,
                locator=Locator(page=1, locator_type="image_region"),
                confidence=0.7,
            ))
        unit = _unit(tenant_id, document_version_id, "image_page", 0, filename, elements, Locator(page=1))
        return ParseResult(
            logical_units=[unit],
            parser_manifest=ParserManifest(provider=self.name, version=self.version, adapter_version="1.0.0"),
            warnings=warnings,
        )
