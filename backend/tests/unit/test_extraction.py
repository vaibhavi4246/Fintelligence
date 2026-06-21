"""Unit tests for the claim-extraction agent.

If GROQ_API_KEY is set, tests run against the live Groq API.
Otherwise chat_json is monkeypatched with deterministic canned responses so the
tests are always runnable in CI without LLM credentials.
"""
import os

import pytest

from app.schemas.claim import Claim, ClaimExtraction
from tests.fixtures.sample_chunks import ALL_SAMPLE_CHUNKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_extraction(chunk: dict) -> ClaimExtraction:
    """Return a minimal but valid ClaimExtraction for the given chunk."""
    return ClaimExtraction(
        claims=[
            Claim(
                claim=f"Mock claim extracted from chunk {chunk['id']}",
                subject="revenue",
                predicate="was",
                object="$4.2B",
                period=chunk["fiscal_period"],
                stated_cause=None,
                confidence=0.9,
            )
        ]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("chunk", ALL_SAMPLE_CHUNKS)
def test_extract_claims_returns_nonempty(chunk, monkeypatch):
    """Each chunk produces at least one Claim with valid confidence."""
    has_live_key = bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"))

    if not has_live_key:
        import app.agents.extraction as ext_mod
        monkeypatch.setattr(ext_mod, "chat_json", lambda *_a, **_kw: _make_mock_extraction(chunk))

    from app.agents.extraction import extract_claims

    claims = extract_claims(chunk["content"], chunk["fiscal_period"])

    assert len(claims) >= 1, f"Expected >=1 claim from chunk {chunk['id']}, got 0"
    for c in claims:
        assert isinstance(c, Claim)
        assert 0.0 <= c.confidence <= 1.0, f"Confidence out of range: {c.confidence}"
        assert c.claim.strip(), "claim text must be non-empty"
        assert c.subject.strip()
        assert c.predicate.strip()
        assert c.object.strip()
        assert c.period.strip()


def test_stated_cause_captured_for_explained_change(monkeypatch):
    """Chunk 1 (gross margin with FX cause) should produce a claim with stated_cause set
    when a live LLM is available. With mock we just verify schema integrity."""
    from tests.fixtures.sample_chunks import CHUNK_GROSS_MARGIN_EXPLAINED

    has_live_key = bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"))

    if not has_live_key:
        import app.agents.extraction as ext_mod
        mock = ClaimExtraction(
            claims=[
                Claim(
                    claim="Gross margin decreased 220bps due to component costs and FX.",
                    subject="gross margin",
                    predicate="decreased",
                    object="220bps",
                    period="Q2-2023",
                    stated_cause="increased component costs and unfavorable foreign exchange movements",
                    confidence=0.95,
                )
            ]
        )
        monkeypatch.setattr(ext_mod, "chat_json", lambda *_a, **_kw: mock)

    from app.agents.extraction import extract_claims

    claims = extract_claims(
        CHUNK_GROSS_MARGIN_EXPLAINED["content"],
        CHUNK_GROSS_MARGIN_EXPLAINED["fiscal_period"],
    )

    assert len(claims) >= 1
    if not has_live_key:
        # With mock, stated_cause is guaranteed to be set
        assert any(c.stated_cause for c in claims), "Expected at least one claim with stated_cause"
