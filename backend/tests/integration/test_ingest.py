"""Integration test for POST /ingest.

Requires the Postgres DB up (cd infra && docker compose up -d postgres) with the
Alembic schema applied. Asserts the endpoint returns a valid document_id.
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ingest_returns_document_id():
    payload = {
        "ticker": "AAPL",
        "filing_type": "10-Q",
        "fiscal_period": "Q2",
        "fiscal_year": 2023,
    }
    resp = client.post("/ingest", json=payload)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # document_id must be a valid UUID
    uuid.UUID(body["document_id"])
    assert body["processing_status"] == "pending"


def test_langgraph_noop_runs():
    """The LangGraph spine compiles and a no-op invocation passes state through."""
    from app.agents.graph import graph

    out = graph.invoke({"document_ids": ["x"]})
    assert out["document_ids"] == ["x"]
