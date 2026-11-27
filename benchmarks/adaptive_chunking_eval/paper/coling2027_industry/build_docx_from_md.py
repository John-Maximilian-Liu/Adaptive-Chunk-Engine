#!/usr/bin/env python3
"""Build Industry DOCX from manuscript_submission.md (改8+)."""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parent
MD = ROOT / "manuscript_submission.md"
FIG = ROOT / "figures"
OUT = ROOT / "ACE_COLING2027_Industry_Manuscript.docx"
OUT_REV = ROOT / "ACE_COLING2027_Industry_Manuscript（改8）.docx"


def set_run_font(run, *, size=11, bold=False, italic=False, name="Times New Roman"):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def add_runs_markdown_inline(paragraph, text, *, size=11, bold=False):
    """Minimal **bold** and `code` handling."""
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            set_run_font(run, size=size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            set_run_font(run, size=size, italic=True)
        else:
            run = paragraph.add_run(part)
            set_run_font(run, size=size, bold=bold)


def add_para(doc, text, *, size=11, bold=False, space_after=8, align="left"):
    p = doc.add_paragraph()
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    add_runs_markdown_inline(p, text, size=size, bold=bold)
    return p


def _set_cell_border(cell, **edges):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge, spec in edges.items():
        if spec is None:
            continue
        sz, color = spec
        element = tcBorders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            tcBorders.append(element)
        element.set(qn("w:val"), "single" if sz else "nil")
        element.set(qn("w:sz"), str(sz))
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    n_rows = 1 + len(rows)
    n_cols = len(headers)
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        set_run_font(run, size=9, bold=True)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(val).replace("**", ""))
            set_run_font(run, size=9)
    TOP, MID, BOT, NIL = (12, "000000"), (6, "000000"), (12, "000000"), (0, "FFFFFF")
    for r in range(n_rows):
        for c in range(n_cols):
            edges = {"start": NIL, "end": NIL, "top": NIL, "bottom": NIL}
            if r == 0:
                edges["top"] = TOP
                edges["bottom"] = MID
            elif r == n_rows - 1:
                edges["bottom"] = BOT
            _set_cell_border(table.rows[r].cells[c], **edges)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(8)


def add_figure(doc, path: Path, caption: str, width=6.0):
    if not path.exists():
        add_para(doc, f"[Missing figure: {path.name}]", size=10, space_after=4, align="center")
        add_para(doc, caption, size=10, space_after=10, align="center")
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(caption)
    set_run_font(r, size=10, italic=True)
    cap.paragraph_format.space_after = Pt(10)


def parse_md(text: str) -> list[tuple]:
    """Yield ('heading'|'para'|'table'|'figure'|'bullet'|'skip', payload)."""
    # drop YAML front matter
    if text.startswith("---"):
        text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    lines = text.splitlines()
    i = 0
    events = []
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            events.append(("title", line[2:].strip()))
            i += 1
            continue
        if line.startswith("## "):
            events.append(("h1", line[3:].strip()))
            i += 1
            continue
        if line.startswith("### "):
            events.append(("h2", line[4:].strip()))
            i += 1
            continue
        if line.startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
            if m:
                events.append(("figure", (m.group(1), m.group(2))))
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            events.append(("table", (header, rows)))
            continue
        if line.startswith(("- ", "* ", "1. ", "2. ", "3. ", "4. ")):
            events.append(("bullet", re.sub(r"^(\d+\.|[-*])\s+", "", line.strip())))
            i += 1
            continue
        if line.startswith("$$") or line.strip() == "$$":
            buf = [line]
            i += 1
            while i < len(lines):
                buf.append(lines[i])
                if lines[i].strip().endswith("$$") and len(buf) > 1:
                    i += 1
                    break
                i += 1
            events.append(("math", "\n".join(buf)))
            continue
        # accumulate paragraph
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "![", "- ", "* ", "1. ", "2. ", "3. ", "4. ", "$$")):
            if re.match(r"^\|[\s\-:|]+\|$", lines[i].strip()):
                break
            buf.append(lines[i])
            i += 1
        events.append(("para", " ".join(x.strip() for x in buf)))
    return events


def build() -> None:
    events = parse_md(MD.read_text(encoding="utf-8"))
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    skip_next_anon = True
    for kind, payload in events:
        if kind == "title":
            add_para(doc, payload, size=16, bold=True, align="center", space_after=6)
        elif kind == "h1":
            add_para(doc, payload, size=14, bold=True, space_after=6)
        elif kind == "h2":
            add_para(doc, payload, size=12, bold=True, space_after=4)
        elif kind == "para":
            text = payload
            if text.startswith("**Anonymous") or text.startswith("Paper under double-blind"):
                add_para(doc, text.replace("**", ""), size=10, align="center", space_after=4)
                continue
            # figure captions often precede images
            if text.startswith("**Figure") or text.startswith("**Table"):
                add_para(doc, text.replace("**", ""), size=10, space_after=4, align="left")
                continue
            add_para(doc, text, size=11, space_after=8, align="justify")
        elif kind == "bullet":
            p = doc.add_paragraph(style="List Bullet")
            p.clear()
            add_runs_markdown_inline(p, payload, size=11)
            p.paragraph_format.space_after = Pt(3)
        elif kind == "table":
            headers, rows = payload
            add_table(doc, headers, rows)
        elif kind == "figure":
            caption, rel = payload
            path = (ROOT / rel).resolve()
            add_figure(doc, path, caption or path.name)
        elif kind == "math":
            # flatten display math as monospace-ish paragraph
            flat = payload.replace("$$", "").replace("\n", " ").strip()
            add_para(doc, flat, size=10, space_after=8, align="center")

    doc.save(OUT)
    doc.save(OUT_REV)
    print(f"Wrote {OUT}")
    print(f"Wrote {OUT_REV}")


if __name__ == "__main__":
    build()
