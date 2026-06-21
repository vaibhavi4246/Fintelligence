"""EDGAR filing fetch.

TEMP stub — Vaibhavi owns the real EDGAR HTML/XBRL fetch (Tue W1, Vaibhavi).
This stub lets Sanyam's /ingest endpoint and downstream pipeline run end-to-end
before the real fetcher lands. It returns placeholder text and a canonical
EDGAR-style source URL so the rest of the pipeline has something to chunk/embed.
"""
from dataclasses import dataclass

from app.schemas.ingest import IngestRequest


@dataclass
class RawFiling:
    ticker: str
    filing_type: str
    fiscal_period: str
    fiscal_year: int
    source_url: str
    text: str


def fetch_filing(req: IngestRequest) -> RawFiling:
    """Return a RawFiling for the requested ticker/period.

    STUB: emits placeholder text. Replace with the real EDGAR HTML/XBRL
    parser (selectolax/BeautifulSoup + XBRL facts) — Vaibhavi.
    """
    source_url = req.source_url or (
        f"https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&ticker={req.ticker}&type={req.filing_type}"
    )
    text = (
        f"[STUB FILING] {req.ticker} {req.filing_type} {req.fiscal_period} "
        f"{req.fiscal_year}. Replace with real EDGAR content."
    )
    return RawFiling(
        ticker=req.ticker,
        filing_type=req.filing_type,
        fiscal_period=req.fiscal_period,
        fiscal_year=req.fiscal_year,
        source_url=source_url,
        text=text,
    )
