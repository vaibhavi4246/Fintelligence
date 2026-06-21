"""Minimal section-aware chunker.

TEMP — Vaibhavi owns the real section-aware chunker (Thu W1, Vaibhavi).
Replace with: MD&A 512t/50 overlap, Risk Factors at item boundaries,
tables as atomic chunks with metadata.

This stub splits on token count using tiktoken so the embedding pipeline
and integration tests can run end-to-end before the real chunker lands.
"""
import re
from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")
_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 50

_SECTION_PATTERNS = [
    (re.compile(r"item\s+1a", re.I), "Risk Factors"),
    (re.compile(r"item\s+2", re.I), "MD&A"),
    (re.compile(r"item\s+7", re.I), "MD&A"),
    (re.compile(r"risk factor", re.I), "Risk Factors"),
    (re.compile(r"management.{0,30}discussion", re.I), "MD&A"),
    (re.compile(r"financial statement", re.I), "Financial Statements"),
]


@dataclass
class Chunk:
    chunk_index: int
    content: str
    section_label: str | None
    page_number: int | None
    fiscal_period: str | None


def _detect_section(text: str) -> str | None:
    for pattern, label in _SECTION_PATTERNS:
        if pattern.search(text):
            return label
    return None


def chunk_text(
    text: str,
    fiscal_period: str | None = None,
    chunk_tokens: int = _CHUNK_TOKENS,
    overlap_tokens: int = _OVERLAP_TOKENS,
) -> list[Chunk]:
    """Split `text` into overlapping token-window chunks with light section detection."""
    tokens = _ENC.encode(text)
    step = chunk_tokens - overlap_tokens
    chunks: list[Chunk] = []

    for i, start in enumerate(range(0, len(tokens), step)):
        token_slice = tokens[start : start + chunk_tokens]
        content = _ENC.decode(token_slice)
        if not content.strip():
            continue
        chunks.append(
            Chunk(
                chunk_index=i,
                content=content,
                section_label=_detect_section(content),
                page_number=None,
                fiscal_period=fiscal_period,
            )
        )

    return chunks
