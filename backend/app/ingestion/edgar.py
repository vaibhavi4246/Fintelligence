"""EDGAR filing fetch.

Fetches SEC submissions metadata, resolves the archive filing URL, and strips
the filing HTML into plain text for downstream chunking and storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
import re

import httpx

from app.core.config import get_settings
from app.schemas.ingest import IngestRequest


SEC_BASE_URL = "https://www.sec.gov"
SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_TICKER_URL = f"{SEC_BASE_URL}/files/company_tickers.json"
REQUEST_TIMEOUT = 30.0

_KNOWN_TICKER_CIKS: dict[str, str] = {
    "AAPL": "0000320193",
    "GS": "0000886982",
    "BLK": "0001364742",
}


@dataclass
class RawFiling:
    ticker: str
    filing_type: str
    fiscal_period: str
    fiscal_year: int
    source_url: str
    text: str


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        text = unescape("".join(self._parts))
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


def _headers() -> dict[str, str]:
    return {
        "User-Agent": get_settings().sec_user_agent,
        "Accept": "application/json, text/html,application/xhtml+xml",
    }


def _get_json(url: str) -> dict:
    response = httpx.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def _get_text(url: str) -> str:
    response = httpx.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    return response.text


@lru_cache(maxsize=1)
def _company_tickers() -> dict[str, str]:
    payload = _get_json(SEC_TICKER_URL)
    tickers: dict[str, str] = {}
    for row in payload.values():
        ticker = str(row["ticker"]).upper()
        tickers[ticker] = str(int(row["cik_str"])).zfill(10)
    return tickers


def _resolve_cik(ticker: str) -> str:
    normalized_ticker = ticker.upper()
    company_tickers = _company_tickers()
    if normalized_ticker in company_tickers:
        return company_tickers[normalized_ticker]
    if normalized_ticker in _KNOWN_TICKER_CIKS:
        return _KNOWN_TICKER_CIKS[normalized_ticker]
    raise LookupError(f"Unknown SEC ticker: {ticker}")


def _archive_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_path = str(int(cik))
    accession_folder = accession_number.replace("-", "")
    return f"{SEC_BASE_URL}/Archives/edgar/data/{cik_path}/{accession_folder}/{primary_document}"


def _select_filing(submissions: dict, filing_type: str, fiscal_year: int) -> tuple[str, str]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])

    normalized_form = filing_type.upper()
    fallback_match: tuple[str, str] | None = None

    for index, form in enumerate(forms):
        if str(form).upper() != normalized_form:
            continue
        accession_number = accession_numbers[index]
        primary_document = primary_documents[index]
        filing_date = filing_dates[index] if index < len(filing_dates) else ""
        if filing_date.startswith(str(fiscal_year)):
            return accession_number, primary_document
        if fallback_match is None:
            fallback_match = (accession_number, primary_document)

    if fallback_match is not None:
        return fallback_match

    raise LookupError(f"No {filing_type} filing found for fiscal year {fiscal_year}")


def _extract_text(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def fetch_filing(req: IngestRequest) -> RawFiling:
    """Return a RawFiling for the requested ticker/period."""
    if req.source_url:
        source_url = req.source_url
        text = _extract_text(_get_text(source_url))
    else:
        cik = _resolve_cik(req.ticker)
        submissions_url = f"{SEC_DATA_BASE_URL}/submissions/CIK{cik}.json"
        submissions = _get_json(submissions_url)
        accession_number, primary_document = _select_filing(submissions, req.filing_type, req.fiscal_year)
        source_url = _archive_url(cik, accession_number, primary_document)
        text = _extract_text(_get_text(source_url))

    return RawFiling(
        ticker=req.ticker,
        filing_type=req.filing_type,
        fiscal_period=req.fiscal_period,
        fiscal_year=req.fiscal_year,
        source_url=source_url,
        text=text,
    )
