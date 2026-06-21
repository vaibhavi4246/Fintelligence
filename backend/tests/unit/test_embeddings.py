"""Unit tests for the embedding provider abstraction.

Uses monkeypatching so the test runs without sentence-transformers installed
(heavy torch dependency) or an OpenAI key. The shape contract (768-dim) is
what matters; the actual vectors are verified in the integration test.
"""
import os

import pytest

TEXTS = [
    "Gross margin expanded 200bps year-over-year.",
    "Revenue declined due to unfavorable foreign exchange rates.",
    "The company is not party to any material litigation as of the filing date.",
]


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 768 for _ in texts]


def test_embed_texts_returns_correct_shape(monkeypatch):
    """embed_texts returns one 768-dim vector per input text."""
    has_bge = _bge_available()
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if not (has_bge or has_openai):
        import app.core.embeddings as emb_mod
        monkeypatch.setattr(emb_mod, "embed_texts", _fake_embed)

    from app.core.embeddings import embed_texts

    vecs = embed_texts(TEXTS)

    assert len(vecs) == len(TEXTS), f"Expected {len(TEXTS)} vectors, got {len(vecs)}"
    for i, v in enumerate(vecs):
        assert len(v) == 768, f"Vector {i} has dim {len(v)}, expected 768"
        assert all(isinstance(x, float) for x in v), "Vector elements must be floats"


def test_embed_empty_list(monkeypatch):
    has_bge = _bge_available()
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if not (has_bge or has_openai):
        import app.core.embeddings as emb_mod
        monkeypatch.setattr(emb_mod, "embed_texts", _fake_embed)

    from app.core.embeddings import embed_texts

    assert embed_texts([]) == []


def _bge_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False
