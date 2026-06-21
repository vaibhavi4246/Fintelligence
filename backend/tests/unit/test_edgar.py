"""Unit tests for the SEC EDGAR fetcher."""

import httpx

from app.schemas.ingest import IngestRequest


def test_fetch_filing_resolves_and_extracts_text(monkeypatch):
    from app.ingestion import edgar

    payloads = {
        edgar.SEC_TICKER_URL: {
            "0": {"ticker": "AAPL", "cik_str": 320193},
            "1": {"ticker": "GS", "cik_str": 886982},
            "2": {"ticker": "BLK", "cik_str": 1364742},
        },
        f"{edgar.SEC_DATA_BASE_URL}/submissions/CIK0000320193.json": {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": ["2024-11-01"],
                    "accessionNumber": ["0000320193-24-000123"],
                    "primaryDocument": ["aapl-20240928.htm"],
                }
            }
        },
        f"{edgar.SEC_BASE_URL}/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm": (
            "<html><body><h1>AAPL 10-K</h1><p>Revenue increased.</p><script>ignore()</script></body></html>"
        ),
    }

    def fake_get(url, headers=None, timeout=None, follow_redirects=None):
        if url not in payloads:
            raise AssertionError(f"Unexpected SEC request: {url}")
        payload = payloads[url]
        if isinstance(payload, str):
            return httpx.Response(200, text=payload, request=httpx.Request("GET", url))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(edgar.httpx, "get", fake_get)

    filing = edgar.fetch_filing(
        IngestRequest(ticker="AAPL", filing_type="10-K", fiscal_period="FY", fiscal_year=2024)
    )

    assert filing.source_url.endswith("/aapl-20240928.htm")
    assert filing.text.startswith("AAPL 10-K")
    assert "Revenue increased." in filing.text
    assert "ignore()" not in filing.text


def test_fetch_filing_supports_known_tickers_without_lookup(monkeypatch):
    from app.ingestion import edgar

    monkeypatch.setattr(edgar, "_company_tickers", lambda: {})

    assert edgar._resolve_cik("GS") == "0000886982"