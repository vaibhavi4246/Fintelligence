"""Section-aware filing chunker."""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")
_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 50

_SECTION_LABELS = {
    "item 1": "Business",
    "item 1a": "Risk Factors",
    "item 1b": "Unresolved Staff Comments",
    "item 2": "MD&A",
    "item 7": "MD&A",
    "item 7a": "Quantitative and Qualitative Disclosures",
    "item 8": "Financial Statements",
}

_SECTION_HEADING_RE = re.compile(r"^item\s+(1a|1b|1|2|7a|7|8)\b", re.I)
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*[-: ]{3,}\s*(\|\s*[-: ]{3,}\s*)+\|?$")


@dataclass
class Chunk:
    chunk_index: int
    content: str
    section_label: str | None
    page_number: int | None
    fiscal_period: str | None


@dataclass
class _Block:
    text: str
    kind: str


@dataclass
class _Section:
    title: str
    section_label: str | None
    blocks: list[_Block]


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _section_label(line: str) -> str | None:
    match = _SECTION_HEADING_RE.match(line)
    if not match:
        return None
    return _SECTION_LABELS.get(f"item {match.group(1).lower()}")


def _is_section_heading(line: str) -> bool:
    return bool(_SECTION_HEADING_RE.match(line))


def _split_blocks(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    blocks: list[str] = []
    current: list[str] = []
    for line in normalized.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(stripped)
    if current:
        blocks.append("\n".join(current).strip())
    return blocks


def _is_table_block(block: str) -> bool:
    lines = [line.strip() for line in block.split("\n") if line.strip()]
    if len(lines) < 2:
        return False
    pipe_lines = sum("|" in line for line in lines)
    if pipe_lines >= 2 and any(_TABLE_SEPARATOR_RE.match(line) for line in lines):
        return True
    if pipe_lines >= 3:
        return True
    return False


def _split_sections(blocks: list[str]) -> list[_Section]:
    sections: list[_Section] = []
    current_title = "Document"
    current_label: str | None = None
    current_blocks: list[_Block] = []

    def flush() -> None:
        nonlocal current_blocks
        if current_blocks:
            sections.append(_Section(title=current_title, section_label=current_label, blocks=current_blocks))
        current_blocks = []

    for block in blocks:
        first_line = block.split("\n", 1)[0].strip()
        label = _section_label(first_line)
        if label and _is_section_heading(first_line):
            flush()
            current_title = first_line
            current_label = label
            continue
        current_blocks.append(_Block(text=block, kind="table" if _is_table_block(block) else "text"))

    flush()
    return sections


def _token_chunks(text: str, chunk_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = _ENC.encode(text)
    if not tokens:
        return []
    if len(tokens) <= chunk_tokens:
        return [_ENC.decode(tokens).strip()]

    step = max(1, chunk_tokens - overlap_tokens)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        content = _ENC.decode(tokens[start:end]).strip()
        if content:
            chunks.append(content)
        if end >= len(tokens):
            break
        start += step
    return chunks


def _emit_section_chunks(section: _Section, fiscal_period: str | None, chunk_tokens: int, overlap_tokens: int, start_index: int) -> list[Chunk]:
    emitted: list[Chunk] = []
    chunk_index = start_index
    pending_text: list[str] = []

    def flush_pending_text() -> None:
        nonlocal chunk_index, pending_text
        if not pending_text:
            return
        segment = "\n\n".join(pending_text)
        for content in _token_chunks(segment, chunk_tokens, overlap_tokens):
            emitted.append(
                Chunk(
                    chunk_index=chunk_index,
                    content=content,
                    section_label=section.section_label,
                    page_number=None,
                    fiscal_period=fiscal_period,
                )
            )
            chunk_index += 1
        pending_text = []

    for block in section.blocks:
        if block.kind == "table":
            flush_pending_text()
            emitted.append(
                Chunk(
                    chunk_index=chunk_index,
                    content=block.text,
                    section_label=section.section_label,
                    page_number=None,
                    fiscal_period=fiscal_period,
                )
            )
            chunk_index += 1
        else:
            pending_text.append(block.text)

    flush_pending_text()
    return emitted


def chunk_text(
    text: str,
    fiscal_period: str | None = None,
    chunk_tokens: int = _CHUNK_TOKENS,
    overlap_tokens: int = _OVERLAP_TOKENS,
) -> list[Chunk]:
    """Split filing text into section-aware chunks with token overlap."""
    blocks = _split_blocks(text)
    if not blocks:
        return []

    sections = _split_sections(blocks)
    chunks: list[Chunk] = []
    chunk_index = 0
    for section in sections:
        section_chunks = _emit_section_chunks(section, fiscal_period, chunk_tokens, overlap_tokens, chunk_index)
        chunks.extend(section_chunks)
        chunk_index += len(section_chunks)
    return chunks