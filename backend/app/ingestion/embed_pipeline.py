"""Batch embedding pipeline: reads chunks with NULL embedding, embeds, writes back.

Idempotent — safe to re-run; only processes un-embedded chunks.
Call after chunking is complete for a document, and before building the IVFFlat index.
"""
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.embeddings import embed_texts

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


def embed_pending_chunks(db: Session, document_id: uuid.UUID | None = None) -> int:
    """Embed all chunks that have a NULL embedding.

    Args:
        db: SQLAlchemy session.
        document_id: If provided, restrict to chunks of that document only.

    Returns:
        Number of chunks embedded.
    """
    filter_clause = "WHERE embedding IS NULL"
    params: dict = {}
    if document_id:
        filter_clause += " AND document_id = :doc_id"
        params["doc_id"] = str(document_id)

    rows = db.execute(
        text(f"SELECT id, content FROM chunks {filter_clause} ORDER BY chunk_index"),
        params,
    ).fetchall()

    if not rows:
        logger.info("No un-embedded chunks found.")
        return 0

    ids = [r[0] for r in rows]
    texts_ = [r[1] for r in rows]

    logger.info("Embedding %d chunks in batches of %d...", len(ids), _BATCH_SIZE)
    vectors = embed_texts(texts_)

    for chunk_id, vec in zip(ids, vectors):
        db.execute(
            text("UPDATE chunks SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": str(vec), "id": str(chunk_id)},
        )

    db.commit()
    logger.info("Embedded %d chunks.", len(ids))
    return len(ids)
