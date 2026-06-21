# FinDocIntel — Progress Summary

---

## Day 1 (Mon, Week 1) — 2026-06-19

### What Sanyam did

| Item | Status |
|---|---|
| Repo directory structure created per plan §6 | Done |
| `backend/app/main.py` — FastAPI app + `GET /health` → 200 | Done |
| `backend/requirements.txt` — fastapi, uvicorn, sqlalchemy, alembic, psycopg2-binary, pgvector, pydantic, langgraph, openai | Done |
| `backend/Dockerfile` — python:3.11-slim, installs reqs, runs uvicorn | Done |
| `infra/docker-compose.yml` — `api` + `postgres` (pgvector/pgvector:pg16), healthcheck, depends_on | Done |
| `.env.example` — DATABASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY, API_SECRET_KEY, NEXT_PUBLIC_API_URL | Done |
| `.gitignore` — per plan §6 | Done |
| `CLAUDE.md` — project working rules (day-wise, branch-per-day, commit convention) | Done |

### Day 1 EOW gate (Sanyam)
- [x] Docker Desktop installed + `docker compose up` runs clean
- [x] `/health` returns 200
- [x] PR `sanyam/day1 → main` opened and reviewed

---

## Instructions for Vaibhavi — Day 1 (Mon, Week 1)

### Your deliverable today
> All 9 PostgreSQL tables created via Alembic migrations. IVFFlat index on `chunks.embedding`. Local DB seeds with 1 test document without errors.

### Setup
1. Clone repo, checkout `dev`, create your branch:
   ```bash
   git checkout dev && git pull origin dev
   git checkout -b vaibhavi/day1
   ```
2. Install Docker Desktop (same as Sanyam above) if not already done.
3. Copy env: `cp .env.example .env` (no real keys needed for Day 1 DB work).
4. Boot the DB only:
   ```bash
   cd infra
   docker compose up -d postgres
   ```

### What to build today

**Alembic setup + 9 migrations**

Initialize Alembic inside `backend/`:
```bash
cd backend
alembic init app/db/migrations
```

Update `alembic.ini` → set `sqlalchemy.url` to read from env:
```
sqlalchemy.url = %(DATABASE_URL)s
```

Update `app/db/migrations/env.py` to import your `Base` metadata.

Create and run migrations for all 9 tables (one migration file per logical group is fine):

| Table | Key columns |
|---|---|
| `documents` | id, ticker, filing_type, fiscal_period, fiscal_year, source_url, ingested_at, chunk_count, processing_status |
| `chunks` | id, document_id, chunk_index, content, embedding vector(768), section_label, page_number |
| `intelligence_reports` | id, query_id, document_ids, model_version, generated_at, structured_output jsonb, overall_confidence, contradiction_count, risk_signal_count |
| `claims` | id, report_id, claim_text, claim_type, confidence_score, supporting_chunk_ids, cited_document_ids, verified bool |
| `contradictions` | id, report_id, claim_a_id, claim_b_id, document_a/b_id, period_a/b, contradiction_type enum, stated_cause, restatement_source, severity, explanation |
| `risk_signals` | id, report_id, signal_text, taxonomy_category, severity, source_chunk_id, confidence_score |
| `claim_nodes` | id, ticker, subject, predicate, object, period, claim_id, canonical_entity_id |
| `claim_edges` | id, source_node_id, target_node_id, edge_type enum, weight, period_delta |
| `eval_runs` | id, model_version, run_at, test_set_id, factuality_score, citation_accuracy, calibration_score, contradiction_precision, contradiction_recall, precision_ci_low, precision_ci_high, extractor_model, judge_model, judge_agreement_rate, inter_judge_kappa, cost_usd, gpu_seconds, p50_latency_ms, p95_latency_ms, notes |
| `eval_test_cases` | id, test_set_id, input_query, input_document_ids, expected_output jsonb, adversarial bool, created_by, created_at |
| `eval_results` | id, eval_run_id, test_case_id, model_output jsonb, factuality_pass bool, citation_pass bool, llm_judge_score, llm_judge_reasoning |

