"""Request/response schemas for the /ingest endpoint."""
import uuid

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    ticker: str = Field(..., examples=["AAPL"])
    filing_type: str = Field(..., examples=["10-Q", "10-K"])
    fiscal_period: str = Field(..., examples=["Q2"])
    fiscal_year: int = Field(..., examples=[2023])
    source_url: str | None = Field(default=None, description="Override; otherwise set by the EDGAR fetcher.")


class IngestResponse(BaseModel):
    document_id: uuid.UUID
    processing_status: str
