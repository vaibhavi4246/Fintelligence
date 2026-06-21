"""Create the IVFFlat index on chunks.embedding after rows are loaded.

Safe to re-run (IF NOT EXISTS). The index must be built post-load because
IVFFlat needs rows to distribute across lists. The Alembic migration already
created it on the empty table; this script rebuilds/refreshes it after data loads.

Usage:
    python backend/scripts/build_ivfflat_index.py
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def main() -> None:
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url)

    with engine.begin() as conn:
        row = conn.execute(text("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL")).scalar()
        print(f"Chunks with embeddings: {row}")

        if row == 0:
            print("No embedded chunks yet — skipping index build (run embed_pipeline first).")
            return

        conn.execute(text("SET ivfflat.probes = 10"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat "
            "ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        ))
        print("IVFFlat index created (or already exists).")


if __name__ == "__main__":
    main()
