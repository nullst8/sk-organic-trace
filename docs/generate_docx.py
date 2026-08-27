#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
GREEN = RGBColor(0x1B, 0x4D, 0x2E)
GOLD = RGBColor(0x8B, 0x6B, 0x1F)
INK = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x55, 0x55, 0x55)
HEADER_BG = "1B4D2E"
ALT_ROW = "F4EFE6"
CODE_BG = "F5F0E6"


def _set_cell_shading(cell, hex_color: str) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tc_pr.append(shd)


def _set_run_font(run, *, name="Calibri", size=11, bold=False, color=INK, mono=False):
    run.font.name = "Consolas" if mono else name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), run.font.name)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color


def _add_inline(paragraph, text: str, *, size=11) -> None:
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            _set_run_font(run, size=size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            _set_run_font(run, size=size - 1, mono=True, color=GOLD)
        else:
            run = paragraph.add_run(part)
            _set_run_font(run, size=size)


def _style_paragraph(p, *, space_after=8, space_before=0):
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE


def _add_heading(doc: Document, text: str, level: int) -> None:
    h = doc.add_heading("", level=level)
    run = h.add_run(text)
    if level == 0:
        _set_run_font(run, name="Calibri", size=22, bold=True, color=GREEN)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif level == 1:
        _set_run_font(run, name="Calibri", size=14, bold=True, color=GREEN)
    else:
        _set_run_font(run, name="Calibri", size=12, bold=True, color=GOLD)
    _style_paragraph(h, space_before=14 if level else 0, space_after=8)


def _add_table(doc: Document, rows: list[list[str]]) -> None:
    if not rows:
        return
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(cols):
            cell = table.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            val = row[j] if j < len(row) else ""
            _add_inline(p, val, size=10)
            _style_paragraph(p, space_after=2, space_before=2)
            if i == 0:
                _set_cell_shading(cell, HEADER_BG)
                for run in p.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    run.font.size = Pt(10)
            elif i % 2 == 0:
                _set_cell_shading(cell, ALT_ROW)
    doc.add_paragraph()


def _add_code_block(doc: Document, lines: list[str]) -> None:
    p = doc.add_paragraph()
    _style_paragraph(p, space_after=10, space_before=4)
    run = p.add_run("\n".join(lines))
    _set_run_font(run, size=9, mono=True, color=INK)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), CODE_BG)
    shd.set(qn("w:val"), "clear")
    pPr.append(shd)


def _is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", line))


def _parse_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "`":
            in_code = not in_code
            current.append(ch)
        elif ch == "\\" and i + 1 < len(line) and line[i + 1] == "|" and not in_code:
            current.append("|")
            i += 1
        elif ch == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    cells.append("".join(current).strip())
    return cells


def _normalize_table(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    cols = len(rows[0])
    out = []
    for row in rows:
        if len(row) < cols:
            row = row + [""] * (cols - len(row))
        elif len(row) > cols:
            row = row[: cols - 1] + [" | ".join(row[cols - 1 :])]
        out.append(row)
    return out


def convert(md_path: Path, out_path: Path, subtitle: str) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK

    i = 0
    in_code = False
    code_lines: list[str] = []
    first_title_done = False

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            if in_code:
                _add_code_block(doc, code_lines)
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip() or line.strip() == "---":
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            rows = [_parse_table_row(line)]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                if not _is_table_sep(lines[i]):
                    rows.append(_parse_table_row(lines[i]))
                i += 1
            _add_table(doc, _normalize_table(rows))
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            if not first_title_done:
                _add_heading(doc, title, 0)
                sub = doc.add_paragraph()
                sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = sub.add_run(subtitle)
                _set_run_font(run, size=12, color=GOLD, bold=True)
                _style_paragraph(sub, space_after=18)
                first_title_done = True
            else:
                _add_heading(doc, title, 1)
            i += 1
            continue
        if line.startswith("## "):
            _add_heading(doc, line[3:].strip(), 1)
            i += 1
            continue
        if line.startswith("### "):
            _add_heading(doc, line[4:].strip(), 2)
            i += 1
            continue
        if re.match(r"^[-*] ", line):
            p = doc.add_paragraph(style="List Bullet")
            _add_inline(p, line[2:].strip())
            _style_paragraph(p, space_after=4)
            i += 1
            continue
        if re.match(r"^\d+\. ", line):
            p = doc.add_paragraph(style="List Number")
            _add_inline(p, re.sub(r"^\d+\. ", "", line))
            _style_paragraph(p, space_after=4)
            i += 1
            continue
        p = doc.add_paragraph()
        _add_inline(p, line)
        _style_paragraph(p, space_after=8)
        i += 1

    doc.save(out_path)
    print(f"Wrote {out_path}")


def main() -> None:
    convert(ROOT / "PROJECT.md", ROOT / "PROJECT.docx", "Project Design Document — PBL")
    convert(
        ROOT / "FINAL_REPORT.md",
        ROOT / "FINAL_REPORT.docx",
        "Final Report — Supply Chain Traceability Using Blockchain",
    )


if __name__ == "__main__":
    main()
