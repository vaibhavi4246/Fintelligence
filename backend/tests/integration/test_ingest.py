"""Integration test for POST /ingest.

Requires the Postgres DB up (cd infra && docker compose up -d postgres) with the
Alembic schema applied. Asserts the endpoint returns a valid document_id.
"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import ingest as ingest_module
from app.db.models import Document
from app.db.session import SessionLocal
from app.ingestion.edgar import RawFiling
from app.main import app

client = TestClient(app)


def test_ingest_returns_document_id():
    fake_text = "AAPL 10-K filing text"

    def fake_fetch_filing(req):
        return RawFiling(
            ticker=req.ticker,
            filing_type=req.filing_type,
            fiscal_period=req.fiscal_period,
            fiscal_year=req.fiscal_year,
            source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
            text=fake_text,
        )

    original_fetch_filing = ingest_module.fetch_filing
    ingest_module.fetch_filing = fake_fetch_filing
    payload = {
        "ticker": "AAPL",
        "filing_type": "10-K",
        "fiscal_period": "FY",
        "fiscal_year": 2024,
    }
    document = None
    try:
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 200, resp.text

        body = resp.json()
        uuid.UUID(body["document_id"])
        assert body["processing_status"] == "pending"

        session = SessionLocal()
        try:
            document = session.get(Document, uuid.UUID(body["document_id"]))
            assert document is not None
            assert document.raw_text == fake_text
            assert document.processing_status.value == "pending"
        finally:
            if document is not None:
                session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": str(document.id)})
                session.commit()
            session.close()
    finally:
        ingest_module.fetch_filing = original_fetch_filing


def test_langgraph_noop_runs():
    """The LangGraph spine compiles and a no-op invocation passes state through."""
    from app.agents.graph import graph

    out = graph.invoke({"document_ids": ["x"]})
    assert out["document_ids"] == ["x"]