**IVFFlat index** on `chunks.embedding` — add this after data load (not in migration, it needs rows):
```sql
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Seed 1 test document** — write a small seed script `backend/scripts/seed_test_doc.py` that inserts 1 row into `documents` with status `pending`. Run it to confirm no DB errors.

### Coordinate with Sanyam
- Use **same `docker-compose.yml`** (already in `infra/`) — don't create a separate one.
- Postgres service name is `postgres`, DB name `findocint`, user `findocint`, password `findocint`.
- `DATABASE_URL` in `.env` should be: `postgresql://findocint:findocint@localhost:5432/findocint`
- The `chunks.embedding` column must be `vector(768)` — this matches `bge-base-en-v1.5` which Sanyam will use for embeddings on Day 4 (W1).

### EOD checklist
- [x] `alembic upgrade head` runs with 0 errors
- [x] All required schema tables visible in DB (`\dt` in psql)
- [x] IVFFlat index created on `chunks.embedding`
- [x] Seed script inserts 1 test doc without errors
- [ ] PR `vaibhavi/day1 → dev` opened

### Execution update (completed now)
- Added Alembic config and migration scaffold under `backend/app/db/migrations`
- Added SQLAlchemy schema models in `backend/app/db/models.py`
- Added initial migration `20260619_0001_initial_schema.py` for all required tables + enums + pgvector extension
- Added seed script `backend/scripts/seed_test_doc.py` and inserted 1 test document with `processing_status = pending`
- Created IVFFlat index: `idx_chunks_embedding_ivfflat` on `chunks.embedding`
- Verified alembic head version: `20260619_0001`

---

## Day 2 (Tue, Week 1) — 2026-06-21 | Branch: Sanyam/day2 → merged main

### What Sanyam did

| Item | Status |
|---|---|
| `backend/app/core/config.py` — pydantic-settings: DATABASE_URL, LLM_PROVIDER, GROQ_API_KEY, Ollama config, embedding provider | Done |
| `backend/app/db/session.py` — SQLAlchemy engine + SessionLocal + FastAPI `get_db()` dependency | Done |
| `.env.example` — added Groq, Ollama, embedding provider vars | Done |
| `backend/requirements.txt` — added groq, sentence-transformers, tiktoken, numpy | Done |
| `backend/app/schemas/ingest.py` — IngestRequest + IngestResponse Pydantic models | Done |
| `backend/app/ingestion/edgar.py` — EDGAR fetch **stub** (TEMP — Vaibhavi replaces) | Done |
| `backend/app/api/ingest.py` — `POST /ingest`: inserts Document row, returns document_id | Done |
| `backend/app/agents/state.py` — AgentState TypedDict for LangGraph | Done |
| `backend/app/agents/graph.py` — LangGraph StateGraph wired | Done |
| `backend/app/main.py` — ingest router registered | Done |
| `backend/tests/integration/test_ingest.py` — 2 tests pass | Done |

---

## Day 3 (Wed, Week 1) — 2026-06-21 | Branch: Sanyam/day3 → merged main

### What Sanyam did

| Item | Status |
|---|---|
| `backend/app/schemas/claim.py` — Claim + ClaimExtraction Pydantic models (confidence 0–1 constrained, stated_cause field) | Done |
| `backend/app/core/llm.py` — `chat_json()`: Groq primary (JSON mode) → Ollama fallback | Done |
| `backend/app/agents/extraction.py` — `extract_claims()` + `extraction_node` for LangGraph DAG | Done |
| `backend/app/agents/graph.py` — extraction node wired (replaces no-op) | Done |
| `backend/tests/fixtures/sample_chunks.py` — 3 hand-picked MD&A/financial/risk chunks | Done |
| `backend/tests/unit/test_extraction.py` — 4 tests pass (monkeypatched in CI; live LLM if GROQ_API_KEY set) | Done |

---

## Day 4 + Day 5 (Thu–Fri, Week 1) — 2026-06-21 | Branch: Sanyam/day4

