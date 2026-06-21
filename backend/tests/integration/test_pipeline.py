"""Fri W1 integration test: ingest -> chunk -> embed -> cosine query returns results.

Requires Postgres up with Alembic schema applied.
Embeddings are monkeypatched to 768-dim random vectors unless bge or OpenAI is
available, so the test verifies the pipeline wiring without needing a GPU or API key.

The cosine query here is the precursor to the W2 /retrieve endpoint.
"""
import os
import uuid
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.models import Document, Chunk, ProcessingStatus

FIXTURE_TEXT = (Path(__file__).parent.parent / "fixtures" / "aapl_q2_sample.txt").read_text()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_vec(dim: int = 768) -> list[float]:
    v = np.random.randn(dim).astype(float)
    v /= np.linalg.norm(v)
    return v.tolist()


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [_random_vec() for _ in texts]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def aapl_document(db):
    """Insert a test Document row; clean up after the test."""
    doc = Document(
        ticker="AAPL",
        filing_type="10-Q",
        fiscal_period="Q2",
        fiscal_year=2023,
        source_url="https://www.sec.gov/test/aapl-q2-2023",
        processing_status=ProcessingStatus.processing,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    yield doc
    db.execute(text("DELETE FROM chunks WHERE document_id = :id"), {"id": str(doc.id)})
    db.execute(text("DELETE FROM documents WHERE id = :id"), {"id": str(doc.id)})
    db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_chunk_embed_query_pipeline(db, aapl_document, monkeypatch):
    """Full W1 pipeline: text -> chunks -> embeddings written to DB -> cosine query."""
    from app.ingestion.chunker import chunk_text

    # Step 1: Chunk the fixture filing
    chunks = chunk_text(FIXTURE_TEXT, fiscal_period="Q2-2023")
    assert len(chunks) >= 3, f"Expected >=3 chunks from AAPL fixture, got {len(chunks)}"

    # Step 2: Insert chunk rows (no embedding yet)
    chunk_rows = []
    for c in chunks:
        row = Chunk(
            document_id=aapl_document.id,
            chunk_index=c.chunk_index,
            content=c.content,
            embedding=None,
            section_label=c.section_label,
            page_number=c.page_number,
        )
        db.add(row)
        chunk_rows.append(row)
    db.commit()

    # Step 3: Embed — monkeypatch unless a real provider is available
    has_real_embedder = _has_real_embedder()
    if not has_real_embedder:
        import app.core.embeddings as emb_mod
        monkeypatch.setattr(emb_mod, "embed_texts", _fake_embed)

    from app.ingestion.embed_pipeline import embed_pending_chunks
    count = embed_pending_chunks(db, document_id=aapl_document.id)
    assert count == len(chunks), f"Expected {len(chunks)} chunks embedded, got {count}"

    # Step 4: Verify embeddings written to DB
    result = db.execute(
        text("SELECT count(*) FROM chunks WHERE document_id = :id AND embedding IS NOT NULL"),
        {"id": str(aapl_document.id)},
    ).scalar()
    assert result == len(chunks), "Not all chunks have embeddings after pipeline"

    # Step 5: Cosine similarity query (precursor to /retrieve)
    query_vec = _random_vec()
    query_vec_str = str(query_vec)

    rows = db.execute(
        text(
            "SELECT id, content, 1 - (embedding <=> CAST(:qvec AS vector)) AS score "
            "FROM chunks "
            "WHERE document_id = :doc_id "
            "ORDER BY score DESC "
            "LIMIT 5"
        ),
        {"qvec": query_vec_str, "doc_id": str(aapl_document.id)},
    ).fetchall()

    assert len(rows) > 0, "Cosine query returned no results — embedding pipeline or query broken"
    scores = [r[2] for r in rows]
    assert all(-1.0 <= s <= 1.0 for s in scores), f"Unexpected cosine scores: {scores}"


def _has_real_embedder() -> bool:
    if os.environ.get("OPENAI_API_KEY") and os.environ["OPENAI_API_KEY"] not in ("sk-...", ""):
        return True
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False
