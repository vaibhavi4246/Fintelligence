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
- [ ] Docker Desktop installed + `docker compose up` runs clean
- [ ] `/health` returns 200
- [ ] PR `sanyam/day1 → dev` opened and reviewed

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
- [ ] `alembic upgrade head` runs with 0 errors
- [ ] All 9 tables visible in DB (`\dt` in psql)
- [ ] IVFFlat index created on `chunks.embedding`
- [ ] Seed script inserts 1 test doc without errors
- [ ] PR `vaibhavi/day1 → dev` opened

---

*Updated: 2026-06-19 | Next update: end of Day 2*
