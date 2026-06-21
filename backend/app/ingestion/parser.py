"""Filing parsing helpers.

Supports PDF parsing via pdfplumber, plus a text/HTML fallback so the parser
can still structure SEC archive pages that are delivered as HTML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
from typing import BinaryIO

try:
    import pdfplumber
except ImportError:  # pragma: no cover - optional in environments without pdfplumber installed
    pdfplumber = None


_SECTION_LABELS = {
    "item 1": "Business",
    "item 1a": "Risk Factors",
    "item 1b": "Unresolved Staff Comments",
    "item 2": "MD&A",
    "item 7": "MD&A",
    "item 7a": "Quantitative and Qualitative Disclosures",
    "item 8": "Financial Statements",
}

_HEADING_RE = re.compile(r"^item\s+(1a|1b|1|2|7a|7|8)\b", re.I)
_SECTION_HINT_RE = re.compile(
    r"(management.*discussion|risk factors?|financial statements?|results of operations|liquidity and capital resources)",
    re.I,
)


@dataclass
class ParsedSection:
    title: str
    section_label: str | None
    page_number: int | None
    text: str


@dataclass
class ParsedTable:
    page_number: int | None
    section_label: str | None
    rows: list[dict[str, str | None]]
    source_rows: list[list[str | None]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    text: str
    sections: list[ParsedSection] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        text = unescape("".join(self._parts))
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _section_label(line: str) -> str | None:
    match = _HEADING_RE.match(line)
    if match:
        return _SECTION_LABELS.get(f"item {match.group(1).lower()}")
    if _SECTION_HINT_RE.search(line):
        if "risk factor" in line.lower():
            return "Risk Factors"
        if "financial statements" in line.lower():
            return "Financial Statements"
        return "MD&A"
    return None


def _is_heading(line: str) -> bool:
    return bool(_section_label(line)) or (line.isupper() and 4 <= len(line.split()) <= 12)


def _table_to_rows(table: list[list[str | None]]) -> list[dict[str, str | None]]:
    cleaned_rows = [[cell.strip() if isinstance(cell, str) else cell for cell in row] for row in table if any(cell for cell in row)]
    if not cleaned_rows:
        return []

    header = cleaned_rows[0]
    has_header = len(cleaned_rows) > 1 and any(cell for cell in header)
    if has_header:
        columns = [str(cell).strip() if cell is not None else f"column_{index + 1}" for index, cell in enumerate(header)]
        data_rows = cleaned_rows[1:]
    else:
        columns = [f"column_{index + 1}" for index in range(len(cleaned_rows[0]))]
        data_rows = cleaned_rows

    structured_rows: list[dict[str, str | None]] = []
    for row in data_rows:
        row_map: dict[str, str | None] = {}
        for index, column in enumerate(columns):
            value = row[index] if index < len(row) else None
            row_map[column] = value if value not in ("", None) else None
        structured_rows.append(row_map)
    return structured_rows


def _parse_text_document(text: str, source_page: int | None = None) -> ParsedDocument:
    normalized = _normalize_text(text)
    if not normalized:
        return ParsedDocument(text="")

    sections: list[ParsedSection] = []
    section_title = "Document"
    section_label: str | None = None
    section_lines: list[str] = []
    seen_heading = False

    for line in normalized.split("\n"):
        stripped = line.strip()
        if not stripped:
            if section_lines and section_lines[-1] != "":
                section_lines.append("")
            continue

        current_label = _section_label(stripped)
        if current_label:
            if section_lines:
                sections.append(
                    ParsedSection(
                        title=section_title,
                        section_label=section_label,
                        page_number=source_page,
                        text=_normalize_text("\n".join(section_lines)),
                    )
                )
            section_title = stripped
            section_label = current_label
            section_lines = []
            seen_heading = True
            continue

        if not seen_heading and _is_heading(stripped):
            section_title = stripped
            section_label = _section_label(stripped)
            seen_heading = True
            continue

        section_lines.append(stripped)

    if section_lines:
        sections.append(
            ParsedSection(
                title=section_title,
                section_label=section_label,
                page_number=source_page,
                text=_normalize_text("\n".join(section_lines)),
            )
        )

    return ParsedDocument(text=normalized, sections=sections)


def parse_html_document(html: str) -> ParsedDocument:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return _parse_text_document(extractor.get_text())


def parse_pdf_document(source: str | Path | BinaryIO | bytes) -> ParsedDocument:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required to parse PDF filings")

    if isinstance(source, bytes):
        handle = BytesIO(source)
    else:
        handle = source

    sections: list[ParsedSection] = []
    tables: list[ParsedTable] = []
    page_texts: list[str] = []

    with pdfplumber.open(handle) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = _normalize_text(page.extract_text() or "")
            if page_text:
                page_texts.append(page_text)
                page_doc = _parse_text_document(page_text, source_page=page_number)
                sections.extend(page_doc.sections)

            raw_tables = page.extract_tables() or []
            # pdfplumber may return either a list-of-tables (each table is list-of-rows)
            # or directly a list-of-rows for a single table. Normalize to list-of-tables.
            tables_iter = raw_tables
            if raw_tables and raw_tables and isinstance(raw_tables[0], list) and (
                not raw_tables[0] or not isinstance(raw_tables[0][0], list)
            ):
                # raw_tables looks like a single table (list-of-rows)
                tables_iter = [raw_tables]

            for table in tables_iter:
                rows = _table_to_rows(table)
                if not rows:
                    continue
                tables.append(
                    ParsedTable(
                        page_number=page_number,
                        section_label=sections[-1].section_label if sections else None,
                        rows=rows,
                        source_rows=[[cell if cell not in ("", None) else None for cell in row] for row in table],
                    )
                )

    return ParsedDocument(text="\n\n".join(page_texts), sections=sections, tables=tables)


def parse_filing_content(content: bytes | str, *, source_url: str | None = None, content_type: str | None = None) -> ParsedDocument:
    is_pdf = False
    if content_type and "pdf" in content_type.lower():
        is_pdf = True
    if source_url and source_url.lower().endswith(".pdf"):
        is_pdf = True
    if isinstance(content, bytes) and content.startswith(b"%PDF"):
        is_pdf = True

    if is_pdf:
        return parse_pdf_document(content if isinstance(content, bytes) else content.encode("utf-8"))
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="ignore")
    if "<html" in content.lower() or "<body" in content.lower():
        return parse_html_document(content)
    return _parse_text_document(content)