### What Sanyam did (Thu — embedding pipeline)

| Item | Status |
|---|---|
| `backend/app/core/embeddings.py` — `embed_texts()`: bge-base-en-v1.5 (768-dim) primary, OpenAI text-embedding-3-small (dim=768) fallback | Done |
| `backend/app/ingestion/embed_pipeline.py` — `embed_pending_chunks(db)`: selects NULL-embedding chunks, batches at 100, writes back | Done |
| `backend/scripts/build_ivfflat_index.py` — IVFFlat index `CREATE INDEX IF NOT EXISTS` post-load | Done |
| `backend/app/db/migrations/versions/20260621_0002_make_embedding_nullable.py` — chunks.embedding nullable (insert-then-embed pattern) | Done |
| `backend/app/db/models.py` — embedding column `nullable=True` | Done |
| `backend/tests/unit/test_embeddings.py` — 2 tests: 768-dim shape + empty list | Done |

### What Sanyam did (Fri — eval cases + integration test)

| Item | Status |
|---|---|
| `backend/app/ingestion/chunker.py` — minimal 512t/50-overlap tiktoken chunker, light section heuristic (**TEMP** — Vaibhavi replaces) | Done |
| `backend/tests/fixtures/aapl_q2_sample.txt` — bundled AAPL Q2-2023 10-Q excerpt | Done |
| `backend/scripts/seed_eval_cases.py` — 20 manual EvalTestCase rows (test_set_id='w1-manual', adversarial=False) | Done |
| `backend/tests/integration/test_pipeline.py` — chunk → embed (monkeypatched) → cosine query → non-empty results | Done |
| `summary.md` — updated with Day 2–5 status + handoff notes for Vaibhavi | Done |

### EOW gate (Week 1 — ALL PASS)
- [x] `alembic upgrade head` runs with 0 errors (2 migrations applied)
- [x] All 9 tests pass: `pytest tests/` green
- [x] `seed_eval_cases.py` → 20 rows in `eval_test_cases` (`SELECT count(*) FROM eval_test_cases` = 20)
- [x] Integration test: AAPL fixture → 3 chunks → embed (monkeypatched 768-dim) → cosine query returns results
- [x] `POST /ingest` returns valid UUID `document_id`, `processing_status=pending`

---

## Left for Vaibhavi — required before Sanyam's W2 `/retrieve` can run on real data

| What | Stub file to replace | Real implementation |
|---|---|---|
| **EDGAR fetch** | `backend/app/ingestion/edgar.py` — real SEC fetch + raw text extraction | Done (Tue W1 complete) |
| **Chunker** | `backend/app/ingestion/chunker.py` — naive 512t/50 overlap | Section-aware: MD&A 512t/50 overlap, Risk Factors at item boundaries, tables as atomic JSON chunks — Thu W1 Vaibhavi |

**Interface contract (stable — do not change signatures):**
- `fetch_filing(req: IngestRequest) -> RawFiling` — populate `.text` with real filing content
- `chunk_text(text, fiscal_period) -> list[Chunk]` — populate `section_label`, `page_number` from real parsing

- Day 2 complete: SEC submissions JSON is resolved for AAPL/GS/BLK 10-Ks, archive HTML is stripped to plain text, and `/ingest` stores `raw_text` with passing tests.

---

## Vaibhavi Week 1 remaining deliverables

| Day | Deliverable |
|---|---|
| **Tue W1** | SEC EDGAR REST API fetch working: AAPL, GS, BLK 10-Ks fetched and raw text stored | Done |
| **Wed W1** | pdfplumber parser: text + section labels + tables as structured JSON |
| **Thu W1** | Real section-aware chunker: MD&A 512t/50 overlap, Risk Factors at item boundaries, tables atomic |
| **Fri W1** | Next.js 14 project init + document upload page + file → `POST /ingest` + status indicator |

---

*Updated: 2026-06-21 | Sanyam Week 1 complete (Day 1–5). Vaibhabi Tue W1 complete; Wed–Fri pending.*
