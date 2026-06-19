import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")

    engine = create_engine(database_url)
    doc_id = uuid.uuid4()

    insert_sql = text(
        """
        INSERT INTO documents (
            id, ticker, filing_type, fiscal_period, fiscal_year,
            source_url, ingested_at, chunk_count, processing_status
        )
        VALUES (
            :id, :ticker, :filing_type, :fiscal_period, :fiscal_year,
            :source_url, :ingested_at, :chunk_count, :processing_status
        )
        """
    )

    with engine.begin() as connection:
        connection.execute(
            insert_sql,
            {
                "id": str(doc_id),
                "ticker": "MSFT",
                "filing_type": "10-Q",
                "fiscal_period": "Q1",
                "fiscal_year": 2026,
                "source_url": "https://www.sec.gov/ixviewer/ix.html",
                "ingested_at": datetime.now(timezone.utc),
                "chunk_count": 0,
                "processing_status": "pending",
            },
        )

    print(f"Inserted test document id={doc_id}")


if __name__ == "__main__":
    main()
