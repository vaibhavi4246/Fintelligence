"""/ingest router: accepts ticker + period, fetches (stub), stores a Document."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Document, ProcessingStatus
from app.db.session import get_db
from app.ingestion.edgar import fetch_filing
from app.schemas.ingest import IngestRequest, IngestResponse

router = APIRouter(tags=["ingestion"])


@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """Fetch a filing (stub) and persist a Document row with status=pending.

    The full chunk -> embed -> claim-graph pipeline is wired in later (W1 Thu/Fri,
    W2). For now this registers the document so a document_id can be returned.
    """
    filing = fetch_filing(req)

    document = Document(
        ticker=filing.ticker,
        filing_type=filing.filing_type,
        fiscal_period=filing.fiscal_period,
        fiscal_year=filing.fiscal_year,
        source_url=filing.source_url,
        raw_text=filing.text,
        processing_status=ProcessingStatus.pending,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return IngestResponse(
        document_id=document.id,
        processing_status=document.processing_status.value,
    )
